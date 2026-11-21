"""Spec v2.5 s.13 file naming (Tim's decision 2026-11-19).

The harness writes one audit's four files under a shared prefix —
<firm_id>__<query_id>__<vendor>-<product>__<YYYYMMDDTHHMMSS±hhmm> —
with query_id (<trade>-<town>-<zip>-t<task>, all lowercase) and
checked_at (ISO 8601 with seconds and offset) in the run record. The
loader accepts spec_version 2.5, checks a v2.5 filename against the run
record (firm_id, query_id, vendor, product, checked_at as the same
instant), stores the sha256 of the file bytes as audits.file_hash, and
rejects a file whose hash is already in the DB (renamed-copy rule).
Legacy 2.1/2.3 files (plain audit-data.json etc., no query_id/checked_at)
still load exactly as before, with NO filename check applied to them.

Deterministic: engine-scored fixture evidence, no network. Every load
goes to a scratch database in a temp dir; the real
aisharc-audit-v2.sqlite is never touched.
Run: python3 tests/test_spec25_filenames.py
"""
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HARNESS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(HARNESS_DIR.parent / "aisharc-audit-db"))

import run_audit
from aisharc_harness.rules.engine import load_definitions, score_audit
from load_run import (check_v25_filename, find_named_file, load_allocation,
                      load_firm, validate_audit_data)
from test_load_run_vendor import make_audit_data
from test_v21_scoring import all_pass_evidence
import build_aisharc_db_v2

DEFS = load_definitions()
ALLOC = load_allocation(str(HARNESS_DIR / "aisharc_harness" / "rules"
                            / "definitions.json"))

FIRM = {"firm_id": "example-heating", "name": "Example Heating",
        "group_2026": None}
PREFIX = ("example-heating__hvac-coppell-75019-t1__aisharc-harness__"
          "20261118T171300-0600")
CHECKED_AT = "2026-11-18T17:13:00-06:00"


def make_v25_audit_data(run_id="2026-11-18-1713-v25",
                        checked_at=CHECKED_AT):
    """A valid 36-row v2.5 audit-data dict (Coppell, Task 1)."""
    data = make_audit_data(spec_version="2.5")
    data["run"].update({
        "run_id": run_id,
        "query_id": "hvac-coppell-75019-t1",
        "checked_at": checked_at,
        "evidence_source":
            "runs/2026-11-18/example-heating/%s__audit-data.json" % PREFIX,
    })
    return data


def write_v25_firm(firm_dir, data=None, prefix=PREFIX):
    """Write a v2.5 firm dir (audit-data + summary + delivery-check)."""
    os.makedirs(firm_dir, exist_ok=True)
    data = data if data is not None else make_v25_audit_data()
    audit_bytes = json.dumps(data, indent=2).encode("utf-8")
    with open(os.path.join(firm_dir, prefix + "__audit-data.json"),
              "wb") as fh:
        fh.write(audit_bytes)
    with open(os.path.join(firm_dir, prefix + "__summary.json"),
              "w", encoding="utf-8") as fh:
        json.dump({}, fh)
    with open(os.path.join(firm_dir, prefix + "__delivery-check.json"),
              "w", encoding="utf-8") as fh:
        json.dump({"published_business_email": "",
                   "collection_method": "TEST",
                   "do_not_harvest_notice_present": "No",
                   "notice_wording_page": "", "notice_type": "none",
                   "can_spam_requirements_met": "No",
                   "delivery_route": "website verification only",
                   "note": "TEST"}, fh)
    return hashlib.sha256(audit_bytes).hexdigest()


def scratch_db(tmp):
    db_path = os.path.join(tmp, "scratch-v2.sqlite")
    build_aisharc_db_v2.DB = Path(db_path)
    con = build_aisharc_db_v2.build()
    con.close()
    return db_path


