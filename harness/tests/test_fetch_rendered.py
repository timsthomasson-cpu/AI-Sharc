"""Rendered-page fetch (Spec s.4.1.1, added 16 Nov 2026).

The two-method rule: a website is readable if the initial HTML reads OR
the rendered page reads. The rendered read is a headless Chromium
(Playwright) that runs the page's JavaScript and returns the rendered
HTML. It is attempted only when the initial HTML did not provide readable
text. It is a real browser reading the same public web a Shopping Agent
reads — not a bypass of any block. In this environment the egress proxy
refuses the renderer's network traffic, so the rendered read fails at
runtime with a [PROXY-REFUSED] reason and fast-fails later calls in the
same process; the code is correct and ready for an environment where the
platform allows the renderer's traffic.

Deterministic: Playwright and the direct fetch are mocked, so no browser
or network is needed. Run: python3 tests/test_fetch_rendered.py
"""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from aisharc_harness.evidence import fetchers as F

JS_SHELL = (
    "<html><head><title>Felix Air</title></head>"
    "<body><div id=\"app\"></div>"
    "<script src=\"/app.js\"></script></body></html>"
)
RENDERED_HTML = (
    "<html><head><title>Felix Air</title></head>"
    "<body><h1>Felix Air Services</h1>"
    "<p>AC installation and repair in Coppell, TX 75019.</p>"
    "<p>Call (972) 555-0100.</p></body></html>"
)
TEXT_PAGE = (
    "<html><head><title>Felix Air</title></head>"
    "<body><h1>Felix Air Services</h1>"
    "<p>AC installation and repair in Coppell, TX 75019.</p></body></html>"
)

QUIGLEY_EXTRACT = (
    "# Quigley Heating & Air Conditioning | Better Business Bureau\n\n"
    "**BBB Accredited Since:** 12/1/1958\n\n"
    "**Years in Business:** 80\n\n"
    "BBB File Opened: 12/1/1958\n\n"
    "Business Started: 1/1/1946\n\n"
    "- # What is the BBB rating of Quigley Heating & Air Conditioning?\n\n"
    "    Quigley Heating & Air Conditioning has an A+ BBB rating.\n\n"
    "- # How many complaints has Quigley received in the last 3 years?\n\n"
    "    Quigley Heating & Air Conditioning has no complaints filed with "
    "BBB in the last 3 years.\n\n"
    "- # How many customer reviews does Quigley have?\n\n"
    "    Quigley Heating & Air Conditioning has 10 customer reviews on BBB.\n\n"
    "- # Where is Quigley located?\n\n"
    "    Quigley Heating & Air Conditioning is located at 13720 Diplomat "
    "Dr, Farmers Branch, TX 75234-8916.\n\n"
    "Visit Website quigleyac.com (972) 992-1450\n"
)

BERKEYS_EXTRACT = (
    "[479262459686932204] Berkeys Air Conditioning, Plumbing and "
    "Electrical | BBB Business Profile "
    "(https://www.bbb.org/us/tx/dallas/profile/air-conditioning-"
    "contractor/berkeys-air-conditioning-plumbing-and-electrical-"
    "0875-8001488)\n"
    "**viewing lines [0 - 123] of 123**\n"
    "# About This Business\n\n"
    "**BBB Accredited Since:** 11/1/1992\n\n"
    "**Years in Business:** 51\n\n"
    "Business Started: 7/9/1975\n\n"
    "- # What is the BBB rating of Berkeys Air Conditioning, Plumbing "
    "and Electrical?\n\n"
    "    Berkeys Air Conditioning, Plumbing and Electrical has an A+ BBB "
    "rating.\n\n"
    "- # Where is Berkeys located?\n\n"
    "    Berkeys Air Conditioning, Plumbing and Electrical is located at "
    "4311 Belmont Ave STE 125, Dallas, TX 75204-3032.\n\n"
    "Visit Website www.berkeys.com (214) 612-0133\n"
)


def _fake_playwright(html="", goto_error=None, launches=None):
    """A fake playwright package whose Chromium returns `html` from
    content(), or raises `goto_error` from goto(). `launches` records
    each browser launch."""
    sync_api = types.ModuleType("playwright.sync_api")
    pkg = types.ModuleType("playwright")

    class FakePage:
        def goto(self, url, timeout=None, wait_until=None):
            if goto_error:
                raise Exception(goto_error)

        def wait_for_timeout(self, ms):
            pass

        def content(self):
            return html

    class FakeBrowser:
        def new_page(self, user_agent=None):
            return FakePage()

        def close(self):
            pass

    class FakeChromium:
        def launch(self):
            if launches is not None:
                launches.append(1)
            return FakeBrowser()

    class FakePW:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        @property
        def chromium(self):
            return FakeChromium()

    def sync_playwright():
        return FakePW()

    sync_api.sync_playwright = sync_playwright
    pkg.sync_api = sync_api
    return pkg, sync_api


class _Resp:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code
        self.url = "https://felixairconditioning.com/"


