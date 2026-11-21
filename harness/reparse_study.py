#!/usr/bin/env python3
"""Re-parse the saved study agent responses with the current matching
rules (run_study_agents.parse_answer) and fix up the run outputs.

Used after a matching-rule fix (e.g. abbreviation variants, dash-split
heading cleaning): the agent calls are NOT repeated — the saved
muse-spark-response.json is re-read, the named set is re-derived, and
only newly-named firms get a fresh scorer call. Observation files for
firms no longer named are removed; positions are updated in place.

Usage:
  python3 reparse_study.py --dry-run   # report what would change
  python3 reparse_study.py             # apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from run_study_agents import (  # noqa: E402
    RUN_DATE, SPEC_VERSION, PRIMARY_CATEGORY, STUDY_DIR, FIRM_LIST,
    TASKS, build_jobs, brand_token, firm_aliases, parse_answer, score_one)
from aisharc_harness.agent import muse_api, scorer as SC  # noqa: E402
from aisharc_harness.rules.engine import load_definitions  # noqa: E402

STOP = threading.Event()


def reparse_run(run_dir: str, meta: dict, firms: list, defs,
                dry_run: bool) -> dict:
    """Re-derive one run's named set from its saved response."""
    with open(os.path.join(run_dir, "muse-spark-response.json"),
              encoding="utf-8") as fh:
        body = json.load(fh)
    obs = muse_api._extract_observation(body)
    aliases = {f["firm_id"]: firm_aliases(f) for f in firms}
    town = meta["town"]
    brands = {f["firm_id"]: brand_token(f, town) for f in firms}
    parsed = parse_answer(obs["answer_text"], firms, aliases, brands)
    by_id = {f["firm_id"]: f for f in firms}
    new_ordered = parsed["ordered"]
    new_ids = {o["firm_id"] for o in new_ordered}
    old_ids = {f["firm_id"] for f in meta.get("firms_named", [])}
    gained = sorted(new_ids - old_ids)
    lost = sorted(old_ids - new_ids)
    positions = {o["firm_id"]: o["position"] for o in new_ordered}
    return {"run_dir": run_dir, "meta": meta, "body": body, "obs": obs,
            "parsed": parsed, "by_id": by_id, "positions": positions,
            "gained": gained, "lost": lost, "dry_run": dry_run}


