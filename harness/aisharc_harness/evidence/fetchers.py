"""AI Sharc evidence fetchers — Spec v1.22, s.14.

Fetches the public evidence the rules engine scores. Every fact is returned as
an engine.Evidence (method + source URL + date + exact wording/figure) or as
Not accessible with the reason. Nothing is invented: a source that cannot be
read is Not accessible, never estimated.

Guardrails (Spec s.14, hard): only publicly accessible, non-login data. No
bypassing a login, paywall, CAPTCHA, or bot blocker. Respect Terms, robots.txt,
and do-not-harvest notices. Ordinary request rates (a short delay between
requests; see POLITE_DELAY_S).

Two-method rule (Spec s.4.1.1): a website is readable if the initial HTML
reads OR the rendered page reads. It is unreadable only when BOTH fail. The
rendered read is performed by `fetch_rendered` (headless Chromium via
Playwright, installed 2026-11-16) and is attempted only when the initial
HTML did not provide readable text — when the initial HTML already provides
text, the site is readable and the rendered read adds nothing. The rendered
read is a real browser reading the same public web a Shopping Agent reads;
it is not a bypass of any block. NOTE (2026-11-16): in this environment the
egress proxy refuses the renderer's network connections (HTTP 403 on the
CONNECT tunnel, empty response on plain HTTP) for every host, while the
same CONNECT from a plain socket succeeds — the platform blocks Chromium's
traffic. `fetch_rendered` therefore fails at runtime here with a
[PROXY-REFUSED] reason and fast-fails later calls in the same process; the
code is correct and ready for an environment where the platform allows the
renderer's traffic. Until then the rendered method cannot rescue a site
whose initial HTML fails.

PROXY-REFUSED workaround (Spec s.4.1.1, added 15 Nov 2026, while the
approval-card path is broken): when the direct fetch is refused by the
egress proxy with no approval card raised, fetch_website reads the page
through the browser page-text service instead. The fallback returns
rendered text, not raw HTML, so M2 (raw HTML) and M4 (JSON-LD) are recorded
as Not accessible when it is used, and M1/M5 stay Not accessible because
their files are read only by the direct fetcher. The Stage 1 Gates and
text-based Items are verified from the fallback text. The fallback triggers
only on PROXY-REFUSED, never on a firm-side block, and never to bypass an
approval card. When the approval-card path is fixed, retire this workaround
and re-check.

Places listings come from the Places connector CLI (/opt/hatch/bin/places
details <place_id> --summary); the place ID is found by a place search. BBB
is read by `fetch_bbb`: the search page is fetched directly (readable), the
profile page is read through the browser page-text service (the direct
fetcher gets HTTP 403 / a reset connection on profile pages; the profile
page is publicly readable in a browser, the same route used for Yelp). The
search page itself also carries the BBB Rating. Google Business Profile has
no independent read in this environment: the Maps page is a JavaScript app
with no extractable page text, and the renderer that could read it is
blocked by the egress proxy (see above) — recorded as Not accessible.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any, Dict, List, Optional

import requests

from ..rules.engine import Evidence, norm_licence, norm_text

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
TIMEOUT_S = 20
POLITE_DELAY_S = 1.0

# TDLR — All Licenses, data.texas.gov (dataset 7358-krk7, Socrata API).
# Verified 2026-11-06. No status column; active = expiration on/after the
# audit date. licence_number is numeric only.
TDLR_API = "https://data.texas.gov/resource/7358-krk7.json"
TDLR_META = "https://data.texas.gov/api/views/7358-krk7"

# M1 blocking tokens (Spec s.6.9).
M1_BLOCKING_TOKENS = (
    "OAI-SearchBot", "Claude-SearchBot", "PerplexityBot",
    "Meta-WebIndexer", "Applebot", "Claude-User",
)
M1_NON_BLOCKING_TOKENS = (
    "GPTBot", "ClaudeBot", "Google-Extended",
    "Applebot-Extended", "Meta-ExternalAgent",
)


def today() -> str:
    return date.today().isoformat()


def _classify_fetch_error(exc: BaseException) -> Optional[str]:
    """Map a requests failure to an Inability to Access Website Reason code
    (Spec s.4.1.1, added 15 Nov 2026). Only what the fetcher observes:
    proxy refusals, certificate failures, and DNS/connection failures.
    Returns None when the failure has no code in the set (e.g. an
    unclassified HTTP status). APPROVAL-EXPIRED is recorded from the
    approval record, not here — the fetcher cannot see whether a card was
    raised. PARKED, WRONG-CONTENT, and JS-ONLY are recorded from the page
    read or a page-text check, not auto-classified here."""
    text = str(exc)
    if isinstance(exc, requests.exceptions.SSLError) \
            or "certificate" in text.lower():
        return "CERT-INVALID"
    if isinstance(exc, requests.exceptions.ProxyError):
        return "PROXY-REFUSED"
    if isinstance(exc, requests.exceptions.Timeout):
        return "DEAD"
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "DEAD"
    return None


def fetch_url(url: str, timeout: int = TIMEOUT_S) -> Evidence:
    """GET a URL with a browser user-agent. Returns the body as the exact
    wording, or Not accessible with the reason (status, timeout, block).
    When the failure maps to an Inability to Access Website Reason code
    (Spec s.4.1.1), the reason is prefixed with that code in brackets."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT},
                            timeout=timeout, allow_redirects=True)
    except requests.exceptions.Timeout:
        return Evidence("website-html", url, today(), accessible=False,
                        reason="[DEAD] request timed out after %ds" % timeout)
    except requests.exceptions.RequestException as exc:
        code = _classify_fetch_error(exc)
        prefix = "[%s] " % code if code else ""
        return Evidence("website-html", url, today(), accessible=False,
                        reason="%srequest failed: %s" % (prefix, exc))
    if resp.status_code in (401, 403, 429):
        return Evidence("website-html", url, today(), accessible=False,
                        reason="[BLOCKED] HTTP %d (blocked / rate-limited); "
                        "not worked around" % resp.status_code)
    if resp.status_code != 200:
        return Evidence("website-html", url, today(), accessible=False,
                        reason="HTTP %d" % resp.status_code)
    return Evidence("website-html", resp.url, today(), exact=resp.text,
                    accessible=True)


