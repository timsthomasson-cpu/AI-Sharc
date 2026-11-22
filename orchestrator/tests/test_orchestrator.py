"""Offline tests for the orchestrator: the firm registry and the dry-run load path. No network, no database."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ORCH = os.path.dirname(HERE)
ROOT = os.path.dirname(ORCH)
sys.path.insert(0, ORCH)

import firm_registry as FR  # noqa: E402


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def execute(self, sql, params):
        self.sql, self.params = sql, params

    def fetchone(self):
        return self.row


def test_parse_query_id():
    assert FR.parse_query_id("hvac-houston-77002-t2") == ("hvac", "houston", "77002", 2)


def test_query_id_rejected():
    try:
        FR.parse_query_id("hvac-houston-7700-t2")
    except SystemExit:
        return
    raise AssertionError("bad query_id accepted")


def test_context_from_run():
    ctx = FR.query_context(FakeCursor(("Find an HVAC firm in Houston, TX 77002 for AC repair and compare the firms you find.",
                                       "Houston, TX 77002")), "hvac-houston-77002-t2")
    assert ctx["town"] == "Houston" and ctx["zip"] == "77002" and ctx["task"] == 2
    assert ctx["task_text"].startswith("Find an HVAC firm in Houston")


def test_context_without_run_uses_spec_wording():
    ctx = FR.query_context(FakeCursor(None), "hvac-wichitafalls-76301-t3")
    assert ctx["task_text"] == ("Find an HVAC firm whose service area includes Wichitafalls, TX 76301 for AC installation "
                                "and replacement and compare the firms you find.")


def test_registry_uses_query_town_not_firm_address():
    ctx = {"query_id": "hvac-houston-77002-t1", "task_text": "t", "town": "Houston", "zip": "77002", "task": 1, "trade": "HVAC"}
    reg = FR.build_registry([("mannysac", "Manny's AC & Heating Services", "https://mannysacheatingservices.com/",
                              "2035933526757552", "+17137918689", "1612 Sheridan Rd, Pasadena, TX 77502", "HVAC")], ctx)
    f = reg["firms"][0]
    assert (f["town"], f["town_zip"], f["first_task"]) == ("Houston", "77002", 1)
    assert f["website"] == "https://mannysacheatingservices.com/" and f["phone_recorded"] == "+17137918689"


def _audit_file(folder, firm="testfirm", ts="20261121T150000-0600", iso="2026-11-21T15:00:00-06:00", rows=36):
    rows_ = []
    for i in range(1, rows + 1):
        t = "Category result" if i <= 7 else "Item" if i <= 28 else "Ranking Suggestion"
        res = "0 of 10 points" if t == "Category result" else "Not accessible" if t == "Item" else "Not checked"
        rows_.append({"#": i, "Row type": t, "Item": "x%d" % i, "Item result": res})
    run = {"run_id": "r", "firm_id": firm, "firm": "Test Firm", "query": "q", "query_id": "hvac-houston-77002-t1",
           "town_zip": "Houston, TX 77002", "checked_at": iso, "spec_version": "2.6", "vendor": "AI Sharc", "product": "harness"}
    prefix = "%s__hvac-houston-77002-t1__aisharc-harness__%s" % (firm, ts)
    d = os.path.join(folder, firm)
    os.makedirs(d, exist_ok=True)
    json.dump({"run": run, "rows": rows_}, open(os.path.join(d, prefix + "__audit-data.json"), "w"))
    json.dump({"website_unreadable": False}, open(os.path.join(d, prefix + "__summary.json"), "w"))


def _dry_run(folder):
    p = subprocess.run([sys.executable, os.path.join(ORCH, "load_results.py"), "audits", folder, "--dry-run"],
                       capture_output=True, text=True)
    return p.stdout + p.stderr


def test_dry_run_accepts_a_good_audit(tmp_path):
    _audit_file(str(tmp_path))
    out = _dry_run(str(tmp_path))
    assert "1 audits bundled, 0 rejected" in out and "dry run: 1 audits" in out


def test_dry_run_rejects_timestamp_mismatch(tmp_path):
    _audit_file(str(tmp_path), iso="2026-11-21T15:00:01-06:00")
    out = _dry_run(str(tmp_path))
    assert "0 audits bundled, 1 rejected" in out and "does not match filename timestamp" in out


def test_dry_run_rejects_wrong_row_count(tmp_path):
    _audit_file(str(tmp_path), rows=35)
    out = _dry_run(str(tmp_path))
    assert "expected 36 (7/21/8)" in out


class StatusCursor:
    def __init__(self, status):
        self.status, self.calls = status, []

    def execute(self, sql, params):
        self.calls.append(sql.split()[0])

    def fetchone(self):
        return (self.status,)


def test_record_closed_sets_status_or_queues():
    import load_results as LR
    c = [{"firm_id": "x", "firm_status": "permanently closed", "source": "Meta place listing", "checked_at": "2026-11-22"}]
    cur = StatusCursor(None)
    assert LR.record_closed(cur, c) == (1, 0) and cur.calls[-1] == "update"
    cur = StatusCursor("in business")
    assert LR.record_closed(cur, c) == (0, 1) and cur.calls[-1] == "insert"
