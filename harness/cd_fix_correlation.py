#!/usr/bin/env python3
"""Spearman correlation of each merged Grade item with the Shopping Agent
ranking position, using the same pooled method as compute_correlation.py:
one (pass/fail, mean_pos) pair per observation row (3,792 rows), where
pass/fail is the merged Grade item in the firm's corrected audit.

Also recomputes the plain Item rhos as a check against the corrected
correlation.json values (C1.1 -0.219, C1.2 -0.199, ...).
"""
import json
import re
import sqlite3
from collections import defaultdict

try:
    from scipy.stats import spearmanr
except ImportError:
    spearmanr = None

HERE = __file__.rsplit("/", 1)[0]
DB = HERE + "/../aisharc-audit-db/aisharc-audit.sqlite"
ROWS = HERE + "/runs/2026-11-15-reaudit-55/correlation-rows.json"
CORR = HERE + "/runs/2026-11-15-reaudit-55/correlation.json"

MERGE = {"C2.1": "G3", "C2.4": "G4", "C6.1": "G4", "C5.1": "G5"}  # C2.2 removed 2026-11-16 (Tim): service-page only, no G2 listings requirement
GATE_ITEMS = {"G1", "G6"}
ALLOC_V2 = {
    "C1.1": 9, "C1.2": 9, "C1.3": 4,
    "C2.1": 7, "C2.2": 6, "C2.3": 4, "C2.4": 3,
    "C3.1": 7, "G6": 3,
    "C4.2": 7, "C4.3": 3, "C4.4": 3,
    "C5.1": 5, "C5.2": 2,
    "C6.1": 3, "C6.2": 6, "G1": 6,
    "C7.1": 3, "C7.2": 3, "C7.3": 5, "C7.4": 2,
}
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


def spearman(xs, ys):
    if spearmanr is None:
        raise RuntimeError("scipy not available")
    r = spearmanr(xs, ys)
    rho = float(r.statistic) if r.statistic == r.statistic else None
    p = float(r.pvalue) if r.pvalue == r.pvalue else None
    return rho, p, len(xs)


def main():
    con = sqlite3.connect(DB)
    with open(ROWS, encoding="utf-8") as fh:
        obs = json.load(fh)
    print(f"observation rows: {len(obs)}")

    # audit_id -> item pass / gate pass, for the audits in the rows.
    audit_ids = sorted({r["audit_id"] for r in obs})
    audit_items = defaultdict(dict)
    audit_gates = defaultdict(dict)
    for aid in audit_ids:
        for rtype, cat, item, res in con.execute(
                "select row_type, category_or_gate, item, result "
                "from audit_rows where audit_id=?", (aid,)):
            if rtype == "Item":
                c = item_code(item)
                if c:
                    audit_items[aid][c] = is_pass(res)
            elif rtype == "Gate":
                c = gate_code(cat)
                if c:
                    audit_gates[aid][c] = (res == "Pass")
    print(f"audits covered: {len(audit_ids)}")

    # Merged Grade-item pass per audit.
    merged = defaultdict(dict)
    for aid in audit_ids:
        items = audit_items[aid]
        gates = audit_gates[aid]
        for code in ALLOC_V2:
            if code in GATE_ITEMS:
                merged[aid][code] = gates.get(code, False)
            elif code in MERGE:
                merged[aid][code] = items.get(code, False) \
                    and gates.get(MERGE[code], False)
            else:
                merged[aid][code] = items.get(code, False)

    # Check: plain Item rhos against the corrected correlation.json.
    with open(CORR, encoding="utf-8") as fh:
        corr = json.load(fh)
    print("\nplain-Item check (computed vs corrected correlation.json):")
    bad = 0
    for code, _ in ITEM_KEYWORDS:
        xs, ys = [], []
        for r in obs:
            v = audit_items[r["audit_id"]].get(code)
            if v is None:
                continue
            xs.append(1 if v else 0)
            ys.append(r["mean_pos"])
        rho, p, n = spearman(xs, ys)
        ref = corr["per_item"][code]["rho"]
        ok = (rho is None and ref is None) or (
            rho is not None and ref is not None and abs(rho - ref) < 0.001)
        if not ok:
            bad += 1
        print(f"  {code}: computed {rho} vs ref {ref} {'OK' if ok else 'MISMATCH'}")
    print(f"plain-Item mismatches: {bad}")

    # Merged Grade-item rhos.
    print("\nmerged Grade-item rhos (Spearman, pass=1 vs mean position):")
    out = {}
    for code in ALLOC_V2:
        xs, ys = [], []
        for r in obs:
            v = merged[r["audit_id"]].get(code)
            if v is None:
                continue
            xs.append(1 if v else 0)
            ys.append(r["mean_pos"])
        rho, p, n = spearman(xs, ys)
        out[code] = {"rho": rho, "p": p, "n": n}
        print(f"  {code}: rho {rho:+.3f}  p {p:.2g}  n {n}")
    with open(HERE + "/cd_fix_correlation.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("\nsaved cd_fix_correlation.json")


if __name__ == "__main__":
    main()
