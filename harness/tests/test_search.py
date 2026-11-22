"""Web search routing: Brave when BRAVE_SEARCH_API_KEY is set, the Muse CLI otherwise. No network."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aisharc_harness.evidence import search, google_yelp, fetchers  # noqa: E402


class FakeResp:
    status_code = 200

    def json(self):
        return {"web": {"results": [
            {"title": "Manny's AC - Yelp", "url": "https://www.yelp.com/biz/mannys-ac-heating-pasadena",
             "description": "HVAC in Pasadena"},
            {"title": "BBB", "url": "https://www.bbb.org/us/tx/pasadena/profile/heating-and-air-conditioning/mannys-ac-0915-1"}]}}


def test_brave_used_when_key_set(monkeypatch):
    seen = {}

    def fake_get(url, params, headers, timeout):
        seen.update(url=url, q=params["q"], token=headers["X-Subscription-Token"])
        return FakeResp()

    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(search.requests, "get", fake_get)
    top = fetchers.web_search_top("Manny's AC Pasadena TX bbb.org")
    assert seen["url"] == search.BRAVE_URL and seen["token"] == "test-key"
    assert top[1]["url"].startswith("https://www.bbb.org/us/tx/")
    assert google_yelp.find_yelp_urls("Manny's AC", "Pasadena") == ["https://www.yelp.com/biz/mannys-ac-heating-pasadena"]


def test_brave_failure_returns_empty(monkeypatch):
    class Bad:
        status_code = 429

    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(search.requests, "get", lambda *a, **k: Bad())
    assert fetchers.web_search_top("x") == [] and google_yelp.web_search("x") == ""


def test_muse_cli_used_without_key(monkeypatch):
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.setattr(search, "_muse", lambda q: {"top": [{"title": "t", "url": "https://u", "excerpt": "e"}],
                                                     "content": "L1: https://www.yelp.com/biz/abc"})
    assert fetchers.web_search_top("x")[0]["url"] == "https://u"
    assert google_yelp.web_search("x") == "https://www.yelp.com/biz/abc"