# Browser page-text service (the browser route), used ONLY as the
# PROXY-REFUSED fallback in fetch_website.
BROWSER_SERVICE = "/opt/hatch/bin/browser-service"
PAGE_TEXT_TIMEOUT_S = 120


def _strip_line_numbers(text: str) -> str:
    """Strip the browser-service line-number prefixes ('L12: ') that the
    page-text service puts at the start of every extract line."""
    return re.sub(r"^L\d+:\s?", "", text, flags=re.M)


def fetch_url_via_page_text(url: str) -> Evidence:
    """Read a page through the browser page-text service. Returns the
    page's text extract, or Not accessible. This is the browser route —
    the same route the October 2026 manual research used — not a scrape
    around a block. The extract is rendered text, not raw HTML: it cannot
    be used for M2 (key facts in the initial HTML) or M4 (JSON-LD)."""
    try:
        out = subprocess.run(
            [BROWSER_SERVICE, "--operation", "open", "--url", url],
            capture_output=True, text=True, timeout=PAGE_TEXT_TIMEOUT_S)
    except (subprocess.SubprocessError, OSError) as exc:
        return Evidence("website-html-pagetext", url, today(),
                        accessible=False,
                        reason="page-text service failed: %s" % exc)
    if out.returncode != 0:
        return Evidence("website-html-pagetext", url, today(),
                        accessible=False,
                        reason="page-text service returned exit %d"
                        % out.returncode)
    text = _strip_line_numbers(out.stdout or "").strip()
    if not text:
        return Evidence("website-html-pagetext", url, today(),
                        accessible=False,
                        reason="page-text service returned no extractable "
                        "content")
    return Evidence("website-html-pagetext", url, today(), exact=text,
                    accessible=True)


def html_to_text(html: str) -> str:
    """Strip tags/scripts/styles to readable text (for key-fact checks)."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html,
                  flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _body_text(html: str) -> str:
    """The readable text of a page's body only. The <title> is metadata,
    not content: a JavaScript shell whose initial HTML is only a title
    and an empty <div id="app"> provides no readable text, so the
    rendered read is needed. Used only for the two-method decision in
    fetch_website (the returned text still includes the title)."""
    body = re.sub(r"<title[^>]*>.*?</title>", " ", html,
                  flags=re.S | re.I)
    return html_to_text(body)


# ---------------------------------------------------------------------------
# Rendered page (headless Chromium via Playwright)
# ---------------------------------------------------------------------------

# Set True once a rendered read is refused by the egress proxy: the
# platform blocks the renderer's network traffic for every host in this
# environment (verified 2026-11-16), so later calls in the same process
# fast-fail instead of launching a browser that cannot connect.
_RENDERER_PROXY_BLOCKED = False

# Playwright error text that means the egress proxy refused the
# renderer's connection (platform-side), not a problem with the site.
_PROXY_TUNNEL_MARKERS = (
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_PROXY_CONNECTION_FAILED",
    "ERR_PROXY_AUTH_UNSUPPORTED",
    "net::ERR_PROXY",
)


def _is_proxy_tunnel_error(text: str) -> bool:
    """True when a render failure is the egress proxy refusing the
    renderer's connection (a platform-side block), not the site failing."""
    low = (text or "").lower()
    return any(m.lower() in low for m in _PROXY_TUNNEL_MARKERS) \
        or "tunnel connection failed" in low


