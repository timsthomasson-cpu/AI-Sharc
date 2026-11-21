"""PROXY-REFUSED page-text fallback (Spec s.4.1.1, added 15 Nov 2026).

The direct fetch is refused by the egress proxy with no approval card
raised. The harness reads the page through the browser page-text service
instead. The fallback returns rendered text, not raw HTML, so M2 (raw
HTML) and M4 (JSON-LD) are Not accessible when it is used, and the sitemap
and llms.txt reads are Not accessible when their direct fetches fail with
anything other than a 404 (a 404 still means the file does not exist).

Deterministic: the browser-service call and the direct fetch are mocked.
Run: python3 tests/test_fetch_fallback.py
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from aisharc_harness.evidence import fetchers as F
import run_audit as R

EXTRACT = (
    "L1: Felix Air Services\n"
    "L2: AC installation and repair in Coppell, TX 75019.\n"
    "L3: Call (972) 555-0100. Open Monday to Friday 8am to 5pm.\n"
)


class _Out:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode


def _proxy_error(*a, **k):
    raise requests.exceptions.ProxyError(
        "Tunnel connection failed: 403 Forbidden")


def _page_text_ok(*a, **k):
    return _Out(EXTRACT, 0)


class TestFetchFallback(unittest.TestCase):
    def test_fetch_url_via_page_text(self):
        with patch.object(F.subprocess, "run", _page_text_ok):
            ev = F.fetch_url_via_page_text("https://felixairconditioning.com/")
        self.assertTrue(ev.accessible)
        self.assertIn("Felix Air Services", ev.exact)
        self.assertNotIn("L1:", ev.exact)  # line numbers stripped
        self.assertEqual(ev.method, "website-html-pagetext")

    def test_fetch_website_falls_back_on_proxy_refused(self):
        with patch.object(requests, "get", _proxy_error), \
                patch.object(F.subprocess, "run", _page_text_ok):
            w = F.fetch_website("https://felixairconditioning.com/")
        self.assertTrue(w.get("initial_via_fallback"))
        self.assertFalse(w.get("unreadable"))
        self.assertIn("Felix Air Services", w.get("text") or "")

    def test_fetch_firm_pages_forces_m2_m4_not_accessible(self):
        R.TOWN = "Coppell"
        R.ZIP = "75019"
        R._CUR_TOWN_SLUG = "coppell"
        R._CUR_TOWN_HYPHEN = "coppell"
        with patch.object(requests, "get", _proxy_error), \
                patch.object(F.subprocess, "run", _page_text_ok):
            notes = []
            pages = R.fetch_firm_pages(
                {"name": "Felix Air Services"},
                "https://felixairconditioning.com/", notes)
        self.assertFalse(pages["home_m2"].get("accessible"))
        self.assertIn("PROXY-REFUSED", pages["home_m2"].get("reason") or "")
        self.assertFalse(pages["home_json_ld"].get("accessible"))
        self.assertFalse(pages["robots"].get("accessible"))
        self.assertFalse(pages["sitemap"].get("accessible"))
        self.assertTrue(any("fallback" in n.lower() for n in notes))

    def test_sitemap_and_llms_distinguish_404_from_proxy_refused(self):
        with patch.object(requests, "get", _proxy_error):
            sm = F.fetch_sitemap("https://felixairconditioning.com")
            ll = F.fetch_llms_txt("https://felixairconditioning.com")
        self.assertFalse(sm.get("accessible"))
        self.assertIn("PROXY-REFUSED", sm.get("reason") or "")
        self.assertFalse(ll.get("accessible"))

        class Resp:
            status_code = 404
            url = "https://felixairconditioning.com/sitemap.xml"
            text = ""

        with patch.object(requests, "get", lambda *a, **k: Resp()):
            sm = F.fetch_sitemap("https://felixairconditioning.com")
            ll = F.fetch_llms_txt("https://felixairconditioning.com")
        self.assertTrue(sm.get("accessible"))
        self.assertFalse(sm.get("present"))
        self.assertTrue(ll.get("accessible"))
        self.assertFalse(ll.get("exists"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
