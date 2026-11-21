#!/usr/bin/env python3
"""Texas HVAC correlation study — correlation computation (Stage 2c).

Reads the audit DB (Spec v1.22, 40 rows per audit) and the 600 agent-run
metadata files, and computes the correlation between the AI Sharc audit
grade/points and the firm's position in the MUSE-SPARK answer's list.

Measures (plan §1):
- Spearman rank correlation between category points (and grade rank) and
  agent position, per town, per task, and pooled statewide. Not observed
  is treated as below every named firm (position = n_named + 1 in that
  repeat; the per-task position is the mean across the 2 repeats).
- Share of agent-named firms eligible (0 Critical) vs F.
- Mean category points of named vs not-named firms.
- The same correlation per Item (all 21 Items, plus Gates and Categories),
  pooled — Item result is Pass=1 / Fail=0 from the core audit.

Positions are the FULL-list positions as the agent gave them (including
non-cohort firms occupying positions). A firm's grade is from its single
study audit (2026-11-14); if a firm has more than one study audit, the
audit for the run's town is used, else its first study audit.

With --corrections-date DATE, a re-audit dated DATE replaces the study audit for any firm that has one (same firm/query/town): the corrections-date audit is preferred for that firm, and all other firms keep their study audit. The original correlation.json is never overwritten by a corrections run — pass --out for the corrected output.

The observation-scoring pass for the additions is NOT an input here: the
correlation uses audit grades/points and agent positions only. The
per-Item correlation uses the AUDIT Item results, not the observation
scores.

Usage:
  python3 compute_correlation.py [--db PATH] [--runs ROOT] [--out FILE]
  python3 compute_correlation.py --corrections-date 2026-11-15 --out runs/2026-11-15-reaudit-55/correlation.json
Writes the computed numbers as JSON to --out (default:
runs/2026-11-14-study/correlation.json) and prints a summary.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from scipy.stats import spearmanr

DB = os.path.join(HERE, "..", "aisharc-audit-db", "aisharc-audit.sqlite")
RUNS_ROOT = os.path.join(HERE, "runs", "2026-11-14-study", "agent")
STUDY_FIRMS = os.path.join(HERE, "study-firms.json")
ADDITIONS_FIRMS = os.path.join(HERE, "study-additions-firms.json")
ABILENE9_FIRMS = os.path.join(HERE, "study-additions-firms-abilene-9.json")
RUN_DATE = "2026-11-14"

GRADE_RANK = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}

# Item code <- distinctive keyword in the audit_rows item name (normalized).
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
ITEM_CATEGORIES = {
    "C1.1": 1, "C1.2": 1, "C1.3": 1,
    "C2.1": 2, "C2.2": 2, "C2.3": 2, "C2.4": 2,
    "C3.1": 3, "C3.2": 3,
    "C4.1": 4, "C4.2": 4, "C4.3": 4, "C4.4": 4,
    "C5.1": 5, "C5.2": 5,
    "C6.1": 6, "C6.2": 6,
    "C7.1": 7, "C7.2": 7, "C7.3": 7, "C7.4": 7,
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ",
                  re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()
                         .replace("&", " and "))).strip()


def item_code(item_name: str) -> str | None:
    n = norm(item_name)
    for code, kw in ITEM_KEYWORDS:
        if norm(kw) in n:
            return code
    return None


def gate_code(cat: str) -> str | None:
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


def cat_num(cat: str) -> int | None:
    m = re.match(r"(\d)\.", cat.strip())
    if m:
        return int(m.group(1))
    names = {"reputation": 1, "area coverage": 2, "credentials and trust": 3,
             "pricing and warranty": 4, "hours and active status": 5,
             "identity and contact": 6, "machine readability": 7}
    return names.get(norm(cat))


def is_pass(result: str) -> bool:
    return result in ("Pass", "Pass with warning")


def spearman(xs, ys):
    """Spearman rho + two-sided p; None when undefined (constant input)."""
    if len(xs) < 3:
        return None, None, len(xs)
    try:
        r = spearmanr(xs, ys)
    except Exception:
        return None, None, len(xs)
    rho = float(r.statistic) if r.statistic == r.statistic else None
    p = float(r.pvalue) if r.pvalue == r.pvalue else None
    return rho, p, len(xs)


def main() -> None:
    ap = argparse.ArgumentParser(description="Texas HVAC correlation study")
    ap.add_argument("--db", default=DB)
    ap.add_argument("--runs", default=RUNS_ROOT)
    ap.add_argument("--out", default=os.path.join(
        HERE, "runs", "2026-11-14-study", "correlation.json"))
    ap.add_argument("--dump-rows", default=None,
                    help="Optional path to write the per-(town, task, firm) "
                         "rows (points, mean position) as JSON, for "
                         "verification.")
    ap.add_argument("--corrections-date", default=None,
                    help="Optional re-audit date (e.g. 2026-11-15). A "
                         "re-audit dated this replaces the study audit for "
                         "any firm that has one; all other firms keep "
                         "their study audit.")
    args = ap.parse_args()
    CORR_DATE = args.corrections_date
    audit_dates = (RUN_DATE, CORR_DATE) if CORR_DATE else (RUN_DATE,)
    date_placeholders = ",".join("?" for _ in audit_dates)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    # ---- Audits (study date only) -------------------------------------
    # audit_summary view layout (verified): audit_id, firm (name), query,
    # town_zip, date_checked, spec_version, is_sample, critical_issues,
    # high_issues, passed_items, category_points, grade, eligible_rank,
    # eligible_count, top_percent. Join the audits table for the integer
    # firm_id; the view's firm column is the name, not the id.
    audits = {}
    for row in conn.execute(
            "SELECT a.audit_id, a.firm_id, a.town_zip, s.critical_issues, "
            "s.high_issues, s.passed_items, s.category_points, s.grade, "
            "a.date_checked "
            "FROM audits a JOIN audit_summary s ON s.audit_id = a.audit_id "
            "WHERE a.date_checked IN (%s)" % date_placeholders,
            audit_dates):
        r = tuple(row)
        audits[r[0]] = {
            "firm_db_id": r[1], "town_zip": r[2],
            "critical": r[3], "high": r[4], "passed": r[5],
            "points": r[6], "grade": r[7], "date_checked": r[8],
        }
    firms_db = {r[0]: r[1] for r in conn.execute(
        "SELECT firm_id, name FROM firms")}
    name_to_db = {}
    for fid, name in firms_db.items():
        name_to_db.setdefault(norm(name), []).append(fid)

    # Per-audit Item / Gate / Category results (row_type distinguishes).
    audit_items = defaultdict(dict)   # audit_id -> {code: bool}
    audit_gates = defaultdict(dict)   # audit_id -> {G1..G6: bool}
    audit_cats = defaultdict(dict)    # audit_id -> {1..7: bool}
    for audit_id, row_type, cat, item, result in conn.execute(
            "SELECT audit_id, row_type, category_or_gate, item, result "
            "FROM audit_rows WHERE audit_id IN "
            "(SELECT audit_id FROM audits WHERE date_checked IN (%s))"
            % date_placeholders,
            audit_dates):
        if row_type == "Item":
            code = item_code(item)
            if code:
                audit_items[audit_id][code] = is_pass(result)
        elif row_type == "Gate":
            code = gate_code(cat)
            if code:
                audit_gates[audit_id][code] = (result == "Pass")
        elif row_type == "Category result":
            n = cat_num(cat)
            if n:
                audit_cats[audit_id][n] = (result == "Pass")

    # Firm (DB id) -> its study audits, keyed by town.
    firm_audits = defaultdict(list)
    for aid, a in audits.items():
        firm_audits[a["firm_db_id"]].append((aid, a))

    def audit_for(firm_db_id, town):
        """The study audit for this firm in this town, else its first.
        With --corrections-date, the re-audit dated that day is preferred
        for the firm (same town first, then any town)."""
        cands = firm_audits.get(firm_db_id, [])
        if not cands:
            return None
        town_norm = norm(town)
        if CORR_DATE:
            for aid, a in cands:
                if a.get("date_checked") == CORR_DATE and \
                        norm(a["town_zip"].split(",")[0]) == town_norm:
                    return (aid, a)
            for aid, a in cands:
                if a.get("date_checked") == CORR_DATE:
                    return (aid, a)
        for aid, a in cands:
            if norm(a["town_zip"].split(",")[0]) == town_norm:
                return (aid, a)
        return cands[0]

    # ---- Firm registries (slug -> name, town) --------------------------
    with open(STUDY_FIRMS, encoding="utf-8") as fh:
        cohort = json.load(fh)["firms"]
    with open(ADDITIONS_FIRMS, encoding="utf-8") as fh:
        additions = json.load(fh)["firms"]
    # The 9 Abilene additions were audited with the first (cohort) run
    # and are NOT in the merged 615 additions file (preserved
    # separately); they were named by the agent in Abilene runs with
    # list positions, so they belong in the registry. They are not
    # cohort firms, so they do not join cohort_by_town.
    with open(ABILENE9_FIRMS, encoding="utf-8") as fh:
        abilene9 = json.load(fh)["firms"]

    slug_to_db = {}
    for f in cohort + additions + abilene9:
        hits = name_to_db.get(norm(f["name"]), [])
        if len(hits) == 1:
            slug_to_db[f["firm_id"]] = hits[0]
        elif len(hits) > 1:
            # Same name, several DB firms: prefer the one whose audit town
            # matches the firm's town.
            town_norm = norm(f["town"])
            pick = None
            for h in hits:
                for aid, a in firm_audits.get(h, []):
                    if norm(a["town_zip"].split(",")[0]) == town_norm:
                        pick = h
                        break
                if pick is not None:
                    break
            slug_to_db[f["firm_id"]] = pick if pick is not None else hits[0]
    cohort_by_town = defaultdict(list)
    for f in cohort:
        cohort_by_town[f["town"]].append(f["firm_id"])
    # Name index for matching agent-named (non-cohort) firms to a
    # registry firm: the agent's wording often differs slightly (a
    # dropped word, a branch suffix, a parenthetical). Match exactly
    # first, then by a word-boundary prefix in either direction — but
    # only when the match resolves to a single DB firm, so a short name
    # never claims the wrong firm. Returns (slug, db_id) or (None, None).
    registry_names = []  # (norm_name, slug)
    for f in cohort + additions + abilene9:
        registry_names.append((norm(f["name"]), f["firm_id"]))

    def match_registry(agent_name: str):
        n = norm(agent_name)
        if not n:
            return None, None

        def resolve(slugs):
            dbs = {slug_to_db[s] for s in slugs if s in slug_to_db}
            return next(iter(dbs)) if len(dbs) == 1 else None

        exact = [s for (rn, s) in registry_names if rn == n]
        if exact:
            db = resolve(exact)
            return (exact[0], db) if db is not None else (None, None)
        cands = set()
        for rn, s in registry_names:
            if rn.startswith(n + " ") or n.startswith(rn + " "):
                cands.add(s)
        if cands:
            db = resolve(sorted(cands))
            if db is not None:
                return sorted(cands)[0], db
        return None, None

    # ---- Agent runs ------------------------------------------------------
    # Firm identity key throughout: the integer DB firm id for any firm
    # with an audit; ("no-audit", norm_name) for a named firm with none.
    # (One key per firm, so a firm named via the cohort list in one
    # repeat and via the non-cohort list in another is not double-counted.)
    runs = []  # (town, task_id, repeat, {key: position}, max_pos)
    unaudited_named = defaultdict(int)  # name -> namings with no audit
    run_files = []
    for town_dir in sorted(os.listdir(args.runs)):
        tdir = os.path.join(args.runs, town_dir)
        if not os.path.isdir(tdir):
            continue
        for task_dir in sorted(os.listdir(tdir)):
            for rep in sorted(os.listdir(os.path.join(tdir, task_dir))):
                p = os.path.join(tdir, task_dir, rep,
                                 "muse-spark-observation.json")
                if os.path.exists(p):
                    run_files.append(p)
    for p in run_files:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        town = d["town"]
        task_id = d["task_id"]
        repeat = int(d["repeat"])
        pos = {}
        for e in d.get("firms_named", []):
            db = slug_to_db.get(e["firm_id"])
            key = db if db is not None else (
                "no-audit", norm(e["name"]))
            if db is None:
                unaudited_named[e["name"]] += 1
            try:
                pval = int(e["position"])
            except (TypeError, ValueError):
                pval = None
            pos[key] = pval
        for e in d.get("firms_named_not_in_cohort", []):
            # Match against the additions AND the cohort by name: the
            # agent worker's short-name match sometimes missed a cohort
            # firm (e.g. named in another town's run, or with a dropped
            # word), so it lands here even though it has an audit.
            slug, db = match_registry(e["name"])
            if db is None:
                unaudited_named[e["name"]] += 1
                key = ("no-audit", norm(e["name"]))
            else:
                key = db
            try:
                pval = int(e["position"])
            except (TypeError, ValueError):
                pval = None
            pos[key] = pval
        # Positions of None (named in prose, no list position) are kept
        # as None and excluded from the position mean for that repeat
        # (unknown position, not "below"). Not named at all in a run is
        # a different case: below every named firm (max list position + 1).
        max_pos = 0
        for v in pos.values():
            if v is not None and v > max_pos:
                max_pos = v
        runs.append((town, task_id, repeat, pos, max_pos))

    # ---- Per (town, task) firm sets and mean positions -------------------
    # firm key -> audit (grade/points) + mean position per (town, task)
    # Candidate firms per (town, task): the town's cohort firms plus
    # every firm named in EITHER repeat of that (town, task). The union
    # is taken across repeats so a firm named in one repeat is also a
    # candidate in the other (where it is NOT_NAMED and gets max+1),
    # rather than being silently dropped from that repeat's mean.
    task_cands = defaultdict(set)
    for town, task_id, repeat, pos, max_pos in runs:
        for fid in cohort_by_town.get(town, []):
            db = slug_to_db.get(fid)
            if db is not None:
                task_cands[(town, task_id)].add(db)
        for key in pos:
            task_cands[(town, task_id)].add(key)
    town_tasks = defaultdict(lambda: defaultdict(dict))
    # (town, task) -> {firm_key: [pos_r1, pos_r2]} with None for un-named
    for town, task_id, repeat, pos, max_pos in runs:
        tt = town_tasks[(town, task_id)]
        for key in task_cands[(town, task_id)]:
            # "NOT_NAMED" = not named in this run at all (below every
            # named firm). None = named in prose, no list position
            # (unknown position — excluded from the mean, not penalised).
            tt.setdefault(key, {})[repeat] = (
                pos[key] if key in pos else "NOT_NAMED")
        tt.setdefault("__max_pos__", {})[repeat] = max_pos

    def mean_position(rep_pos, max_pos):
        vals = []
        named_any = False
        for rep in (1, 2):
            v = rep_pos.get(rep)
            if v == "NOT_NAMED":
                vals.append(max_pos.get(rep, 0) + 1)
            elif v is None:
                continue  # named in prose: position unknown, skip repeat
            else:
                vals.append(v)
                named_any = True
        if not vals:
            return None, named_any
        return sum(vals) / len(vals), named_any

    obs = []  # (town, task, firm_key, db_id, points, grade_rank, mean_pos)
    per_town_task = {}
    for (town, task_id), tt in sorted(town_tasks.items()):
        max_pos = tt.pop("__max_pos__")
        rows = []
        for key, rep_pos in tt.items():
            if not isinstance(key, int):
                continue  # named but no audit (hallucination/fragment)
            db = key
            got = audit_for(db, town)
            if got is None:
                continue
            aid, a = got
            mp, named_any = mean_position(rep_pos, max_pos)
            if mp is None:
                continue  # named in prose in both repeats: no position
            rows.append({
                "firm_key": key, "db_id": db, "audit_id": aid,
                "points": a["points"], "grade": a["grade"],
                "grade_rank": GRADE_RANK.get(a["grade"], 0),
                "critical": a["critical"], "mean_pos": mp,
                "named_any": named_any,
                "town": town, "task": task_id,
            })
        per_town_task[(town, task_id)] = rows
        obs.extend(rows)

    # ---- Correlations ------------------------------------------------------
    def corr(rows, xkey, ykey="mean_pos"):
        xs = [r[xkey] for r in rows]
        ys = [r[ykey] for r in rows]
        rho, p, n = spearman(xs, ys)
        return {"rho": rho, "p": p, "n": n}

    out = {
        "run_date": RUN_DATE,
        "corrections_date": CORR_DATE,
        "runs_read": len(runs),
        "firms_with_audit_in_analysis": len({r["db_id"] for r in obs}),
        "observations_town_task_firm": len(obs),
        "unaudited_named_firms": {k: v for k, v in
                                   sorted(unaudited_named.items(),
                                          key=lambda kv: -kv[1])[:50]},
        "unaudited_named_total": sum(unaudited_named.values()),
        "pooled": {},
        "per_task": {},
        "per_town_task": {},
        "per_town_summary": {},
        "named_vs_not": {},
        "per_item": {},
        "per_gate": {},
        "per_category": {},
    }

    out["pooled"]["points"] = corr(obs, "points")
    out["pooled"]["grade_rank"] = corr(obs, "grade_rank")
    for task_id in ("task1", "task2", "task3"):
        sub = [r for r in obs if r["task"] == task_id]
        out["per_task"][task_id] = {
            "points": corr(sub, "points"),
            "grade_rank": corr(sub, "grade_rank"),
        }

    # Per (town, task) correlations (only where n>=5 and variance exists).
    town_rhos = []
    for (town, task_id), rows in sorted(per_town_task.items()):
        c = corr(rows, "points")
        out["per_town_task"][f"{town} / {task_id}"] = {
            "points": c, "grade_rank": corr(rows, "grade_rank"),
            "n_firms": len(rows),
            "n_named": sum(1 for r in rows if r["named_any"]),
        }
        if c["rho"] is not None:
            town_rhos.append(c["rho"])
    if town_rhos:
        import statistics as st
        out["per_town_summary"] = {
            "n_town_tasks_with_rho": len(town_rhos),
            "median_rho_points": st.median(town_rhos),
            "mean_rho_points": st.mean(town_rhos),
            "frac_negative": sum(1 for x in town_rhos if x < 0) / len(town_rhos),
            "frac_positive": sum(1 for x in town_rhos if x > 0) / len(town_rhos),
        }

    # Named vs not-named (distinct firms with an audit), from the run
    # files directly: a firm counts as named if it appears with a
    # position in any run.
    named_keys = set()
    for town, task_id, repeat, pos, max_pos in runs:
        for key, v in pos.items():
            if isinstance(key, int):
                named_keys.add(key)
    all_audited = {a["firm_db_id"] for a in audits.values()}
    never_ids = all_audited - named_keys
    named_ids = named_keys & all_audited
    def points_of(db_id):
        got = audit_for(db_id, "")
        return got[1]["points"] if got else None
    def eligible_of(db_id):
        got = audit_for(db_id, "")
        return (got[1]["critical"] == 0) if got else None
    named_pts = [points_of(i) for i in named_ids]
    never_pts = [points_of(i) for i in never_ids]
    named_pts = [p for p in named_pts if p is not None]
    never_pts = [p for p in never_pts if p is not None]
    import statistics as st
    out["named_vs_not"] = {
        "n_named_distinct": len(named_ids),
        "n_never_named_distinct": len(never_ids),
        "mean_points_named": st.mean(named_pts) if named_pts else None,
        "mean_points_never_named": st.mean(never_pts) if never_pts else None,
        "median_points_named": st.median(named_pts) if named_pts else None,
        "median_points_never_named": st.median(never_pts) if never_pts else None,
        "eligible_share_named": (
            sum(1 for i in named_ids if eligible_of(i)) / len(named_ids)
            if named_ids else None),
        "eligible_share_never_named": (
            sum(1 for i in never_ids if eligible_of(i)) / len(never_ids)
            if never_ids else None),
        "grade_dist_named": {g: sum(1 for i in named_ids
                                     if audit_for(i, "")[1]["grade"] == g)
                             for g in ("A", "B", "C", "D", "F")},
        "grade_dist_never_named": {g: sum(1 for i in never_ids
                                          if audit_for(i, "")[1]["grade"] == g)
                                   for g in ("A", "B", "C", "D", "F")},
    }

    # Per-Item / per-Gate / per-Category pooled correlations.
    # Build (audit_id -> item pass) once; obs rows carry audit_id.
    for code in [c for c, _ in ITEM_KEYWORDS]:
        xs, ys = [], []
        for r in obs:
            v = audit_items.get(r["audit_id"], {}).get(code)
            if v is None:
                continue
            xs.append(1 if v else 0)
            ys.append(r["mean_pos"])
        rho, p, n = spearman(xs, ys)
        out["per_item"][code] = {
            "rho": rho, "p": p, "n": n,
            "pass_rate_named": None,
        }
    for g in ("G1", "G2", "G3", "G4", "G5", "G6"):
        xs, ys = [], []
        for r in obs:
            v = audit_gates.get(r["audit_id"], {}).get(g)
            if v is None:
                continue
            xs.append(1 if v else 0)
            ys.append(r["mean_pos"])
        rho, p, n = spearman(xs, ys)
        out["per_gate"][g] = {"rho": rho, "p": p, "n": n}
    for cat in range(1, 8):
        xs, ys = [], []
        for r in obs:
            v = audit_cats.get(r["audit_id"], {}).get(cat)
            if v is None:
                continue
            xs.append(1 if v else 0)
            ys.append(r["mean_pos"])
        rho, p, n = spearman(xs, ys)
        out["per_category"][f"Cat{cat}"] = {"rho": rho, "p": p, "n": n}

    # Pass rate per Item among named vs never-named firms (distinct).
    for code in [c for c, _ in ITEM_KEYWORDS]:
        def rate(ids):
            vals = []
            for i in ids:
                got = audit_for(i, "")
                if got is None:
                    continue
                v = audit_items.get(got[0], {}).get(code)
                if v is not None:
                    vals.append(1 if v else 0)
            return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)
        rn, nn = rate(named_ids)
        rv, nv = rate(never_ids)
        out["per_item"][code]["pass_rate_named"] = rn
        out["per_item"][code]["pass_rate_never_named"] = rv
        out["per_item"][code]["n_named"] = nn
        out["per_item"][code]["n_never"] = nv

    if args.dump_rows:
        with open(args.dump_rows, "w", encoding="utf-8") as fh:
            json.dump([{
                "firm": firms_db.get(r["db_id"]),
                "db_id": r["db_id"], "town": r["town"], "task": r["task"],
                "audit_id": r["audit_id"], "points": r["points"],
                "grade": r["grade"], "mean_pos": r["mean_pos"],
                "named_any": r["named_any"],
            } for r in obs], fh, indent=2)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=False)
    print(json.dumps({
        "runs_read": out["runs_read"],
        "observations": out["observations_town_task_firm"],
        "pooled_points": out["pooled"]["points"],
        "pooled_grade_rank": out["pooled"]["grade_rank"],
        "per_task": out["per_task"],
        "named_vs_not": out["named_vs_not"],
        "out": args.out,
    }, indent=2))


if __name__ == "__main__":
    main()