def fetch_rendered(url: str, timeout: int = TIMEOUT_S,
                   settle_ms: int = 2000) -> Evidence:
    """Render a page in a headless browser and return the rendered HTML.

    Method "website-rendered". Returns the full rendered HTML (after
    JavaScript) as the exact wording, or Not accessible with the reason.
    This is a real browser reading the same public web a Shopping Agent
    reads — it does not bypass a login, paywall, CAPTCHA, or bot blocker,
    and it does not use a third-party fetching service. If Playwright is
    not installed, the read is recorded as "not attempted" (not a failure).
    If the egress proxy refuses the renderer's connection, the reason is
    prefixed [PROXY-REFUSED] and later calls in this process fast-fail
    (the block is per-environment, not per-site)."""
    global _RENDERER_PROXY_BLOCKED
    if _RENDERER_PROXY_BLOCKED:
        return Evidence("website-rendered", url, today(), accessible=False,
                        reason="[PROXY-REFUSED] rendered-page read not "
                        "re-attempted: the egress proxy refuses the "
                        "renderer's network traffic in this environment "
                        "(first attempt failed the same way)")
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return Evidence("website-rendered", url, today(), accessible=False,
                        reason="not attempted — no headless-browser renderer "
                        "installed in this environment")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(url, timeout=timeout * 1000,
                          wait_until="domcontentloaded")
                page.wait_for_timeout(settle_ms)
                body = page.content()
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 — a render failure is evidence
        text = str(exc)
        if _is_proxy_tunnel_error(text):
            _RENDERER_PROXY_BLOCKED = True
            return Evidence("website-rendered", url, today(),
                            accessible=False,
                            reason="[PROXY-REFUSED] rendered-page read "
                            "refused by the egress proxy: %s"
                            % text.split("\n")[0][:200])
        return Evidence("website-rendered", url, today(), accessible=False,
                        reason="rendered-page read failed: %s"
                        % text.split("\n")[0][:200])
    if not body or not body.strip():
        return Evidence("website-rendered", url, today(), accessible=False,
                        reason="rendered page returned no content")
    return Evidence("website-rendered", url, today(), exact=body)


# ---------------------------------------------------------------------------
# Website (two-method rule)
# ---------------------------------------------------------------------------


def fetch_website(url: str) -> Dict[str, Any]:
    """Fetch a website by the two methods (Spec s.4.1.1).

    Returns {"initial_html": Evidence, "rendered": Evidence|None,
    "unreadable": bool, "text": str|None}. The rendered read is attempted
    only when the initial HTML did not provide readable text (the initial
    fetch failed, or the page is a JavaScript shell with no text) — when
    the initial HTML already provides text, the site is readable and the
    rendered read adds nothing, so it is recorded as not attempted. The
    site is unreadable only when BOTH methods fail. The PROXY-REFUSED
    page-text fallback for the initial fetch is unchanged (see below)."""
    initial = fetch_url(url)
    initial.accessible = initial.accessible  # Evidence already carries it
    # PROXY-REFUSED workaround: the direct fetch was refused by the egress
    # proxy with no approval card raised — a Muse-side failure, not evidence
    # the site is unreadable. Read the page through the page-text service
    # instead. The fallback returns rendered text, not raw HTML.
    initial_via_fallback = False
    if (not initial.accessible and initial.reason
            and initial.reason.startswith("[PROXY-REFUSED]")):
        fb = fetch_url_via_page_text(url)
        if fb.accessible and fb.exact:
            initial = fb
            initial_via_fallback = True
    initial_ok = bool(initial.accessible)
    # The rendered read is needed when the initial HTML provided no
    # readable body text (a JavaScript shell is only a title and an
    # empty <div>). The <title> alone does not count as readable text.
    # The returned text still includes the title when the initial HTML
    # is used (it can carry the firm name); only the decision uses the
    # body-only text.
    initial_body = _body_text(initial.exact) \
        if initial_ok and initial.exact else None
    initial_body = initial_body if initial_body else None
    initial_text = html_to_text(initial.exact) \
        if initial_ok and initial.exact else None
    # Rendered read: only when the initial HTML did not provide readable
    # body text. A rendered read that fails because the egress proxy refuses
    # the renderer's connection is a platform-side failure (recorded with
    # a [PROXY-REFUSED] reason); it is still a failed method for the
    # two-method rule, because no rendered text was obtained.
    rendered: Optional[Evidence] = None
    rendered_not_attempted = False
    rendered_not_needed = False
    if initial_ok and initial_body:
        rendered_not_attempted = True
        rendered_not_needed = True
    else:
        rendered = fetch_rendered(url)
        if not rendered.accessible and \
                (rendered.reason or "").startswith("not attempted"):
            rendered_not_attempted = True
    # A "not attempted" rendered read is not a failure for the two-method rule.
    rendered_ok = bool(rendered.accessible) if rendered else False
    rendered_failed = bool(rendered) and not rendered.accessible \
        and not rendered_not_attempted
    unreadable = (not initial_ok) and rendered_failed
    # No readable content when the initial HTML was title-only and the
    # rendered read did not provide text.
    text = initial_text if initial_body else None
    if text is None and rendered_ok and rendered and rendered.exact:
        text = html_to_text(rendered.exact)
    return {
        "initial_html": initial,
        "rendered": rendered,
        "rendered_not_attempted": rendered_not_attempted,
        "rendered_not_needed": rendered_not_needed,
        "unreadable": unreadable,
        "text": text,
        "initial_via_fallback": initial_via_fallback,
    }


