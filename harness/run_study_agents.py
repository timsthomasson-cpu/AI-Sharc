#!/usr/bin/env python3
"""AI Sharc harness — Texas HVAC correlation study, agent side (Stage 2b).

Runs the MUSE-SPARK agent calls for the study towns: 3 standard tasks
(Design Rev 9 s.2.2) x 2 repeats per town, one Model API call per
(task, town, repeat), then scores each named COHORT firm with the
LLM-assisted scorer (scorer.py, validated against run 1).

Non-cohort firms the agent names are NOT scored here: they are recorded
in the run meta (firms_named_not_in_cohort, with section text) and
collected afterwards into agent-named-additions.json, the handoff to the
audit stage, which audits and scores them (plan s.4, DECIDED 14 Nov 2026).
The saved responses make a later scoring pass possible without new calls.

Usage:
  python3 run_study_agents.py --all [--workers N] [--max-jobs N]
  python3 run_study_agents.py --town Abilene --town Dallas [--workers N]
  python3 run_study_agents.py --list-jobs

Checkpointing: a (town, task, repeat) whose muse-spark-observation.json
exists (with all per-firm files) is skipped. A saved
muse-spark-response.json is reused without a new agent call.

Concurrency: a global semaphore caps in-flight Model API calls at 5
(agent calls + scorer calls together). On a 429 / block response the
batch stops (STOP event); completed jobs are kept, the rest stay unrun.

The agent call uses the connector helper (muse_spark.py) as a subprocess
— the connector's own code path, so no key is handled here. The scorer
uses the same registered connection via the dynamic-credentials surrogate
(scorer.call_model_no_tools). No key, token, or surrogate is ever written
to an output file.

Output: runs/2026-11-14-study/agent/<town-slug>/<task>/<repeat>/
  muse-spark-response.json      raw Responses API JSON (verbatim)
  muse-spark-observation.json   run-level metadata + ordered firm list
  muse-observation-<firm_id>.json  one per named cohort firm
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from aisharc_harness.agent import muse_api, scorer as SC
from aisharc_harness.rules.engine import load_definitions

RUN_DATE = "2026-11-14"
SPEC_VERSION = "1.22"
PRIMARY_CATEGORY = "HVAC Contractor"
STUDY_DIR = os.path.join(HERE, "runs", "2026-11-14-study", "agent")
FIRM_LIST = os.path.join(
    os.path.dirname(HERE),
    "Texas HVAC correlation study — firm list — 2026-11-14 — DRAFT.json")
HELPER = os.path.expanduser(
    "~/workspace/custom-connectors/custom.meta-model-api/bin/muse_spark.py")

# Design Rev 9 s.2.2 — the three standard tasks, exact wording.
# (task_id, task label, dir name, service need)
TASKS = [
    ("task1", "Combined", "task1-combined",
     "AC installation and repair"),
    ("task2", "Repair only", "task2-repair-only",
     "AC repair"),
    ("task3", "Installation/replacement only",
     "task3-installation-replacement",
     "AC installation and replacement"),
]
REPEATS = (1, 2)

# At most 5 Model API calls in flight at once (agent + scorer together).
API_SEMAPHORE = threading.Semaphore(5)
STOP = threading.Event()
LOG_LOCK = threading.Lock()
PROGRESS_PATH = os.path.join(STUDY_DIR, "_progress.jsonl")

NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4",
                "five": "5", "six": "6", "seven": "7", "eight": "8",
                "nine": "9", "ten": "10", "twenty": "20"}
GENERIC_TAIL = [
    "heating and air conditioning", "heating & air conditioning",
    "air conditioning and heating", "air conditioning & heating",
    "heating and air", "heating & air", "heating and cooling",
    "heating & cooling", "air conditioning", "heating services",
    "heating", "cooling", "hvac", "air conditioning services",
    "llc", "inc", "corp", "co", "ltd", "company", "services",
    "mechanical",
]
CORE_STOPLIST = {"air", "ac", "hvac", "heat", "heating", "cooling",
                 "comfort", "home", "services", "service", "company",
                 "mechanical", "pro", "pros", "team", "group",
                 "solutions", "systems", "llc", "inc"}
GENERIC_HEADINGS = ("comparison", "next step", "quick", "summary",
                    "verdict", "recommendation", "bottom line",
                    "how to choose", "cost", "price", "what to ask",
                    "final", "overview", "note")


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ",
                  (s or "").lower().replace("&", " and ")).strip()


def norm_compact(s: str) -> str:
    return re.sub(r"\s+", " ", norm(s)).strip()


def digit_words(s: str) -> str:
    return " ".join(NUMBER_WORDS.get(w, w) for w in norm_compact(s).split())


def firm_aliases(firm: dict) -> list:
    """Match strings for a firm: full normalised name, a distinctive core
    (generic trade suffixes stripped), and digit-word variants of both.
    A core is kept only when it is >= 3 chars and not a generic word.
    Abbreviation variants are added: 'air conditioning' <-> 'a c',
    'brothers' <-> 'bros' (the agent shortens firm names both ways)."""
    out = []

    def add(name: str) -> None:
        for variant in alias_variants(name):
            if variant and variant not in out:
                out.append(variant)

    full = norm_compact(firm["name"])
    if full:
        add(full)
    core = full
    changed = True
    while changed:
        changed = False
        for tail in GENERIC_TAIL:
            if core.endswith(" " + tail):
                core = core[: -len(tail) - 1].strip()
                changed = True
            elif core == tail:
                core = ""
                changed = True
    core = core.strip()
    if len(core) >= 3 and core not in CORE_STOPLIST:
        add(core)
    return [a for a in out if a]


def alias_variants(name: str) -> list:
    """Abbreviation variants of one normalised name."""
    variants = [name, digit_words(name)]
    if "air conditioning" in name:
        variants.append(name.replace("air conditioning", "a c"))
        variants.append(digit_words(name.replace("air conditioning",
                                                "a c")))
    if " a c " in " %s " % name or name.startswith("a c "):
        variants.append(name.replace("a c", "air conditioning"))
    if "brothers" in name:
        variants.append(name.replace("brothers", "bros"))
    if "bros" in name.split():
        variants.append(name.replace("bros", "brothers"))
    return [v for v in dict.fromkeys(variants) if v]


BRAND_STOP = CORE_STOPLIST | {"the", "and", "of", "a", "an", "one", "all",
                             "american", "best", "top", "pro", "cool",
                             "texas", "first", "quality", "premier",
                             "elite", "superior", "advanced", "total",
                             "complete", "reliable"}


def brand_token(firm: dict, town: str) -> str | None:
    """The firm's first distinctive word (e.g. 'salt' for SALT Plumbing
    Air & Electric) — for heading-only matching, where the agent
    shortens a firm to brand + generic ('SALT Service Co.'). Needs
    >= 4 chars, not generic, not the town name. None when there is no
    such word (a firm whose name starts with a generic word has no
    brand token)."""
    town_words = set(norm_compact(town).split())
    for tok in norm_compact(firm["name"]).split():
        if len(tok) >= 4 and tok not in BRAND_STOP \
                and tok not in town_words:
            return tok
    return None


def alias_match(aliases: list, text_flat: str):
    """Longest alias that matches text_flat with word boundaries, else None."""
    best = None
    for a in aliases:
        if a and re.search(r"\b" + re.escape(a) + r"\b", text_flat):
            if best is None or len(a) > len(best):
                best = a
    return best


def log_progress(rec: dict) -> None:
    rec = dict(rec, ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
    with LOG_LOCK:
        with open(PROGRESS_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    print("[%(town)s %(task_id)s r%(repeat)d] %(status)s%(extra)s" % {
        "town": rec.get("town", "?"), "task_id": rec.get("task_id", "?"),
        "repeat": rec.get("repeat", 0), "status": rec.get("status", "?"),
        "extra": (" — " + rec["extra"]) if rec.get("extra") else "",
    }, flush=True)


class RateLimited(Exception):
    pass


def agent_call(question: str, town: str, zip_code: str, out_path: str) -> dict:
    """One standard-question agent call via the connector helper.
    Saves the raw Responses API JSON verbatim. Raises RateLimited on a
    429 / block so the batch stops instead of retrying in a loop."""
    with API_SEMAPHORE:
        proc = subprocess.run(
            [sys.executable, HELPER, "--question", question,
             "--town", town, "--zip", zip_code, "--out", out_path],
            capture_output=True, text=True, timeout=400)
    if proc.returncode != 0:
        err = proc.stderr.strip()[:2000]
        if "429" in err or "rate" in err.lower() or "blocked" in err.lower():
            raise RateLimited("agent call %s: %s" % (town, err))
        raise RuntimeError("agent call failed: %s" % err)
    with open(out_path, encoding="utf-8") as fh:
        return json.load(fh)


def score_one(answer: str, citations: list, firm_name: str, defs) -> dict:
    """One scorer call, under the shared API semaphore."""
    with API_SEMAPHORE:
        return SC.score_firm(answer, citations, firm_name, defs)


def extract_headings(answer_text: str) -> list:
    """Ordered headings: numbered ('### 1. Name') or lettered
    ('#### A. Name - address') firm entries, in document order. Each
    entry is (raw_name, section_text). Section headings ('### 1. Firms
    Located IN 79602') are returned too and filtered by parse_answer."""
    heads = []
    lines = answer_text.splitlines()
    cur = None
    for line in lines:
        m = re.match(r"^#{1,4}\s*(?:\d+\.|[A-Za-z]\.)\s*(.+)$", line)
        if m:
            if cur is not None:
                heads.append(cur)
            cur = [m.group(1).strip(), []]
            continue
        # Bold numbered list items ('**1. Ace Air - Best for ...**')
        # are firm entries too — they start a new entry whenever seen.
        m3 = re.match(r"^\s*\*\*\d+\.\s*(.+?)\*\*", line)
        if m3:
            if cur is not None:
                heads.append(cur)
            cur = [m3.group(1).strip(), [line]]
            continue
        m2 = re.match(r"^\s*(?:\d+\.|[-*])\s*\*\*(.+?)\*\*", line)
        if m2 and cur is None:
            heads.append([m2.group(1).strip(), [line]])
            continue
        if cur is not None:
            cur[1].append(line)
    if cur is not None:
        heads.append(cur)
    return [(h, "\n".join(sec)) for h, sec in heads]


SECTION_MARKERS = ("firms located", "firms serving", "top-rated firms",
                   "top rated firms", "outside zip", "just outside",
                   "located in", "serving ", "in the zip", "near ",
                   "options that serve", "installation / replacement",
                   "ac installation", "ac repair")


def is_section_heading(hn: str) -> bool:
    """A heading that labels a section of the list, not a firm."""
    if any(k in hn for k in GENERIC_HEADINGS):
        return True
    if "firms" in hn.split() or hn.startswith("other "):
        return True
    return any(m in hn for m in SECTION_MARKERS)


def clean_heading_name(raw: str) -> str:
    # Split off a descriptive suffix: ' - address', ' – serves 78006',
    # ' — Serves 77840', ' / alternate spelling'.
    name = re.split(r"\s+[-–—]\s+", raw.strip(), maxsplit=1)[0]
    name = name.split(" / ")[0].strip()
    name = re.sub(r"\*+", "", name).strip()
    return name


def heading_address(raw: str) -> str | None:
    """The ' - 926 A S Treadway, Abilene, TX 79602' tail of a firm
    heading, when it looks like a street address (never guessed)."""
    parts = re.split(r"\s+[-–—]\s+", raw.strip(), maxsplit=1)
    if len(parts) < 2:
        return None
    tail = re.sub(r"\*+", "", parts[1]).strip()
    if re.search(r"\d", tail) and (
            "TX" in tail or re.search(
                r"\b(Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|"
                r"Lane|Ln|Court|Ct|Parkway|Pkwy|Highway|Hwy)\b", tail)):
        return tail
    return None


def parse_answer(answer_text: str, firms: list, aliases: dict,
                 brands: dict | None = None) -> dict:
    """Which cohort firms the answer named (with list position), and the
    firm headings that are NOT in the cohort (leads/additions).
    `brands` maps firm_id -> brand token (heading-only match, for
    agent-shortened names like 'SALT Service Co.')."""
    flat = norm_compact(answer_text)
    brands = brands or {}
    # A brand token shared by two firms in the same town is ambiguous —
    # it matches neither.
    brand_counts: dict = {}
    for fid, tok in brands.items():
        if tok:
            brand_counts[tok] = brand_counts.get(tok, 0) + 1
    headings = [(clean_heading_name(h), sec, heading_address(h))
                for h, sec in extract_headings(answer_text)]
    # Position: the firm's order in the agent's list as given — the
    # ordinal among firm headings (cohort + non-cohort), in order.
    # Section headings take no position.
    ordered = []          # [{firm_id, name, position, heading}]
    heading_firm_ids = set()
    non_cohort = []       # [{name, section, position}]
    pos = 0
    for hname, sec, haddr in headings:
        hn = norm_compact(hname)
        if not hn or is_section_heading(hn):
            continue
        pos += 1
        best_firm, best_alias = None, None
        for firm in firms:
            a = alias_match(aliases[firm["firm_id"]], hn)
            if a and (best_alias is None or len(a) > len(best_alias)):
                best_firm, best_alias = firm, a
        if best_firm is None:
            # Heading-only brand match: the agent shortened the firm to
            # brand + generic ('SALT Service Co.'). The heading's first
            # word must be the brand token.
            first = hn.split()[0] if hn.split() else ""
            for firm in firms:
                tok = brands.get(firm["firm_id"])
                if tok and brand_counts.get(tok, 0) == 1 and first == tok:
                    best_firm = firm
                    break
        if best_firm is not None:
            if best_firm["firm_id"] not in heading_firm_ids:
                heading_firm_ids.add(best_firm["firm_id"])
                ordered.append({"firm_id": best_firm["firm_id"],
                                "name": best_firm["name"],
                                "position": pos, "heading": hname})
        else:
            non_cohort.append({"name": hname, "section": sec,
                               "position": pos,
                               "heading_address": haddr})
    # Cohort firms named in the text but with no heading (position None).
    for firm in firms:
        if firm["firm_id"] in heading_firm_ids:
            continue
        if alias_match(aliases[firm["firm_id"]], flat):
            ordered.append({"firm_id": firm["firm_id"],
                            "name": firm["name"],
                            "position": None, "heading": None})
    return {"ordered": ordered, "non_cohort": non_cohort}


def extract_run_meta(body: dict, run_dir: str, town: str, zip_code: str,
                     task: tuple, repeat: int, question: str) -> dict:
    obs = muse_api._extract_observation(body)
    searches = obs["web_search_calls"]
    n_results = sum(len(s.get("results") or []) for s in searches)
    distinct = []
    for c in obs["citations"]:
        if c.get("url") and c["url"] not in distinct:
            distinct.append(c["url"])
    cost = SC.cost_from_usage(body, web_searches=len(searches))
    return {
        "audit_id": "MUSE-SPARK",
        "agent_label": "MUSE-SPARK",
        "query": task[3],
        "task": task[1],
        "task_id": task[0],
        "task_dir": task[2],
        "repeat": repeat,
        "task_text": question,
        "town": town,
        "town_zip": "%s, TX %s" % (town, zip_code),
        "date_checked": RUN_DATE,
        "spec_version": SPEC_VERSION,
        "primary_business_category": PRIMARY_CATEGORY,
        "model": body.get("model", muse_api.MODEL),
        "tools": ["web_search"],
        "surface_tested": muse_api.SURFACE,
        "transcript_ref": os.path.join(
            "runs", "2026-11-14-study", "agent", slug(town), task[2],
            str(repeat), "muse-spark-response.json"),
        "response_id": body.get("id"),
        "web_search_calls": len(searches),
        "web_search_results": n_results,
        "url_citation_count": len(obs["citations"]),
        "distinct_urls": distinct,
        "cost_usd": cost,
        "usage": body.get("usage") or {},
        "answer_text": obs["answer_text"],
        "citations": obs["citations"],
        "searched": obs["searched"],
    }


def run_job(job: dict, defs, firms_by_town: dict) -> dict:
    """One (town, task, repeat): agent call (unless saved), score each
    named cohort firm, write the run files. Returns a progress record."""
    town = job["town"]
    zip_code = job["zip"]
    task = job["task"]
    repeat = job["repeat"]
    base = {"town": town, "task_id": task[0], "repeat": repeat}
    run_dir = os.path.join(STUDY_DIR, slug(town), task[2], str(repeat))
    os.makedirs(run_dir, exist_ok=True)
    response_path = os.path.join(run_dir, "muse-spark-response.json")
    obs_path = os.path.join(run_dir, "muse-spark-observation.json")
    firms = firms_by_town[town]
    aliases = {f["firm_id"]: firm_aliases(f) for f in firms}
    brands = {f["firm_id"]: brand_token(f, town) for f in firms}
    by_id = {f["firm_id"]: f for f in firms}

    if os.path.exists(obs_path):
        named_ids = []
        try:
            with open(obs_path, encoding="utf-8") as fh:
                prev = json.load(fh)
            named_ids = [f["firm_id"] for f in prev.get("firms_named", [])]
        except Exception:
            named_ids = []
        if named_ids and all(
                os.path.exists(os.path.join(
                    run_dir, "muse-observation-%s.json" % fid))
                for fid in named_ids):
            return dict(base, status="skipped",
                        extra="already complete (%d named)"
                              % len(named_ids))
        if not named_ids:
            # A completed run with zero named firms still has an obs file.
            return dict(base, status="skipped",
                        extra="already complete (0 named)")
    question = ("Find an HVAC firm in %s, TX %s for %s and compare the "
                "firms you find." % (town, zip_code, task[3]))
    t0 = time.time()
    if os.path.exists(response_path):
        with open(response_path, encoding="utf-8") as fh:
            body = json.load(fh)
        reused = True
    else:
        if STOP.is_set():
            return dict(base, status="not run",
                        extra="stopped before agent call")
        body = agent_call(question, town, zip_code, response_path)
        reused = False
    meta = extract_run_meta(body, run_dir, town, zip_code, task, repeat,
                            question)
    parsed = parse_answer(meta["answer_text"], firms, aliases, brands)
    ordered = parsed["ordered"]
    named = [by_id[o["firm_id"]] for o in ordered]
    positions = {o["firm_id"]: o["position"] for o in ordered}
    run_meta = {
        "primary_business_category": PRIMARY_CATEGORY,
        "query": task[3],
        "town_zip": "%s, TX %s" % (town, zip_code),
        "date_checked": RUN_DATE,
        "model": meta["model"],
        "transcript_ref": meta["transcript_ref"],
        "response_id": meta["response_id"],
        "web_search_calls": meta["web_search_calls"],
        "web_search_results": meta["web_search_results"],
        "url_citation_count": meta["url_citation_count"],
        "distinct_urls": meta["distinct_urls"],
        "cost_usd": meta["cost_usd"],
    }
    scorer_total = 0.0
    scored = {}
    if named:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = {pool.submit(score_one, meta["answer_text"],
                                meta["citations"], f["name"], defs): f
                    for f in named}
            for fut in as_completed(futs):
                firm = futs[fut]
                if STOP.is_set():
                    raise RateLimited("stopped during scoring")
                try:
                    scored[firm["firm_id"]] = fut.result()
                except RuntimeError as exc:
                    msg = str(exc)
                    if "429" in msg or "rate" in msg.lower():
                        raise RateLimited("scorer %s: %s"
                                          % (firm["name"], msg))
                    raise
        for fid, s in scored.items():
            scorer_total += s.get("scorer_cost_usd") or 0.0
    for firm in named:
        s = scored[firm["firm_id"]]
        obs = SC.build_observation(firm, s, run_meta, defs, True)
        obs["task"] = task[1]
        obs["task_id"] = task[0]
        obs["repeat"] = repeat
        obs["task_text"] = question
        obs["position"] = positions.get(firm["firm_id"])
        with open(os.path.join(run_dir, "muse-observation-%s.json"
                               % firm["firm_id"]), "w",
                  encoding="utf-8") as fh:
            json.dump(obs, fh, indent=2, sort_keys=False)
    run_obs = dict(meta)
    run_obs["firms_named"] = [
        {"firm_id": o["firm_id"], "name": o["name"],
         "position": o["position"]} for o in ordered]
    run_obs["firms_not_named"] = [
        f["name"] for f in firms if f["firm_id"] not in
        {o["firm_id"] for o in ordered}]
    run_obs["firms_named_not_in_cohort"] = parsed["non_cohort"]
    run_obs["scorer_total_cost_usd"] = round(scorer_total, 4)
    run_obs["total_cost_usd"] = round(meta["cost_usd"] + scorer_total, 4)
    with open(obs_path, "w", encoding="utf-8") as fh:
        json.dump(run_obs, fh, indent=2, sort_keys=False)
    return dict(base, status="done",
                extra="%s%d named, agent $%.4f + scorer $%.4f = $%.4f, %.0fs"
                      % ("reused response, " if reused else "",
                         len(named), meta["cost_usd"], scorer_total,
                         run_obs["total_cost_usd"], time.time() - t0),
                named=len(named), agent_cost=meta["cost_usd"],
                scorer_cost=round(scorer_total, 4))


def build_jobs(towns_filter=None):
    with open(FIRM_LIST, encoding="utf-8") as fh:
        data = json.load(fh)
    firms_by_town = {}
    for f in data["firms"]:
        firms_by_town.setdefault(f["town"], []).append(f)
    jobs = []
    for town in sorted(firms_by_town):
        if towns_filter and town not in towns_filter:
            continue
        zip_code = firms_by_town[town][0]["town_zip"]
        for task in TASKS:
            for repeat in REPEATS:
                jobs.append({"town": town, "zip": zip_code,
                             "task": task, "repeat": repeat})
    return jobs, firms_by_town


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true",
                        help="run all 600 (town, task, repeat) jobs")
    parser.add_argument("--town", action="append", default=[],
                        help="run one town (repeatable)")
    parser.add_argument("--list-jobs", action="store_true")
    parser.add_argument("--workers", type=int, default=8,
                        help="job workers (API calls capped at 5 total)")
    parser.add_argument("--max-jobs", type=int, default=0,
                        help="only run the first N jobs (testing)")
    args = parser.parse_args()
    jobs, firms_by_town = build_jobs(args.town or None)
    if args.list_jobs:
        print("%d jobs, %d towns" % (len(jobs), len(firms_by_town)))
        return
    if not args.all and not args.town:
        parser.print_help()
        sys.exit(2)
    if args.max_jobs:
        jobs = jobs[:args.max_jobs]
    os.makedirs(STUDY_DIR, exist_ok=True)
    defs = load_definitions()
    print("study agent run: %d jobs (%d towns x 3 tasks x 2 repeats), "
          "run date %s" % (len(jobs), len(firms_by_town), RUN_DATE))
    done = skipped = failed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run_job, job, defs, firms_by_town): job
                for job in jobs}
        for fut in as_completed(futs):
            job = futs[fut]
            base = {"town": job["town"], "task_id": job["task"][0],
                    "repeat": job["repeat"]}
            try:
                rec = fut.result()
            except RateLimited as exc:
                STOP.set()
                rec = dict(base, status="RATE LIMITED",
                           extra=str(exc)[:300])
                log_progress(rec)
                print("!! RATE LIMIT — stopping the batch. Completed jobs "
                      "are kept; the rest stay unrun.", flush=True)
                failed += 1
                # Cancel jobs not yet started.
                for f in futs:
                    if not f.done():
                        f.cancel()
                break
            except Exception as exc:  # noqa: BLE001 - record and continue
                rec = dict(base, status="FAILED",
                           extra="%s: %s" % (type(exc).__name__, str(exc)[:300]))
                failed += 1
            log_progress(rec)
            if rec["status"] == "done":
                done += 1
            elif rec["status"] == "skipped":
                skipped += 1
            elif rec["status"] not in ("not run",):
                failed += 1
    print("finished: %d done, %d skipped, %d failed/not run "
          "(STOP=%s)" % (done, skipped, failed, STOP.is_set()))


if __name__ == "__main__":
    main()
