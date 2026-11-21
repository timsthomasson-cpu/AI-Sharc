#!/usr/bin/env python3
"""Top fixes for C- and D-grade firms under the 100-point v2 grading.

Rebuilds the v2 scores from the audit DB (corrected audits: the 2026-11-15
re-audit where one exists, else the 2026-11-14 study audit), applies the
new F rule and the v2 bands (A>=65, B 50-64, C 30-49, D<30), then for the
C and D firms reports, per Grade item: % failing (within C, within D,
within C+D), the points the fix is worth, the expected point gain
(points x % failing among C+D), and how many firms would move up one
grade by fixing that single item alone (C->B needs >=50, D->C needs >=30).

Saved here (not /tmp) because /tmp is cleared between turns.
"""
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict

HERE = __file__.rsplit("/", 1)[0]
DB = HERE + "/../aisharc-audit-db/aisharc-audit.sqlite"
ROWS = HERE + "/runs/2026-11-15-reaudit-55/correlation-rows.json"

# v2 allocation (21 Grade items; C3.2 and C4.1 are Placement Suggestions now)
ALLOC_V2 = {
    "C1.1": 9, "C1.2": 9, "C1.3": 4,
    "C2.1": 7, "C2.2": 6, "C2.3": 4, "C2.4": 3,
    "C3.1": 7, "G6": 3,
    "C4.2": 7, "C4.3": 3, "C4.4": 3,
    "C5.1": 5, "C5.2": 2,
    "C6.1": 3, "C6.2": 6, "G1": 6,
    "C7.1": 3, "C7.2": 3, "C7.3": 5, "C7.4": 2,
}
DESC = {
    "C1.1": "rating and review count readable",
    "C1.2": "rating figures consistent across sources",
    "C1.3": "no recurring unaddressed complaint pattern",
    "C2.1": "service-area page naming town and ZIP",
    "C2.2": "install and repair listed separately on that page",
    "C2.3": "brands and system types served",
    "C2.4": "unique primary phone and booking route on that page",
    "C3.1": "licence published",
    "G6": "verifiable listing",
    "C4.2": "diagnostic fee in dollars",
    "C4.3": "free-estimate status for install",
    "C4.4": "free-estimate status for repair",
    "C5.1": "day-by-day hours readable",
    "C5.2": "hours consistency",
    "C6.1": "one unique primary phone number everywhere",
    "C6.2": "founding year and business lineage consistent",
    "G1": "exact name",
    "C7.1": "AI crawler access (M1)",
    "C7.2": "key facts readable without JavaScript (M2)",
    "C7.3": "LocalBusiness structured data (M4)",
    "C7.4": "sitemap (M5)",
}
# Merged-item pass rule: merged item passes only if BOTH the Item and the
# absorbed Gate pass. G1/G6 items are their Gate results.
# DECIDED 2026-11-16 (Tim): C2.2 install and repair listed separately on
# that page is service-page only — the G2 services in plain words listings
# requirement is dropped, so C2.2 is NOT a merged item; it passes on the
# Item (service page) alone. C2.1, C2.4, C6.1, C5.1 stay merged as before.
MERGE = {"C2.1": "G3", "C2.4": "G4", "C6.1": "G4", "C5.1": "G5"}
GATE_ITEMS = {"G1", "G6"}
# The 9 firms verified genuinely unreachable, firm-side (55-firm check).
UNREACHABLE_9 = {585, 700, 591, 787, 319, 184, 284, 970, 127}

ITEM_KEYWORDS = [
    ("C1.1", "rating and review count readable"),
    ("C1.2", "rating figures consistent"),
    ("C1.3", "no recurring unaddressed complaint pattern"),
    ("C2.1", "service-area page naming"),
    ("C2.2", "install and repair listed separately"),
    ("C2.3", "brands and system types served"),
    ("C2.4", "unique primary phone and booking route"),
    ("C3.1", "single consistent applicable state licence"),
    ("C3.2", "bbb accreditation"),
    ("C4.1", "six-line warranty card"),
    ("C4.2", "diagnostic fee in dollars"),
    ("C4.3", "free-estimate status for install"),
    ("C4.4", "free-estimate status for repair"),
    ("C5.1", "day-by-day hours readable"),
    ("C5.2", "hours, 24-hour, weekend, and emergency status consistent"),
    ("C6.1", "one unique primary phone number everywhere"),
    ("C6.2", "founding year and business lineage consistent"),
    ("C7.1", "ai crawler access"),
    ("C7.2", "key facts readable without javascript"),
    ("C7.3", "localbusiness structured data"),
    ("C7.4", "sitemap"),
]


def norm(s):
    return re.sub(r"\s+", " ",
                  re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()
                         .replace("&", " and "))).strip()


def item_code(name):
    n = norm(name)
    for code, kw in ITEM_KEYWORDS:
        if norm(kw) in n:
            return code
    return None


def gate_code(cat):
    n = norm(cat)
    if "exact name" in n:
        return "G1"
    if "services in plain" in n:
        return "G2"
    if "area coverage" in n:
        return "G3"
    if "contact" in n:
        return "G4"
    if "hours" in n:
        return "G5"
    if "verifiable listing" in n:
        return "G6"
    return None