# ---------------------------------------------------------------------------
# robots.txt / M1
# ---------------------------------------------------------------------------

_AGENT_RE = re.compile(r"^\s*User-agent:\s*(.+?)\s*$", re.I | re.M)
_DISALLOW_RE = re.compile(r"^\s*Disallow:\s*(.*?)\s*$", re.I | re.M)
_SITEMAP_RE = re.compile(r"^\s*Sitemap:\s*(.*?)\s*$", re.I | re.M)


def parse_robots_txt(body: str) -> Dict[str, Any]:
    """Parse robots.txt into per-agent disallow lists. Returns the tokens that
    are disallowed from '/' (a full-site block) and the sitemap URLs."""
    blocks: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _AGENT_RE.match(line)
        if m:
            current = m.group(1).strip()
            blocks.setdefault(current, [])
            continue
        m = _DISALLOW_RE.match(line)
        if m and current is not None:
            blocks[current].append(m.group(1).strip())
    blocked_tokens: List[str] = []
    for agent, paths in blocks.items():
        if agent == "*":
            continue
        if any(p in ("", "/") for p in paths):
            blocked_tokens.append(agent)
    sitemaps = _SITEMAP_RE.findall(body)
    return {"blocks": blocks, "blocked_tokens": blocked_tokens,
            "sitemaps": sitemaps}


def fetch_robots_txt(base_url: str) -> Dict[str, Any]:
    """Fetch and parse <base>/robots.txt. Missing robots.txt passes M1
    (Spec s.6.9): a 404 is "missing", not "unreadable" — it returns
    accessible=True with exists=False. Any other fetch failure (timeout,
    block, 5xx) is Not accessible."""
    url = base_url.rstrip("/") + "/robots.txt"
    ev = fetch_url(url)
    if not ev.accessible:
        if (ev.reason or "") == "HTTP 404":
            return {"accessible": True, "exists": False, "blocked_tokens": [],
                    "sitemaps": [], "url": url}
        return {"accessible": False, "reason": ev.reason, "exists": False,
                "blocked_tokens": [], "sitemaps": [], "url": url}
    if not ev.exact or not ev.exact.strip():
        return {"accessible": True, "exists": False, "blocked_tokens": [],
                "sitemaps": [], "url": url}
    parsed = parse_robots_txt(ev.exact)
    parsed.update({"accessible": True, "exists": True, "url": url,
                   "body": ev.exact})
    return parsed


# ---------------------------------------------------------------------------
# JSON-LD / M4, sitemap / M5, llms.txt / M3
# ---------------------------------------------------------------------------

_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.S | re.I)