class TestHarnessWritesV25Names(unittest.TestCase):
    def test_four_files_share_prefix_and_record_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            ev = all_pass_evidence()
            result = score_audit("Example Heating",
                                 "AC installation and repair",
                                 "Coppell, TX 75019", "2026-11-17", ev, DEFS)
            pages = {"website_url": "https://example.com",
                     "home_url": "https://example.com/",
                     "service_url": "https://example.com/service-area"}
            run_audit.write_firm_outputs(tmp, FIRM, {}, result, {}, [],
                                         DEFS, pages, {"place_id": "ChIJx"},
                                         delivery={"firm_id": "example-heating",
                                                   "firm": "Example Heating",
                                                   "date_checked": "2026-11-17",
                                                   "delivery_route":
                                                   "website verification only"})
            names = sorted(os.listdir(tmp))
            self.assertEqual(len(names), 4)
            prefix = names[0].rsplit("__", 1)[0]
            self.assertTrue(all(n.startswith(prefix + "__") for n in names))
            self.assertEqual(
                sorted(n.rsplit("__", 1)[1] for n in names),
                ["audit-data.json", "delivery-check.json",
                 "human-review.json", "summary.json"])
            with open(os.path.join(
                    tmp, find_named_file(tmp, "audit-data")),
                    encoding="utf-8") as fh:
                audit_data = json.load(fh)
            run = audit_data["run"]
            self.assertEqual(run["spec_version"], "2.6")
            self.assertTrue(run["run_id"].endswith("-v26"))
            # Spec v2.6 s.13: checked_at is the single identity field —
            # no separate date_checked / time_checked / timezone fields.
            self.assertIn("checked_at", run)
            self.assertNotIn("date_checked", run)
            self.assertNotIn("time_checked", run)
            self.assertNotIn("timezone", run)
            self.assertEqual(run["query_id"], "hvac-coppell-75019-t1")
            # The filename timestamp is the same instant as checked_at.
            check_v25_filename(os.path.join(
                tmp, find_named_file(tmp, "audit-data")), run)
            self.assertIn("audit-data.json", run["evidence_source"])

    def test_query_id_examples(self):
        self.assertEqual(run_audit.build_query_id(
            "HVAC", "Houston", "77002", 2), "hvac-houston-77002-t2")
        self.assertEqual(run_audit.build_query_id(
            "hvac", "Coppell", "75019", 1), "hvac-coppell-75019-t1")
        self.assertEqual(run_audit.build_query_id(
            "hvac", "Wichita Falls", "76301", 3),
            "hvac-wichitafalls-76301-t3")
        # Task derived from the query wording when the firm record
        # carries no first_task (run_houston_audit.py's grouping).
        self.assertEqual(run_audit.derive_task_number(
            {}, "Find an HVAC firm in Houston, TX 77002 for AC repair "
            "and compare the firms you find."), 2)
        self.assertEqual(run_audit.derive_task_number(
            {}, "Find an HVAC firm in Houston, TX 77002 for AC "
            "installation and replacement and compare the firms you "
            "find."), 3)
        self.assertEqual(run_audit.derive_task_number(
            {"first_task": 2}, "AC installation and repair"), 2)


class TestLoaderV25Validation(unittest.TestCase):
    def test_valid_v25_passes(self):
        self.assertEqual(len(validate_audit_data(
            make_v25_audit_data(), ALLOC)), 36)

    def test_v25_missing_query_id_rejected(self):
        data = make_v25_audit_data()
        del data["run"]["query_id"]
        with self.assertRaises(ValueError) as cm:
            validate_audit_data(data, ALLOC)
        self.assertIn("query_id", str(cm.exception))

    def test_v25_missing_checked_at_rejected(self):
        data = make_v25_audit_data()
        del data["run"]["checked_at"]
        with self.assertRaises(ValueError) as cm:
            validate_audit_data(data, ALLOC)
        self.assertIn("checked_at", str(cm.exception))

    def test_v25_bad_query_id_rejected(self):
        data = make_v25_audit_data()
        data["run"]["query_id"] = "HVAC-HOU-77002-T2"  # not lowercase
        with self.assertRaises(ValueError) as cm:
            validate_audit_data(data, ALLOC)
        self.assertIn("query_id", str(cm.exception))

    def test_filename_mismatch_rejected(self):
        run = make_v25_audit_data()["run"]
        with self.assertRaises(ValueError) as cm:
            check_v25_filename(
                "example-heating__hvac-coppell-75019-t2__aisharc-harness__"
                "20261118T171300-0600__audit-data.json", run)
        self.assertIn("query_id", str(cm.exception))