class TestFetchRendered(unittest.TestCase):
    def setUp(self):
        F._RENDERER_PROXY_BLOCKED = False

    def tearDown(self):
        F._RENDERER_PROXY_BLOCKED = False

    def test_fetch_rendered_returns_rendered_html(self):
        pkg, mod = _fake_playwright(html=RENDERED_HTML)
        with patch.dict(sys.modules, {"playwright": pkg,
                                      "playwright.sync_api": mod}):
            ev = F.fetch_rendered("https://felixairconditioning.com/")
        self.assertTrue(ev.accessible)
        self.assertEqual(ev.method, "website-rendered")
        self.assertIn("Felix Air Services", ev.exact)

    def test_fetch_rendered_not_attempted_without_playwright(self):
        # A None entry in sys.modules makes the import raise ImportError.
        with patch.dict(sys.modules, {"playwright": None,
                                      "playwright.sync_api": None}):
            ev = F.fetch_rendered("https://felixairconditioning.com/")
        self.assertFalse(ev.accessible)
        self.assertIn("not attempted", ev.reason or "")

    def test_fetch_rendered_proxy_refused_fast_fails(self):
        launches = []
        pkg, mod = _fake_playwright(
            goto_error="Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED at "
            "https://felixairconditioning.com/",
            launches=launches)
        with patch.dict(sys.modules, {"playwright": pkg,
                                      "playwright.sync_api": mod}):
            ev1 = F.fetch_rendered("https://felixairconditioning.com/")
            ev2 = F.fetch_rendered("https://example.com/")
        self.assertFalse(ev1.accessible)
        self.assertTrue((ev1.reason or "").startswith("[PROXY-REFUSED]"))
        self.assertFalse(ev2.accessible)
        self.assertIn("not re-attempted", ev2.reason or "")
        self.assertEqual(len(launches), 1)  # second call never launched

    def test_fetch_website_attempts_render_when_initial_html_has_no_text(self):
        launches = []
        pkg, mod = _fake_playwright(html=RENDERED_HTML, launches=launches)
        with patch.object(requests, "get",
                          lambda *a, **k: _Resp(JS_SHELL)), \
                patch.dict(sys.modules, {"playwright": pkg,
                                         "playwright.sync_api": mod}):
            w = F.fetch_website("https://felixairconditioning.com/")
        self.assertEqual(len(launches), 1)
        self.assertFalse(w.get("rendered_not_attempted"))
        self.assertTrue(w["rendered"].accessible)
        self.assertFalse(w.get("unreadable"))
        self.assertIn("Felix Air Services", w.get("text") or "")

    def test_fetch_website_skips_render_when_initial_html_has_text(self):
        launches = []
        pkg, mod = _fake_playwright(html=RENDERED_HTML, launches=launches)
        with patch.object(requests, "get",
                          lambda *a, **k: _Resp(TEXT_PAGE)), \
                patch.dict(sys.modules, {"playwright": pkg,
                                         "playwright.sync_api": mod}):
            w = F.fetch_website("https://felixairconditioning.com/")
        self.assertEqual(len(launches), 0)  # renderer never launched
        self.assertTrue(w.get("rendered_not_attempted"))
        self.assertTrue(w.get("rendered_not_needed"))
        self.assertFalse(w.get("unreadable"))
        self.assertIn("Felix Air Services", w.get("text") or "")

    def test_fetch_website_unreadable_when_both_methods_fail(self):
        pkg, mod = _fake_playwright(
            goto_error="Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED")
        with patch.object(requests, "get",
                          lambda *a, **k: _Resp("", 403)), \
                patch.dict(sys.modules, {"playwright": pkg,
                                         "playwright.sync_api": mod}):
            w = F.fetch_website("https://felixairconditioning.com/")
        self.assertTrue(w.get("unreadable"))
        self.assertIsNone(w.get("text"))
        self.assertIn("BLOCKED", w["initial_html"].reason or "")
        self.assertTrue((w["rendered"].reason or "")
                        .startswith("[PROXY-REFUSED]"))


class TestParseBbbProfile(unittest.TestCase):
    def test_quigley_format(self):
        p = F.parse_bbb_profile_text(
            QUIGLEY_EXTRACT,
            "https://www.bbb.org/us/tx/farmers-branch/profile/"
            "heating-and-air-conditioning/"
            "quigley-heating-air-conditioning-0875-8001260")
        self.assertTrue(p.get("accessible"))
        self.assertEqual(p.get("name"),
                         "Quigley Heating & Air Conditioning")
        self.assertTrue(p.get("accredited"))
        self.assertEqual(p.get("accredited_since"), "12/1/1958")
        self.assertEqual(p.get("rating"), "A+")
        self.assertEqual(p.get("years_in_business"), 80)
        self.assertEqual(p.get("business_started"), "1/1/1946")
        self.assertEqual(p.get("address"),
                         "13720 Diplomat Dr, Farmers Branch, "
                         "TX 75234-8916")
        self.assertEqual(p.get("phone"), "(972) 992-1450")
        self.assertEqual(p.get("complaints_3y"), 0)
        self.assertEqual(p.get("review_count"), 10)

    def test_berkeys_format(self):
        p = F.parse_bbb_profile_text(
            BERKEYS_EXTRACT,
            "https://www.bbb.org/us/tx/dallas/profile/"
            "air-conditioning-contractor/"
            "berkeys-air-conditioning-plumbing-and-electrical-0875-8001488")
        self.assertTrue(p.get("accessible"))
        self.assertEqual(p.get("name"),
                         "Berkeys Air Conditioning, Plumbing and Electrical")
        self.assertTrue(p.get("accredited"))
        self.assertEqual(p.get("accredited_since"), "11/1/1992")
        self.assertEqual(p.get("rating"), "A+")
        self.assertEqual(p.get("years_in_business"), 51)
        self.assertEqual(p.get("business_started"), "7/9/1975")
        self.assertEqual(p.get("address"),
                         "4311 Belmont Ave STE 125, Dallas, TX 75204-3032")
        self.assertEqual(p.get("phone"), "(214) 612-0133")
        # This extract states no complaints or review count: not invented.
        self.assertIsNone(p.get("complaints_3y"))
        self.assertIsNone(p.get("review_count"))

    def test_non_profile_text_is_not_accessible(self):
        p = F.parse_bbb_profile_text("Some other page about air "
                                     "conditioning.",
                                     "https://example.com/")
        self.assertFalse(p.get("accessible"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
