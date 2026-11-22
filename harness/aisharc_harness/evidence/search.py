"""Public web search for the harness.

On Railway (and anywhere BRAVE_SEARCH_API_KEY is set) the Brave Search API is used. On Muse, with no key
set, the Muse web-search CLI is used as before. Every caller only needs result URLs (Yelp, Birdeye and BBB
profile discovery), so both routes return the same shape: a list of {title, url, excerpt} dicts.

The key comes from the environment (a Railway secret) and is never written to a file or a log.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Dict, List

import requests

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
MUSE_CLI = "/opt/hatch/bin/web-search"
TIMEOUT_S = 30


def _brave(query: str, key: str) -> List[Dict[str, str]]:
    try:
        resp = requests.get(BRAVE_URL, params={"q": query, "count": 20, "country": "us"},
                            headers={"Accept": "application/json", "X-Subscription-Token": key},
                            timeout=TIMEOUT_S)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []
    results = ((data.get("web") or {}).get("results")) or []
    return [{"title": str(r.get("title") or ""), "url": str(r.get("url") or ""),
             "excerpt": str(r.get("description") or "")}
            for r in results if isinstance(r, dict) and r.get("url")]


def _muse(query: str) -> Dict:
    try:
        out = subprocess.run([MUSE_CLI, "-q", query], capture_output=True, text=True, timeout=120)
    except (subprocess.SubprocessError, OSError):
        return {}
    if out.returncode != 0:
        return {}
    try:
        return json.loads(out.stdout)
    except ValueError:
        return {"content": out.stdout or ""}


def search_top(query: str) -> List[Dict[str, str]]:
    """Top results as {title, url, excerpt}; [] when the search fails."""
    key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if key:
        return _brave(query, key)
    top = _muse(query).get("top") or []
    return [{"title": str(r.get("title") or ""), "url": str(r.get("url") or ""),
             "excerpt": str(r.get("excerpt") or "")}
            for r in top if isinstance(r, dict)]


def search_text(query: str) -> str:
    """Result text that callers scan for profile URLs; "" when the search fails."""
    key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if key:
        return "\n".join("%s\n%s\n%s" % (r["title"], r["url"], r["excerpt"]) for r in _brave(query, key))
    return _muse(query).get("content", "") or ""
