#!/usr/bin/env python3
"""Railway entry point for the AI-Sharc harness service.

With no RUN_QUERY_ID set, it runs a self-check and exits:
  - which settings are present (names only; no value is ever printed),
  - the database connection (test database) and the two load functions,
  - one Brave search, if BRAVE_SEARCH_API_KEY is set,
  - Chromium starts and renders a page.

With RUN_QUERY_ID set (e.g. hvac-houston-77002-t2), it audits that query:
firm_registry -> run_query -> load_results audits. Output goes to RUNS_DIR (default /data/runs,
a Railway volume if one is mounted; otherwise /tmp/runs, which is lost when the job ends).
"""
import os
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "harness"))

SETTINGS = ["DATABASE_URL", "BRAVE_SEARCH_API_KEY", "GOOGLE_PLACES_API_KEY", "META_MODEL_API_KEY"]


def check(label, fn):
    try:
        print("OK    %s: %s" % (label, fn()))
        return True
    except (Exception, SystemExit) as exc:  # noqa: BLE001 — report every check, never stop at the first
        msg = str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__
        print("FAIL  %s: %s" % (label, msg))
        return False


def db_check():
    from db import connect
    with connect() as con, con.cursor() as cur:
        cur.execute("select count(*) from public.firms")
        firms = cur.fetchone()[0]
        cur.execute("select count(*) from pg_proc where proname in ('load_audit_bundle','load_observation_bundle')")
        fns = cur.fetchone()[0]
    if fns != 2:
        raise RuntimeError("load functions missing (%d of 2)" % fns)
    return "%d firms in the central firm list; both load functions present" % firms


def search_check():
    from aisharc_harness.evidence import search
    top = search.search_top("Manny's AC & Heating Services Pasadena TX")
    if not top:
        raise RuntimeError("no results (check the key or the Brave plan)")
    return "%d results" % len(top)


def chromium_check():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content("<title>ok</title>")
        title = page.title()
        browser.close()
    return "rendered a page (title %r)" % title


def self_check():
    print("AI Sharc harness self-check, %s" % datetime.now().isoformat(timespec="seconds"))
    for name in SETTINGS:
        print("%-5s %s %s" % ("OK" if os.environ.get(name) else "MISS", name, "set" if os.environ.get(name) else "not set"))
    results = [check("database", db_check), check("Chromium", chromium_check)]
    if os.environ.get("BRAVE_SEARCH_API_KEY"):
        results.append(check("Brave search", search_check))
    print("self-check %s" % ("passed" if all(results) else "FAILED"))
    return 0 if all(results) else 1


def run(query_id):
    runs = os.environ.get("RUNS_DIR") or ("/data/runs" if os.path.isdir("/data") else "/tmp/runs")
    out_dir = os.path.join(runs, "%s-%s" % (datetime.now().strftime("%Y-%m-%d"), query_id))
    os.makedirs(out_dir, exist_ok=True)
    registry = os.path.join(out_dir, "firms-%s.json" % query_id)
    py = sys.executable
    steps = [[py, os.path.join(HERE, "firm_registry.py"), "--query-id", query_id, "--out", registry],
             [py, os.path.join(HERE, "run_query.py"), "--registry", registry, "--out-dir", out_dir, "--resume"],
             [py, os.path.join(HERE, "load_results.py"), "audits", out_dir]]
    for step in steps:
        print("running: %s" % " ".join(os.path.basename(s) if s.startswith("/") else s for s in step[1:]))
        code = subprocess.call(step, cwd=HERE)
        if code != 0:
            print("step failed with exit code %d" % code)
            return code
    return 0


if __name__ == "__main__":
    qid = os.environ.get("RUN_QUERY_ID", "").strip()
    sys.exit(run(qid) if qid else self_check())
