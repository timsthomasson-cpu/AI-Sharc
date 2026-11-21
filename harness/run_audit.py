#!/usr/bin/env python3
"""AI Sharc harness — full audit runner (Spec v2.6).

Bridges the evidence fetchers to the rules engine for all 36 rows per firm
(7 Category results, 21 Items, 8 Ranking Suggestions) and runs the 19-firm
test. Spec s.13: new audits record spec_version '2.6' with 36 rows
(0/7/21/8) since Tim's decision 2026-11-18 (decision 10): C3.2 BBB
accreditation and rating consistent with bbb.org and C4.1 six-line
warranty card are Ranking Suggestion rows. There are no Gate rows: G1 exact name and G6 verifiable
listing are scored Items, and the other four former Gates are absorbed
into Items or the Website Access minimum condition (Spec s.5).

Usage:
  python3 run_audit.py --validate          # dummy + Airtron validation only
  python3 run_audit.py --run               # full 19-firm run, 2026-11-11
  python3 run_audit.py --run --firms airtron,erics   # subset (testing)

Rules the runner implements (from the task + DESIGN.md):
  * M4 (LocalBusiness JSON-LD): checked on BOTH the homepage and the town
    service page; M4 passes only if valid JSON-LD is on both. If the firm
    has no separate town service page, the homepage alone is the page a
    local search returns, so M4 is judged on the homepage (judgment call,
    flagged in the run report). Airtron is the test case: homepage has
    JSON-LD, the Coppell service page does not, so Airtron M4 is Missing.
  * Site-root rule: robots.txt, sitemap.xml and llms.txt are fetched from
    the site root (scheme://netloc), never from the recorded page URL.
  * Discovery: firms with no recorded website/place ID are resolved from
    discovery.json (web search + Places details, 2026-11-11). A firm with
    no website found is F under Spec s.5 (no website at all). A firm with
    no Meta place ID gets the listing-dependent checks as not verifiable
    (G6 verifiable listing is Not accessible with a human-review flag, per
    the engine's cannot-verify rule).
  * The runner does NOT call the Model API per firm. The MUSE-SPARK
    observation is a single standard-question run, made once per
    (query, town) by run_agent.py (agent call + LLM scorer), which writes
    one muse-observation.json per firm into runs/<date>/<firm_id>/.
    run_all writes the run-report's agent-observation section from those
    files when present.
  * Run record carries run_id + evidence_source (run file path + run id)
    for the loader (Aggregation design s.2). A delivery-check output
    (Spec s.4.2, <prefix>__delivery-check.json) is written per firm.
  * No firm is contacted; no Report Card is issued. Results are a harness
    test only.

Evidence sources (the only ones the harness reads): the firm's website
(homepage + town service page + a linked warranty page, if any), the Meta
place record via the Places CLI, the TDLR register via the Socrata API,
and bbb.org where readable. Since re-run r2 (2026-11-11), also the Yelp
listing (browser page-text service — direct HTTP to yelp.com returns
403) and reviews (Birdeye profile republishing Google reviews, preferred;
the firm's own reviews page as fallback). Google has no independent read
on the available routes: the Google Business Profile page is a JavaScript
app with no extractable page text, and web search only returns the firm's
own site quoting its Google rating.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from aisharc_harness.evidence import fetchers as F
from aisharc_harness.evidence import google_yelp as GY
from aisharc_harness.rules.engine import (
    CATEGORY_ORDER, ITEM_CATALOG, SUGGESTION_IDS, Definitions,
    load_definitions, norm_phone, norm_text, score_audit,
)

# Tim's decision 2026-11-18: runs are identified by date AND time, so a
# same-day re-run is a distinct run from the earlier run that day. Date and
# time are both taken in America/Chicago (Tim's timezone): the VM clock is
# UTC, so date.today() alone would date a run by the UTC day. RUN_TIME is
# the run's start time, HHMM 24-hour form (e.g. "1709").
try:
    from zoneinfo import ZoneInfo
    _RUN_NOW = datetime.now(ZoneInfo("America/Chicago"))
except Exception:  # zoneinfo/tzdata unavailable: fall back to VM local time
    _RUN_NOW = datetime.now()
RUN_DATE = _RUN_NOW.date().isoformat()  # Dynamic: the actual run date. Was hardcoded "2026-11-15" (inherited from the v1.22 Texas study copy); a stale date misdates every audit. Fixed 2026-11-17 before the first real v2.1 Houston audits.
RUN_TIME = _RUN_NOW.strftime("%H%M")
# checked_at / filename timestamp (Spec v2.6 s.13): the run's start instant,
# _RUN_NOW itself, in America/Chicago. checked_at is ISO 8601 with seconds
# and offset (e.g. 2026-11-18T17:13:00-06:00); the filename timestamp is the
# same instant in compact form (20261118T171300-0600) — the ISO 'T'
# separator is kept, never lowercased. One instant for the whole run, so
# every firm in a run shares it (as RUN_DATE / RUN_TIME already do).
# checked_at is the SINGLE identity field in the run record (Spec v2.6
# s.13): it carries the date, time and offset, so there are no separate
# date_checked / time_checked / timezone fields in the run record.
CHECKED_AT = _RUN_NOW.isoformat(timespec="seconds")
FILENAME_TIMESTAMP = _RUN_NOW.strftime("%Y%m%dT%H%M%S%z")
RUN_ID = "%s-%s-v26" % (RUN_DATE, RUN_TIME)  # Dynamic run id for v2.6 audits: date + time. Was RUN_DATE + "-v21" (date only), so a same-day re-run collided with the first run's identity. Was hardcoded "2026-11-15-reaudit-55" (Texas study) before that.
# Spec v2.6 s.13: new audits record spec_version '2.6' with 36 rows
# (0/7/21/8) — the data-format version, amended 2026-11-19 (was '2.5'
# with 36 rows under the pre-amendment §13).
SPEC_VERSION = "2.6"
# Vendor / Product (Tim's decision 2026-11-18): which Shopping Agent
# gathered the audit data. Vendor = the corporation (Meta, OpenAI,
# Anthropic, Google, Perplexity, xAI, AI Sharc); Product = the actual
# tool/agent (MUSE-SPARK, Meta AI, ChatGPT Work, ChatGPT Dots, Claude,
# Gemini, harness). Open text, not a closed enum. The scored audit is
# gathered by the harness itself (run_audit.py), so the defaults are
# AI Sharc / harness; --vendor / --product override them for
# agent-gathered runs.
VENDOR = "AI Sharc"
PRODUCT = "harness"
QUERY = "AC installation and repair"
TOWN = "Coppell"
ZIP = "75019"
TOWN_ZIP = "Coppell, TX 75019"
PRIMARY_CATEGORY = "HVAC Contractor"

# --- Per-firm town context (study generalization, 2026-11-14) --------------
# TOWN/ZIP/TOWN_ZIP above are the module defaults (Coppell, for --validate
# and the original 19-firm run). For the study, build_evidence() calls
# set_town_context() from each firm's record before any evidence is read,
# so the town service page, the town+ZIP check, C2.1 and the Yelp /
# Birdeye / BBB searches all use that firm's town. The run is sequential
# per firm, so module globals are safe here.
_CUR_TOWN = TOWN
_CUR_TOWN_SLUG = "coppell"          # town name lowercased, spaces kept
_CUR_TOWN_HYPHEN = "coppell"        # town name lowercased, spaces -> "-"
_CUR_ZIP = ZIP


def set_town_context(town: str, zip_code: str) -> None:
    """Point the module's town globals at one firm's town (study runs)."""
    global TOWN, ZIP, TOWN_ZIP, _CUR_TOWN, _CUR_TOWN_SLUG, _CUR_TOWN_HYPHEN
    global _CUR_ZIP
    TOWN = town
    ZIP = zip_code
    TOWN_ZIP = "%s, TX %s" % (town, zip_code)
    _CUR_TOWN = town
    _CUR_TOWN_SLUG = town.lower()
    _CUR_TOWN_HYPHEN = town.lower().replace(" ", "-")
    _CUR_ZIP = zip_code


def set_agent_context(vendor: str, product: str) -> None:
    """Point the module's Vendor/Product globals at the Shopping Agent
    that gathered this run's audit data (Tim's decision 2026-11-18).
    The defaults are the harness itself (AI Sharc / harness); the
    --vendor / --product flags override them for agent-gathered runs."""
    global VENDOR, PRODUCT
    VENDOR = vendor
    PRODUCT = product


# --- Spec v2.6 s.13 file naming (Tim's decision 2026-11-19, unchanged from v2.5) ---------------
# runs/<YYYY-MM-DD>/<firm_id>/<firm_id>__<query_id>__<vendor>-<product>__
# <YYYYMMDDTHHMMSS±hhmm>__<audit-data|summary|human-review|delivery-check>.json
# query_id = <trade>-<town>-<zip>-t<task>, all lowercase (trade =
# hvac/plumbing/electrical/roofing; town = town name with spaces and
# punctuation removed; zip = 5-digit ZIP; task = 1, 2 or 3).
# Examples: hvac-houston-77002-t2, hvac-coppell-75019-t1,
# hvac-wichitafalls-76301-t3. The filename timestamp keeps the ISO 'T'
# separator; only the query_id is all lowercase — never lowercase the 'T'.
# The vendor/product segment is slugified the same way (lowercase, all
# non-alphanumerics removed, e.g. "AI Sharc" -> "aisharc"), so the
# filename carries exactly one hyphen there, between vendor and product.
# The loader (load_run.py) applies this same slug rule when it checks a
# v2.6 filename against the run record — the two must stay in step.
# Applies to NEW audits only: existing audit files are never renamed
# (the 2026-11-18 files were recorded without seconds and cannot be
# renamed to the new pattern honestly).

def _slug_segment(value: str) -> str:
    """Lowercase, all non-alphanumerics removed (e.g. 'AI Sharc' ->
    'aisharc', 'MUSE-SPARK' -> 'musespark')."""
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def build_query_id(trade: str, town: str, zip_code: str, task: int) -> str:
    """query_id per Tim's rule 2026-11-19: <trade>-<town>-<zip>-t<task>,
    all lowercase, town with spaces and punctuation removed."""
    town_slug = re.sub(r"[^a-z0-9]", "", (town or "").lower())
    return "%s-%s-%s-t%d" % ((trade or "").lower(), town_slug,
                             zip_code, task)


_TRADE_BY_PRIMARY_CATEGORY = {
    "HVAC Contractor": "hvac",
    "Plumbing Contractor": "plumbing",
    "Plumber": "plumbing",
    "Electrical Contractor": "electrical",
    "Electrician": "electrical",
    "Roofing Contractor": "roofing",
    "Roofer": "roofing",
}


def derive_trade(firm: dict) -> str:
    """The audit's trade, lowercased ('hvac', 'plumbing', 'electrical',
    'roofing'). The firm registry carries it (firms-houston-2026-11-18.json
    'trade'); otherwise it is derived from the Primary Business Category
    (e.g. 'HVAC Contractor' -> 'hvac')."""
    trade = (firm or {}).get("trade")
    if trade:
        return str(trade).lower()
    return _TRADE_BY_PRIMARY_CATEGORY.get(
        PRIMARY_CATEGORY, PRIMARY_CATEGORY.split()[0].lower())


def derive_task_number(firm: dict, query: str) -> int:
    """The shopping-query task number (1, 2 or 3) for this audit. The
    Houston registry carries it per firm ('first_task': the task where
    the firm first appeared); otherwise it is derived from the query
    wording, the same way run_houston_audit.py groups queries — the
    combined 'installation and repair' query is Task 1, a repair-only
    query is Task 2, an installation(-only) query is Task 3. There is
    no task number stored anywhere else in run_audit.py, so a query
    naming neither service defaults to Task 1 (the combined query)."""
    first_task = (firm or {}).get("first_task")
    if first_task is not None:
        try:
            task = int(first_task)
        except (TypeError, ValueError):
            task = 0
        if task in (1, 2, 3):
            return task
    q = (query or "").lower()
    if "installation" in q and "repair" in q:
        return 1
    if "repair" in q:
        return 2
    if "installation" in q or "replacement" in q:
        return 3
    return 1


def audit_filename_prefix(firm_id: str, query_id: str, vendor: str,
                          product: str, filename_timestamp: str) -> str:
    """The shared filename prefix for one audit's four output files:
    <firm_id>__<query_id>__<vendor>-<product>__<timestamp>."""
    return "%s__%s__%s-%s__%s" % (
        firm_id, query_id, _slug_segment(vendor), _slug_segment(product),
        filename_timestamp)


def find_output_file_for_run(out_dir: str, kind: str, run: dict) -> str | None:
    """The output file for one audit's run record, by its exact filename
    prefix. Audit-per-query (Spec v2.6 s.13): one firm dir can hold several
    audits (different query_id), so the first-sorted file is the WRONG file
    for a later query — the exact prefix must be used. Falls back to
    find_output_file when the run record cannot build a prefix (legacy)."""
    try:
        checked_at = datetime.fromisoformat(run.get("checked_at") or "")
        ts = checked_at.strftime("%Y%m%dT%H%M%S%z")
        prefix = audit_filename_prefix(
            run.get("firm_id", ""), run.get("query_id", ""),
            run.get("vendor", ""), run.get("product", ""), ts)
        path = os.path.join(out_dir, "%s__%s.json" % (prefix, kind))
        if os.path.exists(path):
            return path
    except (ValueError, TypeError):
        pass
    return find_output_file(out_dir, kind)


def find_output_file(out_dir: str, kind: str) -> str | None:
    """The path of one per-firm output file, new name first, legacy name
    as fallback. kind is one of 'audit-data', 'summary', 'human-review',
    'delivery-check'. New (v2.5/v2.6) files are
    <prefix>__<kind>.json; pre-v2.5 files are <kind>.json. Returns None
    when neither exists (callers treat a missing summary/delivery-check
    as they did before — a warning, not a failure)."""
    new_names = sorted(
        f for f in os.listdir(out_dir)
        if f.endswith("__%s.json" % kind)) if os.path.isdir(out_dir) else []
    if new_names:
        return os.path.join(out_dir, new_names[0])
    legacy = os.path.join(out_dir, "%s.json" % kind)
    return legacy if os.path.exists(legacy) else None

BRANDS = (
    "Trane", "Carrier", "Lennox", "Goodman", "Rheem", "York", "Bryant",
    "American Standard", "Ruud", "Amana", "Daikin", "Mitsubishi", "Fujitsu",
    "Bosch", "Heil", "Tempstar", "Coleman",
)
SYSTEM_TYPES = (
    "central air", "ductless", "mini-split", "mini split", "heat pump",
    "furnace", "package unit", "split system", "air handler", "condenser",
    "evaporator coil", "ductwork",
)
DAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday",
             "saturday", "sunday")
DAY_ABBR = ("mon", "tue", "tues", "wed", "thu", "thur", "thurs", "fri",
            "sat", "sun")

PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)")
LICENCE_RE = re.compile(r"\b(?:TACLA|TACLB|TECL)\s*\d+[A-Z]?\b")
YEAR_RE = re.compile(
    r"(?:since|founded(?: in)?|established(?: in)?|serving since"
    r"|in business since|est\.?)\s*:?\s*(19\d{2}|20\d{2})", re.I)
RATING_RE = re.compile(r"(\d\.\d)\s*(?:★|stars?|/ ?5|out of 5)", re.I)
COUNT_RE = re.compile(r"([\d,]+)\+?\s*(?:google\s*)?(?:reviews?|ratings?)", re.I)
TIME_RE = re.compile(r"\d{1,2}(:\d{2})?\s*(?:am|pm|AM|PM)")


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------


def find_phones(text: str) -> list:
    """All phone numbers in a block of text, in order, de-duplicated."""
    seen, out = set(), []
    for m in PHONE_RE.finditer(text or ""):
        raw = m.group(0).strip()
        norm = norm_phone(raw)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(raw)
    return out


def _clean_site_name(candidate: str | None, firm_name: str) -> str | None:
    """Clean a candidate website name: unescape entities, strip a trailing
    ': description' / ' - description' / ' | description' (a page title,
    not the business name), and use the firm name when the candidate
    starts with it. Returns None when there is no usable name."""
    import html as _html
    c = _html.unescape((candidate or "").strip())
    for sep in (":", " - ", " | ", " – ", " — "):
        if sep in c:
            head = c.split(sep, 1)[0].strip()
            if head:
                c = head
                break
    if not c:
        return None
    if firm_name and norm_text(c).startswith(norm_text(firm_name)):
        return firm_name
    return c


def site_name_from_html(html: str, url: str, firm_name: str) -> tuple:
    """The business name as shown on the website, and how it was found.

    Priority: LocalBusiness JSON-LD name (the business's own structured
    name), then og:site_name, then the firm name if it appears in the
    visible text, then the <title>'s first segment. Returns (name, method).
    """
    ld = F.parse_json_ld(html or "")
    node = ld.get("node") or {}
    if node.get("name"):
        name = _clean_site_name(str(node["name"]), firm_name)
        if name:
            return name, "json-ld name"
    m = re.search(
        r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)',
        html or "", re.I)
    if m:
        name = _clean_site_name(m.group(1), firm_name)
        if name:
            return name, "og:site_name"
    text = F.html_to_text(html or "")
    if firm_name and norm_text(firm_name) in norm_text(text):
        return firm_name, "firm name found in visible text"
    m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.S | re.I)
    if m:
        title = F.html_to_text(m.group(1)).strip()
        name = _clean_site_name(title, firm_name)
        if name:
            return name, "page <title> first segment"
    return None, "no name found"


def find_service_page(home_html: str, home_url: str) -> str | None:
    """A town service page linked from the homepage, if any.

    Scores same-host links: the town name in the URL or anchor text, and a
    service-area / locations path. Returns the best link, or None."""
    links = re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        home_html or "", re.S | re.I)
    best, best_score = None, 0
    for href, anchor in links:
        href = href.strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        abs_url = urllib.parse.urljoin(home_url, href)
        if urllib.parse.urlparse(abs_url).netloc != \
                urllib.parse.urlparse(home_url).netloc:
            continue
        score = 0
        low_href, low_anchor = abs_url.lower(), F.html_to_text(anchor).lower()
        if _CUR_TOWN_SLUG in low_href or _CUR_TOWN_HYPHEN in low_href:
            score += 3
        if _CUR_TOWN_SLUG in low_anchor:
            score += 1
        if any(p in low_href for p in ("service-area", "service-areas",
                                       "areas-we-serve", "locations",
                                       "service_area")):
            score += 2
        if "service area" in low_anchor:
            score += 1
        if score > best_score:
            best, best_score = abs_url, score
    return best if best_score >= 3 else None


def scan_warranty(text: str) -> dict:
    """The six-line warranty card (Spec s.6.7): each line True if its
    markers appear in a window around a 'warranty' mention, with the
    matched snippet. A card in the exact six-line form is rare; most
    sites will show 0 lines, which the engine reads as Not accessible
    (card not published)."""
    w = text or ""

    def window(alt_sets, need_year=False):
        """First warranty-window matching any alternative marker set."""
        for m in re.finditer(r"warranty", w, re.I):
            lo = max(0, m.start() - 120)
            hi = min(len(w), m.end() + 220)
            win = w[lo:hi]
            low = win.lower()
            for markers in alt_sets:
                if all(n.lower() in low for n in markers):
                    if need_year and not re.search(r"\d+\s*(?:year|yr)", low):
                        continue
                    return " ".join(win.split())
        return None

    def claim_line():
        m = re.search(
            r"call (?:us )?first|diagnose|tell you[^.;]{0,80}before (?:any )?work"
            r"|order (?:the )?part", w, re.I)
        return m.group(0).strip() if m else None

    found = {
        "new_parts": window([["parts", "manufacturer"], ["parts", "factory"],
                             ["new", "parts"]], need_year=True),
        "new_labour": window([["labor", "install"], ["labour", "install"],
                              ["labor", "new"], ["labour", "new"],
                              ["labor", "workmanship"],
                              ["labour", "workmanship"]], need_year=True),
        "repair_parts_labour": window([["repair", "parts", "labor"],
                                       ["repair", "parts", "labour"],
                                       ["repair", "warranty"]], need_year=True),
        "registration": window([["regist", "day"], ["regist", "days"]]),
        "transferable": window([["transferable"]]),
        "claim_line": claim_line(),
    }
    return {k: (v if isinstance(v, str) else bool(v)) for k, v in found.items()}


def scan_text(text: str) -> dict:
    """All the facts the engine needs that can be read from visible text."""
    t = text or ""
    low = t.lower()

    def near(anchor_re: str, words: list, span: int = 200) -> str | None:
        for m in re.finditer(anchor_re, t, re.I):
            lo = max(0, m.start() - 60)
            hi = min(len(t), m.end() + span)
            win = t[lo:hi]
            if all(w.lower() in win.lower() for w in words):
                return " ".join(win.split())
        return None

    # Hours: day names followed (within 60 chars) by a time.
    days_with_time = set()
    hours_snippet = None
    for m in re.finditer(
            r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
            r"mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)\b", t, re.I):
        after = t[m.end():m.end() + 60]
        if TIME_RE.search(after):
            days_with_time.add(m.group(1).lower()[:3])
            if hours_snippet is None:
                hours_snippet = " ".join(t[max(0, m.start() - 20):
                                           m.end() + 120].split())

    # Own-site rating: a star rating with a review count nearby.
    rating, rating_count, rating_text = None, None, None
    for m in RATING_RE.finditer(t):
        val = float(m.group(1))
        window = t[max(0, m.start() - 40):m.end() + 80]
        c = COUNT_RE.search(window)
        if c:
            rating, rating_count = val, int(c.group(1).replace(",", ""))
            rating_text = " ".join(window.split())
            break
        if rating is None:
            rating = val
            rating_text = " ".join(window.split())

    # Diagnostic fee: a dollar figure near a diagnostic / service-call word.
    diag_amount, diag_text, diag_mentioned = None, None, False
    for m in re.finditer(r"diagnostic|service[- ]call|trip fee|dispatch fee",
                         t, re.I):
        diag_mentioned = True
        win = t[max(0, m.start() - 100):m.end() + 200]
        d = re.search(r"\$\s*(\d+(?:\.\d{2})?)", win)
        if d:
            diag_amount = float(d.group(1))
            diag_text = " ".join(win.split())
            break
    if diag_mentioned and diag_text is None:
        m = re.search(r"diagnostic[^.;]{0,120}", t, re.I)
        diag_text = m.group(0).strip() if m else None

    # Free estimates / quote tool.
    fe = re.search(r"free (?:estimate|quote|consultation|in-home estimate)",
                   t, re.I)
    qt = re.search(r"instant quote|online quote|get a quote|request a quote",
                   t, re.I)
    fe_install = fe_repair = False
    fe_text = None
    if fe:
        fe_text = fe.group(0)
        near_install = near(r"free (?:estimate|quote|consultation)",
                            ["install", "replacement"], 200)
        near_repair = near(r"free (?:estimate|quote|consultation)",
                           ["repair"], 200)
        if near_install and not near_repair:
            fe_install, fe_repair = True, False
        elif near_repair and not near_install:
            fe_install, fe_repair = False, True
        else:
            # Generic ("free estimates") or near both: applies to both.
            fe_install = fe_repair = True
        if near_install:
            fe_text = near_install
        elif near_repair:
            fe_text = near_repair
    if qt:
        fe_install = fe_repair = True
        fe_text = (fe_text or qt.group(0))

    # Booking / quote route and next step. The next-step pattern is kept
    # to the firm's own process (we will call you, pick a time slot,
    # confirmation) — a testimonial that says "within 30 minutes of me
    # calling" is a past customer's story, not the booking's next step.
    booking = re.search(
        r"book (?:online|now|service)|schedule (?:online|service|a)|"
        r"request service|contact us|online booking|book a service", t, re.I)
    next_step = re.search(
        r"we'?ll call you[^.;]{0,80}|we will call you[^.;]{0,80}|"
        r"we'?ll confirm[^.;]{0,80}|you'?ll receive[^.;]{0,80}|"
        r"we will contact you[^.;]{0,80}|call you back[^.;]{0,60}|"
        r"confirm your (?:appointment|booking|service)[^.;]{0,60}|"
        r"pick (?:a )?(?:service|time|date)[^.;]{0,60}|"
        r"choose (?:a )?(?:time|date|service)[^.;]{0,60}", t, re.I)
    written_quote = re.search(
        r"written (?:quote|estimate)|quote in writing|flat[- ]rate written|"
        r"upfront pricing|up-front pricing|pricing in writing", t, re.I)
    next_appt = re.search(
        r"same[- ]day|same[- ]night|next available|available today|"
        r"next[- ]morning|next-morning appointments?", t, re.I)
    emergency = re.search(
        r"24/7|24[- ]hour (?:emergency|service)|after-hours emergency|"
        r"emergency (?:service|dispatch|repair)", t, re.I)
    founding = YEAR_RE.search(t)
    bbb = re.search(r"(?:BBB|Better Business Bureau)[^.;\n]{0,80}", t, re.I)
    licence = LICENCE_RE.search(t)

    brands = [b for b in BRANDS if re.search(r"\b" + re.escape(b) + r"\b", t, re.I)]
    systems = [s for s in SYSTEM_TYPES if s in low]

    return {
        "phones": find_phones(t),
        "has_install": bool(re.search(r"\binstall(?:ation|ing|ed|s)?\b|\breplacement\b", t, re.I)),
        "has_repair": bool(re.search(r"\brepair(?:ing|ed|s)?\b", t, re.I)),
        "names_town_zip": (_CUR_TOWN_SLUG in low and _CUR_ZIP in t),
        "brands": brands,
        "system_types": systems,
        "licence": licence.group(0).replace(" ", "") if licence else None,
        "bbb_claim": bbb.group(0).strip() if bbb else None,
        "diagnostic_amount": diag_amount,
        "diagnostic_text": diag_text,
        "diagnostic_mentioned": diag_mentioned,
        "free_estimate_install": fe_install,
        "free_estimate_repair": fe_repair,
        "free_estimate_text": fe_text,
        "quote_tool": bool(qt),
        "booking_text": booking.group(0).strip() if booking else None,
        "next_step": next_step.group(0).strip() if next_step else None,
        "written_quote": written_quote.group(0).strip() if written_quote else None,
        "next_appointment": next_appt.group(0).strip() if next_appt else None,
        "emergency": emergency.group(0).strip() if emergency else None,
        "founding_year": int(founding.group(1)) if founding else None,
        "rating": rating,
        "rating_count": rating_count,
        "rating_text": rating_text,
        "hours_day_by_day": len(days_with_time) >= 2,
        "hours_partial": bool(days_with_time) or ("hours" in low),
        "hours_text": hours_snippet,
        "warranty_lines": scan_warranty(t),
    }


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def site_root(url: str) -> str:
    p = urllib.parse.urlparse(url)
    return "%s://%s" % (p.scheme or "https", p.netloc)


def _page_html(fetch: dict) -> str | None:
    """The raw HTML of a fetched page (initial HTML first, rendered second)."""
    initial = fetch.get("initial_html")
    if initial is not None and initial.accessible and initial.exact:
        return initial.exact
    rendered = fetch.get("rendered")
    if rendered is not None and rendered.accessible and rendered.exact:
        return rendered.exact
    return None


def fetch_firm_pages(firm: dict, website_url: str, notes: list) -> dict:
    """Fetch the homepage, the town service page, and a linked warranty
    page (if any). Returns the pages, their scans, and the C7 facts."""
    out = {"website_url": website_url, "site_root": site_root(website_url)}
    # If the recorded URL already is a town service page (town name in the
    # URL), it is the service page and the site root is the homepage.
    recorded_is_town_page = (_CUR_TOWN_SLUG in website_url.lower()
                             or _CUR_TOWN_HYPHEN in website_url.lower())
    if recorded_is_town_page:
        service_url = website_url
        home_url = site_root(website_url) + "/"
    else:
        home_url = website_url
        service_url = None
    out["home_url"] = home_url

    home = F.fetch_website(home_url)
    out["home_fetch"] = home
    if home.get("initial_via_fallback"):
        notes.append("Homepage %s direct fetch refused (PROXY-REFUSED); "
                     "read via the page-text service fallback. M2 and M4 "
                     "are Not accessible (raw HTML not read)."
                     % home_url)
    home_html = _page_html(home)
    out["home_html"] = home_html
    home_text = home.get("text") or ""
    out["home_text"] = home_text
    out["home_scan"] = scan_text(home_text)
    site_name, method = site_name_from_html(
        home_html or "", home_url, firm["name"])
    out["site_name"], out["site_name_method"] = site_name, method
    if not home.get("text"):
        _rend = home.get("rendered")
        _rend_note = (
            "rendered read: %s" % (_rend.reason or "no reason recorded")
            if _rend is not None else
            "rendered read not attempted (initial HTML already provided text)")
        notes.append("Homepage %s returned no readable text (initial HTML: %s; "
                     "%s)."
                     % (home_url,
                        (home.get("initial_html").reason
                         if home.get("initial_html") else "unknown"),
                        _rend_note))

    if service_url is None and home_html:
        service_url = find_service_page(home_html, home_url)
        if service_url:
            notes.append("Town service page found from a homepage link: %s"
                         % service_url)
    out["service_url"] = service_url
    if service_url and service_url.rstrip("/") != home_url.rstrip("/"):
        svc = F.fetch_website(service_url)
        out["service_fetch"] = svc
        if svc.get("initial_via_fallback"):
            notes.append("Service page %s direct fetch refused "
                         "(PROXY-REFUSED); read via the page-text service "
                         "fallback." % service_url)
        svc_html = _page_html(svc)
        out["service_html"] = svc_html
        svc_text = svc.get("text") or ""
        out["service_text"] = svc_text
        out["service_scan"] = scan_text(svc_text)
        if not svc.get("text"):
            notes.append("Service page %s returned no readable text."
                         % service_url)
    else:
        out["service_fetch"] = home
        out["service_html"] = home_html
        out["service_text"] = home_text
        out["service_scan"] = out["home_scan"]
        if service_url is None:
            notes.append("No separate %s service page found; the "
                         "homepage is the page checked for C2 and M4." % TOWN)

    # The service-area page for C2 is the town page when it exists,
    # otherwise the homepage (the page that names the town+ZIP, if any).
    if service_url and service_url.rstrip("/") != home_url.rstrip("/"):
        out["c2_url"] = service_url
        out["c2_scan"] = out["service_scan"]
        out["c2_html"] = out["service_html"]
    else:
        out["c2_url"] = home_url
        out["c2_scan"] = out["home_scan"]
        out["c2_html"] = home_html

    # A linked warranty page, if the homepage links to one.
    warranty_url = None
    warranty_text = ""
    if home_html:
        for href in re.findall(r'href=["\']([^"\']+)["\']', home_html, re.I):
            if "warranty" in href.lower():
                cand = urllib.parse.urljoin(home_url, href.strip())
                if urllib.parse.urlparse(cand).netloc == \
                        urllib.parse.urlparse(home_url).netloc:
                    warranty_url = cand
                    break
    if warranty_url:
        ev = F.fetch_url(warranty_url)
        if ev.accessible and ev.exact:
            warranty_text = F.html_to_text(ev.exact)
            notes.append("Warranty page fetched: %s" % warranty_url)
        else:
            notes.append("Warranty page linked but not readable: %s (%s)"
                         % (warranty_url, ev.reason))
    out["warranty_url"] = warranty_url
    out["warranty_text"] = warranty_text

    # A linked contact page, if the homepage links to one — the booking
    # route's next step is usually described there, not on the homepage.
    contact_url = None
    contact_text = ""
    if home_html:
        for href in re.findall(r'href=["\']([^"\']+)["\']', home_html, re.I):
            if "contact" in href.lower():
                cand = urllib.parse.urljoin(home_url, href.strip())
                if urllib.parse.urlparse(cand).netloc == \
                        urllib.parse.urlparse(home_url).netloc:
                    contact_url = cand
                    break
    if contact_url:
        ev = F.fetch_url(contact_url)
        if ev.accessible and ev.exact:
            contact_text = F.html_to_text(ev.exact)
            notes.append("Contact page fetched: %s" % contact_url)
        else:
            notes.append("Contact page linked but not readable: %s (%s)"
                         % (contact_url, ev.reason))
    out["contact_url"] = contact_url
    out["contact_text"] = contact_text

    # Linked Privacy Policy and Terms pages, if the homepage links to
    # them — the do-not-harvest check (Spec s.4.2) searches the footer,
    # Privacy Policy, Terms of Use, Contact page, and any anti-spam page.
    def _linked_page(keywords):
        if not home_html:
            return None, ""
        for href in re.findall(r'href=["\']([^"\']+)["\']', home_html, re.I):
            if any(k in href.lower() for k in keywords):
                cand = urllib.parse.urljoin(home_url, href.strip())
                if urllib.parse.urlparse(cand).netloc == \
                        urllib.parse.urlparse(home_url).netloc:
                    return cand, href
        return None, ""

    privacy_url, _ = _linked_page(("privacy",))
    privacy_text = ""
    if privacy_url:
        ev = F.fetch_url(privacy_url)
        if ev.accessible and ev.exact:
            privacy_text = F.html_to_text(ev.exact)
            notes.append("Privacy Policy page fetched: %s" % privacy_url)
        else:
            notes.append("Privacy Policy page linked but not readable: %s (%s)"
                         % (privacy_url, ev.reason))
    out["privacy_url"] = privacy_url
    out["privacy_text"] = privacy_text

    terms_url, _ = _linked_page(("terms", "terms-of-use", "terms-of-service"))
    terms_text = ""
    if terms_url:
        ev = F.fetch_url(terms_url)
        if ev.accessible and ev.exact:
            terms_text = F.html_to_text(ev.exact)
            notes.append("Terms page fetched: %s" % terms_url)
        else:
            notes.append("Terms page linked but not readable: %s (%s)"
                         % (terms_url, ev.reason))
    out["terms_url"] = terms_url
    out["terms_text"] = terms_text

    # Machine readability, from the site root (never the page URL).
    root = out["site_root"]
    out["robots"] = F.fetch_robots_txt(root)
    out["sitemap"] = F.fetch_sitemap(root, out["robots"])
    out["llms"] = F.fetch_llms_txt(root)

    # M2: key facts in the initial HTML, homepage and service page.
    def m2_for(fetch):
        # A page read via the page-text fallback is rendered text, not raw
        # HTML, so M2 cannot be checked on it — Not accessible, not Missing.
        if fetch.get("initial_via_fallback"):
            return {"accessible": False,
                    "reason": "initial HTML not read directly "
                    "(PROXY-REFUSED); page-text fallback is rendered text, "
                    "not raw HTML"}
        initial = fetch.get("initial_html")
        if initial is None or not initial.accessible or not initial.exact:
            return {"accessible": False,
                    "reason": "initial HTML could not be read"}
        return F.key_facts_in_html(initial.exact)

    out["home_m2"] = m2_for(home)
    out["service_m2"] = m2_for(out["service_fetch"])

    # M4: JSON-LD on the homepage and on the service page (both-pages rule).
    visible = {"name": site_name} if site_name else None
    out["home_json_ld"] = F.parse_json_ld(home_html or "", visible)
    if service_url and service_url.rstrip("/") != home_url.rstrip("/"):
        out["service_json_ld"] = F.parse_json_ld(
            out["service_html"] or "", visible)
    else:
        out["service_json_ld"] = None
    # M4: JSON-LD needs the raw HTML. A page read via the page-text
    # fallback is rendered text, not raw HTML, so its JSON-LD cannot be
    # checked — Not accessible, not Missing. (The both-pages rule means
    # M4 is Not accessible if either page used the fallback.)
    _fallback_reason = ("initial HTML not read directly (PROXY-REFUSED); "
                        "page-text fallback is rendered text, not raw HTML")
    if home.get("initial_via_fallback"):
        out["home_json_ld"] = {"accessible": False,
                               "reason": _fallback_reason}
    _svc_fetch = out["service_fetch"]
    if _svc_fetch is not home and _svc_fetch.get("initial_via_fallback"):
        out["service_json_ld"] = {"accessible": False,
                                  "reason": _fallback_reason}
    return out


def fetch_listing(place_id: str | None, notes: list) -> dict | None:
    """The Meta place record via the Places CLI, or None."""
    if not place_id:
        return None
    res = F.places_details(place_id)
    if not res.get("accessible"):
        notes.append("Places record %s not readable: %s"
                     % (place_id, res.get("reason", "")))
        return None
    record = res.get("record") or {}
    det = record.get("details") or record
    links = {l.get("type"): l.get("url") for l in det.get("links", [])}
    rating = det.get("rating") or {}
    addr = det.get("address") or {}
    cats = [c.get("display_name") for c in det.get("categories", []) if c.get("display_name")]
    desc = det.get("description") or ""
    listing = {
        "place_id": place_id,
        "name": det.get("name"),
        "address": addr,
        "city": (addr.get("city") or "").strip(),
        "phone": (det.get("phone_numbers") or {}).get("display_number"),
        "rating": rating.get("avg_rating"),
        "rating_count": rating.get("num_rating"),
        "rating_local_count": rating.get("num_local_rating"),
        "categories": cats,
        "description": desc,
        "opening_hours": det.get("opening_hours") or [],
        "is_permanently_closed": det.get("is_permanently_closed"),
        "is_temporarily_closed": det.get("is_temporarily_closed"),
        "links": links,
        "website_link": links.get("website"),
    }
    listing["text"] = " ".join([desc, " ".join(cats)]).strip()
    listing["scan"] = scan_text(listing["text"])
    listing["yelp_url"] = links.get("yelp")
    return listing


# ---------------------------------------------------------------------------
# Evidence assembly
# ---------------------------------------------------------------------------


def _bbb_evidence(claim: str | None, firm_name: str, notes: list) -> dict:
    """BBB claim vs bbb.org. bbb.org usually blocks automated reads; a
    blocked read is Not accessible, never worked around. If the search page
    does load, the firm's grade is only trusted when it appears next to
    the firm's name on that page. Returns the claim, whether bbb.org was
    readable, whether the rating is consistent with the claim, and whether
    the firm is BBB accredited on bbb.org (True / False / None when the
    read does not state it) — the engine needs accreditation as well as
    rating consistency for C3.2 BBB accreditation and rating consistent
    with bbb.org Complete (Spec s.4.3 rule 8)."""
    if not claim:
        return {"claim": None}
    res = F.fetch_bbb(firm_name, TOWN)
    if not res.get("accessible"):
        notes.append("bbb.org not readable for %s: %s"
                     % (firm_name, res.get("reason", "")))
        return {"claim": claim, "bbb_org_accessible": False,
                "reason": res.get("reason", "")}
    text = res.get("text", "")
    pos = norm_text(text).find(norm_text(firm_name))
    if pos < 0:
        notes.append("bbb.org search page loaded but did not return a "
                     "profile for %s." % firm_name)
        return {"claim": claim, "bbb_org_accessible": False,
                "reason": "bbb.org search page did not return this firm's profile"}
    window = text[max(0, pos - 100):pos + 400]
    grade = re.search(r"\b(A\+|A-|A|B\+|B-|B|C\+|C|D|F)\b", window)
    claim_grade = re.search(r"\b(A\+|A-|A|B\+|B-|B|C\+|C|D|F)\b", claim)
    wlow = window.lower()
    accredited = None
    if "not bbb accredited" in wlow or "not accredited" in wlow:
        accredited = False
    elif "bbb accredited" in wlow or "accredited since" in wlow:
        accredited = True
    if res.get("accredited") is not None:
        # The profile parse is the more reliable source when available.
        accredited = res["accredited"]
    if not grade and accredited is not True:
        return {"claim": claim, "bbb_org_accessible": False,
                "reason": "bbb.org profile found but no rating readable"}
    consistent = True
    bbb_org = window[:200].strip()
    if grade and claim_grade and grade.group(1) != claim_grade.group(1):
        consistent = False
    return {"claim": claim, "bbb_org_accessible": True,
            "consistent": consistent, "bbb_org": bbb_org,
            "accredited": accredited}


def _reviews_evidence(reviews_ev: dict) -> dict:
    """The C1.3 evidence shape from the Google/Yelp reader's review
    source (Birdeye preferred, the firm's own reviews page as fallback).
    The engine reads accessible / recurring_pattern / single_cluster;
    the source URL and method ride in the evidence note via the notes."""
    if not reviews_ev.get("accessible"):
        return {"accessible": False,
                "reason": reviews_ev.get("reason", "no review source readable")}
    return {"accessible": True,
            "recurring_pattern": reviews_ev.get("recurring_pattern"),
            "single_cluster": reviews_ev.get("single_cluster"),
            "reviews_read": reviews_ev.get("reviews_read"),
            "source": reviews_ev.get("source"),
            "url": reviews_ev.get("url"),
            "curated": bool(reviews_ev.get("curated"))}


# ---------------------------------------------------------------------------
# Delivery check (Spec s.4.2) — delivery only, never scored
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Addresses that are not a business contact (role/abuse accounts).
NON_BUSINESS_LOCAL = {"noreply", "donotreply", "no-reply", "abuse",
                      "postmaster", "mailer-daemon", "unsubscribe"}

# Do-not-harvest wording (Spec s.4.2, notice type 4). Two different
# notices, different effects: a term prohibiting harvesting or unsolicited
# commercial email BARS an advertising email; a CAN-SPAM-style notice
# that the site will not give/sell/transfer addresses warns against
# automated harvesting but does not by itself bar a single manual email.
PROHIBITING_PATTERNS = (
    r"do not harvest",
    r"harvest(?:ing)?[^.]{0,80}prohibit",
    r"prohibit[^.]{0,80}harvest",
    r"do not (?:use|send)[^.]{0,80}unsolicited",
    r"unsolicited[^.]{0,80}(?:prohibit|not permitted|may not|is not allowed)",
    r"no unsolicited (?:commercial )?email",
    r"do not send[^.]{0,80}unsolicited",
)
CAN_SPAM_STYLE_PATTERNS = (
    r"will not (?:give|sell|transfer|share|disclose)[^.]{0,80}(?:address|email|information)",
    r"do not sell[^.]{0,80}(?:personal )?(?:information|data)",
    r"we do not (?:sell|share|rent)[^.]{0,40}(?:your )?(?:personal )?(?:information|data)",
    r"will never (?:sell|share|give)[^.]{0,80}(?:address|email|information)",
)


def _find_emails(text: str) -> list:
    """Business contact emails in a block of text, in order, de-duplicated."""
    seen, out = set(), []
    for m in EMAIL_RE.finditer(text or ""):
        addr = m.group(0).lower()
        local = addr.split("@")[0]
        if local in NON_BUSINESS_LOCAL:
            continue
        if addr not in seen:
            seen.add(addr)
            out.append(addr)
    return out


def _notice_search(text: str, patterns) -> str:
    """The exact wording around the first matching notice pattern, or ''."""
    flat = " ".join((text or "").split())
    for pat in patterns:
        m = re.search(pat, flat, re.I)
        if m:
            start = max(0, m.start() - 60)
            end = min(len(flat), m.end() + 140)
            return flat[start:end].strip()
    return ""


def check_delivery(pages, firm: dict, run_date: str) -> dict:
    """The do-not-harvest check (Spec s.4.2), one record per audit.
    Delivery only: it never changes an Item, Category score, Grade,
    or High Priority count, and it is never shown on a
    card. A firm is never penalised for protecting its email address.

    Sources searched, in order: the website footer (homepage text), the
    Contact page, the Privacy Policy, and the Terms page. Collection
    method is recorded honestly: the harness reads pages automatically,
    so it is automated extraction.
    """
    home_text = (pages or {}).get("home_text") or ""
    contact_text = (pages or {}).get("contact_text") or ""
    privacy_text = (pages or {}).get("privacy_text") or ""
    terms_text = (pages or {}).get("terms_text") or ""
    contact_url = (pages or {}).get("contact_url")
    privacy_url = (pages or {}).get("privacy_url")
    terms_url = (pages or {}).get("terms_url")
    home_url = (pages or {}).get("home_url")

    contact_emails = _find_emails(contact_text)
    footer_emails = _find_emails(home_text)
    other_emails = _find_emails(privacy_text + "\n" + terms_text)
    all_emails = []
    for e in contact_emails + footer_emails + other_emails:
        if e not in all_emails:
            all_emails.append(e)

    # Primary email address (Spec s.4.2, decided order, no discretion).
    # Rule 1 needs a listing email, which the runner's listing extracts
    # do not carry — recorded as not applicable in this run.
    primary_email = ""
    primary_source = ""
    if len(contact_emails) == 1:
        primary_email, primary_source = contact_emails[0], contact_url
    elif len(contact_emails) > 1:
        primary_email, primary_source = "Multiple", contact_url
    elif len(footer_emails) == 1:
        primary_email, primary_source = footer_emails[0], home_url
    elif len(footer_emails) > 1:
        primary_email, primary_source = "Multiple", home_url
    else:
        primary_email, primary_source = "None", ""

    # Do-not-harvest notice: search footer, Privacy, Terms, Contact.
    # The footer/homepage text is searched first; Privacy and Terms next.
    sources = [(home_text, home_url, "footer/homepage"),
               (privacy_text, privacy_url, "Privacy Policy"),
               (terms_text, terms_url, "Terms"),
               (contact_text, contact_url, "Contact page")]
    prohibiting = ""
    prohibiting_page = ""
    can_spam_style = ""
    can_spam_page = ""
    for text, url, label in sources:
        if not text:
            continue
        if not prohibiting:
            hit = _notice_search(text, PROHIBITING_PATTERNS)
            if hit:
                prohibiting, prohibiting_page = hit, url or label
        if not can_spam_style:
            hit = _notice_search(text, CAN_SPAM_STYLE_PATTERNS)
            if hit:
                can_spam_style, can_spam_page = hit, url or label
    if prohibiting:
        notice_type = "prohibiting"
        notice_wording = prohibiting
        notice_page = prohibiting_page
    elif can_spam_style:
        notice_type = "can-spam-style"
        notice_wording = can_spam_style
        notice_page = can_spam_page
    else:
        notice_type = "none"
        notice_wording = ""
        notice_page = ""

    # Decision rule (Spec s.4.2). Advertising email may be sent only if a
    # published business email was found, no prohibiting notice was found,
    # and CAN-SPAM can be met. CAN-SPAM cannot be met in this run: AI
    # Sharc has no valid business postal address for a CAN-SPAM-compliant
    # footer (known gap since 2026-11-03), so the route is website
    # verification only for every firm in this run.
    email_found = bool(all_emails)
    if not email_found:
        route = "website verification only"
        route_reason = "no published business email found"
    elif notice_type == "prohibiting":
        route = "website verification only"
        route_reason = "prohibiting do-not-harvest notice found"
    else:
        route = "website verification only"
        route_reason = ("CAN-SPAM requirements cannot be met: no valid "
                        "business postal address for a CAN-SPAM-compliant "
                        "footer (known gap since 2026-11-03)")
    return {
        "firm_id": firm["firm_id"],
        "firm": firm["name"],
        "date_checked": run_date,
        "published_business_email": (
            primary_email if primary_email not in ("Multiple", "None")
            else (all_emails[0] if all_emails else "None")),
        "emails_found": all_emails,
        "primary_email": primary_email,
        "primary_email_source": primary_source or "",
        "primary_email_rule": ("Rule 1 (Contact + listing match) not "
                               "applicable — listing extracts carry no email; "
                               "Rule 2 (Contact page sole email) / Rule 3 "
                               "(footer sole email) / Rule 4 (Multiple/None) "
                               "applied as written"),
        "collection_method": "automated extraction (harness page read)",
        "do_not_harvest_notice_present": "Yes" if notice_type != "none" else "No",
        "notice_wording": notice_wording,
        "notice_wording_page": notice_page or "",
        "notice_type": notice_type,
        "can_spam_requirements_met": "No",
        "can_spam_note": route_reason if route_reason.startswith("CAN-SPAM")
                         else "CAN-SPAM postal address not available",
        "delivery_route": route,
        "delivery_route_reason": route_reason,
        "note": ("Delivery Check is internal only, not scored, and does not "
                 "change the grade. Published email: %s. Notice: %s. Route: %s (%s)."
                 % (primary_email, notice_type, route, route_reason)),
    }


def build_evidence(firm: dict, disc: dict, run_date: str) -> tuple:
    """Fetch everything for one firm and assemble the engine's evidence
    dict, a source-URL map per row, and a list of notes.

    Returns (evidence, source_map, notes, pages, listing, google_yelp).
    """
    # Point every town-dependent check at this firm's town (study runs:
    # town/zip come from the firm record; the original 19-firm
    # records carry no town, so the Coppell module defaults stand).
    set_town_context(firm.get("town") or TOWN,
                     firm.get("town_zip") or ZIP)
    notes = []
    firm_id = firm["firm_id"]
    website_url = disc.get("website", firm.get("website"))
    place_id = disc.get("place_id", firm.get("meta_place_id"))
    if disc:
        notes.append("Discovery: %s" % disc.get("source", ""))
        if disc.get("place_note"):
            notes.append("Discovery note: %s" % disc["place_note"])

    pages = None
    listing = fetch_listing(place_id, notes)
    if listing:
        notes.append("Listing: Meta place %s — %s, %s, phone %s, rating %s"
                     % (place_id, listing["name"], listing["city"],
                        listing["phone"], listing["rating"]))
        if listing["website_link"] and website_url and \
                site_root(listing["website_link"]) != site_root(website_url):
            notes.append("Listing website %s differs from the website used "
                         "%s (different site root)."
                         % (listing["website_link"], website_url))
    else:
        notes.append("No Meta listing readable for this firm "
                     "(place_id %s)." % (place_id or "none"))

    if website_url:
        pages = fetch_firm_pages(firm, website_url, notes)
        F.polite_sleep()
    else:
        notes.append("No firm website found — the firm is F under Spec s.5 "
                     "(no website at all); no Items are scored.")

    # --- Google / Yelp (evidence layer, re-run r2) ----------------------
    # The Yelp URL comes from the Meta place record's links, else a web
    # search; the page is read with the browser page-text service. Google
    # has no independent read on the available routes (see google_yelp).
    gy = GY.collect(firm, disc, listing,
                    pages["home_html"] if pages else "",
                    pages["home_url"] if pages else "", run_date,
                    town=TOWN)
    yelp = gy["yelp"]
    if yelp.get("accessible"):
        notes.append("Yelp: %s — %s, %s, phone %s, rating %s on %s reviews "
                     "(%s); install=%s repair=%s; categories: %s"
                     % (yelp["url"], yelp["name"], yelp["address"],
                        yelp["phone"], yelp["rating"], yelp["count"],
                        yelp.get("found_by", ""), yelp["has_install"],
                        yelp["has_repair"],
                        ", ".join(yelp["categories"]) or "none"))
        if yelp.get("founding_year_field") or yelp.get("founding_year_bio"):
            notes.append("Yelp founding years (NOT fed to C6.2 — flagged "
                         "for a human decision): field=%s, bio=%s"
                         % (yelp.get("founding_year_field"),
                            yelp.get("founding_year_bio")))
    else:
        notes.append("Yelp: not readable — %s" % yelp.get("reason", ""))
    notes.append("Google: %s" % ("independent read not available — " +
                                 gy["google"]["reason"]))
    reviews_ev = gy["reviews"]
    if reviews_ev.get("accessible"):
        notes.append("Reviews (%s): %s — %d reviews read, %d negative, "
                     "recurring=%s, single cluster=%s"
                     % (reviews_ev["source"], reviews_ev.get("url"),
                        reviews_ev.get("reviews_read"),
                        reviews_ev.get("negative_count"),
                        reviews_ev.get("recurring_pattern"),
                        reviews_ev.get("single_cluster")))
        if reviews_ev.get("curated"):
            notes.append("Reviews source is the firm's own reviews page "
                         "(republishing Google reviews; firm-curated).")
        if not reviews_ev.get("dates_shown", True):
            notes.append("Review extract shows no per-review dates or star "
                         "ratings; the pattern check is keyword-based on "
                         "the latest reviews shown.")
    else:
        notes.append("Reviews: not readable — %s" % reviews_ev.get("reason", ""))

    # --- combined scans -------------------------------------------------
    home_scan = pages["home_scan"] if pages else scan_text("")
    svc_scan = pages["service_scan"] if pages else scan_text("")
    c2_scan = pages["c2_scan"] if pages else scan_text("")
    w_scan = scan_text(pages["warranty_text"]) if pages and pages["warranty_text"] else scan_text("")
    contact_scan = scan_text(pages["contact_text"]) if pages and pages["contact_text"] else scan_text("")
    listing_scan = listing["scan"] if listing else scan_text("")
    # Pricing facts may sit on any of the firm's pages. Copy the service
    # scan (do not mutate it — C2 reads the service page only).
    price_scan = dict(svc_scan)
    for extra in (home_scan, w_scan, contact_scan):
        for key in ("diagnostic_amount", "diagnostic_text",
                    "diagnostic_mentioned", "free_estimate_install",
                    "free_estimate_repair", "free_estimate_text",
                    "quote_tool", "booking_text", "next_step",
                    "written_quote", "next_appointment", "emergency"):
            if not price_scan.get(key) and extra.get(key):
                price_scan[key] = extra[key]
    # All six lines, True/False — the engine counts the lines present and
    # names the missing ones, so the dict must carry every line, not only
    # the ones found.
    warranty_lines = {k: False for k in (
        "new_parts", "new_labour", "repair_parts_labour", "registration",
        "transferable", "claim_line")}
    for src in (svc_scan, home_scan, w_scan):
        for line, val in src["warranty_lines"].items():
            if val:
                warranty_lines[line] = True

    # Phones and names across sources.
    all_phones = []
    for src in (home_scan, svc_scan):
        all_phones.extend(src["phones"])
    if listing and listing["phone"]:
        all_phones.append(listing["phone"])
    if yelp.get("accessible") and yelp.get("phone"):
        all_phones.append(yelp["phone"])
    website_phones = []
    for src in (home_scan, svc_scan):
        website_phones.extend(src["phones"])
    if pages and pages.get("home_json_ld", {}).get("node", {}).get("telephone"):
        website_phones.append(
            str(pages["home_json_ld"]["node"]["telephone"]))
    site_name = pages["site_name"] if pages else None
    listing_name = listing["name"] if listing else None

    # Licence (website first, then the listing description).
    licence_no = svc_scan["licence"] or home_scan["licence"] or \
        listing_scan["licence"]
    if licence_no:
        notes.append("Licence published on the website: %s" % licence_no)

    # Hours: website day-by-day wins; otherwise the listing's partial hours.
    hours_day_by_day = home_scan["hours_day_by_day"] or \
        svc_scan["hours_day_by_day"]
    hours_text = svc_scan["hours_text"] or home_scan["hours_text"]
    listing_days = {h.get("day_of_week") for h in (listing["opening_hours"] if listing else [])}
    hours_partial = home_scan["hours_partial"] or svc_scan["hours_partial"] or bool(listing_days)
    if not hours_text and listing_days:
        hours_text = "Listing hours (partial): %s" % ", ".join(sorted(listing_days))
    emergency = svc_scan["emergency"] or home_scan["emergency"] or \
        listing_scan["emergency"]

    # Founding years per source. The firm's llms.txt is a firm-published
    # page on its own site, so a founding year stated there counts as a
    # website source (it is the same firm speaking, on its own domain).
    founding_years = {}
    for src_name, scan in (("website", home_scan), ("website", svc_scan),
                           ("meta", listing_scan)):
        if scan["founding_year"] is not None:
            founding_years.setdefault(src_name, scan["founding_year"])
    if pages and pages.get("llms", {}).get("body"):
        llms_scan = scan_text(pages["llms"]["body"])
        if llms_scan["founding_year"] is not None:
            founding_years.setdefault("website", llms_scan["founding_year"])
            notes.append("Founding year from the firm's llms.txt: %d"
                         % llms_scan["founding_year"])

    # Rating: Meta and Yelp are the independent platforms the harness
    # reads. Google has no independent read on the available routes (see
    # google_yelp); the website's own rating is the own-site claim.
    own_site_rating = svc_scan["rating"] if svc_scan["rating"] is not None \
        else home_scan["rating"]
    own_site_count = svc_scan["rating_count"] if svc_scan["rating_count"] is not None \
        else home_scan["rating_count"]
    rating_platforms = {}
    if listing:
        rating_platforms["meta"] = {
            "rating": listing["rating"], "count": listing["rating_count"],
            "accessible": True}
    if yelp.get("accessible"):
        rating_platforms["yelp"] = {
            "rating": yelp["rating"], "count": yelp["count"],
            "accessible": True}
    rating_platforms["google"] = {
        "rating": None, "count": None, "accessible": False}
    website_rating = None
    if own_site_rating is not None:
        website_rating = {"rating": own_site_rating, "count": own_site_count}

    # Service-area page evidence (C2). C2.1 is town+ZIP only (Spec s.6.2);
    # the former G3 address-in-or-near-town fallback is gone in v2.1.
    c2_page = {
        "accessible": bool(pages),
        "reason": "" if pages else "no website found; no service-area page readable",
        "names_town_zip": bool(c2_scan["names_town_zip"]),
        "install_repair_separate": bool(c2_scan["has_install"] and c2_scan["has_repair"]),
        "brands_listed": bool(c2_scan["brands"] and c2_scan["system_types"]),
        "phone_and_booking": bool(c2_scan["phones"] and
                                  (c2_scan["booking_text"] or c2_scan["phones"])),
    }
    if c2_scan["brands"] or c2_scan["system_types"]:
        notes.append("Service-area page brands: %s; system types: %s"
                     % (", ".join(c2_scan["brands"]) or "none",
                        ", ".join(c2_scan["system_types"]) or "none"))

    # G1 exact name and G6 verifiable listing are scored Items in v2.1
    # (Spec s.5). Names across the sources actually read.
    names = {}
    if site_name:
        names["website"] = site_name
    if listing_name:
        names["meta"] = listing_name
    if yelp.get("accessible") and yelp.get("name"):
        names["yelp"] = yelp["name"]
    # Closed flag (Spec s.5 F condition: closed / permanently closed).
    # Temporarily closed is NOT an F condition.
    closed_flag = None
    closed_permanently = False
    if listing:
        if listing["is_permanently_closed"]:
            closed_flag = "permanently closed (Meta listing)"
            closed_permanently = True
        elif listing["is_temporarily_closed"]:
            closed_flag = "temporarily closed (Meta listing)"
    # G6: a listing matches when the name matches the website (or the
    # firm record when there is no website), the listing phone is one the
    # website publishes (or the recorded phone), and an HVAC category is
    # present on the listing. Meta is tried first, then Yelp; the first
    # listing with no mismatch is the verifiable listing. When none
    # matches, the first checked listing carries its mismatch, so the
    # engine reports the reason instead of a bare Fail.
    def _listing_match(source: str, cand_name, cand_phone, cand_cats):
        """(candidate dict with source/name, mismatch or None) for one
        listing source."""
        name_ok = bool(site_name and cand_name and
                       norm_text(cand_name) == norm_text(site_name)) \
            or (not site_name and cand_name and
                norm_text(cand_name) == norm_text(firm["name"]))
        phone_ok = False
        phone_mismatch = ""
        if cand_phone:
            if website_phones:
                phone_ok = norm_phone(cand_phone) in \
                    {norm_phone(p) for p in website_phones}
                if not phone_ok:
                    phone_mismatch = "listing phone %s is not among the website phones (%s)" \
                        % (cand_phone, ", ".join(sorted(set(website_phones))) or "none")
            elif firm.get("phone_recorded"):
                phone_ok = norm_phone(cand_phone) == norm_phone(firm["phone_recorded"])
                if not phone_ok:
                    phone_mismatch = "listing phone %s does not match the recorded phone %s" \
                        % (cand_phone, firm["phone_recorded"])
        else:
            phone_mismatch = "listing publishes no phone"
        cats_low = " ".join(cand_cats or []).lower()
        hvac_cat = any(w in cats_low for w in ("heating", "air conditioning", "hvac"))
        # A generic trade category (Contractor, Local Service, Home
        # Improvement) is not a different trade — it just does not name
        # the trade. The category check fails only when every category is
        # a specific non-HVAC trade (e.g. only Plumbing Service for an
        # HVAC-only firm). Meta's category system has no "HVAC Contractor"
        # label; many HVAC firms list as plain "Contractor".
        generic_cat = any(w in cats_low for w in (
            "contractor", "local service", "home improvement"))
        cat_ok = hvac_cat or generic_cat
        mismatch = None
        if not name_ok:
            mismatch = "listing name %r does not match the website name %r" \
                % (cand_name, site_name or firm["name"])
        elif not phone_ok:
            mismatch = phone_mismatch
        elif not cat_ok:
            mismatch = "listing categories (%s) include no HVAC or generic trade category" \
                % ", ".join(cand_cats or [])
        cand = {"source": source, "name": cand_name}
        if mismatch:
            cand["mismatch"] = mismatch
        return cand

    listings_checked = []
    matching_listing = None
    first_mismatch = None
    if listing:
        listings_checked.append("meta")
        cand = _listing_match("meta", listing_name, listing["phone"],
                              listing["categories"])
        if "mismatch" not in cand:
            matching_listing = cand
        else:
            first_mismatch = cand
    if matching_listing is None and yelp.get("accessible"):
        listings_checked.append("yelp")
        cand = _listing_match("yelp", yelp["name"], yelp["phone"],
                              yelp["categories"])
        if "mismatch" not in cand:
            matching_listing = cand
        elif first_mismatch is None:
            first_mismatch = cand
    if matching_listing is None:
        matching_listing = first_mismatch

    # (No gates dict in v2.1: G1/G6 are scored Items below; G2/G3/G4/G5
    # are absorbed into C2.2/C2.1/C6.1+C2.4/C5.1+the F condition, Spec s.5.)

    # Items.
    bbb = _bbb_evidence(svc_scan["bbb_claim"] or home_scan["bbb_claim"],
                        firm["name"], notes)
    licence_ev = {"published": bool(licence_no)}
    if licence_no:
        licence_ev["number"] = licence_no
        lic_type = "Electrical Contractor" if licence_no.startswith("TECL") \
            else "A/C Contractor"
        reg = F.tdlr_lookup(licence_no, lic_type, run_date)
        licence_ev["register"] = reg
        notes.append("TDLR %s %s: accessible=%s active=%s (%s)"
                     % (lic_type, licence_no, reg.get("accessible"),
                        reg.get("active"), reg.get("note") or reg.get("reason", "")))
        F.polite_sleep()

    # M4: JSON-LD on both pages (or the homepage alone when there is no
    # separate service page — see the module docstring).
    home_ld = pages["home_json_ld"] if pages else {"accessible": False, "reason": "no website"}
    svc_ld = pages["service_json_ld"] if pages else None
    if svc_ld is None:
        m4 = {"accessible": home_ld.get("accessible", True),
              "present": bool(home_ld.get("present")),
              "mismatch": home_ld.get("mismatch"),
              "reason": home_ld.get("reason", "")}
        m4_pages = "homepage only (no separate service page)"
    else:
        m4 = {"accessible": bool(home_ld.get("accessible", True) and svc_ld.get("accessible", True)),
              "present": bool(home_ld.get("present") and svc_ld.get("present")),
              "mismatch": home_ld.get("mismatch") or svc_ld.get("mismatch"),
              "reason": ""}
        m4_pages = "homepage + service page"
    notes.append("M4 JSON-LD checked on %s: homepage present=%s, service page present=%s"
                 % (m4_pages, home_ld.get("present"),
                    svc_ld.get("present") if svc_ld is not None else "n/a"))

    # M2: key facts in the initial HTML, homepage and service page.
    m2_missing = set()
    m2_accessible = True
    m2_reason = ""
    for label, m2 in (("homepage", pages["home_m2"] if pages else None),
                      ("service page", pages["service_m2"] if pages else None)):
        if m2 is None:
            continue
        if not m2.get("accessible", True):
            m2_accessible = False
            m2_reason = "%s: %s" % (label, m2.get("reason", ""))
        else:
            m2_missing.update(m2.get("missing_facts") or [])

    items = {
        "C1.1": {"rating_platforms": rating_platforms,
                 "own_site_rating": ("%s on %s" % (own_site_rating, own_site_count)
                                     if own_site_rating is not None else None)},
        "C1.2": {"website_rating": website_rating,
                 "rating_platforms": rating_platforms},
        "C1.3": {"reviews": _reviews_evidence(reviews_ev)},
        "C2.1": {"town": TOWN, "zip": ZIP, "service_area_page": c2_page},
        "C2.2": {"service_area_page": c2_page},
        "C2.3": {"service_area_page": c2_page},
        "C2.4": {"service_area_page": c2_page},
        "C3.1": {"licence": licence_ev, "trade": "HVAC"},
        "C3.2": {"bbb": bbb},
        "C4.1": {"warranty": {"accessible": bool(pages),
                              "lines": {k: bool(v) for k, v in warranty_lines.items()},
                              "reason": "" if pages else "no website found"}},
        "C4.2": {"diagnostic_fee": {"accessible": bool(pages),
                                    "amount": price_scan["diagnostic_amount"],
                                    "mentioned": bool(price_scan["diagnostic_mentioned"]),
                                    "text": price_scan["diagnostic_text"] or ""}},
        "C4.3": {"free_estimate_install": {"accessible": bool(pages),
                                           "stated": bool(price_scan["free_estimate_install"]),
                                           "text": price_scan["free_estimate_text"] or ""}},
        "C4.4": {"free_estimate_repair": {"accessible": bool(pages),
                                          "stated": bool(price_scan["free_estimate_repair"]),
                                          "text": price_scan["free_estimate_text"] or ""}},
        "C5.1": {"hours": {"accessible": bool(pages or listing),
                           "day_by_day": hours_day_by_day,
                           "partial": hours_partial and not hours_day_by_day,
                           "text": hours_text or "",
                           # Verifiable 24-hour / emergency claim is an
                           # alternative Pass for C5.1 (Spec s.6.5).
                           "emergency_claim_verified": bool(emergency),
                           "emergency_claim": emergency or ""}},
        "C5.2": {"hours_consistency": {"accessible": bool(pages or listing),
                                       "verified_24h_claim": emergency if hours_day_by_day else None}},
        "C6.1": {"phones": all_phones},
        "C6.2": {"founding_years": founding_years},
        # G1 exact name and G6 verifiable listing are scored Items in v2.1.
        "G1": {"names": names},
        "G6": {"listings_checked": listings_checked,
               "matching_listing": matching_listing},
        "C7.1": {"robots_txt": pages["robots"] if pages else
                 {"accessible": False, "reason": "no website found"}},
        "C7.2": {"initial_html": {"accessible": m2_accessible,
                                  "missing_facts": sorted(m2_missing),
                                  "reason": m2_reason}},
        "C7.3": {"json_ld": m4},
        "C7.4": {"sitemap": pages["sitemap"] if pages else
                 {"accessible": False, "reason": "no website found"}},
    }

    # Ranking Suggestions (hard Observed rules, Spec s.4.3 rule 8, s.9).
    # The evidence key stays "levers" (internal only); the engine emits
    # them as Ranking Suggestion rows.
    levers = {
        "booking_route": {
            "accessible": bool(pages),
            "route": price_scan["booking_text"] or "",
            "next_step": price_scan["next_step"] or "",
            "written_quote": price_scan["written_quote"] or ""},
        "availability": {
            "accessible": bool(pages),
            "next_appointment": price_scan["next_appointment"] or "",
            "emergency_window": emergency or ""},
        "price": {
            "accessible": bool(pages),
            "diagnostic_fee": price_scan["diagnostic_amount"],
            "price_range": None,
            "written_quote_process": price_scan["written_quote"] or ""},
        "brand_coverage": {
            "accessible": bool(pages),
            "brands_listed": ", ".join(c2_scan["brands"]) if c2_scan["brands"] else ""},
        "dispatch": {"accessible": bool(pages)},
        "llms_txt": pages["llms"] if pages else
        {"accessible": False, "reason": "no website found"},
    }

    # Website Access minimum condition (Spec s.5, s.4.1.1): the engine
    # decides F / unverified / ok from these fields. `reason` is the
    # Inability to Access Website Reason code from the initial fetch
    # (e.g. DEAD, CERT-INVALID, PROXY-REFUSED, BLOCKED, or ""); `readable`
    # is whether any method produced text.
    website_unreadable = False
    website_reason = ""
    website_readable = False
    if pages:
        website_unreadable = bool(pages["home_fetch"].get("unreadable"))
        website_readable = bool(pages.get("home_text"))
        initial = pages["home_fetch"].get("initial_html")
        if initial is not None and not initial.accessible:
            m = re.match(r"\[([A-Z-]+)\]", initial.reason or "")
            website_reason = m.group(1) if m else ""
    evidence = {"website": {"unreadable": website_unreadable,
                            "reason": website_reason,
                            "readable": website_readable,
                            "has_website": bool(website_url),
                            "closed_flag": closed_flag,
                            "closed_permanently": closed_permanently},
                "items": items, "levers": levers}

    # Source URL per row (for audit-data.json).
    meta_ref = "Meta place %s" % place_id if place_id else "no Meta listing"
    yelp_ref = "Yelp %s" % yelp["url"] if yelp.get("accessible") else "Yelp not readable"
    reviews_ref = ("Birdeye %s" % reviews_ev["url"]
                   if reviews_ev.get("accessible") and
                   reviews_ev.get("source") == "birdeye"
                   else ("firm reviews page %s" % reviews_ev["url"]
                         if reviews_ev.get("accessible")
                         else "no review source readable"))
    home_url = pages["home_url"] if pages else ""
    svc_url = pages["service_url"] if pages else ""
    c2_url = pages["c2_url"] if pages else ""
    source_map = {
        "C1.1": "%s; %s" % (meta_ref, yelp_ref),
        "C1.2": "%s; %s; %s" % (home_url, meta_ref, yelp_ref),
        "C1.3": reviews_ref,
        "C2.1": c2_url, "C2.2": c2_url, "C2.3": c2_url, "C2.4": c2_url,
        "C3.1": "%s; TDLR data.texas.gov (dataset 7358-krk7)" % home_url,
        "C3.2": "%s; bbb.org" % home_url,
        "C4.1": (pages["warranty_url"] or c2_url) if pages else "",
        "C4.2": c2_url or home_url,
        "C4.3": c2_url or home_url,
        "C4.4": c2_url or home_url,
        "C5.1": "%s; %s" % (home_url, meta_ref),
        "C5.2": "%s; %s" % (home_url, meta_ref),
        "C6.1": "%s; %s" % (home_url, meta_ref),
        "C6.2": "%s; %s" % (home_url, meta_ref),
        "G1": "%s; %s; %s" % (home_url, meta_ref, yelp_ref),
        "G6": "%s; %s" % (meta_ref, yelp_ref),
        "C7.1": pages["robots"]["url"] if pages else "",
        "C7.2": home_url,
        "C7.3": "%s; %s" % (home_url, svc_url or "no separate service page"),
        "C7.4": pages["sitemap"].get("checked_url", "") if pages else "",
        "booking_route": home_url,
        "availability": home_url,
        "price": home_url,
        "brand_coverage": c2_url,
        "dispatch": c2_url,
        "llms_txt": pages["llms"]["url"] if pages else "",
    }
    return evidence, source_map, notes, pages, listing, gy


# ---------------------------------------------------------------------------
# Outputs (DESIGN.md s.7)
# ---------------------------------------------------------------------------

CATEGORY_NUM = {name: i + 1 for i, name in enumerate(CATEGORY_ORDER)}
FAILED_ITEM_RESULTS = ("Missing", "Conflict", "Not accessible")


def _fix_columns(row, defs: Definitions) -> tuple:
    """(Website change, Listing change, Operational change) for a row.

    Failed Items carry the fix direction (the Field Mapping
    pass_criteria) in the Website change column; this is a first pass —
    the card's Exact Fix text is written by the card build, not by the
    harness. Passed rows and totals carry '—'."""
    blank = ("—", "—", "—")
    if row.row_type == "Item" and row.result in FAILED_ITEM_RESULTS:
        fix = (defs.items.get(row.item_id) or {}).get("pass_criteria", "")
        return (fix or "—", "—", "—")
    return blank


def audit_data_rows(result, firm: dict, source_map: dict,
                    defs: Definitions) -> list:
    """The 36 engine rows in Spec s.13 column order."""
    rows = []
    for row in result.rows:
        if row.row_type == "Item":
            stage = "Stage 2 — AI Shopping Health"
            cat_gate = row.category
            item = "%s %s" % (row.item_id, row.label)
            key = row.item_id
            populates = "Category %d: %s" % (
                CATEGORY_NUM[row.category], row.category)
            counts = "High issue" if row.result in FAILED_ITEM_RESULTS \
                else "Item pass"
            priority = "High issue" if row.result in FAILED_ITEM_RESULTS else "—"
        elif row.row_type == "Category result":
            stage = "Stage 2 — AI Shopping Health"
            cat_gate = row.category
            item = "%s (total)" % row.category
            key = "Category:%s" % row.category
            populates = "Summary — Category %d: points subtotal" % (
                CATEGORY_NUM[row.category])
            counts = "No — category total, not an Item or issue"
            priority = "—"
        else:  # Ranking Suggestion
            # Section 4 suggestions (C3.2, C4.1) carry Stage "AI Shopping
            # Health" (Sample Audit Data Rev 4 — they are Section 4
            # suggestions; Spec s.9 covers only the six Section 6
            # suggestions, which carry the Ranking stage below). Their
            # Item text is the code-plus-description label from the
            # engine (row.label), e.g. 'C4.1 six-line warranty card'.
            if row.item_id in ("C3.2", "C4.1"):
                stage = "AI Shopping Health"
            else:
                stage = "Approximate Shopping Health Ranking — ranking suggestions, not scored"
            cat_gate = "Ranking Suggestion"
            item = row.label
            # Section 6 suggestions carry lever_id; Section 4 suggestions
            # (C3.2, C4.1) carry item_id — the source map is keyed by both.
            key = row.lever_id or row.item_id
            populates = "Ranking — suggestion"
            counts = "Ranking Suggestion — not scored"
            priority = "—"
        web, listing, operational = _fix_columns(row, defs)
        rows.append({
            "#": row.seq,
            "Firm": firm["name"],
            "Primary Business Category": PRIMARY_CATEGORY,
            "Query (service)": QUERY,
            "Town + ZIP searched": TOWN_ZIP,
            "Date checked": RUN_DATE,
            "Stage": stage,
            "Row type": row.row_type,
            "Report Card Category / Gate": cat_gate,
            "Item": item,
            "Item result": row.result,
            "Source URL": source_map.get(key, ""),
            "Evidence note": row.evidence,
            "Why it matters": row.why,
            "Website change": web,
            "Listing change": listing,
            "Operational change": operational,
            "Fix priority": priority,
            "Counts toward": counts,
            "Populates": populates,
        })
    return rows


def _run_record_primary_email(delivery: dict | None) -> tuple:
    """(primary_email, primary_email_source) for the run record, taken
    from the Delivery Check (Spec s.4.2) — Spec v2.6 s.13.

    The Delivery Check already determines the Primary email per audit;
    the run record reuses its values and never re-derives them. There
    is no Primary email for the run record when the check records
    Multiple/None (s.4.2 rule 4), when there is no delivery check, or
    when a prohibiting do-not-harvest notice bars collection of the
    address (notice_type 'prohibiting': a term prohibiting harvesting
    or unsolicited commercial email) — in those cases both fields are
    None, never an invented address. A can-spam-style notice is a
    warning against automated harvesting, not a bar on collection, so
    it does not null the address."""
    if not delivery:
        return None, None
    if delivery.get("notice_type") == "prohibiting":
        return None, None
    email = delivery.get("primary_email")
    if not email or email in ("Multiple", "None"):
        return None, None
    return email, delivery.get("primary_email_source") or None


def write_firm_outputs(out_dir: str, firm: dict, disc: dict, result,
                       source_map: dict, notes: list, defs: Definitions,
                       pages, listing, gy: dict | None = None,
                       out_root: str = "", delivery: dict | None = None) -> dict:
    """Per-firm outputs, Spec v2.6 s.13 file naming: all four files share
    the prefix <firm_id>__<query_id>__<vendor>-<product>__<timestamp>
    in runs/<YYYY-MM-DD>/<firm_id>/ — <prefix>__audit-data.json,
    <prefix>__summary.json, <prefix>__human-review.json,
    <prefix>__delivery-check.json."""
    os.makedirs(out_dir, exist_ok=True)
    town = (firm or {}).get("town") or TOWN
    zip_code = (firm or {}).get("town_zip") or ZIP
    query_id = build_query_id(derive_trade(firm), town, zip_code,
                              derive_task_number(firm, QUERY))
    prefix = audit_filename_prefix(firm["firm_id"], query_id, VENDOR,
                                   PRODUCT, FILENAME_TIMESTAMP)
    audit_filename = "%s__audit-data.json" % prefix
    summary_filename = "%s__summary.json" % prefix
    human_review_filename = "%s__human-review.json" % prefix
    delivery_filename = "%s__delivery-check.json" % prefix
    primary_email, primary_email_source = _run_record_primary_email(
        delivery)
    run_record = {
        "run_id": RUN_ID,
        "firm_id": firm["firm_id"],
        "firm": firm["name"],
        "group_2026": firm.get("group_2026"),
        "query": QUERY,
        "query_id": query_id,
        "town_zip": TOWN_ZIP,
        "checked_at": CHECKED_AT,
        "spec_version": SPEC_VERSION,
        "vendor": VENDOR,
        "product": PRODUCT,
        # Primary email (Spec v2.6 s.13): the Delivery Check's Primary
        # email for this audit, or None when there is none (see
        # _run_record_primary_email). Never re-derived here.
        "primary_email": primary_email,
        "primary_email_source": primary_email_source,
        "primary_business_category": PRIMARY_CATEGORY,
        "website": (pages["website_url"] if pages else None),
        "website_home": (pages["home_url"] if pages else None),
        "service_page": (pages["service_url"] if pages else None),
        "meta_place_id": (listing["place_id"] if listing else None),
        "harness": "run_audit.py (Spec v2.6); harness test only — no Report Card issued"
        + ("; output %s" % os.path.basename(out_root.rstrip("/"))
           if out_root else ""),
        # The loader's evidence_source: run file path + run id (Agg. s.2).
        "evidence_source": os.path.relpath(
            os.path.join(out_dir, audit_filename), HERE),
    }
    audit_data = {"run": run_record,
                  "rows": audit_data_rows(result, firm, source_map, defs)}
    with open(os.path.join(out_dir, audit_filename), "w", encoding="utf-8") as fh:
        json.dump(audit_data, fh, indent=2, sort_keys=False)
    summary = result.as_dict()
    summary["run"] = run_record
    summary["notes"] = notes
    if gy is not None:
        summary["google_yelp"] = {
            "yelp": {"accessible": bool(gy["yelp"].get("accessible")),
                     "url": gy["yelp"].get("url"),
                     "rating": gy["yelp"].get("rating"),
                     "count": gy["yelp"].get("count")},
            "google": {"accessible": False},
            "reviews": {"source": gy["reviews"].get("source"),
                        "accessible": bool(gy["reviews"].get("accessible")),
                        "url": gy["reviews"].get("url"),
                        "reviews_read": gy["reviews"].get("reviews_read"),
                        "negative_count": gy["reviews"].get("negative_count")},
        }
    with open(os.path.join(out_dir, summary_filename), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=False)
    not_accessible = [
        {"item_id": r.item_id, "label": r.label, "category": r.category,
         "evidence": r.evidence}
        for r in result.rows
        if r.row_type == "Item" and r.result == "Not accessible"]
    human_review = {
        "run": run_record,
        "needs_human": bool(result.human_review) or result.unverified,
        "human_review_rows": [r.as_dict() for r in result.human_review],
        "not_accessible_items": not_accessible,
        "notes": notes,
    }
    with open(os.path.join(out_dir, human_review_filename), "w", encoding="utf-8") as fh:
        json.dump(human_review, fh, indent=2, sort_keys=False)
    if delivery is not None:
        with open(os.path.join(out_dir, delivery_filename),
                  "w", encoding="utf-8") as fh:
            json.dump(delivery, fh, indent=2, sort_keys=False)
    return summary


# ---------------------------------------------------------------------------
# Validation (DESIGN.md s.8)
# ---------------------------------------------------------------------------


def validate(defs: Definitions) -> bool:
    """Dummy + Airtron validation, through the runner's own scoring path.

    Dummy (Example Heating, Final Rev 6 evidence, re-scored under v2.1):
    74/100, Grade A, 5 High, 16 passed Items, 36 rows, deterministic.
    (Spec s.11: as it stands the dummy scores 74, Grade A, because C3.2
    BBB accreditation and rating consistent with bbb.org and C4.1
    six-line warranty card no longer score and it passes G1 exact name
    and G6 verifiable listing as Items. The dummy card rebuild to Grade C
    is card work, not a harness change.) Airtron (recorded 25 Oct 2026
    evidence): the evidence-backed results reproduce exactly (C1.1
    Missing, C4.2 Not accessible; C3.2 Not checked and C4.1 Suggested
    as Section 4 Ranking Suggestions). The two test files are also run as
    subprocesses so their own assertions execute."""
    import subprocess
    ok = True
    for test_file in ("tests/test_dummy_scoring.py",
                      "tests/test_airtron_validation.py"):
        proc = subprocess.run([sys.executable, test_file],
                              capture_output=True, text=True, cwd=HERE)
        print("--- %s (exit %d) ---" % (test_file, proc.returncode))
        print(proc.stdout.strip())
        if proc.returncode != 0:
            print(proc.stderr.strip())
            ok = False

    sys.path.insert(0, os.path.join(HERE, "tests"))
    import test_dummy_scoring as dummy
    import test_airtron_validation as airtron

    r1 = score_audit("Example Heating & Air Conditioning",
                     QUERY, "Example Town, TX 75000", "2026-11-03",
                     dummy.ev, defs)
    r2 = score_audit("Example Heating & Air Conditioning",
                     QUERY, "Example Town, TX 75000", "2026-11-03",
                     dummy.ev, defs)
    deterministic = json.dumps(r1.as_dict(), sort_keys=True) == \
        json.dumps(r2.as_dict(), sort_keys=True)
    print("--- dummy through the runner's scoring path ---")
    print("grade=%s points=%d/100 high=%d passed=%d rows=%d "
          "deterministic=%s"
          % (r1.grade, r1.total_points,
             r1.high_issues, r1.passed_items, len(r1.rows), deterministic))
    if not (r1.grade == "A" and r1.total_points == 74
            and r1.high_issues == 5
            and r1.passed_items == 16 and len(r1.rows) == 36
            and deterministic):
        print("DUMMY VALIDATION FAILED")
        ok = False
    else:
        print("DUMMY VALIDATION PASSED")

    ev = airtron.airtron_evidence()
    ra = score_audit("Airtron Heating & Air Conditioning", QUERY, TOWN_ZIP,
                     "2026-10-25", ev, defs)
    by_item = {r.item_id: r for r in ra.rows if r.row_type == "Item"}
    by_s4 = {r.item_id: r for r in ra.section_4_suggestions}
    print("--- Airtron evidence-backed results through the runner ---")
    expected = {"C1.1": "Missing", "C4.2": "Not accessible"}
    for item_id, want in expected.items():
        got = by_item[item_id].result
        print("  %s: engine=%s expected=%s %s"
              % (item_id, got, want, "OK" if got == want else "MISMATCH"))
        if got != want:
            ok = False
    expected_s4 = {"C3.2": "Not checked", "C4.1": "Suggested"}
    for item_id, want in expected_s4.items():
        got = by_s4[item_id].result
        print("  %s (Section 4 Ranking Suggestion): engine=%s expected=%s %s"
              % (item_id, got, want, "OK" if got == want else "MISMATCH"))
        if got != want:
            ok = False
    print("AIRTRON VALIDATION %s" % ("PASSED" if ok else "FAILED"))
    return ok


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run_all(firm_ids: list | None = None, resume: bool = False,
            out_root_override: str | None = None,
            firms_file: str = "firms.json",
            discovery_file: str | None = "discovery.json") -> dict:
    """Run the firms and write runs/<date>/ (or out_dir when given).
    Returns the run summary.

    With resume=True, a firm whose <prefix>__summary.json already exists
    in the output dir (same date and spec version) is skipped — the run is
    idempotent, so a killed run can be resumed instead of restarted.
    firms_file selects the registry (study-firms.json for the 861-firm
    study, leaving the original 19-firm firms.json untouched);
    discovery_file None means no discovery overrides (study firms carry
    their website/place_id in the registry itself)."""
    defs = load_definitions()
    with open(os.path.join(HERE, firms_file), encoding="utf-8") as fh:
        registry = json.load(fh)
    if discovery_file:
        with open(os.path.join(HERE, discovery_file), encoding="utf-8") as fh:
            discovery = json.load(fh).get("discovered", {})
    else:
        discovery = {}
    firms = registry["firms"]
    if firm_ids:
        wanted = set(firm_ids)
        firms = [f for f in firms if f["firm_id"] in wanted]
        missing = wanted - {f["firm_id"] for f in firms}
        if missing:
            print("WARNING: unknown firm ids: %s" % ", ".join(sorted(missing)))
    out_root = out_root_override or os.path.join(HERE, "runs", RUN_DATE)
    os.makedirs(out_root, exist_ok=True)

    summaries = []
    for firm in firms:
        fid = firm["firm_id"]
        existing = find_output_file(os.path.join(out_root, fid), "summary")
        if resume and existing and os.path.exists(existing):
            try:
                with open(existing, encoding="utf-8") as fh:
                    done = json.load(fh)
                if done.get("date_checked") == RUN_DATE and \
                        done.get("spec_version") == SPEC_VERSION:
                    print("== %s (%s) == skipped (already done %s)"
                          % (firm["name"], fid, RUN_DATE))
                    done["firm_id"] = fid
                    done["town"] = firm.get("town") or TOWN
                    done["group_2026"] = firm.get("group_2026")
                    done["rank_2026"] = firm.get("rank_2026")
                    summaries.append(done)
                    continue
            except (ValueError, KeyError):
                pass
        print("== %s (%s) ==" % (firm["name"], fid))
        disc = discovery.get(fid, {})
        evidence, source_map, notes, pages, listing, gy = build_evidence(
            firm, disc, RUN_DATE)
        delivery = check_delivery(pages, firm, RUN_DATE)
        result = score_audit(firm["name"], QUERY, TOWN_ZIP, RUN_DATE,
                             evidence, defs, spec_version=SPEC_VERSION)
        out_dir = os.path.join(out_root, fid)
        summary = write_firm_outputs(out_dir, firm, disc, result,
                                     source_map, notes, defs, pages, listing,
                                     gy, out_root, delivery)
        summary["firm_id"] = fid
        summary["town"] = firm.get("town") or TOWN
        summary["group_2026"] = firm.get("group_2026")
        summary["rank_2026"] = firm.get("rank_2026")
        summaries.append(summary)
        print("  grade=%s points=%d/100 high=%d passed=%d "
              "human_review=%d not_accessible_items=%d"
              % (result.grade or "(unverified)", result.total_points,
                 result.high_issues,
                 result.passed_items, len(result.human_review),
                 sum(1 for r in result.rows
                     if r.row_type == "Item" and r.result == "Not accessible")))
        F.polite_sleep()

    # Eligible ranking (Spec s.8): eligible firms only (grade A-D); by
    # total points desc, then fewest High, then the 2026 rank as a
    # tiebreak. Not a Report Card. Ranked WITHIN each town (the
    # correlation study compares firms in the same town); a pooled
    # statewide rank would be meaningless across different competitor
    # sets. eligible_count is the town's eligible count.
    from aisharc_harness.rules.engine import percentile_rank, top_percent
    eligible = []
    towns = {}
    for s in summaries:
        towns.setdefault(s.get("town") or TOWN, []).append(s)
    for town_summaries in towns.values():
        town_eligible = [s for s in town_summaries
                         if s["grade"] not in ("F", "")]
        town_eligible.sort(key=lambda s: (
            -s["total_points"], s["high_issues"],
            s["rank_2026"] if s["rank_2026"] is not None else 99))
        for i, s in enumerate(town_eligible, start=1):
            s["eligible_rank"] = i
            s["eligible_count"] = len(town_eligible)
            s["top_percent"] = top_percent(i, len(town_eligible))
            s["percentile"] = percentile_rank(i, len(town_eligible))
        eligible.extend(town_eligible)
    for s in summaries:
        if s["grade"] in ("F", ""):
            s["eligible_rank"] = None
            s["eligible_count"] = len(
                [t for t in towns.get(s.get("town") or TOWN, [])
                 if t["grade"] not in ("F", "")])
            s["top_percent"] = None
            s["percentile"] = None
    # Re-write the summaries with the ranking attached. Use the exact
    # run-record prefix: one firm dir can hold several audits (different
    # query_id under audit-per-query), so the first-sorted file is the
    # WRONG file for a later query.
    for s in summaries:
        path = find_output_file_for_run(
            os.path.join(out_root, s["firm_id"]), "summary",
            s.get("run") or {})
        if path is None:
            raise FileNotFoundError(
                "no summary file found for %s in %s"
                % (s["firm_id"], out_root))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(s, fh, indent=2, sort_keys=False)

    report = write_run_report(out_root, summaries, eligible)
    return {"out_root": out_root, "summaries": summaries,
            "eligible": eligible, "report": report}


def write_run_report(out_root: str, summaries: list, eligible: list) -> str:
    """run-report.md: what was run, what was found, what could not be
    read, and what needs a human decision. Harness test, not a card."""
    lines = []
    # The study output root is runs/2026-11-14-study/audits/ — "study" is
    # in the run-dir name, not in the audits/ basename, so test the whole
    # path, not the basename.
    is_study = "study" in out_root
    if is_study:
        lines.append("# Texas HVAC correlation study — audit run (Stage 2a)")
        lines.append("")
        lines.append("**Run date:** %s · **Run id:** %s · **Spec:** v%s · "
                     "**Query:** %s"
                     % (RUN_DATE, RUN_ID, SPEC_VERSION, QUERY))
        lines.append("")
        lines.append("**Spec v2.6 (100-point model):** 21 scored Items, 36 rows "
                     "(7 Category results + 21 Items + 8 Ranking "
                     "Suggestions); no Gate rows; F only for Website Access "
                     "or not in business. Eligible ranks are WITHIN each town.")
        lines.append("")
        lines.append("**A#1 Air (a-1-air, Lewisville):** also audited in r3 "
                     "for Coppell (firm_id a1-air). This study audit is a "
                     "fresh audit for Lewisville; the analysis should note "
                     "it holds both an r3 audit and a study audit.")
        lines.append("")
        lines.append("Harness test only. No Report Card was issued to any "
                     "firm, no firm was contacted. Grades below are the "
                     "harness's fresh-audit output for this run, not client "
                     "grades. Eligible ranks are WITHIN each town.")
        lines.append("")
    else:
        lines.append("# AI Sharc harness — 19-firm test run")
        lines.append("")
    if "r2" in os.path.basename(out_root.rstrip("/")):
        lines.append("**Re-run r2 — Google/Yelp reader wired in "
                     "(Yelp listing + Birdeye reviews; Google still has no "
                     "independent read). First run: runs/2026-11-11/.**")
        lines.append("")
    if "2026-11-13" in os.path.basename(out_root.rstrip("/")):
        lines.append("**Run r3 — production-fields plan built (13 Nov 2026): "
                     "MUSE-SPARK agent observation (one call per query/town, "
                     "LLM scorer, one muse-observation.json per firm), "
                     "delivery-check output (Spec s.4.2), run id + "
                     "evidence_source in the run record, DB tables + loader. "
                     "Previous runs: r1 runs/2026-11-11/ (all 19 F, 0 "
                     "eligible), r2 runs/2026-11-11-r2/ (2 eligible).**")
        lines.append("")
    if not is_study:
        lines.append("**Run date:** %s · **Spec:** v%s · **Query:** %s · "
                     "**Town + ZIP:** %s" % (RUN_DATE, SPEC_VERSION, QUERY, TOWN_ZIP))
        lines.append("")
        lines.append("Harness test only. No Report Card was issued to any firm, "
                     "no firm was contacted, and the 25 Oct 2026 results were "
                     "used as historical evidence only (Spec s.4.3 rule 9). "
                     "Grades below are the harness's fresh-audit output for "
                     "this run, not client grades.")
        lines.append("")
    lines.append("## Validation")
    lines.append("")
    lines.append("Run `python3 run_audit.py --validate` for the current "
                 "validation output. The dummy firm scores 74/100, Grade A, "
                 "5 High, 16 passed Items, 36 rows, deterministic; the "
                 "Airtron recorded evidence reproduces the evidence-backed "
                 "results exactly (C1.1 Missing, C4.2 Not accessible; C3.2 "
                 "Not checked and C4.1 Suggested as Section 4 Ranking "
                 "Suggestions).")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    if is_study:
        from collections import Counter
        dist = Counter(s["grade"] for s in summaries)
        pts = Counter(s["total_points"] for s in summaries)
        lines.append("**Grade distribution:** %s"
                     % ", ".join("%s: %d" % (g, dist.get(g, 0))
                                 for g in ("A", "B", "C", "D", "F")))
        lines.append("")
        lines.append("**Total points (out of 100): min %d, max %d.**"
                     % (min(pts) if pts else 0, max(pts) if pts else 0))
        lines.append("")
        lines.append("### Per-town completion")
        lines.append("")
        lines.append("| Town | Firms | Eligible (not F) |")
        lines.append("|---|---|---|")
        per_town = {}
        for s in summaries:
            per_town.setdefault(s.get("town") or "?", []).append(s)
        for town in sorted(per_town):
            ts = per_town[town]
            lines.append("| %s | %d | %d |"
                         % (town, len(ts),
                            sum(1 for s in ts if s["grade"] not in ("F", ""))))
        lines.append("")
    lines.append("| Firm | Grade | Points | High | Passed Items | "
                 "Eligible rank |")
    lines.append("|---|---|---|---|---|---|")
    order = sorted(summaries, key=lambda s: (
        s["grade"] in ("F", ""),
        -(s["total_points"]),
        s["high_issues"]))
    for s in order:
        rank = ("%d of %d" % (s["eligible_rank"], s["eligible_count"])
                if s.get("eligible_rank") else "— (not eligible)")
        lines.append("| %s | %s | %d/100 | %d | %d | %s |"
                     % (s["firm"], s["grade"] or "(unverified)", s["total_points"],
                        s["high_issues"],
                        s["passed_items"], rank))
    lines.append("")
    if is_study:
        lines.append("Eligible firms: %d of %d (not F). Eligible ranks "
                     "are within each town (the correlation compares firms "
                     "in the same town); the pooled count above is a "
                     "statewide total only." % (len(eligible), len(summaries)))
    else:
        lines.append("Eligible firms: %d of %d (not F). The eligible "
                     "ranking is by total points, then fewest High, then "
                     "the 2026 rank as a tiebreak." % (len(eligible), len(summaries)))
    lines.append("")
    lines.append("## Google/Yelp reader")
    lines.append("")
    yelp_ok = [s for s in summaries
               if (s.get("google_yelp") or {}).get("yelp", {}).get("accessible")]
    reviews_ok = [s for s in summaries
                  if (s.get("google_yelp") or {}).get("reviews", {}).get("accessible")]
    g2_pass = [s for s in summaries
               if any(r.get("item_id") == "C2.2" and r["result"] == "Pass"
                      for r in s["rows"] if r["row_type"] == "Item")]
    c13_na = [s for s in summaries
              if any(r["item_id"] == "C1.3" and r["result"] == "Not accessible"
                     for r in s["rows"] if r["row_type"] == "Item")]
    lines.append("- **Yelp listing read for %d of %d firms** (browser page-text "
                 "service; direct HTTP to yelp.com returns 403). The Yelp "
                 "description/specialties text is supporting evidence for "
                 "C2.2 install and repair (service-page only in v2.1), and "
                 "the Yelp rating is the second independent platform for "
                 "C1.1/C1.2." % (len(yelp_ok), len(summaries)))
    lines.append("- **Reviews read for %d of %d firms** (Birdeye profile, "
                 "republishing Google reviews, preferred; the firm's own "
                 "reviews page as fallback). C1.3 is Not accessible for %d "
                 "firms." % (len(reviews_ok), len(summaries), len(c13_na)))
    lines.append("- **C2.2 passes for %d of %d firms** (first run: 0/19)."
                 % (len(g2_pass), len(summaries)))
    lines.append("- **Google has no independent read** on the routes available "
                 "to this build: the Google Business Profile page is a "
                 "JavaScript app with no extractable page text, and web search "
                 "only returns the firm's own site quoting its Google rating "
                 "(the firm's claim, already captured by the website scan). "
                 "A Google read needs a Places API key or a renderer.")
    lines.append("")
    lines.append("## Agent observation (MUSE-SPARK)")
    lines.append("")
    obs_path = os.path.join(out_root, "muse-spark-observation.json")
    if os.path.exists(obs_path):
        with open(obs_path, encoding="utf-8") as fh:
            run_obs = json.load(fh)
        lines.append("- **Agent call:** response %s, %d web_search calls, "
                     "%d results, %d citations from %d distinct URLs, "
                     "cost $%.4f; scorer calls $%.4f; total $%.4f."
                     % (run_obs.get("response_id"),
                        run_obs.get("web_search_calls", 0),
                        run_obs.get("web_search_results", 0),
                        run_obs.get("url_citation_count", 0),
                        len(run_obs.get("distinct_urls") or []),
                        run_obs.get("cost_usd", 0) or 0,
                        run_obs.get("scorer_total_cost_usd", 0) or 0,
                        run_obs.get("total_cost_usd", 0) or 0))
        lines.append("- **Firms named by the agent (%d of %d):** %s."
                     % (len(run_obs.get("firms_named") or []),
                        len(summaries),
                        ", ".join(run_obs.get("firms_named") or []) or "none"))
        lines.append("- **Named, not in the cohort:** %s."
                     % (", ".join(run_obs.get("firms_named_not_in_cohort") or [])
                        or "none"))
        union = set()
        per_firm = []
        for s in summaries:
            opath = os.path.join(out_root, s["firm_id"],
                                 "muse-observation.json")
            if os.path.exists(opath):
                with open(opath, encoding="utf-8") as fh:
                    obs = json.load(fh)
                passed = [i["item_id"] for i in obs["items"]
                          if i["result"] == "Pass"]
                union.update(passed)
                per_firm.append((s["firm"], len(passed), passed))
        lines.append("- **Items demonstrated by the agent (union across "
                     "named firms, %d):** %s."
                     % (len(union), ", ".join(sorted(union)) or "none"))
        for firm, n, passed in sorted(per_firm, key=lambda t: -t[1]):
            lines.append("  - %s: %d Items Pass (%s)."
                         % (firm, n, ", ".join(passed) or "none"))
        lines.append("- **The observation never changes the grade** "
                     "(Design s.9.3). It is recorded per firm in "
                     "muse-observation.json and loaded into "
                     "agent_observations / agent_observation_rows.")
    else:
        lines.append("- No agent observation in this run directory yet — "
                     "run `python3 run_agent.py --run` (one call per "
                     "query/town, then the scorer) before the run report "
                     "is final.")
    lines.append("")
    lines.append("## Delivery check (Spec s.4.2)")
    lines.append("")
    dc = []
    for s in summaries:
        dpath = find_output_file_for_run(
            os.path.join(out_root, s["firm_id"]), "delivery-check",
            s.get("run") or {})
        if dpath and os.path.exists(dpath):
            with open(dpath, encoding="utf-8") as fh:
                dc.append(json.load(fh))
    if dc:
        n_email = sum(1 for d in dc if d.get("primary_email")
                      not in ("", "None", "Multiple"))
        n_prohib = sum(1 for d in dc if d.get("notice_type") == "prohibiting")
        n_style = sum(1 for d in dc if d.get("notice_type") == "can-spam-style")
        lines.append("- **Delivery check written for %d of %d firms.** "
                     "Primary email found for %d; prohibiting "
                     "do-not-harvest notice for %d; CAN-SPAM-style notice "
                     "for %d. **Advertising email is website verification "
                     "only for every firm in this run** — CAN-SPAM cannot "
                     "be met (no valid business postal address for a "
                     "CAN-SPAM-compliant footer, known gap since "
                     "2026-11-03)."
                     % (len(dc), len(summaries), n_email, n_prohib, n_style))
        for d in dc:
            lines.append("  - %s: primary email %s; notice %s; route %s."
                         % (d["firm"], d.get("primary_email") or "none",
                            d.get("notice_type"), d.get("delivery_route")))
    else:
        lines.append("- No delivery-check output in this run directory.")
    lines.append("")
    lines.append("## What could not be read (remaining systematic gaps)")
    lines.append("")
    lines.append("- **BBB (C3.2 BBB accreditation and rating consistent "
                 "with bbb.org, a Section 4 Ranking Suggestion, not "
                 "scored):** bbb.org blocks automated reads in most cases, "
                 "so a published BBB claim is recorded as Not checked "
                 "(claim not independently read on bbb.org).")
    lines.append("- **No headless-browser renderer is installed**, so the "
                 "rendered-page read of the two-method rule (Spec s.4.1.1) "
                 "is recorded as not attempted, not as a failure. A site "
                 "whose initial HTML fails therefore has no readable text "
                 "in this run, and the audit is unverified for that firm "
                 "(no grade assigned until a re-check verifies the site), "
                 "not F.")
    lines.append("")
    lines.append("## Human-review queue")
    lines.append("")
    for s in order:
        flagged = [r for r in s["rows"] if r["human_review"]]
        na = [r for r in s["rows"]
              if r["row_type"] == "Item" and r["result"] == "Not accessible"]
        lines.append("### %s — %s, %d/100, %d High"
                     % (s["firm"], s["grade"] or "(unverified)", s["total_points"],
                        s["high_issues"]))
        lines.append("")
        if flagged:
            for r in flagged:
                lines.append("- **%s** (%s): %s"
                             % (r["label"], r["row_type"], r["review_reason"]))
        else:
            lines.append("- No human-review flags.")
        if na:
            lines.append("- Not accessible Items (%d): %s."
                         % (len(na), ", ".join(
                             r["item_id"] for r in na)))
        lines.append("")
    lines.append("## Per-firm notes")
    lines.append("")
    for s in order:
        lines.append("### %s" % s["firm"])
        lines.append("")
        for note in s.get("notes", []):
            lines.append("- %s" % note)
        lines.append("")
    path = os.path.join(out_root, "run-report.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Sharc harness runner")
    parser.add_argument("--validate", action="store_true",
                        help="dummy + Airtron validation only")
    parser.add_argument("--run", action="store_true",
                        help="run the firms in the firms file "
                        "(default: the 19-firm test)")
    parser.add_argument("--firms", default="",
                        help="comma-separated firm ids (subset of the firms file)")
    parser.add_argument("--firms-file", default="firms.json",
                        help="firm registry file (default firms.json; "
                        "study-firms.json for the 861-firm study)")
    parser.add_argument("--discovery-file", default="discovery.json",
                        help="discovery overrides file; pass NONE for no "
                        "discovery overrides (study runs)")
    parser.add_argument("--resume", action="store_true",
                        help="skip firms whose <prefix>__summary.json "
                        "already exists for this date and spec version")
    parser.add_argument("--out-dir", default="",
                        help="output root (default runs/<RUN_DATE>); use "
                        "runs/2026-11-11-r2 for a re-run that must not "
                        "overwrite the first run")
    parser.add_argument("--vendor", default=VENDOR,
                        help="Vendor (corporation) that gathered the audit "
                        "data, e.g. Meta, OpenAI, AI Sharc "
                        "(default: AI Sharc)")
    parser.add_argument("--product", default=PRODUCT,
                        help="Product (tool/agent) that gathered the audit "
                        "data, e.g. MUSE-SPARK, Meta AI, harness "
                        "(default: harness)")
    args = parser.parse_args()
    set_agent_context(args.vendor, args.product)
    if args.validate:
        defs = load_definitions()
        ok = validate(defs)
        sys.exit(0 if ok else 1)
    if args.run:
        firm_ids = [f.strip() for f in args.firms.split(",") if f.strip()] \
            or None
        result = run_all(firm_ids, resume=args.resume,
                         out_root_override=args.out_dir or None,
                         firms_file=args.firms_file,
                         discovery_file=(None if args.discovery_file == "NONE"
                                         else args.discovery_file))
        print()
        print("Run complete. Outputs in %s" % result["out_root"])
        print("Report: %s" % result["report"])
        return
    parser.print_help()
    sys.exit(2)


if __name__ == "__main__":
    main()
