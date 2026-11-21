#!/usr/bin/env python3
"""Post-run analysis for the additions audit run.

Reads runs/2026-11-14-study/audits-additions/*/summary.json (+ audit-data.json
for the M1 row) and reports:
  - completed firms, grade / points distribution, per-town eligible counts
  - approval-affected firms (homepage fetch failed with ProxyError /
    RemoteDisconnected = per-host approval not granted at fetch time),
    written to approval-affected-firms.json in the run dir, same shape
    as the Stage 2a file.
"""
import json
import os
from collections import Counter

HERE = "/home/hatch/workspace/goals/score-card-audit-product/files/aisharc-harness"
RUN_DIR = os.path.join(HERE, "runs", "2026-11-14-study", "audits-additions")
FIRMS_FILE = os.path.join(HERE, "study-additions-firms.json")


def main():
    firms = {f["firm_id"]: f for f in json.load(open(FIRMS_FILE))["firms"]}
    grades = Counter()
    points = Counter()
    per_town = {}
    approval = []
    completed = []
    for fid in sorted(os.listdir(RUN_DIR)):
        s_path = os.path.join(RUN_DIR, fid, "summary.json")
        if not os.path.exists(s_path):
            continue
        s = json.load(open(s_path))
        completed.append(fid)
        grades[s["grade"]] += 1
        points[s["category_points"]] += 1
        town = s["town"]
        per_town.setdefault(town, {"total": 0, "eligible": 0, "grades": Counter()})
        per_town[town]["total"] += 1
        per_town[town]["grades"][s["grade"]] += 1
        if s["grade"] != "F":
            per_town[town]["eligible"] += 1
        # approval-affected: homepage fetch refused by the egress proxy
        hp_note = None
        for n in s.get("notes") or []:
            if "returned no readable text" in n and "ProxyError" in n \
                    and "RemoteDisconnected" in n:
                hp_note = n
                break
        if hp_note:
            # robots.txt read later in the same audit?
            robots_later = False
            d_path = os.path.join(RUN_DIR, fid, "audit-data.json")
            if os.path.exists(d_path):
                d = json.load(open(d_path))
                for r in d.get("rows", []):
                    if r.get("Item") == "AI crawler access":
                        note = r.get("Evidence note") or ""
                        robots_later = "could not be read" not in note
            f = firms.get(fid, {})
            approval.append({
                "firm_id": fid,
                "firm": s["firm"],
                "town": town,
                "website": s.get("run", {}).get("website") or f.get("website"),
                "reason": "egress proxy refused the connection (ProxyError: Unable to connect to proxy, RemoteDisconnected) — host approval not granted at fetch time; fetch did not happen; website-dependent evidence recorded Not accessible per the engine rules; NOT evidence the site is unreadable",
                "homepage_note": hp_note,
                "robots_txt_later_read": robots_later,
                "grade": s["grade"],
                "critical": s["critical_issues"],
            })
    print("completed: %d / %d firms" % (len(completed), len(firms)))
    print("grades:", dict(sorted(grades.items())))
    print("points:", dict(sorted(points.items())))
    eligible = sum(1 for fid in completed
                   if json.load(open(os.path.join(RUN_DIR, fid, "summary.json")))["grade"] != "F")
    print("eligible (grade != F):", eligible)
    print("approval-affected: %d" % len(approval))
    print("per-town (total / eligible):")
    for t in sorted(per_town):
        print("  %s: %d / %d  %s" % (t, per_town[t]["total"], per_town[t]["eligible"],
                                     dict(sorted(per_town[t]["grades"].items()))))
    out = {
        "note": "Firms whose homepage fetch failed because the egress proxy refused the connection (ProxyError: Unable to connect to proxy, RemoteDisconnected) — the per-host approval card had not been granted when the fetch was attempted, so the fetch did not happen. Per Tim's 2026-11-14 follow-up: stay with the direct fetcher, do not stall, do not re-try in the same run; website-dependent evidence is Not accessible, and these firms are listed here so the analysis can distinguish them from sites that were actually unreadable. A later same-host fetch succeeding (robots_txt_later_read) confirms the host became reachable once approved.",
        "count": len(approval),
        "firms": approval,
    }
    with open(os.path.join(RUN_DIR, "approval-affected-firms.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    print("wrote approval-affected-firms.json (%d firms)" % len(approval))


if __name__ == "__main__":
    main()