class TestLoaderV25Load(unittest.TestCase):
    def test_v25_loads_and_stores_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = scratch_db(tmp)
            run_dir = os.path.join(tmp, "runs", "2026-11-18")
            firm_dir = os.path.join(run_dir, "example-heating")
            file_hash = write_v25_firm(firm_dir)
            rep = load_firm(db_path, run_dir, "example-heating", {},
                            ALLOC, dry_run=False)
            self.assertEqual(rep["audit"], "loaded")
            self.assertEqual(rep["delivery"], "loaded")
            con = sqlite3.connect(db_path)
            row = con.execute(
                "SELECT spec_version, file_hash, run_id FROM audits"
            ).fetchone()
            rec = con.execute(
                "SELECT reconciliation FROM reconciliation").fetchone()
            con.close()
        self.assertEqual(row, ("2.5", file_hash, "2026-11-18-1713-v25"))
        self.assertEqual(rec, ("OK",))

    def test_renamed_copy_recognised_as_already_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = scratch_db(tmp)
            run_dir = os.path.join(tmp, "runs", "2026-11-18")
            firm_dir = os.path.join(run_dir, "example-heating")
            write_v25_firm(firm_dir)
            rep = load_firm(db_path, run_dir, "example-heating", {},
                            ALLOC, dry_run=False)
            self.assertEqual(rep["audit"], "loaded")
            # Same bytes, different filename (timestamp segment changed):
            # the duplicate check runs first, so the copy is recognised
            # as "already loaded" (Spec v2.5 s.13 renamed-copy rule),
            # not rejected and not a second audit.
            src = os.path.join(firm_dir, PREFIX + "__audit-data.json")
            dst = os.path.join(
                firm_dir,
                PREFIX.replace("171300", "171301") + "__audit-data.json")
            shutil.copyfile(src, dst)
            os.remove(src)
            rep2 = load_firm(db_path, run_dir, "example-heating", {},
                             ALLOC, dry_run=False)
            self.assertEqual(rep2["audit"], "already loaded")
            con = sqlite3.connect(db_path)
            count = con.execute("SELECT COUNT(*) FROM audits").fetchone()[0]
            con.close()
            self.assertEqual(count, 1)

    def test_exact_reload_is_already_loaded(self):
        # Loader idempotency holds for v2.5 files exactly as for legacy
        # files: re-loading the identical file is a no-op reported as
        # 'already loaded', not a rejection and not a second audit.
        with tempfile.TemporaryDirectory() as tmp:
            db_path = scratch_db(tmp)
            run_dir = os.path.join(tmp, "runs", "2026-11-18")
            firm_dir = os.path.join(run_dir, "example-heating")
            write_v25_firm(firm_dir)
            load_firm(db_path, run_dir, "example-heating", {},
                      ALLOC, dry_run=False)
            rep2 = load_firm(db_path, run_dir, "example-heating", {},
                             ALLOC, dry_run=False)
            self.assertEqual(rep2["audit"], "already loaded")
            con = sqlite3.connect(db_path)
            count = con.execute("SELECT COUNT(*) FROM audits").fetchone()[0]
            con.close()
            self.assertEqual(count, 1)

    def test_wrong_query_id_filename_rejected(self):
        # Fresh bytes (new run_id, not in the DB) under a filename whose
        # query_id disagrees with the run record.
        with tempfile.TemporaryDirectory() as tmp:
            db_path = scratch_db(tmp)
            run_dir = os.path.join(tmp, "runs", "2026-11-18")
            firm_dir = os.path.join(run_dir, "example-heating")
            data = make_v25_audit_data(
                run_id="2026-11-18-1714-v25",
                checked_at="2026-11-18T17:14:00-06:00")
            bad_prefix = PREFIX.replace("t1__", "t2__").replace(
                "171300", "171400")
            write_v25_firm(firm_dir, data=data, prefix=bad_prefix)
            with self.assertRaises(ValueError) as cm:
                load_firm(db_path, run_dir, "example-heating", {},
                          ALLOC, dry_run=False)
            self.assertIn("query_id", str(cm.exception))

    def test_legacy_v21_still_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = scratch_db(tmp)
            run_dir = os.path.join(tmp, "runs", "2026-11-18")
            firm_dir = os.path.join(run_dir, "example-heating")
            os.makedirs(firm_dir)
            with open(os.path.join(firm_dir, "audit-data.json"),
                      "w", encoding="utf-8") as fh:
                json.dump(make_audit_data(), fh, indent=2)
            with open(os.path.join(firm_dir, "summary.json"),
                      "w", encoding="utf-8") as fh:
                json.dump({}, fh)
            rep = load_firm(db_path, run_dir, "example-heating", {},
                            ALLOC, dry_run=False)
            self.assertEqual(rep["audit"], "loaded")
            # And the legacy no-op re-load is unchanged.
            rep2 = load_firm(db_path, run_dir, "example-heating", {},
                             ALLOC, dry_run=False)
            self.assertEqual(rep2["audit"], "already loaded")
            con = sqlite3.connect(db_path)
            row = con.execute(
                "SELECT spec_version, file_hash IS NOT NULL FROM audits"
            ).fetchone()
            con.close()
        self.assertEqual(row, ("2.1", 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
