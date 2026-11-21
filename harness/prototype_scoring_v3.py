#!/usr/bin/env python3
"""Allocation v3 prototype: move the three anti-aligned Grade items to
Placement Suggestions and re-distribute their 8 points.

SUPERSEDED 2026-11-16 — Tim decided to leave the anti-aligned items as
they are ('leave the anti-aligned items as they are'). Do NOT run this
script or use its output spreadsheet (Grading_Prototype_100pt_v3, moved
to recoverable trash 2026-11-16). Allocation v2 stands. Kept only as a
record of the method.

Removed (Tim leans towards, NOT decided — 2026-11-16):
  C6.1 one unique primary phone number everywhere (3 pts, rho +0.111)
  G6 verifiable listing (3 pts, rho +0.106)
  C5.2 hours consistency (2 pts, rho +0.076)
Freed 8 points re-distributed across the remaining 18 Grade items,
per item, proportionally to v2 points (largest-remainder rounding),
same method as v2. Total stays 100.

Source data: aisharc-audit.sqlite (corrected audits) + the corrected
correlation-rows.json (2026-11-15 re-audit-55 run). Merged-item rule:
a merged item passes only if BOTH the Item and the absorbed Gate pass.
Pass = Item Pass / Pass with warning, Gate Pass. F rule unchanged
(firm-side only: no website / closed flag / verified unreachable).

Validates the method first by reproducing the v2 Firm scores exactly.
"""
import json, sqlite3, statistics, sys
from collections import Counter
sys.path.insert(0, "/home/hatch/workspace/goals/score-card-audit-product/files/aisharc-harness")
import cd_fix_analysis as cfa  # validated v2 rebuild: item/gate code mapping, merged-item rule, F rule

DB = "/home/hatch/workspace/goals/score-card-audit-product/files/aisharc-audit-db/aisharc-audit.sqlite"
ROWS = "/home/hatch/workspace/goals/score-card-audit-product/files/aisharc-harness/runs/2026-11-15-reaudit-55/correlation-rows.json"
V2_XLSX = "/home/hatch/workspace/user/files/Grading_Prototype_100pt_v2_-_Nov_15_2026.xlsx"
OUT_XLSX = "/home/hatch/workspace/user/files/Grading_Prototype_100pt_v3_-_Nov_16_2026.xlsx"

V2 = {
    "C1.1": 9, "C1.2": 9, "C1.3": 4,
    "C2.1": 7, "C2.2": 6, "C2.3": 4, "C2.4": 3,
    "C3.1": 7, "G6": 3,
    "C4.2": 7, "C4.3": 3, "C4.4": 3,
    "C5.1": 5, "C5.2": 2,
    "C6.1": 3, "C6.2": 6, "G1": 6,
    "C7.1": 3, "C7.2": 3, "C7.3": 5, "C7.4": 2,
}
REMOVED = {"C6.1": 3, "G6": 3, "C5.2": 2}
FREED = sum(REMOVED.values())  # 8
REMAIN = {k: v for k, v in V2.items() if k not in REMOVED}
assert sum(REMAIN.values()) == 92

# Largest-remainder redistribution of the 8 freed points.
raw = {k: FREED * v / 92 for k, v in REMAIN.items()}
base = {k: int(x) for k, x in raw.items()}
extra = FREED - sum(base.values())
order = sorted(REMAIN, key=lambda k: (-(raw[k] - base[k]), -REMAIN[k], k))
for k in order[:extra]:
    base[k] += 1
V3 = {k: REMAIN[k] + base[k] for k in REMAIN}
assert sum(V3.values()) == 100, V3
print("v3 allocation:", V3)
print("gainers (+1):", [k for k in V3 if V3[k] != REMAIN[k]])