def parse_json_ld(html: str, visible: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Extract LocalBusiness JSON-LD. Returns present/valid and any mismatch
    against the visible page (name, phone, address)."""
    found = []
    for raw in _LD_RE.findall(html or ""):
        try:
            found.append(json.loads(raw.strip()))
        except (ValueError, TypeError):
            continue
    # Flatten @graph and lists.
    nodes: List[Dict[str, Any]] = []
    for obj in found:
        if isinstance(obj, dict) and "@graph" in obj:
            nodes.extend([n for n in obj["@graph"] if isinstance(n, dict)])
        elif isinstance(obj, dict):
            nodes.append(obj)
        elif isinstance(obj, list):
            nodes.extend([n for n in obj if isinstance(n, dict)])
    lb = None
    for node in nodes:
        types = node.get("@type")
        if isinstance(types, str):
            types = [types]
        if types and any("LocalBusiness" in t or t in (
                "HVACBusiness", "HomeAndConstructionBusiness",
                "GeneralContractor", "Plumber", "Electrician",
                "RoofingContractor") for t in types):
            lb = node
            break
    if lb is None:
        return {"accessible": True, "present": False, "mismatch": None}
    mismatch = None
    if visible:
        for key, page_val in visible.items():
            ld_val = lb.get(key)
            if isinstance(ld_val, dict):
                ld_val = ld_val.get("name") or ld_val.get("streetAddress")
            # Compare names with the same normalisation as the engine's
            # name checks (norm_text): an HTML entity (&amp;), "&" vs
            # "and", commas, and a trailing legal suffix (LLC) are not a
            # real difference between the JSON-LD name and the visible
            # name. A plain lower() comparison failed M4 on those alone.
            if page_val and ld_val and norm_text(str(ld_val)) \
                    != norm_text(str(page_val)):
                mismatch = "%s: JSON-LD %r vs visible page %r" % (
                    key, ld_val, page_val)
                break
    return {"accessible": True, "present": True, "mismatch": mismatch,
            "node": lb}


def fetch_sitemap(base_url: str, robots: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Check for a sitemap: robots.txt Sitemap directives first, then the
    usual locations. Returns present/valid and the URL checked."""
    candidates: List[str] = []
    if robots:
        candidates.extend(robots.get("sitemaps") or [])
    base = base_url.rstrip("/")
    candidates.extend([base + "/sitemap.xml", base + "/sitemap_index.xml",
                       base + "/sitemap-index.xml"])
    seen = set()
    unreadable_reason = ""
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        ev = fetch_url(url)
        if not ev.accessible:
            # A 404 means no sitemap at that location (Missing); any other
            # failure means the sitemap could not be checked (Not accessible).
            if (ev.reason or "") != "HTTP 404" and not unreadable_reason:
                unreadable_reason = ev.reason or ""
            continue
        body = (ev.exact or "").strip()
        if not body:
            continue
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return {"accessible": True, "present": True, "valid": False,
                    "reason": "sitemap at %s is not valid XML" % url,
                    "url": url, "checked_url": url}
        tag = root.tag.split("}")[-1]
        if tag in ("sitemapindex", "urlset"):
            return {"accessible": True, "present": True, "valid": True,
                    "url": url, "checked_url": url}
        return {"accessible": True, "present": True, "valid": False,
                "reason": "sitemap at %s is not a sitemapindex/urlset" % url,
                "url": url, "checked_url": url}
    if unreadable_reason:
        return {"accessible": False, "reason": unreadable_reason,
                "present": False, "checked_url": ", ".join(candidates)}
    return {"accessible": True, "present": False,
            "checked_url": ", ".join(candidates)}


def fetch_llms_txt(base_url: str) -> Dict[str, Any]:
    """Check /llms.txt: exists, reachable, lists services and the service area."""
    url = base_url.rstrip("/") + "/llms.txt"
    ev = fetch_url(url)
    if not ev.accessible:
        # A 404 means no /llms.txt (Recommendation); any other failure
        # means it could not be checked (Not checked).
        if (ev.reason or "") == "HTTP 404":
            return {"accessible": True, "exists": False, "url": url}
        return {"accessible": False, "reason": ev.reason, "exists": False,
                "url": url}
    body = (ev.exact or "").lower()
    return {"accessible": True, "exists": True, "url": url,
            "lists_services": any(w in body for w in (
                "install", "repair", "service", "hvac")),
            "lists_area": any(w in body for w in (
                "coppell", "dallas", "texas", "tx", "service area")),
            "body": ev.exact}


# ---------------------------------------------------------------------------
# TDLR licence register
# ---------------------------------------------------------------------------


def tdlr_lookup(licence_number: str, licence_type: str,
                audit_date: str) -> Dict[str, Any]:
    """Look up a TDLR licence in the data.texas.gov Socrata dataset.

    Matching: licence_number numeric only (prefix and leading zeros stripped),
    licence_type + number together. Active = expiration on/after the audit
    date. Returns accessible/active plus the register row and the dataset
    update date."""
    number = norm_licence(licence_number)
    if not number:
        return {"accessible": False, "reason": "licence number not numeric",
                "active": False}
    # license_type is matched as stored ("A/C Contractor") — Socrata string
    # comparison is case-sensitive, so do not uppercase it.
    params = {
        "$where": "license_number='%s' AND license_type='%s'" % (
            number, licence_type),
        "$limit": "5",
    }
    try:
        resp = requests.get(TDLR_API, params=params,
                            headers={"User-Agent": USER_AGENT},
                            timeout=TIMEOUT_S)
    except requests.exceptions.RequestException as exc:
        return {"accessible": False, "reason": "TDLR API request failed: %s" % exc,
                "active": False}
    if resp.status_code != 200:
        return {"accessible": False,
                "reason": "TDLR API HTTP %d" % resp.status_code,
                "active": False}
    rows = resp.json()
    if not rows:
        return {"accessible": True, "active": False,
                "note": "no %s row for licence number %s in the TDLR dataset"
                % (licence_type.upper(), number)}
    row = rows[0]
    # The dataset's expiry is license_expiration_date_mmddccyy (MM/DD/YYYY).
    raw_expiry = row.get("license_expiration_date_mmddccyy") or ""
    expiry = ""
    if re.match(r"\d{2}/\d{2}/\d{4}$", raw_expiry):
        mm, dd, yyyy = raw_expiry.split("/")
        expiry = "%s-%s-%s" % (yyyy, mm, dd)
    active = bool(expiry) and expiry >= audit_date
    dataset_updated = None
    try:
        meta = requests.get(TDLR_META, timeout=TIMEOUT_S).json()
        dataset_updated = (meta.get("rowsUpdatedAt") or "")[:10]
    except Exception:  # noqa: BLE001 — metadata is nice-to-have
        dataset_updated = None
    return {"accessible": True, "active": active, "row": row,
            "expiry": expiry, "dataset_updated": dataset_updated,
            "note": "licence_type %s, subtype %s, expiry %s"
            % (row.get("license_type"), row.get("license_subtype"), expiry)}


# ---------------------------------------------------------------------------
# Places listings (Places connector CLI) and BBB
# ---------------------------------------------------------------------------


def places_details(place_id: str) -> Dict[str, Any]:
    """Read a place's details via the Places connector CLI. place_id must be
    a numeric ID returned by a place search. Returns the record, or
    Not accessible with the reason."""
    try:
        out = subprocess.run(
            ["/opt/hatch/bin/places", "details", str(place_id), "--summary"],
            capture_output=True, text=True, timeout=60)
    except (subprocess.SubprocessError, OSError) as exc:
        return {"accessible": False, "reason": "places CLI failed: %s" % exc}
    if out.returncode != 0:
        return {"accessible": False,
                "reason": "places CLI exit %d: %s" % (
                    out.returncode, out.stderr.strip()[:200])}
    try:
        data = json.loads(out.stdout)
    except ValueError:
        return {"accessible": False, "reason": "places CLI returned non-JSON"}
    data.pop("_meta", None)
    record = data.get(str(place_id)) or next(iter(data.values()), None)
    if not record:
        return {"accessible": False,
                "reason": "no record for place_id %s" % place_id}
    return {"accessible": True, "record": record}


def bbb_search(firm_name: str, town: str = "Coppell") -> Dict[str, Any]:
    """Search bbb.org for the firm (name + town as separate parameters —
    putting them together in find_text returns 'No Results').

    The search page is readable by the direct fetcher and already carries
    the BBB Rating in each result card. Returns the search HTML, the
    profile links found, and the rating shown for each link."""
    url = ("https://www.bbb.org/search?find_country=USA&find_text=%s"
           "&find_loc=%s" % (urllib.parse.quote_plus(firm_name),
                             urllib.parse.quote_plus("%s, TX" % town)))
    ev = fetch_url(url)
    if not ev.accessible:
        return {"accessible": False, "reason": ev.reason, "url": url}
    html = ev.exact or ""
    text = html_to_text(html)
    links = []
    seen = set()
    # Profile URLs are /us/<state>/<town>/profile/<category>/<slug>,
    # sometimes with a suffix such as /addressId/<id> or /details.
    # Capture only the canonical profile path (up to the slug): the
    # regex stops the capture at the next "/" and lets [^"]* consume
    # any suffix before the closing quote, so a suffixed URL is still
    # found and canonicalised.
    for m in re.finditer(
            r'href="(/us/[a-z]{2}/[^"]*?/profile/[^/]+/[^"/]+)[^"]*"',
            html):
        link = m.group(1)
        if link in seen:
            continue
        seen.add(link)
        # The rating shown in the search result card for this profile.
        rating = None
        # The result card text follows the link in the raw HTML; take a
        # window after the link and look for "BBB Rating: X".
        window = html_to_text(html[m.start():m.start() + 4000])
        rm = re.search(r"BBB Rating:\s*(A\+|A-|A|B\+|B-|B|C\+|C|D|F|Not Rated)",
                       window)
        if rm:
            rating = rm.group(1)
        links.append({"url": "https://www.bbb.org" + link,
                      "slug": link.rsplit("/", 1)[-1],
                      "rating": rating})
    return {"accessible": True, "url": url, "html": html, "text": text,
            "links": links}


def _bbb_slug_name(slug: str) -> str:
    """The business name from a BBB profile URL slug, e.g.
    'erics-home-services-1075-28158140' -> 'erics home services' (the
    trailing BBB id is stripped)."""
    slug = re.sub(r"-\d{4}-\d+$", "", slug)  # trailing "-0875-8001260"
    slug = re.sub(r"-\d+$", "", slug)
    return slug.replace("-", " ").strip()


def web_search(query: str) -> str:
    """Public web search (Brave on Railway, the Muse CLI on Muse; see search.py).
    Returns the result text, or "" when the search fails."""
    from aisharc_harness.evidence import search
    return _strip_line_numbers(search.search_text(query))


def web_search_top(query: str) -> List[Dict[str, str]]:
    """Public web search returning the top results as {title, url, excerpt}
    dicts; [] when the search fails (see search.py)."""
    from aisharc_harness.evidence import search
    return search.search_top(query)


_BBB_PROFILE_RE = re.compile(
    r"https://www\.bbb\.org/us/[a-z]{2}/[^/\s]+/profile/[^/\s\"'#?/]+"
    r"/[^/\s\"'#?/]+")


def find_bbb_profile_url(firm_name: str, town: str = "Coppell") -> str:
    """The firm's BBB profile URL from a public web search.

    Used when bbb.org's own search does not surface the firm (its
    results are fuzzy and a profile can be missing from them even when
    it exists — e.g. Eric's of Dallas). The candidate is verified
    against the firm name and town before use, and must be an HVAC
    profile. Returns "" when no verified profile URL is found."""
    firm_norm = norm_text(firm_name).replace("'", "")
    town_norm = norm_text(town).replace("-", " ")
    for r in web_search_top("%s %s TX bbb.org" % (firm_name, town)):
        url = r.get("url", "")
        m = _BBB_PROFILE_RE.match(url)
        if not m:
            continue
        url = m.group(0)
        slug = url.rsplit("/", 1)[-1]
        slug_name = norm_text(_bbb_slug_name(slug)).replace("'", "")
        url_town = norm_text(
            url.split("/us/tx/")[1].split("/")[0]
            ).replace("-", " ") if "/us/tx/" in url else ""
        hvac = any(k in url for k in (
            "heating", "air-conditioning", "hvac",
            "air-conditioning-contractors"))
        name_ok = bool(firm_norm) and (slug_name == firm_norm
                                       or firm_norm in slug_name
                                       or slug_name in firm_norm)
        if name_ok and hvac and url_town == town_norm:
            return url
    return ""


def parse_bbb_profile_text(text: str, url: str) -> Dict[str, Any]:
    """Parse the browser page-text extract of a BBB Business Profile.

    Returns the profile facts (accreditation, rating, address, phone,
    business start, complaints and reviews in the last 3 years), or
    {"accessible": False} when the text is not a BBB profile extract.
    Every field is None when the extract does not state it — never
    inferred."""
    if not text or ("Better Business Bureau" not in text
                     and "BBB Business Profile" not in text):
        return {"accessible": False, "url": url,
                "reason": "BBB profile page had no extractable content"}
    name = None
    # Header is either "# Name | Better Business Bureau" or
    # "[<id>] Name | BBB Business Profile (<url>)" (the page-text
    # service's extract format varies between profiles).
    m = re.search(
        r"^(?:#\s+|\[\d+\]\s+)?(.+?)\s*\|\s*"
        r"(?:Better Business Bureau|BBB Business Profile)\b",
        text, re.M)
    if m:
        name = m.group(1).strip()
    accredited = None
    accredited_since = None
    # The profile facts are markdown-bolded in the extract:
    # "**BBB Accredited Since:** 12/1/1958".
    m = re.search(r"BBB Accredited Since:\s*\*+\s*([0-9/]+)", text)
    if m:
        accredited = True
        accredited_since = m.group(1).strip()
    elif "not BBB accredited" in text:
        accredited = False
    rating = None
    m = re.search(r"has an?\s+(A\+|A-|A|B\+|B-|B|C\+|C|D|F)\s+BBB rating",
                  text)
    if m:
        rating = m.group(1)
    if rating is None:
        m = re.search(r"BBB Rating:\s*(A\+|A-|A|B\+|B-|B|C\+|C|D|F)", text)
        if m:
            rating = m.group(1)
    business_started = None
    m = re.search(r"Business Started:\s*([0-9/]+)", text)
    if m:
        business_started = m.group(1).strip()
    years_in_business = None
    m = re.search(r"Years in Business:\s*\*+\s*(\d+)", text)
    if m:
        years_in_business = int(m.group(1))
    address = None
    m = re.search(r"is located at\s+(.+?\bTX\s+\d{5}(?:-\d{4})?)\.", text)
    if m:
        address = m.group(1).strip()
    phone = None
    # The firm's own phone sits next to the "Visit Website" link at the
    # end of the extract; other numbers in the page (e.g. the TDLR
    # regulator's number in the licensing section) are not the firm's.
    m = re.search(r"Visit Website[^\n]{0,60}?\((\d{3})\)\s*(\d{3})[-.\s](\d{4})",
                  text)
    if m:
        phone = "(%s) %s-%s" % (m.group(1), m.group(2), m.group(3))
    if phone is None:
        phones = re.findall(r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}", text)
        if phones:
            phone = phones[-1].strip()
    complaints_3y = None
    if "no complaints filed with BBB in the last 3 years" in text:
        complaints_3y = 0
    else:
        m = re.search(r"(\d+)\s+complaints? (?:filed )?in the last 3 years",
                      text)
        if m:
            complaints_3y = int(m.group(1))
    review_count = None
    m = re.search(r"has\s+(\d+)\s+customer reviews? on BBB", text)
    if m:
        review_count = int(m.group(1))
    return {
        "accessible": True,
        "url": url,
        "name": name,
        "accredited": accredited,
        "accredited_since": accredited_since,
        "rating": rating,
        "business_started": business_started,
        "years_in_business": years_in_business,
        "address": address,
        "phone": phone,
        "complaints_3y": complaints_3y,
        "review_count": review_count,
        "text": text,
    }


def fetch_bbb_profile(profile_url: str) -> Dict[str, Any]:
    """Read a BBB Business Profile page and parse it.

    The profile page blocks the direct fetcher (HTTP 403 / a reset
    connection), but it is publicly readable in a browser — no login, no
    paywall, no CAPTCHA — so it is read through the browser page-text
    service, the same route used for Yelp. The page-text service is
    occasionally flaky (it can return no extractable content once and
    then read the same page), so an empty first attempt is retried once.
    Returns the parsed profile, or {"accessible": False, "reason": ...}."""
    ev = fetch_url_via_page_text(profile_url)
    if (not ev.accessible or not ev.exact) and ev.reason \
            and "no extractable content" in ev.reason:
        ev = fetch_url_via_page_text(profile_url)
    if not ev.accessible or not ev.exact:
        return {"accessible": False, "url": profile_url,
                "reason": ev.reason or "BBB profile page not readable"}
    return parse_bbb_profile_text(ev.exact, profile_url)


def fetch_bbb(firm_name: str, town: str = "Coppell") -> Dict[str, Any]:
    """Fetch the firm's BBB profile: search bbb.org (direct fetcher),
    pick the firm's profile link, and read the profile page through the
    browser page-text service.

    Returns {"accessible", "text", "url", "profile_url", "accredited",
    "accredited_since", "rating", "address", "phone", ...}. The text is
    the profile extract when it could be read; when the profile page
    cannot be read but the search page shows the firm and its rating, the
    search text is returned instead (with "profile_readable": False).
    When bbb.org has no profile for the firm, the result is Not
    accessible with the reason "no BBB profile found" — that is evidence
    the firm is not listed on BBB, not a read failure. This is evidence
    only; the C3.2 rule (BBB claim readable but bbb.org Not accessible =
    Not accessible) is unchanged."""
    search = bbb_search(firm_name, town)
    if not search.get("accessible"):
        return {"accessible": False, "reason": search.get("reason", "")}
    # norm_text keeps an apostrophe ("Eric's" -> "eric's"), but BBB slugs
    # drop it ("erics"), so strip apostrophes on both sides before
    # comparing. Candidate order, fail-closed against the wrong firm:
    # (1) an exact-name match, any town (a firm can sit just outside the
    # searched town, e.g. Quigley of Farmers Branch serving Coppell);
    # (2) a substring-name match only in the SAME town (a substring
    # match in another town is a different firm — Eric's Home Services
    # of Mabank is not Eric's of Dallas); (3) a public web search for
    # the profile URL, verified against name and town.
    firm_norm = norm_text(firm_name).replace("'", "")
    # BBB URL towns are hyphenated ("farmers-branch"); norm_text keeps
    # hyphens, so normalise them to spaces here for the town comparison
    # only (norm_text itself is the G1 rule and is not changed).
    town_norm = norm_text(town).replace("-", " ")
    exact, sub_same_town = [], []
    for link in search.get("links", []):
        slug_name = norm_text(_bbb_slug_name(link["slug"])).replace("'", "")
        if not slug_name or not firm_norm:
            continue
        url_town = norm_text(
            link["url"].split("/us/tx/")[1].split("/")[0]
            ).replace("-", " ") if "/us/tx/" in link["url"] else ""
        hvac = any(k in link["url"] for k in (
            "heating", "air-conditioning", "hvac",
            "air-conditioning-contractors"))
        rank = (0 if url_town == town_norm else 1, 0 if hvac else 1)
        if slug_name == firm_norm:
            exact.append((rank, link))
        elif firm_norm in slug_name or slug_name in firm_norm:
            if url_town == town_norm:
                sub_same_town.append((rank, link))
    profile_url = None
    search_rating = None
    for pool in (exact, sub_same_town):
        if pool:
            pool.sort(key=lambda kv: kv[0])
            profile_url = pool[0][1]["url"]
            search_rating = pool[0][1].get("rating")
            break
    if not profile_url:
        # bbb.org's own search is fuzzy: a profile can exist yet not
        # appear in its results. Fall back to a public web search for
        # the profile URL (same route the Yelp reader uses), verified
        # against name and town before use.
        profile_url = find_bbb_profile_url(firm_name, town)
    if not profile_url:
        return {"accessible": False,
                "url": search["url"],
                "reason": "no BBB profile found for %s near %s, TX"
                % (firm_name, town)}
    profile = fetch_bbb_profile(profile_url)
    if profile.get("accessible"):
        profile["search_url"] = search["url"]
        profile["search_rating"] = search_rating
        profile["profile_readable"] = True
        return profile
    # The profile page could not be read, but the search page shows the
    # firm and (usually) its rating — return that, marked as search-only.
    return {"accessible": True,
            "text": search["text"],
            "url": search["url"],
            "profile_url": profile_url,
            "profile_readable": False,
            "rating": search_rating,
            "accredited": None,
            "reason": "BBB profile page not readable: %s"
            % profile.get("reason", "")}


# ---------------------------------------------------------------------------
# Key facts in the initial HTML (M2)
# ---------------------------------------------------------------------------

KEY_FACT_PATTERNS = {
    "phone": re.compile(r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}"),
    "service area": re.compile(r"service\s+area", re.I),
    "install": re.compile(r"install", re.I),
    "repair": re.compile(r"repair", re.I),
    "hours": re.compile(r"(monday|mon\b|hours)", re.I),
}


def key_facts_in_html(html: str) -> Dict[str, Any]:
    """Check which key facts are present in the initial HTML (M2)."""
    text = html_to_text(html or "")
    missing = [name for name, pat in KEY_FACT_PATTERNS.items()
               if not pat.search(text)]
    return {"accessible": True, "missing_facts": missing,
            "present": [n for n in KEY_FACT_PATTERNS if n not in missing]}


def polite_sleep() -> None:
    time.sleep(POLITE_DELAY_S)