def is_pass(result):
    return result in ("Pass", "Pass with warning")


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    with open(ROWS, encoding="utf-8") as fh:
        corr = json.load(fh)
    firm_audit = {}
    for r in corr:
        firm_audit.setdefault(r["db_id"], r["audit_id"])
    print(f"correlation population: {len(firm_audit)} firms")

    firms = {}   # db_id -> {score, band, fails: set of grade-item codes}
    f_count = 0
    for db_id, audit_id in firm_audit.items():
        f = con.execute("select website_url from firms where firm_id=?",
                        (db_id,)).fetchone()
        website = (f["website_url"] or "").strip() if f else ""
        rows = con.execute(
            "select row_type, category_or_gate, item, result, evidence_note "
            "from audit_rows where audit_id=?", (audit_id,)).fetchall()
        items = {}
        gates = {}
        for r in rows:
            if r["row_type"] == "Item":
                c = item_code(r["item"])
                if c:
                    items[c] = (r["result"], r["evidence_note"])
            elif r["row_type"] == "Gate":
                c = gate_code(r["category_or_gate"])
                if c:
                    gates[c] = (r["result"], r["evidence_note"] or "")
        # New F rule: no website, closed flag, or verified firm-side unreachable.
        g5_note = gates.get("G5", ("", ""))[1]
        is_f = (not website) or ("Closed flag present" in g5_note) \
            or (db_id in UNREACHABLE_9)
        if is_f:
            f_count += 1
            continue
        # Merged-item pass / fail.
        passed = {}
        for code in ALLOC_V2:
            if code in GATE_ITEMS:
                passed[code] = gates.get(code, ("", ""))[0] == "Pass"
            elif code in MERGE:
                g = MERGE[code]
                passed[code] = is_pass(items.get(code, ("", ""))[0]) \
                    and gates.get(g, ("", ""))[0] == "Pass"
            else:
                passed[code] = is_pass(items.get(code, ("", ""))[0])
        score = sum(ALLOC_V2[c] for c, ok in passed.items() if ok)
        band = "A" if score >= 65 else "B" if score >= 50 \
            else "C" if score >= 30 else "D"
        firms[db_id] = {"score": score, "band": band,
                        "fails": {c for c, ok in passed.items() if not ok}}
    bands = Counter(v["band"] for v in firms.values())
    scores = sorted(v["score"] for v in firms.values())
    n = len(scores)
    mean = sum(scores) / n
    med = scores[n // 2]
    print(f"F: {f_count} | eligible: {n} | bands A {bands['A']} B {bands['B']} "
          f"C {bands['C']} D {bands['D']} | median {med} mean {mean:.1f} "
          f"max {max(scores)}")
    # Distribution after the 2026-11-16 C2.2 rule change (service-page
    # only; the G2 listings requirement dropped). Was A 64 / B 146 /
    # C 349 / D 484 before the change; C2.2 passes for more firms now,
    # so the mean rose 32.9 -> 35.3 and A/B grew. The proposed bands
    # (A 65+, B 50-64, C 30-49, D below 30) no longer hit Tim's targets
    # (A 5%, B 10%, C 25%, D 33%) — they now give A 6.9%, B 12.1%,
    # C 23.9%, D 30.1% — and need recalibrating if the targets stand.
    assert f_count == 386 and n == 1043 and bands["A"] == 98 \
        and bands["B"] == 173 and bands["C"] == 342 and bands["D"] == 430, \
        "v2 rebuild does not match the reported distribution!"

    c_firms = [v for v in firms.values() if v["band"] == "C"]
    d_firms = [v for v in firms.values() if v["band"] == "D"]
    cd = c_firms + d_firms
    print(f"C firms: {len(c_firms)} | D firms: {len(d_firms)} | C+D: {len(cd)}")
    print()
    print("rank | item | pts | %C fail | %D fail | %C+D fail | "
          "expected pts | firms moving up on this fix alone (C->B / D->C)")
    table = []
    for code, pts in ALLOC_V2.items():
        fc = sum(1 for v in c_firms if code in v["fails"])
        fd = sum(1 for v in d_firms if code in v["fails"])
        fcd = fc + fd
        pc = 100 * fc / len(c_firms)
        pd = 100 * fd / len(d_firms)
        pcd = 100 * fcd / len(cd)
        exp_pts = pts * pcd / 100
        # Single-fix grade movers.
        mc = sum(1 for v in c_firms
                 if code in v["fails"] and v["score"] + pts >= 50)
        md = sum(1 for v in d_firms
                 if code in v["fails"] and v["score"] + pts >= 30)
        table.append({"code": code, "desc": DESC[code], "pts": pts,
                      "fail_c": fc, "fail_d": fd, "fail_cd": fcd,
                      "pct_c": pc, "pct_d": pd, "pct_cd": pcd,
                      "exp_pts": exp_pts, "move_c": mc, "move_d": md})
    table.sort(key=lambda t: (-t["exp_pts"], -t["pct_cd"]))
    for i, t in enumerate(table, 1):
        print(f"{i:>2} | {t['code']} {t['desc']} | {t['pts']} | "
              f"{t['pct_c']:.1f}% ({t['fail_c']}) | {t['pct_d']:.1f}% ({t['fail_d']}) | "
              f"{t['pct_cd']:.1f}% ({t['fail_cd']}) | {t['exp_pts']:.2f} | "
              f"{t['move_c']} / {t['move_d']}")
    with open(HERE + "/cd_fix_analysis.json", "w", encoding="utf-8") as fh:
        json.dump({"bands": dict(bands), "f": f_count, "n_eligible": n,
                   "table": table}, fh, indent=1)
    print()
    print("saved cd_fix_analysis.json")


if __name__ == "__main__":
    main()