ITEM_LABEL = {
    "C1.1": "Rating and review count readable",
    "C1.2": "Rating figures consistent across sources",
    "C1.3": "No recurring unaddressed complaint pattern",
    "C2.1": "Service-area page naming town and ZIP",
    "C2.2": "Install and repair listed separately on that page",
    "C2.3": "Brands and system types served on that page",
    "C2.4": "Unique primary phone and booking route on that page",
    "C3.1": "Single consistent applicable state licence number published",
    "C4.2": "Diagnostic fee in dollars",
    "C4.3": "Free-estimate status for install, stated separately",
    "C4.4": "Free-estimate status for repair, stated separately",
    "C5.1": "Day-by-day hours readable",
    "C5.2": "Hours, 24-hour, weekend, and emergency status consistent across sources",
    "C6.1": "One unique primary phone number everywhere",
    "C6.2": "Founding year and business lineage consistent across sources",
    "C7.1": "AI crawler access (M1)",
    "C7.2": "Key facts readable without JavaScript (M2)",
    "C7.3": "LocalBusiness structured data (M4)",
    "C7.4": "Sitemap (M5)",
    "G1": "Exact name",
    "G6": "Verifiable listing",
}
GATE_LABEL = {"G1": "Exact name", "G2": "Services in plain words",
              "G3": "Area coverage", "G4": "Contact",
              "G5": "Hours / Active Status", "G6": "Verifiable listing"}
# merged item -> absorbed gate (None = item alone)
ABSORB = {"C2.1": "G3", "C2.2": "G2", "C2.4": "G4", "C5.1": "G5"}
UNREACHABLE_9 = {
    "Mr Cool", "Roger's Siding and Exteriors",
    "N Slyvania Air Conditioning Repair", "TexFresh Best Services",
    "Conroe AC Repair", "Apply Tek Foam Insulation",
    "Charleston Electric & Air", "American Air Systems",
    "Air Texas AC & Heating",
}

corr = json.load(open(ROWS))
firms = {}  # db_id -> (audit_id, firm name, town)
for r in corr:
    firms.setdefault(r["db_id"], (r["audit_id"], r["firm"], r["town"]))
print("firms in correlation:", len(firms))
assert len(firms) == 1429

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

def audit_passes(audit_id):
    # Same code mapping as cd_fix_analysis (validated v2 rebuild): DB item
    # names are matched by keyword, gates by category phrase. Returns
    # code-keyed (result, evidence_note) dicts, plus the G5 note.
    gates, items = {}, {}
    for row in con.execute(
        "SELECT row_type, category_or_gate, item, result, evidence_note "
        "FROM audit_rows WHERE audit_id=?", (audit_id,)):
        if row["row_type"] == "Gate":
            c = cfa.gate_code(row["category_or_gate"])
            if c:
                gates[c] = (row["result"], row["evidence_note"] or "")
        elif row["row_type"] == "Item":
            c = cfa.item_code(row["item"])
            if c:
                items[c] = (row["result"], row["evidence_note"])
    g5_note = gates.get("G5", ("", ""))[1]
    return gates, items, g5_note

def merged_pass(code, gates, items):
    # Identical to cd_fix_analysis: Gate items are their Gate result;
    # merged items pass only if both the Item and the absorbed Gate pass.
    if code in cfa.GATE_ITEMS:
        return gates.get(code, ("", ""))[0] == "Pass"
    if code in cfa.MERGE:
        g = cfa.MERGE[code]
        return cfa.is_pass(items.get(code, ("", ""))[0]) \
            and gates.get(g, ("", ""))[0] == "Pass"
    return cfa.is_pass(items.get(code, ("", ""))[0])

def score(passes, alloc):
    return sum(alloc[c] for c in alloc if passes.get(c))