def apply_run(rec: dict, defs) -> dict:
    """Score newly-named firms, update the run's files. Returns a report."""
    run_dir, meta = rec["run_dir"], rec["meta"]
    obs, parsed = rec["obs"], rec["parsed"]
    by_id, positions = rec["by_id"], rec["positions"]
    gained, lost = rec["gained"], rec["lost"]
    if rec["dry_run"]:
        return {"run_dir": run_dir, "gained": gained, "lost": lost,
                "scorer_cost": 0.0}
    if STOP.is_set():
        return {"run_dir": run_dir, "gained": [], "lost": [],
                "scorer_cost": 0.0, "status": "not run (stopped)"}
    run_meta = {
        "primary_business_category": PRIMARY_CATEGORY,
        "query": meta["query"],
        "town_zip": meta["town_zip"],
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
    scorer_total = meta.get("scorer_total_cost_usd", 0.0)
    # Score the gained firms (parallel, capped by the shared semaphore
    # inside score_one).
    scored = {}
    if gained:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = {pool.submit(score_one, obs["answer_text"],
                                obs["citations"], by_id[fid]["name"], defs):
                    fid for fid in gained}
            for fut in as_completed(futs):
                fid = futs[fut]
                try:
                    scored[fid] = fut.result()
                except RuntimeError as exc:
                    msg = str(exc)
                    if "429" in msg or "rate" in msg.lower():
                        STOP.set()
                        raise RuntimeError("scorer rate-limited: %s" % msg)
                    raise
        for fid, s in scored.items():
            scorer_total += s.get("scorer_cost_usd") or 0.0
            firm = by_id[fid]
            o = SC.build_observation(firm, s, run_meta, defs, True)
            o["task"] = meta["task"]
            o["task_id"] = meta["task_id"]
            o["repeat"] = meta["repeat"]
            o["task_text"] = meta["task_text"]
            o["position"] = positions.get(fid)
            with open(os.path.join(run_dir, "muse-observation-%s.json"
                                   % fid), "w", encoding="utf-8") as fh:
                json.dump(o, fh, indent=2, sort_keys=False)
    # Update positions in already-scored files if they moved.
    for fid, pos in positions.items():
        path = os.path.join(run_dir, "muse-observation-%s.json" % fid)
        if fid in gained or not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            o = json.load(fh)
        if o.get("position") != pos:
            o["position"] = pos
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(o, fh, indent=2, sort_keys=False)
    # Remove files for firms no longer named.
    for fid in lost:
        path = os.path.join(run_dir, "muse-observation-%s.json" % fid)
        if os.path.exists(path):
            os.remove(path)
    # Rewrite the run meta.
    firms = rec["firms"]
    meta["firms_named"] = [
        {"firm_id": o["firm_id"], "name": o["name"],
         "position": o["position"]} for o in parsed["ordered"]]
    meta["firms_not_named"] = [
        f["name"] for f in firms
        if f["firm_id"] not in {o["firm_id"] for o in parsed["ordered"]}]
    meta["firms_named_not_in_cohort"] = parsed["non_cohort"]
    meta["scorer_total_cost_usd"] = round(scorer_total, 4)
    meta["total_cost_usd"] = round(meta["cost_usd"] + scorer_total, 4)
    with open(os.path.join(run_dir, "muse-spark-observation.json"),
              "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, sort_keys=False)
    return {"run_dir": run_dir, "gained": gained, "lost": lost,
            "scorer_cost": round(
                sum((scored[f].get("scorer_cost_usd") or 0.0)
                    for f in scored), 4)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    jobs, firms_by_town = build_jobs()
    defs = load_definitions()
    recs = []
    for job in jobs:
        town, task, repeat = job["town"], job["task"], job["repeat"]
        from run_study_agents import slug
        run_dir = os.path.join(STUDY_DIR, slug(town), task[2], str(repeat))
        meta_path = os.path.join(run_dir, "muse-spark-observation.json")
        if not os.path.exists(meta_path):
            print("MISSING run meta: %s" % run_dir)
            continue
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        recs.append(reparse_run(run_dir, meta, firms_by_town[town], defs,
                                args.dry_run))
    for rec in recs:
        rec["firms"] = firms_by_town[
            rec["meta"]["town"]]
    changed = [r for r in recs if r["gained"] or r["lost"]]
    print("%d runs, %d would change (%d firms gained, %d lost)"
          % (len(recs), len(changed),
             sum(len(r["gained"]) for r in changed),
             sum(len(r["lost"]) for r in changed)))
    for r in changed:
        print("  %s gained=%s lost=%s"
              % (r["run_dir"].split("agent/")[-1], r["gained"], r["lost"]))
    if args.dry_run:
        return
    total_cost = 0.0
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(apply_run, rec, defs): rec for rec in changed}
        for fut in as_completed(futs):
            try:
                rep = fut.result()
            except Exception as exc:  # noqa: BLE001 - record and continue
                print("FAILED %s: %s" % (futs[fut]["run_dir"], exc))
                continue
            total_cost += rep.get("scorer_cost", 0.0)
            print("  applied %s gained=%s lost=%s scorer $%.4f"
                  % (rep["run_dir"].split("agent/")[-1], rep["gained"],
                     rep["lost"], rep.get("scorer_cost", 0.0)))
    print("reparse done, extra scorer cost $%.4f (STOP=%s)"
          % (total_cost, STOP.is_set()))


if __name__ == "__main__":
    main()
