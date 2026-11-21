#!/usr/bin/env python3
"""Load the Texas HVAC correlation study agent observations into the
audit DB (Stage 2b).

Why a wrapper, not load_run.py directly: load_run.py loads a run dir of
per-firm subdirs that each hold audit-data.json first (it returns early
without one, so an observation-only dir never loads), and its observation
uniqueness check is (agent_label, firm_id, query, town_zip, date_checked).

Two study facts the adopted schema does not have columns for:
  1. The study runs each task TWICE per town on the same date. Two
     repeats of the same task would collide on the UNIQUE key.
  2. The DB has no task / repeat / position column.

Resolution (no schema change — the schema is adopted and shared with the
concurrent audit-runs worker): the DB `query` value is the task's service
need plus the task and run, e.g. "AC repair (task 2, run 1)". The
observation JSON files keep the clean query ("AC repair") plus explicit
task / task_id / repeat / task_text / position fields, and the loader
records task, repeat and position in the observation's notes JSON, so the
correlation can group by (firm, town, task, repeat) from the DB alone.
If Tim later approves task/repeat columns, the rows migrate cleanly:
the notes JSON already carries the values.

Also: only observation files are loaded — never audit rows, never
delivery checks. Re-loading is a no-op (the UNIQUE check). SQLite lock
errors (the audit worker writes to the same DB) are retried with
backoff. Loading r3 observations is out of scope: this loader only
walks runs/2026-11-14-study/agent/.

Usage:
  python3 load_study_observations.py --db <path-to-aisharc-audit.sqlite> [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from load_run import validate_observation  # noqa: E402

STUDY_DIR = os.path.join(HERE, "runs", "2026-11-14-study", "agent")
FIRM_LIST = os.path.join(
    os.path.dirname(HERE),
    "Texas HVAC correlation study — firm list — 2026-11-14 — DRAFT.json")
DB_TIMEOUT = 120
LOCK_RETRIES = 6


def db_query(obs: dict) -> str:
    """The DB query value: service need + task + run (see module doc)."""
    return "%s (task %s, run %s)" % (
        obs["query"], obs["task_id"][-1], obs["repeat"])


def load_observation(con, obs: dict, registry: dict, dry_run: bool) -> str:
    """Insert one observation + its 40 rows. Returns loaded / already
    loaded / would load. Caller handles transactions and lock retries."""
    validate_observation(obs)
    firm_row = con.execute(
        "SELECT firm_id FROM firms WHERE name = ?", (obs["firm"],)
    ).fetchone()
    if firm_row is None:
        reg = registry.get(obs["firm_id"], {}) or {}
        if dry_run:
            return "would load (new firm)"
        con.execute(
            "INSERT INTO firms (name, primary_business_category, trade, "
            "website_url, address, unique_primary_phone, meta_place_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (obs["firm"], obs.get("primary_business_category"),
             "HVAC", reg.get("website"), reg.get("address"),
             reg.get("phone_recorded"), reg.get("meta_place_id")))
        firm_row = con.execute(
            "SELECT firm_id FROM firms WHERE name = ?",
            (obs["firm"],)).fetchone()
    db_firm_id = firm_row[0]
    query = db_query(obs)
    existing = con.execute(
        "SELECT observation_id FROM agent_observations "
        "WHERE agent_label = ? AND firm_id = ? AND query = ? "
        "AND town_zip = ? AND date_checked = ?",
        (obs["agent_label"], db_firm_id, query, obs["town_zip"],
         obs["date_checked"])).fetchone()
    if existing is not None:
        return "already loaded"
    if dry_run:
        return "would load"
    delegation = obs.get("delegation") or {}
    del_text = ""
    if delegation.get("from"):
        del_text = "%s -> %s: %s" % (
            delegation.get("from"), delegation.get("to"),
            delegation.get("what"))
    notes = {"task": obs.get("task"), "task_id": obs.get("task_id"),
             "repeat": obs.get("repeat"),
             "task_text": obs.get("task_text"),
             "position": obs.get("position"),
             "scorer": obs.get("scorer") or {}}
    cur = con.execute(
        "INSERT INTO agent_observations (agent_label, profile, firm_id, "
        "query, town_zip, date_checked, model, tools, transcript_ref, "
        "delegation, auditor, response_id, web_search_calls, "
        "web_search_results, url_citation_count, distinct_urls, cost_usd, "
        "notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (obs["agent_label"], "Muse Spark Model Observation",
         db_firm_id, query, obs["town_zip"], obs["date_checked"],
         obs.get("model"), json.dumps(obs.get("tools") or []),
         obs.get("transcript_ref"), del_text, obs.get("auditor"),
         obs.get("response_id"), obs.get("web_search_calls"),
         obs.get("web_search_results"), obs.get("url_citation_count"),
         json.dumps(obs.get("distinct_urls") or []),
         obs.get("cost_usd"), json.dumps(notes)))
    obs_id = cur.lastrowid
    rows = []
    for g in obs["gates"]:
        rows.append(("Gate", g["gate_id"], g["result"],
                     g.get("exact_wording", ""), g.get("cited_source", ""),
                     g.get("reason", "")))
    for c in obs["category_results"]:
        rows.append(("Category", c["category"], c["result"],
                     "", "", c.get("note", "")))
    for it in obs["items"]:
        rows.append(("Item", it["item_id"], it["result"],
                     it.get("exact_wording", ""), it.get("cited_source", ""),
                     it.get("reason", "")))
    for lv in obs["levers"]:
        rows.append(("Lever", lv["lever_id"], lv["result"],
                     "", "", lv.get("note", "")))
    if len(rows) != 40:
        raise ValueError("expected 40 observation rows, got %d" % len(rows))
    for check_type, check_id, result, wording, source, reason in rows:
        con.execute(
            "INSERT INTO agent_observation_rows (observation_id, "
            "check_type, check_id, result, exact_wording, cited_source, "
            "reason) VALUES (?,?,?,?,?,?,?)",
            (obs_id, check_type, check_id, result, wording, source, reason))
    return "loaded"


def iter_observation_files(study_dir: str):
    for town in sorted(os.listdir(study_dir)):
        town_dir = os.path.join(study_dir, town)
        if not os.path.isdir(town_dir) or town.startswith("_"):
            continue
        for task in sorted(os.listdir(town_dir)):
            task_dir = os.path.join(town_dir, task)
            if not os.path.isdir(task_dir):
                continue
            for repeat in sorted(os.listdir(task_dir)):
                run_dir = os.path.join(task_dir, repeat)
                if not os.path.isdir(run_dir):
                    continue
                for name in sorted(os.listdir(run_dir)):
                    if name.startswith("muse-observation-") \
                            and name.endswith(".json"):
                        yield os.path.join(run_dir, name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    with open(FIRM_LIST, encoding="utf-8") as fh:
        data = json.load(fh)
    registry = {f["firm_id"]: f for f in data["firms"]}
    files = list(iter_observation_files(STUDY_DIR))
    print("loading %d observation files from %s (dry_run=%s)"
          % (len(files), STUDY_DIR, args.dry_run))
    counts = {"loaded": 0, "already loaded": 0, "would load": 0,
              "would load (new firm)": 0, "failed": 0}
    failures = []
    for path in files:
        with open(path, encoding="utf-8") as fh:
            obs = json.load(fh)
        status = None
        for attempt in range(LOCK_RETRIES):
            con = sqlite3.connect(args.db, timeout=DB_TIMEOUT)
            con.execute("PRAGMA foreign_keys = ON")
            try:
                status = load_observation(con, obs, registry, args.dry_run)
                if not args.dry_run:
                    con.commit()
                break
            except sqlite3.OperationalError as exc:
                con.rollback()
                if "locked" in str(exc).lower() \
                        and attempt < LOCK_RETRIES - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
                status = "FAILED: %s" % exc
            except Exception as exc:  # noqa: BLE001 - record and continue
                con.rollback()
                status = "FAILED: %s" % exc
                break
            finally:
                con.close()
        key = status if status in counts else "failed"
        counts[key] = counts.get(key, 0) + 1
        if key == "failed":
            failures.append((path, status))
            print("  FAIL %s: %s" % (path, status))
    print("done: %s" % counts)
    if failures:
        print("%d failures" % len(failures))
        sys.exit(1)


if __name__ == "__main__":
    main()