results = []  # dicts per firm
for db_id, (audit_id, name, town) in firms.items():
    gates, items, g5_note = audit_passes(audit_id)
    passes = {c: merged_pass(c, gates, items) for c in V2}
    f = con.execute("SELECT website_url FROM firms WHERE firm_id=?",
                    (db_id,)).fetchone()
    website = (f["website_url"] or "").strip() if f else ""
    closed = "Closed flag present" in (g5_note or "")
    f_reason = []
    if not website:
        f_reason.append("no website")
    if closed:
        f_reason.append("closed flag / not in business")
    if db_id in cfa.UNREACHABLE_9:
        f_reason.append("website genuinely unreachable, firm-side, verified")
    results.append({
        "db_id": db_id, "name": name, "town": town, "audit_id": audit_id,
        "passes": passes, "g6_pass": passes["G6"],
        "v2": score(passes, V2), "v3": score(passes, V3),
        "f_reason": "; ".join(f_reason) if f_reason else None,
    })

f_firms = [r for r in results if r["f_reason"]]
elig = [r for r in results if not r["f_reason"]]
print("F firms:", len(f_firms), "| eligible:", len(elig))
assert len(f_firms) == 386 and len(elig) == 1043, (len(f_firms), len(elig))

# --- validate v2 reproduction against the v2 spreadsheet ---
import openpyxl
wb2 = openpyxl.load_workbook(V2_XLSX, data_only=True)
ws = wb2["Firm scores"]
v2_sheet = {}
for row in ws.iter_rows(min_row=4, values_only=True):
    if row[0]:
        v2_sheet[(row[0], row[1])] = row[2]
mismatch = [(r["name"], r["town"], r["v2"], v2_sheet.get((r["name"], r["town"])))
            for r in elig if v2_sheet.get((r["name"], r["town"])) != r["v2"]]
print("v2 per-firm mismatches vs spreadsheet:", len(mismatch))
for m in mismatch[:10]:
    print("  ", m)
assert not mismatch, "v2 reproduction failed"

