#!/usr/bin/env python3
"""Compare harness runs (r1, r2, r3) per firm and per Item.

Reads summary.json from runs/2026-11-11 (r1), runs/2026-11-11-r2 (r2),
runs/2026-11-13 (r3) and the muse-observation.json files in r3, and
writes runs/2026-11-13/comparison.md. The observation NEVER changes the
grade — the comparison states that explicitly.

Usage: python3 compare_runs.py
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = {
    "r1": os.path.join(HERE, "runs", "2026-11-11"),
    "r2": os.path.join(HERE, "runs", "2026-11-11-r2"),
    "r3": os.path.join(HERE, "runs", "2026-11-13"),
}


def load_summaries(run_dir: str) -> dict:
    out = {}
    if not os.path.isdir(run_dir):
        return out
    for fid in sorted(os.listdir(run_dir)):
        sp = os.path.join(run_dir, fid, "summary.json")
        if os.path.isfile(sp):
            with open(sp, encoding="utf-8") as fh:
                out[fid] = json.load(fh)
    return out


def item_results(summary: dict) -> dict:
    return {r["item_id"]: r["result"] for r in summary["rows"]
            if r["row_type"] == "Item"}


def gate_results(summary: dict) -> dict:
    return {r["gate_id"]: r["result"] for r in summary["rows"]
            if r["row_type"] == "Gate"}


def main() -> int:
    r1 = load_summaries(RUNS["r1"])
    r2 = load_summaries(RUNS["r2"])
    r3 = load_summaries(RUNS["r3"])
    if not r3:
        print("no r3 summaries in %s" % RUNS["r3"])
        return 2
    fids = sorted(set(r1) | set(r2) | set(r3))
    lines = []
    lines.append("# Harness runs — comparison r3 vs r1 and r2")
    lines.append("")
    lines.append("**Run dates:** r1 2026-11-11, r2 2026-11-11 (Google/Yelp "
                 "reader), r3 2026-11-13 (production-fields plan: agent "
                 "observation, delivery check, run id + evidence_source, "
                 "DB tables + loader). Query: AC installation and repair, "
                 "Coppell TX 75019, Spec v1.22, 19 firms.")
    lines.append("")
    lines.append("Harness test only. No Report Card was issued to any firm, "
                 "no firm was contacted. Grades are the harness's fresh-audit "
                 "output for each run date, not client grades. **The "
                 "MUSE-SPARK observation never changes the grade** (Design "
                 "s.9.3) — it is recorded separately and compared in its own "
                 "section below.")
    lines.append("")
    lines.append("## Per-firm results")
    lines.append("")
    lines.append("| Firm | r1 grade | r2 grade | r3 grade | r1 pts | r2 pts | "
                 "r3 pts | r1 Crit | r2 Crit | r3 Crit | r1 High | r2 High | "
                 "r3 High | r1 passed | r2 passed | r3 passed |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for fid in fids:
        def cell(run, key, default="—"):
            s = run.get(fid)
            return str(s[key]) if s else default
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | "
                     "%s | %s | %s | %s | %s | %s |"
                     % (r3.get(fid, r2.get(fid, r1.get(fid, {}))).get("firm", fid),
                        cell(r1, "grade"), cell(r2, "grade"), cell(r3, "grade"),
                        cell(r1, "category_points"), cell(r2, "category_points"),
                        cell(r3, "category_points"),
                        cell(r1, "critical_issues"), cell(r2, "critical_issues"),
                        cell(r3, "critical_issues"),
                        cell(r1, "high_issues"), cell(r2, "high_issues"),
                        cell(r3, "high_issues"),
                        cell(r1, "passed_items"), cell(r2, "passed_items"),
                        cell(r3, "passed_items")))
    lines.append("")
    for label, a, b in (("r1", r1, None), ("r2", r2, None)):
        pass
    elig = {k: [fid for fid, s in run.items() if s["critical_issues"] == 0]
            for k, run in (("r1", r1), ("r2", r2), ("r3", r3))}
    lines.append("Eligible firms (0 Critical): r1 %d of %d, r2 %d of %d, "
                 "r3 %d of %d."
                 % (len(elig["r1"]), len(r1), len(elig["r2"]), len(r2),
                    len(elig["r3"]), len(r3)))
    lines.append("")
    lines.append("## What moved, r2 -> r3 (per firm)")
    lines.append("")
    moved_any = False
    for fid in fids:
        s2, s3 = r2.get(fid), r3.get(fid)
        if not s2 or not s3:
            continue
        changes = []
        if s2["grade"] != s3["grade"]:
            changes.append("grade %s -> %s" % (s2["grade"], s3["grade"]))
        if s2["category_points"] != s3["category_points"]:
            changes.append("points %d -> %d" % (s2["category_points"],
                                                s3["category_points"]))
        if s2["critical_issues"] != s3["critical_issues"]:
            changes.append("Critical %d -> %d" % (s2["critical_issues"],
                                                  s3["critical_issues"]))
        if s2["high_issues"] != s3["high_issues"]:
            changes.append("High %d -> %d" % (s2["high_issues"],
                                              s3["high_issues"]))
        i2, i3 = item_results(s2), item_results(s3)
        item_moves = ["%s: %s -> %s" % (iid, i2.get(iid), i3.get(iid))
                      for iid in sorted(i2) if i2.get(iid) != i3.get(iid)]
        g2, g3 = gate_results(s2), gate_results(s3)
        gate_moves = ["%s: %s -> %s" % (gid, g2.get(gid), g3.get(gid))
                      for gid in sorted(g2) if g2.get(gid) != g3.get(gid)]
        if changes or item_moves or gate_moves:
            moved_any = True
            lines.append("### %s" % s3["firm"])
            lines.append("")
            if changes:
                lines.append("- %s." % "; ".join(changes))
            if gate_moves:
                lines.append("- Gates moved: %s." % "; ".join(gate_moves))
            if item_moves:
                lines.append("- Items moved: %s." % "; ".join(item_moves))
            lines.append("")
    if not moved_any:
        lines.append("No firm moved on grade, points, Critical, High, or "
                     "any Gate/Item between r2 and r3.")
        lines.append("")
    lines.append("## What moved, r1 -> r3 (summary)")
    lines.append("")
    for fid in fids:
        s1, s3 = r1.get(fid), r3.get(fid)
        if not s1 or not s3:
            continue
        if (s1["grade"] != s3["grade"]
                or s1["category_points"] != s3["category_points"]
                or s1["critical_issues"] != s3["critical_issues"]
                or s1["high_issues"] != s3["high_issues"]):
            lines.append("- %s: grade %s -> %s, points %d -> %d, Critical "
                         "%d -> %d, High %d -> %d."
                         % (s3["firm"], s1["grade"], s3["grade"],
                            s1["category_points"], s3["category_points"],
                            s1["critical_issues"], s3["critical_issues"],
                            s1["high_issues"], s3["high_issues"]))
    lines.append("")
    lines.append("## Item pass counts across the 19 firms (r1 / r2 / r3)")
    lines.append("")
    lines.append("| Item | r1 Pass | r2 Pass | r3 Pass |")
    lines.append("|---|---|---|---|")
    all_items = sorted({iid for run in (r1, r2, r3) for s in run.values()
                        for iid in item_results(s)})
    for iid in all_items:
        def count(run):
            return sum(1 for s in run.values()
                       if item_results(s).get(iid) in ("Pass", "Pass with warning"))
        lines.append("| %s | %d | %d | %d |" % (iid, count(r1), count(r2), count(r3)))
    lines.append("")
    lines.append("## Gate pass counts across the 19 firms (r1 / r2 / r3)")
    lines.append("")
    lines.append("| Gate | r1 Pass | r2 Pass | r3 Pass |")
    lines.append("|---|---|---|---|")
    all_gates = sorted({gid for run in (r1, r2, r3) for s in run.values()
                        for gid in gate_results(s)})
    for gid in all_gates:
        def gcount(run):
            return sum(1 for s in run.values()
                       if gate_results(s).get(gid) == "Pass")
        lines.append("| %s | %d | %d | %d |" % (gid, gcount(r1), gcount(r2), gcount(r3)))
    lines.append("")
    lines.append("## MUSE-SPARK observation — r3 vs run 1 (2026-11-11)")
    lines.append("")
    lines.append("The observation never changes the grade. This section "
                 "compares what the model demonstrated, not scores.")
    lines.append("")
    obs_path = os.path.join(RUNS["r3"], "muse-spark-observation.json")
    if os.path.exists(obs_path):
        with open(obs_path, encoding="utf-8") as fh:
            run_obs = json.load(fh)
        lines.append("- **r3 agent call:** response %s, %d web_search "
                     "calls, %d results, %d citations from %d distinct "
                     "URLs, cost $%.4f; scorer calls $%.4f; total $%.4f."
                     % (run_obs.get("response_id"),
                        run_obs.get("web_search_calls", 0),
                        run_obs.get("web_search_results", 0),
                        run_obs.get("url_citation_count", 0),
                        len(run_obs.get("distinct_urls") or []),
                        run_obs.get("cost_usd", 0) or 0,
                        run_obs.get("scorer_total_cost_usd", 0) or 0,
                        run_obs.get("total_cost_usd", 0) or 0))
        lines.append("- **Run 1 (2026-11-11):** response "
                     "resp_6af4d52c3d277297d741445c, 6 web_search calls, 23 "
                     "results, 99 citations from 4 distinct URLs, cost "
                     "~$0.06.")
        lines.append("- **Firms named in r3 (%d):** %s."
                     % (len(run_obs.get("firms_named") or []),
                        ", ".join(run_obs.get("firms_named") or []) or "none"))
        lines.append("- **Firms named in run 1 (2 of 19):** Coppell Heating "
                     "and Air Conditioning, Eric's Home Services (plus "
                     "Airmatics and Quigley Heating & Air, not in the "
                     "cohort).")
        lines.append("- **Named in r3, not in the cohort:** %s."
                     % (", ".join(run_obs.get("firms_named_not_in_cohort") or [])
                        or "none"))
        union = set()
        for fid in fids:
            opath = os.path.join(RUNS["r3"], fid, "muse-observation.json")
            if os.path.exists(opath):
                with open(opath, encoding="utf-8") as fh:
                    obs = json.load(fh)
                union.update(i["item_id"] for i in obs["items"]
                             if i["result"] == "Pass")
        lines.append("- **Items demonstrated in r3 (union, %d):** %s."
                     % (len(union), ", ".join(sorted(union)) or "none"))
        lines.append("- **Items demonstrated in run 1 (9):** C1.1, C2.2, "
                     "C2.3, C2.4, C3.1, C3.2, C4.2, C5.1, C6.2.")
        lines.append("- **Items in run 1 but not r3:** %s."
                     % (", ".join(sorted({"C1.1", "C2.2", "C2.3", "C2.4",
                                          "C3.1", "C3.2", "C4.2", "C5.1",
                                          "C6.2"} - union)) or "none"))
        lines.append("- **Items in r3 but not run 1:** %s."
                     % (", ".join(sorted(union - {"C1.1", "C2.2", "C2.3",
                                                  "C2.4", "C3.1", "C3.2",
                                                  "C4.2", "C5.1", "C6.2"}))
                        or "none"))
    else:
        lines.append("No r3 agent observation file found.")
    lines.append("")
    out = os.path.join(RUNS["r3"], "comparison.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
