#!/usr/bin/env python3
"""Run the harness for one shopping query.

Reads a registry written by firm_registry.py, sets the harness's query to that query's task text (Spec §3:
the audit's Query field holds the task text), and runs run_audit.run_all() into <out_dir>. Every firm gets
the four files of Spec §13 (__audit-data.json, __summary.json, __human-review.json, __delivery-check.json).

Usage:
  run_query.py --registry firms-hvac-houston-77002-t2.json --out-dir runs/2026-11-21-hvac-houston-77002-t2 [--resume]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.join(os.path.dirname(HERE), "harness")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registry", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    registry = os.path.abspath(args.registry)
    with open(registry, encoding="utf-8") as fh:
        reg = json.load(fh)
    if not reg.get("firms"):
        raise SystemExit("registry has no firms")

    sys.path.insert(0, HARNESS)
    os.chdir(HARNESS)
    import run_audit  # noqa: E402  (the harness module)
    run_audit.QUERY = reg["query"]["task_text"]
    summary = run_audit.run_all(resume=args.resume, out_root_override=os.path.abspath(args.out_dir),
                                firms_file=registry, discovery_file=None)
    print("%d firms audited, %d eligible; files in %s; report %s"
          % (len(summary["summaries"]), len(summary["eligible"]), summary["out_root"], summary["report"]))


if __name__ == "__main__":
    main()