def dist(scores):
    c = Counter((s // 10) * 10 for s in scores)
    return [c.get(b, 0) for b in range(0, 100, 10)]

v2_scores = [r["v2"] for r in elig]
v3_scores = [r["v3"] for r in elig]
print("v2: min %d median %.0f mean %.1f max %d" %
      (min(v2_scores), statistics.median(v2_scores),
       statistics.mean(v2_scores), max(v2_scores)))
print("v3: min %d median %.0f mean %.1f max %d" %
      (min(v3_scores), statistics.median(v3_scores),
       statistics.mean(v3_scores), max(v3_scores)))
print("v2 dist:", dist(v2_scores))
print("v3 dist:", dist(v3_scores))
changes = [r["v3"] - r["v2"] for r in elig]
print("mean change v2->v3: %.1f range %+d..%+d unchanged: %d" %
      (statistics.mean(changes), min(changes), max(changes),
       sum(1 for c in changes if c == 0)))

def bands(scores):
    return {"A": sum(1 for s in scores if s >= 65),
            "B": sum(1 for s in scores if 50 <= s < 65),
            "C": sum(1 for s in scores if 30 <= s < 50),
            "D": sum(1 for s in scores if s < 30)}
print("v2 bands (A65+/B50-64/C30-49/D<30) over 1429 incl F:",
      bands(v2_scores + [0] * 0), "eligible only:", bands(v2_scores))
print("v3 bands over eligible:", bands(v3_scores))
print("v3 grade distribution over all 1429 (F separate):",
      {**bands(v3_scores), "F": len(f_firms)})

# Consequence flagged in chat: firms with no verifiable listing scoring highly.
no_g6 = [r for r in elig if not r["g6_pass"]]
print("eligible firms failing G6 verifiable listing:", len(no_g6),
      "| max v3 score among them:", max(r["v3"] for r in no_g6),
      "| scoring A (>=65):", sum(1 for r in no_g6 if r["v3"] >= 65),
      "| scoring B+:", sum(1 for r in no_g6 if r["v3"] >= 50))
print("top 5 no-G6 scorers under v3:")
for r in sorted(no_g6, key=lambda x: -x["v3"])[:5]:
    print("  ", r["name"], r["town"], r["v3"], "(v2 %d)" % r["v2"])

# Top firms under v3 and biggest movers.
print("top 5 under v3:")
for r in sorted(elig, key=lambda x: -x["v3"])[:5]:
    print("  ", r["name"], r["town"], r["v3"], "(v2 %d)" % r["v2"])
print("biggest drops v2->v3:")
for r in sorted(elig, key=lambda x: x["v3"] - x["v2"])[:5]:
    print("  ", r["name"], r["town"], r["v2"], "->", r["v3"])

json.dump([{"name": r["name"], "town": r["town"], "db_id": r["db_id"],
            "v2": r["v2"], "v3": r["v3"], "f_reason": r["f_reason"],
            "g6_pass": r["g6_pass"],
            "passes": {c: bool(r["passes"][c]) for c in V3}}
           for r in results],
          open("/tmp/v3_scores.json", "w"), indent=1)

# --- build the v3 spreadsheet (mirrors v2 structure) ---
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
GROUPS = {"C1.1": "1. Reputation", "C1.2": "1. Reputation", "C1.3": "1. Reputation",
          "C2.1": "2. Area Coverage", "C2.2": "2. Area Coverage",
          "C2.3": "2. Area Coverage", "C2.4": "2. Area Coverage",
          "C3.1": "3. Credentials and Trust",
          "C4.2": "4. Pricing and Warranty", "C4.3": "4. Pricing and Warranty",
          "C4.4": "4. Pricing and Warranty",
          "C5.1": "5. Hours and Active Status",
          "C6.2": "6. Identity and Contact", "G1": "6. Identity and Contact",
          "C7.1": "7. Machine Readability", "C7.2": "7. Machine Readability",
          "C7.3": "7. Machine Readability", "C7.4": "7. Machine Readability"}
RHO = {"C1.1": -0.219, "C1.2": -0.199, "C1.3": -0.044, "C2.1": -0.126,
       "C2.2": -0.029, "C2.3": -0.079, "C2.4": 0.008, "C3.1": -0.116,
       "C4.2": -0.121, "C4.3": -0.021, "C4.4": -0.022, "C5.1": -0.045,
       "C6.2": -0.106, "G1": -0.107, "C7.1": 0.019, "C7.2": 0.032,
       "C7.3": -0.077, "C7.4": -0.011}
# NOTE (2026-11-16, fixed before running): the draft used the PLAIN-Item
# rhos for C2.2 (-0.063) and C2.4 (-0.013), copied from the v2 sheet.
# Those are wrong for merged Grade items: a merged item passes only when
# both the Item and its absorbed Gate pass, and the merged rhos are
# C2.2 -0.029 and C2.4 +0.008 (cd_fix_correlation.json, same pooled
# method, n=3,792; also the values in the C-and-D fixes sheet and in
# the 2026-11-16 chat). All other items are identical plain vs merged.
PASS_RATE = {c: sum(1 for r in elig if r["passes"][c]) / len(elig) for c in V3}
RAT = {"C1.1": "Strongest correlation; +1 from the redistribution (9 -> 10).",
       "C1.2": "Second-strongest correlation; +1 (9 -> 10).",
       "C1.3": "Weak correlation; reviews readable for almost no firm. Unchanged.",
       "C2.1": "Strong correlation; +1 (7 -> 8).",
       "C2.2": "Most common real-world failure; +1 (6 -> 7).",
       "C2.3": "Medium correlation. Unchanged.",
       "C2.4": "Near-zero, slightly inverse as a merged item (+0.008). Unchanged.",
       "C3.1": "Strong correlation; +1 (7 -> 8).",
       "C4.2": "Strong correlation; the biggest lever almost no firm passes; +1 (7 -> 8).",
       "C4.3": "Weak correlation. Unchanged.",
       "C4.4": "Weak correlation. Unchanged.",
       "C5.1": "Weak-medium correlation. Unchanged.",
       "C6.2": "Strong correlation; +1 (6 -> 7).",
       "G1": "Strong correlation (-0.107); +1 (6 -> 7).",
       "C7.1": "Near-zero correlation; a core 'can the agent read you' item. Unchanged.",
       "C7.2": "Near-zero correlation. Unchanged.",
       "C7.3": "Medium correlation. Unchanged.",
       "C7.4": "Weak correlation. Unchanged."}

ws = wb.active
ws.title = "Allocation v3"
ws["A1"] = "100-point allocation — v3 (16 Nov 2026, PROTOTYPE — NOT DECIDED)"
ws["A2"] = ("18 Grade items, total 100 points. C6.1 one unique primary phone "
            "number everywhere (3 points), G6 verifiable listing (3 points) and "
            "C5.2 hours consistency (2 points) moved to Placement Suggestions "
            "(see below) — they are anti-aligned with the Shopping Agent "
            "ranking (positive rho). Their 8 points were re-distributed across "
            "the remaining items, per item, proportionally to their v2 points "
            "(largest-remainder rounding): the 8 largest fractional parts "
            "gained +1. Total stays 100. Tim leans towards this removal "
            "(2026-11-16); no removal approved yet.")
ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
ws.row_dimensions[2].height = 45
hdr = ["Item", "Group", "Description", "Points v2", "Points v3",
       "Correlation (rho)", "% of eligible firms passing", "Rationale"]
ws.append([])
ws.append(hdr)
for c in ws[4]:
    c.font = Font(bold=True)
order = ["C1.1", "C1.2", "C1.3", "C2.1", "C2.2", "C2.3", "C2.4", "C3.1",
         "C4.2", "C4.3", "C4.4", "C5.1", "C6.2", "G1", "C7.1", "C7.2",
         "C7.3", "C7.4"]
for code in order:
    desc = ITEM_LABEL[code]
    if code == "C2.1":
        desc += " (absorbs G3 area coverage)"
    if code == "C2.2":
        desc += " (absorbs G2 services in plain words)"
    if code == "C2.4":
        desc += " (absorbs G4 contact, booking route)"
    if code == "C5.1":
        desc += " (absorbs G5 hours / Active Status, hours part)"
    if code == "C6.2":
        desc = "Founding year and business lineage consistent across sources"
    if code == "G1":
        desc = "Exact name (new Item from the Gates)"
    ws.append([code, GROUPS[code], desc, V2[code], V3[code],
               RHO[code], PASS_RATE[code], RAT[code]])
ws.append([None, None, "Total (Grade items)", 92, 100, None, None, None])
ws.append([])
ws.append(["Moved to Placement Suggestions (not scored)"])
for row in ws.iter_rows(min_row=ws.max_row, max_row=ws.max_row):
    for c in row:
        c.font = Font(bold=True)
REMOVED_DESC = {
    "C3.2": "BBB accreditation and rating consistent with bbb.org",
    "C4.1": "Six-line warranty card",
    "C6.1": "One unique primary phone number everywhere (absorbs G4 contact, phone part)",
    "G6": "Verifiable listing (new Item from the Gates)",
    "C5.2": "Hours, 24-hour, weekend, and emergency status consistent across sources",
}
REMOVED_NOTE = {
    "C3.2": "Passed by only 2 of 1,043 eligible firms (0.2%). Moved in v2.",
    "C4.1": "Passed by 0 of 1,043 eligible firms. Moved in v2.",
    "C6.1": "Anti-aligned (+0.111); passes for 62.9% of eligible firms. Moved in v3 (proposed).",
    "G6": "Anti-aligned (+0.106); passes for 58.3% of eligible firms. Moved in v3 (proposed).",
    "C5.2": "Anti-aligned (+0.076); passes for every eligible firm (100%) — free points. Moved in v3 (proposed).",
}
for code in ["C3.2", "C4.1", "C6.1", "G6", "C5.2"]:
    ws.append([code, None, REMOVED_DESC[code],
               V2.get(code, 0), 0, None, None, REMOVED_NOTE[code]])
for col, w in zip("ABCDEFGH", [8, 24, 62, 10, 10, 16, 22, 62]):
    ws.column_dimensions[col].width = w

ws2 = wb.create_sheet("Distribution")
ws2["A1"] = "Score distribution — 1,043 eligible firms (v3 vs v2)"
ws2.append([])
ws2.append(["Score band", "Firms (v3)", "% of eligible (v3)", "Firms (v2)"])
for c in ws2[3]:
    c.font = Font(bold=True)
d3, d2 = dist(v3_scores), dist(v2_scores)
for i, b in enumerate(range(0, 100, 10)):
    ws2.append([f"{b}-{b+9}", d3[i], d3[i] / len(elig), d2[i]])
ws2.append([])
ws2.append([f"Summary v3: min {min(v3_scores)}, median {statistics.median(v3_scores):.0f}, "
            f"mean {statistics.mean(v3_scores):.1f}, max {max(v3_scores)}. "
            f"Summary v2: min {min(v2_scores)}, median {statistics.median(v2_scores):.0f}, "
            f"mean {statistics.mean(v2_scores):.1f}, max {max(v2_scores)}. "
            f"Mean score change v2 -> v3: {statistics.mean(changes):+.1f} "
            f"(range {min(changes):+d} to {max(changes):+d}; "
            f"{sum(1 for c in changes if c == 0)} firms unchanged)."])
ws2.append([])
b3, b2 = bands(v3_scores), bands(v2_scores)
ws2.append(["Grade bands (proposed v2 bands: A 65+, B 50-64, C 30-49, D below 30) — eligible firms only"])
ws2.append(["Grade", "Firms (v3)", "% of eligible (v3)", "Firms (v2)"])
for g in "ABCD":
    ws2.append([g, b3[g], b3[g] / len(elig), b2[g]])
ws2.append([f"Over all 1,429 firms (F separate): v3 A {b3['A']}, B {b3['B']}, "
            f"C {b3['C']}, D {b3['D']}, F {len(f_firms)}. "
            f"v2 was A 64, B 146, C 349, D 484, F 386."])
for col, w in zip("ABCD", [42, 12, 18, 12]):
    ws2.column_dimensions[col].width = w

ws3 = wb.create_sheet("Firm scores")
ws3["A1"] = ("Eligible firms scored (1,043), highest first — v3 score with "
             "v2 for comparison (PROTOTYPE — NOT DECIDED)")
ws3.append([])
ws3.append(["Firm", "Town", "Score v3 /100", "Score v2 /100", "Change",
            "G6 verifiable listing passes?"])
for c in ws3[3]:
    c.font = Font(bold=True)
for r in sorted(elig, key=lambda x: (-x["v3"], x["name"])):
    ws3.append([r["name"], r["town"], r["v3"], r["v2"], r["v3"] - r["v2"],
                "Yes" if r["g6_pass"] else "No"])
ws3.column_dimensions["A"].width = 55
ws3.column_dimensions["B"].width = 20

ws4 = wb.create_sheet("F firms")
ws4["A1"] = "New F firms (386) — firm-side only (unchanged from v2)"
ws4["A2"] = ("F = no website (375) OR closed flag / not in business (3) OR "
             "website genuinely unreachable, firm-side, verified (9). One firm "
             "has two reasons (no website + closed flag).")
ws4.append([])
ws4.append(["Firm", "Town", "F reason(s)"])
for c in ws4[4]:
    c.font = Font(bold=True)
for r in sorted(f_firms, key=lambda x: x["name"]):
    ws4.append([r["name"], r["town"], r["f_reason"]])
ws4.column_dimensions["A"].width = 55
ws4.column_dimensions["B"].width = 20

wb.save(OUT_XLSX)
print("saved", OUT_XLSX)
