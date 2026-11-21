#!/usr/bin/env python3
"""Score the agent-named additions firms from the saved agent responses.

For each of the 615 merged additions firms, in each run where it was
named (runs from the dedupe log, cross-checked against the merged firms
file's discovery_note — 1,944 (firm, run) pairs), run the LLM-assisted
scorer (scorer.py, same as the agent worker) over the saved answer text
and citations. NO new agent calls.

Writes one muse-observation-<firm_id>.json per (firm, run) into the run
dir, alongside the agent worker's layout, so load_study_observations.py
picks them up. Position comes from the run's muse-spark-observation.json
firms_named_not_in_cohort list (name matched against the merged firm
name + folded-entry aliases), falling back to the run's firms_named
list (the 11 name-collision firms were matched to the cohort entry by
the agent worker's parser, so their position lives there). Comparison
headings ('A vs B', 'A + B') are split so each firm in them takes the
heading's position. Pairs with no matching heading get position None —
the agent worker's treatment for a firm named in the body only (171 of
1,944 pairs in the dry run; 163 of those are named somewhere in the
answer text, 8 only loosely or not at all).

Skips pairs whose observation file already exists (resume-safe).
Progress is logged to a jsonl file after every scored firm, so an
interruption resumes cleanly.

On a 429 / rate-limit response the run STOPS (hard stop): progress is
kept, the rest stay unscored, and the script exits non-zero with the
counts. Any other per-firm scorer failure is recorded and the run
continues with the rest.

Usage:
  python3 score_additions.py [--limit N] [--dry-run]
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = "/home/hatch/workspace/goals/score-card-audit-product/files/aisharc-harness"
sys.path.insert(0, HERE)

from aisharc_harness.agent import scorer as SC
from aisharc_harness.rules.engine import load_definitions

AGENT_DIR = os.path.join(HERE, "runs", "2026-11-14-study", "agent")
PROGRESS = os.path.join(HERE, "worker-scripts", "score_additions_progress.jsonl")
STOP = threading.Event()


def norm_name(s):
    s = (s or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # abbreviation collapse: the agent writes 'Co.' for 'Company',
    # 'A/C' or 'A C' for 'AC'.
    toks = ["company" if t == "co" else t for t in s.split(" ")]
    s = " ".join(toks)
    s = re.sub(r"\ba c\b", "ac", s)
    return s


def name_match(a, b):
    """True if normalized names are equal, one is a word-boundary prefix
    of the other (agent shortens 'Ace Air Conditioning Company' to
    'Ace Air Conditioning'), or the shorter name's tokens appear
    contiguously inside the longer one (agent shortens 'Valley
    Action-Aire' to 'Action Aire'). Requires >= 2 tokens on the shorter
    side so a bare generic ('Air Conditioning') never matches."""
    na, nb = norm_name(a), norm_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na.startswith(nb + " ") or nb.startswith(na + " "):
        return True
    ta, tb = na.split(" "), nb.split(" ")
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(short) < 2:
        return False
    for i in range(len(long_) - len(short) + 1):
        if long_[i:i + len(short)] == short:
            return True
    return False


def build_pairs():
    log = json.load(open(os.path.join(HERE, "additions-dedupe-log.json")))
    runs_by_fid = {f["firm_id"]: f.get("runs_named_in", []) for f in log["firms"]}
    allf = {f["firm_id"]: f for f in
            json.load(open(os.path.join(HERE, "study-additions-firms-all.json")))["firms"]}
    merged = json.load(open(os.path.join(HERE, "study-additions-firms.json")))["firms"]
    spec = importlib.util.spec_from_file_location(
        "merge_mod", os.path.join(HERE, "worker-scripts", "merge_additions.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    folded = {}   # folded firm_id -> survivor firm_id
    for s, fl, t, tz, r in mod.GROUPS:
        for f in fl:
            folded[f] = s
    pairs = []    # (firm dict, run path, [alias names])
    for e in merged:
        fid = e["firm_id"]
        runs = set(runs_by_fid.get(fid, []))
        aliases = [e["name"]]
        for f, s in folded.items():
            if s == fid:
                runs |= set(runs_by_fid.get(f, []))
                aliases.append(allf[f]["name"])
        for run in sorted(runs):
            pairs.append((e, run, aliases))
    return pairs


def load_run(run_path):
    """Saved run observation file: answer text, citations, run meta,
    and the non-cohort firms named with positions."""
    path = os.path.join(AGENT_DIR, run_path, "muse-spark-observation.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def find_position(run_obs, aliases):
    """Position of the firm in the run's named list. Sources, in order:
    the run's firms_named_not_in_cohort headings, then its firms_named
    (cohort) headings — the 11 name-collision firms were matched to the
    cohort entry by the agent worker's parser, so their position lives
    there. Comparison headings ('A vs B', 'A + B') are split so each firm
    in them takes the heading's position. None if no heading matched (the
    firm was named in the body only, as the agent worker's position-None
    treatment)."""
    candidates = []
    for nc in run_obs.get("firms_named_not_in_cohort") or []:
        candidates.append((nc.get("name"), nc.get("position")))
    for fn in run_obs.get("firms_named") or []:
        candidates.append((fn.get("name"), fn.get("position")))
    for name, pos in candidates:
        if name is None:
            continue
        parts = [p.strip() for p in re.split(r"\s+(?:vs\.?|\+)\s+", name)] or [name]
        for part in parts:
            for a in aliases:
                if name_match(part, a):
                    return pos
    return None


def score_one(args):
    firm, run_path, aliases, defs = args
    run_obs = load_run(run_path)
    run_dir = os.path.join(AGENT_DIR, run_path)
    out_path = os.path.join(run_dir, "muse-observation-%s.json" % firm["firm_id"])
    if os.path.exists(out_path):
        return {"status": "skipped", "firm_id": firm["firm_id"], "run": run_path}
    if STOP.is_set():
        return {"status": "not run", "firm_id": firm["firm_id"], "run": run_path}
    town, task_dir, repeat = run_path.split("/")
    repeat = int(repeat)
    run_meta = {
        "primary_business_category": run_obs.get("primary_business_category"),
        "query": run_obs.get("query"),
        "town_zip": run_obs.get("town_zip"),
        "date_checked": run_obs.get("date_checked"),
        "model": run_obs.get("model"),
        "transcript_ref": run_obs.get("transcript_ref"),
        "response_id": run_obs.get("response_id"),
        "web_search_calls": run_obs.get("web_search_calls"),
        "web_search_results": run_obs.get("web_search_results"),
        "url_citation_count": run_obs.get("url_citation_count"),
        "distinct_urls": run_obs.get("distinct_urls"),
        "cost_usd": run_obs.get("cost_usd"),
    }
    scored = SC.score_firm(run_obs["answer_text"], run_obs.get("citations") or [],
                           firm["name"], defs)
    obs = SC.build_observation(firm, scored, run_meta, defs, True)
    obs["task"] = run_obs.get("task")
    obs["task_id"] = run_obs.get("task_id")
    obs["repeat"] = repeat
    obs["task_text"] = run_obs.get("task_text")
    obs["position"] = find_position(run_obs, aliases)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(obs, fh, indent=2, sort_keys=False)
    return {"status": "scored", "firm_id": firm["firm_id"], "run": run_path,
            "position": obs["position"],
            "scorer_cost_usd": scored.get("scorer_cost_usd") or 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pairs = build_pairs()
    print("scoring pairs: %d" % len(pairs))
    if args.limit:
        pairs = pairs[:args.limit]
        print("limited to %d" % len(pairs))
    if args.dry_run:
        # verify every run dir loads and every firm has a position match
        unmatched = []
        for firm, run_path, aliases in pairs:
            run_obs = load_run(run_path)
            if find_position(run_obs, aliases) is None:
                unmatched.append((firm["firm_id"], run_path, firm["name"]))
        print("pairs with no position match: %d" % len(unmatched))
        for u in unmatched[:20]:
            print("  ", u)
        return

    defs = load_definitions()
    done = {"scored": 0, "skipped": 0, "failed": 0, "not run": 0}
    total_cost = 0.0
    failures = []
    t0 = time.time()
    logfh = open(PROGRESS, "a", encoding="utf-8")
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {pool.submit(score_one, (f, r, a, defs)): (f, r)
                for f, r, a in pairs}
        for fut in as_completed(futs):
            firm, run_path = futs[fut]
            try:
                rec = fut.result()
            except RuntimeError as exc:
                msg = str(exc)
                if "429" in msg or "rate" in msg.lower():
                    print("RATE LIMITED — stopping: %s" % msg)
                    STOP.set()
                    rec = {"status": "rate-limited", "firm_id": firm["firm_id"],
                           "run": run_path, "error": msg}
                    failures.append(rec)
                    break
                rec = {"status": "failed", "firm_id": firm["firm_id"],
                       "run": run_path, "error": msg}
            except Exception as exc:  # noqa: BLE001
                rec = {"status": "failed", "firm_id": firm["firm_id"],
                       "run": run_path, "error": str(exc)}
            st = rec["status"]
            if st in done:
                done[st] += 1
            else:
                done["failed"] += 1
            if st == "scored":
                total_cost += rec.get("scorer_cost_usd") or 0.0
            if st == "failed":
                failures.append(rec)
            logfh.write(json.dumps(rec) + "\n")
            logfh.flush()
            n = sum(done.values())
            if n % 50 == 0:
                print("%d/%d scored=%d skipped=%d failed=%d cost=$%.4f %.0fs"
                      % (n, len(pairs), done["scored"], done["skipped"],
                         done["failed"], total_cost, time.time() - t0))
    logfh.close()
    # anything not attempted after a rate-limit stop
    attempted = done["scored"] + done["skipped"] + done["failed"]
    if attempted < len(pairs):
        print("not attempted: %d (stopped early)" % (len(pairs) - attempted))
    print("done: %s scorer_total_cost_usd=%.4f elapsed=%.0fs"
          % (done, total_cost, time.time() - t0))
    if failures:
        print("failures: %d" % len(failures))
        for f in failures[:20]:
            print("  ", f)
    if any(f.get("status") == "rate-limited" for f in failures):
        sys.exit(2)


if __name__ == "__main__":
    main()
