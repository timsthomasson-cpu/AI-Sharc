#!/usr/bin/env python3
"""Combined-fix analysis for C/D firms under the 100-point v2 grading.

Follows cd_fix_analysis.py (same DB rebuild, same v2 allocation, same
bands A>=65, B 50-64, C 30-49, D<30, same new-F rule). Answers the
question behind the single-fix table: how many C/D firms move up a
grade when they fix several top fixes together, rather than one alone.
"""
import json
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, "/home/hatch/workspace/goals/score-card-audit-product/files/aisharc-harness")
import cd_fix_analysis as cfa

con = sqlite3.connect(cfa.DB)
con.row_factory = sqlite3.Row
corr = json.load(open(cfa.ROWS, encoding="utf-8"))
firm_audit = {}
for r in corr:
    firm_audit.setdefault(r["db_id"], r["audit_id"])

firms = {}
f_count = 0
for db_id, audit_id in firm_audit.items():
    f = con.execute("select website_url from firms where firm_id=?", (db_id,)).fetchone()
    website = (f["website_url"] or "").strip() if f else ""
    rows = con.execute("select row_type, category_or_gate, item, result, evidence_note from audit_rows where audit_id=?", (audit_id,)).fetchall()
    items, gates = {}, {}
    for r in rows:
        if r["row_type"] == "Item":
            c = cfa.item_code(r["item"])
            if c: items[c] = (r["result"], r["evidence_note"])
        elif r["row_type"] == "Gate":
            c = cfa.gate_code(r["category_or_gate"])
            if c: gates[c] = (r["result"], r["evidence_note"] or "")
    g5_note = gates.get("G5", ("", ""))[1]
    if (not website) or ("Closed flag present" in g5_note) or (db_id in cfa.UNREACHABLE_9):
        f_count += 1
        continue
    passed = {}
    for code in cfa.ALLOC_V2:
        if code in cfa.GATE_ITEMS:
            passed[code] = gates.get(code, ("", ""))[0] == "Pass"
        elif code in cfa.MERGE:
            g = cfa.MERGE[code]
            passed[code] = cfa.is_pass(items.get(code, ("", ""))[0]) and gates.get(g, ("", ""))[0] == "Pass"
        else:
            passed[code] = cfa.is_pass(items.get(code, ("", ""))[0])
    score = sum(cfa.ALLOC_V2[c] for c, ok in passed.items() if ok)
    band = "A" if score >= 65 else "B" if score >= 50 else "C" if score >= 30 else "D"
    firms[db_id] = {"score": score, "band": band, "fails": {c for c, ok in passed.items() if not ok}}
bands = Counter(v["band"] for v in firms.values())
assert f_count == 386 and bands == {"A": 98, "B": 173, "C": 342, "D": 430}, (f_count, bands)  # updated 2026-11-16 for the C2.2 service-page-only rule (was A 64 / B 146 / C 349 / D 484)
print(f"rebuilt OK: F {f_count}, bands {dict(bands)}")

c_firms = [v for v in firms.values() if v["band"] == "C"]
d_firms = [v for v in firms.values() if v["band"] == "D"]

def movers(combo, label):
    pts = sum(cfa.ALLOC_V2[c] for c in combo)
    mc = sum(1 for v in c_firms if any(c in v["fails"] for c in combo) and v["score"] + sum(cfa.ALLOC_V2[c] for c in combo if c in v["fails"]) >= 50)
    md = sum(1 for v in d_firms if any(c in v["fails"] for c in combo) and v["score"] + sum(cfa.ALLOC_V2[c] for c in combo if c in v["fails"]) >= 30)
    # also: firms that would move TWO grades (D->B needs >=50, C->A needs >=65)
    md2 = sum(1 for v in d_firms if v["score"] + sum(cfa.ALLOC_V2[c] for c in combo if c in v["fails"]) >= 50)
    mc2 = sum(1 for v in c_firms if v["score"] + sum(cfa.ALLOC_V2[c] for c in combo if c in v["fails"]) >= 65)
    print(f"{label}: {combo} = {pts} pts | C->B {mc}/{len(c_firms)} ({100*mc/len(c_firms):.1f}%) | D->C {md}/{len(d_firms)} ({100*md/len(d_firms):.1f}%) | D->B {md2} | C->A {mc2}")
    return {"label": label, "combo": combo, "pts": pts, "move_c": mc, "move_d": md, "move_d2": md2, "move_c2": mc2}

out = []
out.append(movers(["C4.2", "C2.1", "C2.2"], "Top 3 by expected points"))
out.append(movers(["C4.2", "C2.1", "C2.2", "C3.1", "C1.2"], "Top 5 by expected points"))
out.append(movers(["C4.2", "C2.1", "C2.2", "C3.1", "C1.2", "C1.1", "C6.2", "C5.1", "C7.3", "C1.3"], "Top 10 by expected points"))
out.append(movers(["C2.1", "C2.2", "C2.3", "C2.4"], "Service-page Category 2 set (C2.1+C2.2+C2.3+C2.4)"))
out.append(movers(["C2.1", "C2.2", "C4.2"], "Service-page trio (same as Top 3)"))
out.append(movers(["C4.2", "C3.1"], "Fee + licence (14 pts)"))
# Gap to next band
import statistics
print("C firms: points short of B (50): median", statistics.median([50-v["score"] for v in c_firms]), "| D firms: points short of C (30): median", statistics.median([30-v["score"] for v in d_firms]))
print("C firms within 7 pts of B:", sum(1 for v in c_firms if 50-v["score"] <= 7), "| D firms within 7 pts of C:", sum(1 for v in d_firms if 30-v["score"] <= 7))
print("C firms within 20 pts of B:", sum(1 for v in c_firms if 50-v["score"] <= 20), "| D firms within 20 pts of C:", sum(1 for v in d_firms if 30-v["score"] <= 20))
json.dump({"combos": out,
           "gap_median_c": statistics.median([50-v["score"] for v in c_firms]),
           "gap_median_d": statistics.median([30-v["score"] for v in d_firms])},
          open("/home/hatch/workspace/goals/score-card-audit-product/files/aisharc-harness/cd_fix_combos.json", "w"), indent=1)
print("saved cd_fix_combos.json")
