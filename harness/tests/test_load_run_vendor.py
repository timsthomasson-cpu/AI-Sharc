"""Loader Vendor/Product requirement (Tim's decision 2026-11-18).

The run record of every v2.1 audit-data.json must carry vendor and
product — which Shopping Agent gathered the audit data. Vendor is the
corporation (Meta, OpenAI, Anthropic, Google, Perplexity, xAI,
AI Sharc); Product is the actual tool/agent (MUSE-SPARK, Meta AI,
ChatGPT Work, ChatGPT Dots, Claude, Gemini, harness). Open text, not
a closed enum. The loader requires both present and non-empty (checked
AFTER spec_version, so a pre-2.1 file is still rejected on
spec_version first) and stores them on audits.vendor / audits.product.
The harness writes them into the run record (defaults AI Sharc /
harness, overridable with --vendor / --product).

Deterministic: engine-scored fixture evidence, no network. The
load_firm test builds a scratch database in a temp dir; the real
aisharc-audit-v2.sqlite is never touched.
Run: python3 tests/test_load_run_vendor.py
"""
import copy
import json
import os
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
from load_run import load_allocation, load_firm, validate_audit_data
from test_v21_scoring import all_pass_evidence
import build_aisharc_db_v2

DEFS = load_definitions()
ALLOC = load_allocation(str(HARNESS_DIR / "aisharc_harness" / "rules"
                            / "definitions.json"))

FIRM = {"firm_id": "example-heating", "name": "Example Heating",
        "group_2026": None}


def make_audit_data(spec_version="2.1"):
    """A valid 36-row v2.1 audit-data dict, built through the engine
    and run_audit.audit_data_rows so the row shape is exactly what
    the harness writes."""
    ev = all_pass_evidence()
    result = score_audit("Example Heating", "AC installation and repair",
                         "Coppell, TX 75019", "2026-11-17", ev, DEFS)
    rows = run_audit.audit_data_rows(result, FIRM, {}, DEFS)
    run = {
        "run_id": "2026-11-18-v21",
        "firm_id": "example-heating",
        "firm": "Example Heating",
        "group_2026": None,
        "query": "AC installation and repair",
        "town_zip": "Coppell, TX 75019",
        "date_checked": "2026-11-18",
        "spec_version": spec_version,
        "vendor": "AI Sharc",
        "product": "harness",
        "primary_business_category": "HVAC Contractor",
        "website": "https://example.com",
        "website_home": "https://example.com/",
        "service_page": "https://example.com/service-area",
        "meta_place_id": None,
        "evidence_source":
            "runs/2026-11-18/example-heating/audit-data.json",
    }
    return {"run": run, "rows": rows}


class TestVendorProductValidation(unittest.TestCase):
    def test_valid_file_passes(self):
        data = make_audit_data()
        rows = validate_audit_data(data, ALLOC)
        self.assertEqual(len(rows), 36)

    def test_missing_vendor_rejected(self):
        data = make_audit_data()
        del data["run"]["vendor"]
        with self.assertRaises(ValueError) as cm:
            validate_audit_data(data, ALLOC)
        self.assertIn("vendor", str(cm.exception))

    def test_missing_product_rejected(self):
        data = make_audit_data()
        del data["run"]["product"]
        with self.assertRaises(ValueError) as cm:
            validate_audit_data(data, ALLOC)
        self.assertIn("product", str(cm.exception))

    def test_empty_vendor_rejected(self):
        data = make_audit_data()
        data["run"]["vendor"] = ""
        with self.assertRaises(ValueError) as cm:
            validate_audit_data(data, ALLOC)
        self.assertIn("vendor", str(cm.exception))

    def test_empty_product_rejected(self):
        data = make_audit_data()
        data["run"]["product"] = ""
        with self.assertRaises(ValueError) as cm:
            validate_audit_data(data, ALLOC)
        self.assertIn("product", str(cm.exception))

    def test_pre_21_file_rejected_on_spec_version_first(self):
        # A pre-2.1 file with no vendor/product is still rejected on
        # spec_version, not on vendor — the vendor/product check runs
        # after the spec_version check.
        data = make_audit_data(spec_version="2.0")
        del data["run"]["vendor"]
        del data["run"]["product"]
        with self.assertRaises(ValueError) as cm:
            validate_audit_data(data, ALLOC)
        self.assertIn("spec_version", str(cm.exception))
        self.assertNotIn("vendor", str(cm.exception))


class TestHarnessWritesVendorProduct(unittest.TestCase):
    def setUp(self):
        # Restore the harness defaults after each test.
        self.addCleanup(run_audit.set_agent_context, "AI Sharc", "harness")

    def _write_outputs(self, out_dir):
        ev = all_pass_evidence()
        result = score_audit("Example Heating",
                             "AC installation and repair",
                             "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        pages = {"website_url": "https://example.com",
                 "home_url": "https://example.com/",
                 "service_url": "https://example.com/service-area"}
        listing = {"place_id": "ChIJexample"}
        run_audit.write_firm_outputs(out_dir, FIRM, {}, result, {}, [],
                                     DEFS, pages, listing)
        # Spec v2.5 s.13 names: <prefix>__audit-data.json /
        # <prefix>__summary.json (pre-v2.5: audit-data.json / summary.json).
        audit_path = run_audit.find_output_file(out_dir, "audit-data")
        summary_path = run_audit.find_output_file(out_dir, "summary")
        with open(audit_path, encoding="utf-8") as fh:
            audit_data = json.load(fh)
        with open(summary_path, encoding="utf-8") as fh:
            summary = json.load(fh)
        return audit_data, summary

    def test_defaults_are_ai_sharc_harness(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_data, summary = self._write_outputs(tmp)
        self.assertEqual(audit_data["run"]["vendor"], "AI Sharc")
        self.assertEqual(audit_data["run"]["product"], "harness")
        # The run record is shared into summary.json too.
        self.assertEqual(summary["run"]["vendor"], "AI Sharc")
        self.assertEqual(summary["run"]["product"], "harness")

    def test_set_agent_context_override(self):
        run_audit.set_agent_context("Meta", "Meta AI")
        with tempfile.TemporaryDirectory() as tmp:
            audit_data, summary = self._write_outputs(tmp)
        self.assertEqual(audit_data["run"]["vendor"], "Meta")
        self.assertEqual(audit_data["run"]["product"], "Meta AI")
        self.assertEqual(summary["run"]["vendor"], "Meta")
        self.assertEqual(summary["run"]["product"], "Meta AI")


class TestLoadFirmStoresVendorProduct(unittest.TestCase):
    def test_load_firm_stores_vendor_product(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "scratch-v2.sqlite")
            build_aisharc_db_v2.DB = Path(db_path)
            con = build_aisharc_db_v2.build()
            con.close()
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
            con = sqlite3.connect(db_path)
            row = con.execute(
                "SELECT vendor, product, spec_version FROM audits"
            ).fetchone()
            con.close()
        self.assertEqual(row, ("AI Sharc", "harness", "2.1"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
