"""Spec v2.13 s.5: closed firms are not audited; run_all records them in closed-firms.json."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_audit  # noqa: E402


def _listing(perm=False, temp=False):
    return {"is_permanently_closed": perm, "is_temporarily_closed": temp}


def test_closure_check(monkeypatch):
    firm = {"firm_id": "x", "name": "X", "meta_place_id": "1"}
    monkeypatch.setattr(run_audit, "fetch_listing", lambda pid, notes: _listing(perm=True))
    assert run_audit.closure_check(firm)["firm_status"] == "permanently closed"
    monkeypatch.setattr(run_audit, "fetch_listing", lambda pid, notes: _listing(temp=True))
    assert run_audit.closure_check(firm)["firm_status"] == "temporarily closed"
    monkeypatch.setattr(run_audit, "fetch_listing", lambda pid, notes: _listing())
    assert run_audit.closure_check(firm) is None
    monkeypatch.setattr(run_audit, "fetch_listing", lambda pid, notes: None)
    assert run_audit.closure_check(firm) is None  # unreadable listing never marks a firm closed


def test_run_all_skips_closed_firms(monkeypatch, tmp_path):
    reg = tmp_path / "firms.json"
    reg.write_text(json.dumps({"firms": [{"firm_id": "shut", "name": "Shut AC", "meta_place_id": "9"}]}))
    monkeypatch.setattr(run_audit, "fetch_listing", lambda pid, notes: _listing(perm=True))
    monkeypatch.setattr(run_audit, "build_evidence", lambda *a: (_ for _ in ()).throw(AssertionError("audited")))
    out = run_audit.run_all(out_root_override=str(tmp_path / "out"), firms_file=str(reg), discovery_file=None)
    assert out["summaries"] == [] and out["closed"][0]["firm_status"] == "permanently closed"
    saved = json.loads((tmp_path / "out" / "closed-firms.json").read_text())
    assert saved["closed"][0]["firm_id"] == "shut"
    assert not (tmp_path / "out" / "shut").exists()
