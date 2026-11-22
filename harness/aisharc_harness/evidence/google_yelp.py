"""Google / Yelp listing + review reader — AI Sharc harness, Spec v1.22 s.14.

Reads the two independent listing platforms the first 19-firm run could not
read (only the Meta place record was read). It fixes five things at once:

  G2   Services in plain words — the Places CLI record never carries
       install/repair as separate services; read them from the Yelp
       listing text (description / specialties / bio) instead.
  C1.1 Rating figures — Yelp rating + review count (independent platform).
  C1.2 Rating figures consistent — a second platform's figures to compare
       against the website claim and Meta.
  C1.3 Customer review analysis — review text (Birdeye, republishing
       Google reviews; the firm's own reviews page as a fallback) so the
       engine can check for a recurring unaddressed complaint pattern.
  G1/G6 Exact name / Verifiable listing — a second independent listing
       source beyond Meta.

HOW THE DATA IS READ (in order, per source):
  * Yelp business page — the URL comes from the Meta place record's links
    (type "yelp") where present, else from a web search. The page is read
    with the browser page-text service (`browser-service --operation open`),
    which returns the page's structured extract (name, categories, address,
    phone, hours, rating, review count, bio/specialties). A direct HTTP
    fetch of yelp.com returns HTTP 403 from this environment, so direct
    HTTP is NOT used for Yelp: the page is publicly readable in a browser
    and the page-text service is the browser route, not a workaround — the
    read is recorded with its method, source URL, and date, and no
    login/paywall/CAPTCHA is bypassed.
  * Google Business Profile — read with the headless renderer
    (`fetch_google_listing`, added 2026-11-16): the Maps page is a
    JavaScript app, so the direct fetcher gets no usable HTML and the
    browser page-text service returns no extractable content (verified
    2026-11-11 and again 2026-11-16). A real browser is the only route
    that can read it — the same public page a Shopping Agent reads. The
    renderer is currently blocked by the egress proxy in this
    environment (it refuses the renderer's network traffic for every
    host), so the Google read is Not accessible with that reason until
    the platform allows it; the code is ready for that environment.
    Web search only returns the firm's own site quoting its Google
    rating, which is the firm's claim, not an independent read.
  * Birdeye profile — web search finds the reviews.birdeye.com profile;
    the page is read with the browser page-text service. Birdeye republishes
    Google reviews and the profile states whether the business claimed it,
    so it is independent of the firm. The extract shows the overall rating,
    the review count, and the latest review texts (no per-review dates or
    star ratings in the extract — recorded as a limitation).
  * The firm's own reviews page — fallback for C1.3 when no Birdeye
    profile is found: a /reviews (or testimonials) page linked from the
    homepage, fetched by plain HTTP. It republishes Google reviews but is
    firm-curated, so the evidence note says so.

COMPLAINT-PATTERN ANALYSIS (C1.3, judgment calls — flagged in the report):
  A review is negative when its text contains complaint keywords. Reviews
  are grouped by complaint theme (pricing, no-show/late, professionalism,
  repair quality, mess/damage, billing, warranty, trust). A review that is
  followed by a business response on the page counts as addressed.
  * >= 3 unaddressed negative reviews sharing one theme -> recurring_pattern
    (the engine reads this as Missing).
  * 2 unaddressed negatives, or >= 3 unaddressed negatives with no shared
    theme -> single_cluster (the engine reads this as Pass with warning).
  * 0-1 negative reviews -> no pattern (Pass).
  The analysis is keyword-based on the small "latest reviews" sample the
  extract shows; it is not a full review census. The evidence note records
  how many reviews were read and from where.

WHAT IS DELIBERATELY NOT FED TO THE ENGINE (flagged for Tim):
  * Yelp founding year — Yelp's bio and its "Year Established" field can
    disagree with each other and with the website (Eric's: bio 2015,
    "Year Established" 2025, website "Founded: 2024"). Wiring it into C6.2
    would create Missings on a noisy source; it is recorded in the notes
    only, for a human decision.
  * Yelp hours — recorded in the notes only; C5.1/C5.2 keep the
    website/listing hours they already use.

GUARDRAILS (Spec s.14 / C-08): only publicly accessible, non-login data.
No bypassing a login, paywall, CAPTCHA, or bot blocker. If a source returns
a block (403/429/CAPTCHA), the read stops on that source and the Item is
Not accessible with the reason — no retry through another route, no rate
lowering to continue. Ordinary request rates (1s polite delay between
calls, via fetchers.polite_sleep). Every confirmed fact carries method +
source URL + date + exact wording/figure, or it is Not accessible.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import date
from typing import Any, Dict, List, Optional

from . import fetchers as F
from ..rules.engine import norm_phone, norm_text

BROWSER_SERVICE = "/opt/hatch/bin/browser-service"
WEB_SEARCH = "/opt/hatch/bin/web-search"
SUBPROCESS_TIMEOUT_S = 120


def today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Scriptable routes: web search + browser page-text service
# ---------------------------------------------------------------------------


def _strip_line_numbers(text: str) -> str:
    """Strip the browser-service line-number prefixes ('L12: ') that the
    page-text service puts at the start of every extract line. Without
    this, field regexes anchored at line start never match, and wrapped
    bio text carries a stray 'L55:' mid-sentence."""
    return re.sub(r"^L\d+:\s?", "", text, flags=re.M)


def web_search(query: str) -> str:
    """Public web search (Brave on Railway, the Muse CLI on Muse; see search.py).
    Returns the result text, or "" when the search fails."""
    from aisharc_harness.evidence import search
    return _strip_line_numbers(search.search_text(query))


def browser_open(url: str) -> str:
    """Page-text read via the browser service CLI. Returns the page text
    (structured extract), or "" when the page has no extractable content
    or the read fails. This is the browser route — the same route the
    October 2026 manual research used — not a scrape around a block."""
    try:
        out = subprocess.run(
            [BROWSER_SERVICE, "--operation", "open", "--url", url],
            capture_output=True, text=True,
            timeout=SUBPROCESS_TIMEOUT_S)
    except (subprocess.SubprocessError, OSError):
        return ""
    if out.returncode != 0:
        return ""
    return _strip_line_numbers(out.stdout or "")


# ---------------------------------------------------------------------------
# Yelp
# ---------------------------------------------------------------------------

_YELP_BIZ_RE = re.compile(r"https://www\.yelp\.com/biz/[A-Za-z0-9_-]+")


def find_yelp_urls(firm_name: str, town: str = "Coppell") -> List[str]:
    """The firm's Yelp business URLs from a web search, in order. The
    search can return a different location of the same firm (e.g. Airtron
    Austin for Airtron Dallas), so callers must verify each candidate's
    name before using it."""
    text = web_search("%s Yelp %s TX" % (firm_name, town))
    if not text:
        return []
    seen, out = set(), []
    for m in _YELP_BIZ_RE.finditer(text):
        if m.group(0) not in seen:
            seen.add(m.group(0))
            out.append(m.group(0))
    return out


def _name_matches(page_name: Optional[str], firm_name: str) -> bool:
    """The page's business name is the firm: equal after normalisation,
    or the firm name is a substring of the page name (e.g. 'A#1 Air' in
    'A#1 Air Conditioning'). A different location/brand ('Airtron Austin'
    for 'Airtron Heating & Air Conditioning') does NOT match. Fail closed:
    no extractable name means no match."""
    if not page_name:
        return False
    page, firm = norm_text(page_name), norm_text(firm_name)
    return page == firm or firm in page


def _field(text: str, label: str) -> Optional[str]:
    m = re.search(r"^%s:\s*(.+?)\s*$" % re.escape(label), text,
                  re.M)
    return m.group(1).strip() if m else None


def parse_yelp_text(text: str, url: str) -> Dict[str, Any]:
    """Parse the browser-service extract of a Yelp business page.

    The extract is a structured dump: 'Information about <name>',
    'Primary Category:', 'Address:', 'Phone:', 'Hours' (day lines),
    '### Ratings for <name>' with 'Rating: X stars' / 'Based on N reviews',
    '### Attributes' with 'Bio:', 'Specialties:', 'Year Established:'.
    Returns the listing facts, or {"accessible": False} when the text is
    not a Yelp business extract."""
    if not text or "Information about" not in text:
        return {"accessible": False, "url": url,
                "reason": "Yelp page had no extractable content"}
    name = None
    m = re.search(r"## Information about (.+?)\s*$", text, re.M)
    if m:
        name = m.group(1).strip()
    rating = None
    m = re.search(r"Rating:\s*(\d(?:\.\d)?)\s*stars", text)
    if m:
        rating = float(m.group(1))
    count = None
    m = re.search(r"Based on ([\d,]+) reviews?", text)
    if m:
        count = int(m.group(1).replace(",", ""))
    address = _field(text, "Address")
    phone = _field(text, "Phone")
    city = None
    if address:
        m = re.search(r",\s*([A-Za-z][A-Za-z ]+?),\s*TX\b", address)
        if m:
            city = m.group(1).strip()
    categories = []
    primary = _field(text, "Primary Category")
    if primary:
        categories.append(primary)
    other = _field(text, "Other Categories")
    if other:
        categories.extend([c.strip() for c in other.split(",") if c.strip()])
    # Services in plain words: the bio + specialties text.
    services_text = ""
    m = re.search(r"Bio:\s*(.+?)(?:\nYear Established:|\n### |\Z)",
                  text, re.S)
    if m:
        services_text += " " + m.group(1).strip()
    m = re.search(r"Specialties:\s*(.+?)(?:\nYear Established:|\n### |\Z)",
                  text, re.S)
    if m:
        services_text += " " + m.group(1).strip()
    services_text = re.sub(r"\s+", " ", services_text).strip()
    # Install/repair as separate services, in plain words.
    low = services_text.lower()
    has_install = bool(re.search(r"\binstall(?:ation|ing|ed|s)?\b|\breplacement\b", low))
    has_repair = bool(re.search(r"\brepair(?:ing|ed|s)?\b", low))
    founding_year = None
    m = re.search(r"Year Established:\s*(\d{4})", text)
    if m:
        founding_year = int(m.group(1))
    bio_year = None
    m = re.search(r"founded in (\d{4})", services_text, re.I)
    if m:
        bio_year = int(m.group(1))
    hours = {}
    for day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                "Saturday", "Sunday"):
        m = re.search(r"^%s:\s*(.+?)\s*$" % day, text, re.M)
        if m:
            hours[day] = m.group(1).strip()
    return {
        "accessible": True,
        "url": url,
        "name": name,
        "address": address,
        "city": city,
        "phone": phone,
        "categories": categories,
        "hours": hours,
        "rating": rating,
        "count": count,
        "services_text": services_text,
        "has_install": has_install,
        "has_repair": has_repair,
        "founding_year_field": founding_year,
        "founding_year_bio": bio_year,
    }


def fetch_yelp(firm_name: str, yelp_url: Optional[str],
               town: str = "Coppell") -> Dict[str, Any]:
    """Fetch and parse a firm's Yelp listing. yelp_url may come from the
    Meta place record; when None, a web search finds candidates. Each
    candidate is tried in order and must pass the name check — a Yelp page
    for a different location of the same firm is not the firm's listing.
    Returns the parsed listing, or {"accessible": False, "reason": ...}."""
    candidates: List[str] = []
    found_by = None
    if yelp_url:
        candidates = [yelp_url]
        found_by = "Meta place record link"
    else:
        candidates = find_yelp_urls(firm_name, town)
        found_by = "web search" if candidates else None
        F.polite_sleep()
    if not candidates:
        return {"accessible": False, "reason": "no Yelp business page found"}
    tried = []
    for url in candidates:
        text = browser_open(url)
        F.polite_sleep()
        if not text:
            tried.append("%s (no extractable content)" % url)
            continue
        parsed = parse_yelp_text(text, url)
        if not parsed.get("accessible"):
            tried.append("%s (%s)" % (url, parsed.get("reason", "")))
            continue
        if not _name_matches(parsed.get("name"), firm_name):
            tried.append("%s (name %r is not the firm %r)"
                         % (url, parsed.get("name"), firm_name))
            continue
        parsed["found_by"] = found_by
        return parsed
    return {"accessible": False,
            "reason": "no Yelp page matched the firm name; tried: %s"
            % "; ".join(tried)}


# ---------------------------------------------------------------------------
# Birdeye (Google reviews, republished) — the C1.3 review reader
# ---------------------------------------------------------------------------

_BIRDEYE_RE = re.compile(r"https://reviews\.birdeye\.com/[A-Za-z0-9_-]+")


def find_birdeye_urls(firm_name: str, town: str = "Coppell") -> List[str]:
    """The firm's Birdeye profile URLs from a web search, in order. The
    search page can list other firms' profiles, so callers must verify
    each candidate's name before using it."""
    text = web_search("%s Birdeye %s TX reviews" % (firm_name, town))
    if not text:
        return []
    seen, out = set(), []
    for m in _BIRDEYE_RE.finditer(text):
        if m.group(0) not in seen:
            seen.add(m.group(0))
            out.append(m.group(0))
    return out


# Complaint themes (C1.3): keywords that mark a review negative and the
# theme it belongs to. A review is negative when it contains any of these.
COMPLAINT_KEYWORDS = {
    "pricing": ("overcharged", "overcharge", "too expensive", "ripped off",
                "price gouging", "hidden fee", "hidden charge", "quoted one price"),
    "no-show": ("never showed", "no-show", "no show", "didn't show",
                "did not show", "never came", "stood me up",
                "showed up late", "arrived late", "was late", "hours late"),
    "professionalism": ("rude", "unprofessional", "disrespectful", "arrogant",
                        "condescending", "yelled"),
    "repair-quality": ("didn't fix", "did not fix", "still broken",
                       "broke again", "not fixed", "made it worse", "worse than",
                       "had to call someone else", "another company fixed"),
    "mess-damage": ("left a mess", "damaged", "damage", "dirty",
                    "holes in", "broke my"),
    "billing": ("charged twice", "charged for work", "billing", "charged me for",
                "unauthorized charge"),
    "warranty": ("wouldn't honor", "would not honor", "refused to honor",
                 "warranty denied", "voided"),
    "trust": ("scam", "ripoff", "rip-off", "fraud", "dishonest", "lied",
              "never again", "do not use", "avoid this company", "stay away"),
    "general": ("terrible", "awful", "horrible", "worst", "waste of money",
                "disappointed", "unhappy", "poor service", "bad experience"),
}


def _negative_themes(text: str) -> List[str]:
    """The complaint themes a review text hits (empty = not negative)."""
    low = (text or "").lower()
    return [theme for theme, words in COMPLAINT_KEYWORDS.items()
            if any(w in low for w in words)]


def analyze_reviews(reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Complaint-pattern analysis over the reviews read.

    reviews: [{"text": str, "addressed": bool}]. Returns
    {"recurring_pattern": str|None, "single_cluster": str|None,
     "negative_count": int, "reviews_read": int}."""
    by_theme: Dict[str, int] = {}
    unaddressed_negative = 0
    for r in reviews:
        if r.get("addressed"):
            continue
        themes = _negative_themes(r.get("text", ""))
        if not themes:
            continue
        unaddressed_negative += 1
        for theme in themes:
            by_theme[theme] = by_theme.get(theme, 0) + 1
    recurring = None
    for theme, n in sorted(by_theme.items(), key=lambda kv: -kv[1]):
        if n >= 3:
            recurring = "%d unaddressed negative reviews share the theme '%s'" \
                % (n, theme)
            break
    single = None
    if not recurring and unaddressed_negative >= 2:
        themes = ", ".join("%s (%d)" % kv
                           for kv in sorted(by_theme.items(),
                                            key=lambda kv: -kv[1]))
        single = "%d unaddressed negative reviews (themes: %s)" \
            % (unaddressed_negative, themes or "general complaints")
    return {"recurring_pattern": recurring, "single_cluster": single,
            "negative_count": unaddressed_negative,
            "reviews_read": len(reviews)}


def parse_birdeye_text(text: str, url: str) -> Dict[str, Any]:
    """Parse the browser-service extract of a Birdeye profile page.

    The extract carries the overall rating and review count, the business
    description, and the latest review texts (each optionally followed by
    a 'Business response:' block, which marks that review addressed).
    The extract shows no per-review dates or star ratings — recorded as a
    limitation. Returns the profile facts and the analysed reviews, or
    {"accessible": False} when the text is not a Birdeye profile extract."""
    if not text or "Birdeye" not in text:
        return {"accessible": False, "url": url,
                "reason": "Birdeye page had no extractable content"}
    name = None
    m = re.search(r"^#\s+(.+?)\s+-\s+\d+\s+Reviews\s+-", text, re.M)
    if m:
        name = m.group(1).strip()
    rating = None
    m = re.search(r"\n(\d(?:\.\d)?)\s*\n- Heating", text)
    if m:
        rating = float(m.group(1))
    count = None
    m = re.search(r"\*\*(\d(?:\.\d)?)\*\*(\d+)\s+reviews", text)
    if m:
        rating = float(m.group(1))
        count = int(m.group(2))
    if count is None:
        m = re.search(r"has a (\d(?:\.\d)?) star rating with (\d+) reviews",
                      text)
        if m:
            rating = float(m.group(1))
            count = int(m.group(2))
    phone = None
    m = re.search(r"\*\*Phone:\*\*\s*(\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4})", text)
    if m:
        phone = m.group(1).strip()
    address = None
    m = re.search(r"^(\d+ .+?,\s*[A-Za-z ]+,\s*TX,\s*\d{5}[^\n]*)",
                  text, re.M)
    if m:
        address = m.group(1).strip()
    # Review texts: the extract shows the latest reviews as paragraphs
    # between the rating/count line and the FAQ heading. Paragraphs are
    # separated by blank lines; a paragraph that is exactly "Business
    # response:" marks the previous review as addressed, and the paragraph
    # after it is the response text (skipped). Furniture lines (the rating
    # selector, hours table, location, description) are dropped.
    reviews: List[Dict[str, Any]] = []
    rating_line = re.search(r"\*\*(\d(?:\.\d)?)\*\*(\d+)\s+reviews", text)
    start = rating_line.end() if rating_line else 0
    faq = text.find("## Frequently asked questions", start)
    region = text[start:faq if faq > 0 else len(text)]
    cut = re.search(r"\n\| Weekday \|", region)
    if cut:
        region = region[:cut.start()]
    paragraphs = [re.sub(r"\s+", " ", p).strip()
                  for p in re.split(r"\n\s*\n", region)]
    pending_response = False
    last_review_idx = -1
    for para in paragraphs:
        if not para:
            continue
        low = para.lower()
        if low in ("select a rating",) or low.startswith("**"):
            continue
        if low.startswith("business response"):
            pending_response = True
            continue
        if pending_response:
            # This paragraph is the response text, not a review.
            if last_review_idx >= 0:
                reviews[last_review_idx]["addressed"] = True
            pending_response = False
            continue
        if any(k in low for k in ("frequently asked questions",
                                  "about this business", "location details",
                                  "additional details", "hours:")):
            continue
        if len(para) >= 40:
            reviews.append({"text": para, "addressed": False})
            last_review_idx = len(reviews) - 1
    # De-duplicate identical review texts (the extract sometimes repeats).
    seen, unique = set(), []
    for r in reviews:
        key = r["text"][:120]
        if key not in seen:
            seen.add(key)
            unique.append(r)
    analysis = analyze_reviews(unique)
    return {
        "accessible": True,
        "url": url,
        "name": name,
        "rating": rating,
        "count": count,
        "phone": phone,
        "address": address,
        "reviews": unique,
        "reviews_read": len(unique),
        "recurring_pattern": analysis["recurring_pattern"],
        "single_cluster": analysis["single_cluster"],
        "negative_count": analysis["negative_count"],
        "dates_shown": False,
        "per_review_ratings_shown": False,
    }


def fetch_birdeye(firm_name: str, town: str = "Coppell") -> Dict[str, Any]:
    """Find and read a firm's Birdeye profile (Google reviews, republished).
    Each candidate URL is tried in order and must pass the name check —
    Birdeye sometimes merges names, so a profile whose name is not the
    firm is not used. Returns the parsed profile, or
    {"accessible": False, "reason": ...}."""
    candidates = find_birdeye_urls(firm_name, town)
    F.polite_sleep()
    if not candidates:
        return {"accessible": False,
                "reason": "no Birdeye profile found by web search"}
    tried = []
    for url in candidates:
        text = browser_open(url)
        F.polite_sleep()
        if not text:
            tried.append("%s (no extractable content)" % url)
            continue
        parsed = parse_birdeye_text(text, url)
        if not parsed.get("accessible"):
            tried.append("%s (%s)" % (url, parsed.get("reason", "")))
            continue
        if not _name_matches(parsed.get("name"), firm_name):
            tried.append("%s (profile name %r is not the firm %r)"
                         % (url, parsed.get("name"), firm_name))
            continue
        return parsed
    return {"accessible": False,
            "reason": "no Birdeye profile matched the firm name; tried: %s"
            % "; ".join(tried)}


# ---------------------------------------------------------------------------
# Google Business Profile (renderer route)
# ---------------------------------------------------------------------------


def fetch_google_listing(firm_name: str, town: str = "Coppell") -> Dict[str, Any]:
    """Read the firm's Google Business Profile via the headless renderer.

    The Google Business Profile / Maps page is a JavaScript app: the
    direct fetcher gets no usable HTML and the browser page-text service
    returns no extractable content (verified 2026-11-11 and again
    2026-11-16). A real browser is the only route that can read it — the
    same public page a Shopping Agent reads when it searches Google.
    The Maps search page is rendered, the visible text is extracted, and
    the listing facts are read from it. The name check is fail-closed:
    if the firm name does not appear in the rendered text, the result is
    Not accessible rather than another firm's listing.

    NOTE (2026-11-16): in this environment the egress proxy refuses the
    renderer's network traffic, so this returns Not accessible with a
    [PROXY-REFUSED] reason until the platform allows the renderer's
    traffic. The code is correct and ready for that environment."""
    import urllib.parse as _up
    query = "%s %s TX" % (firm_name, town)
    url = "https://www.google.com/maps/search/" + _up.quote(query)
    rendered = F.fetch_rendered(url)
    if not rendered.accessible or not rendered.exact:
        return {"accessible": False, "url": url,
                "reason": rendered.reason or "Google listing not readable"}
    text = F.html_to_text(rendered.exact)
    if not text or norm_text(firm_name) not in norm_text(text):
        return {"accessible": False, "url": url,
                "reason": "Google Maps search rendered but the firm name "
                "does not appear in the listing text"}
    rating = None
    count = None
    m = re.search(r"(\d(?:\.\d)?)\s*\(\s*([\d,]+)\s*\)", text)
    if m:
        rating = float(m.group(1))
        count = int(m.group(2).replace(",", ""))
    phone = None
    m = re.search(r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}", text)
    if m:
        phone = m.group(0).strip()
    address = None
    m = re.search(r"(\d+\s+[^,]+,\s*[A-Za-z ]+,\s*TX\s*\d{5})", text)
    if m:
        address = m.group(1).strip()
    return {
        "accessible": True,
        "url": url,
        "method": "website-rendered",
        "name": firm_name,
        "rating": rating,
        "count": count,
        "phone": phone,
        "address": address,
        "text": text,
    }


# ---------------------------------------------------------------------------
# Firm's own reviews page (fallback for C1.3)
# ---------------------------------------------------------------------------


def fetch_firm_reviews_page(home_html: str, home_url: str) -> Dict[str, Any]:
    """A /reviews (or testimonials) page linked from the homepage, fetched
    by plain HTTP. It republishes Google reviews but is firm-curated, so
    the evidence note must say so. Returns review texts with dates where
    the page shows them, or {"accessible": False, "reason": ...}."""
    if not home_html:
        return {"accessible": False, "reason": "no homepage HTML to link from"}
    import urllib.parse as _up
    review_url = None
    for href in re.findall(r'href=["\']([^"\']+)["\']', home_html, re.I):
        if "review" in href.lower() or "testimonial" in href.lower():
            cand = _up.urljoin(home_url, href.strip())
            if _up.urlparse(cand).netloc == _up.urlparse(home_url).netloc:
                review_url = cand
                break
    if not review_url:
        return {"accessible": False,
                "reason": "no reviews/testimonials page linked from the homepage"}
    ev = F.fetch_url(review_url)
    if not ev.accessible or not ev.exact:
        return {"accessible": False, "url": review_url,
                "reason": ev.reason or "reviews page not readable"}
    text = F.html_to_text(ev.exact)
    # Review blocks: on these pages the review text comes first and the
    # attribution ("Verified Google Review · Month YYYY") follows it, so
    # take the text BEFORE each date, not after it. Drop sentences that
    # are page furniture (the site's own claims about its reviews, service
    # area, licence, phone, fees) — a real review does not contain them.
    furniture = ("verified", "google reviews", "service area", "diagnostic",
                 "license", "licence", "phone:", "rating:", "reviews averaging",
                 "5-star reviews", "five-star reviews", "star average",
                 "quick answer", "doing the work right")
    reviews = []
    for m in re.finditer(
            r"\b(January|February|March|April|May|June|July|August|September|"
            r"October|November|December)\s+(\d{4})\b", text):
        before = text[max(0, m.start() - 600):m.start()]
        sentences = [s.strip() for s in re.split(r"[.!?]\s+", before)
                     if s.strip()]
        kept = [s for s in sentences
                if not any(f in s.lower() for f in furniture)]
        snippet = ". ".join(kept[-3:]).strip()
        if len(snippet) >= 40:
            reviews.append({"text": snippet,
                            "date": "%s %s" % (m.group(1), m.group(2)),
                            "addressed": False})
    if not reviews:
        return {"accessible": False, "url": review_url,
                "reason": "reviews page readable but no dated review text found"}
    analysis = analyze_reviews(reviews)
    return {
        "accessible": True,
        "url": review_url,
        "reviews": reviews,
        "reviews_read": len(reviews),
        "recurring_pattern": analysis["recurring_pattern"],
        "single_cluster": analysis["single_cluster"],
        "negative_count": analysis["negative_count"],
        "curated": True,
        "dates_shown": True,
        "per_review_ratings_shown": False,
    }


# ---------------------------------------------------------------------------
# Collection for one firm
# ---------------------------------------------------------------------------


def collect(firm: dict, disc: dict, listing: Optional[dict],
            home_html: Optional[str], home_url: Optional[str],
            run_date: str, town: str = "Coppell") -> Dict[str, Any]:
    """Collect the Google/Yelp evidence for one firm.

    firm: the firms.json record. disc: the discovery.json record (may carry
    a yelp URL). listing: the Meta place record from fetch_listing (may
    carry a yelp link). home_html/home_url: the homepage, for the reviews
    fallback. Returns {"yelp": {...}, "google": {...}, "reviews": {...}}
    where "reviews" is the C1.3 source (Birdeye preferred, firm's own
    reviews page as fallback)."""
    firm_name = firm["name"]
    out: Dict[str, Any] = {"firm": firm_name, "date": run_date}

    # --- Yelp -----------------------------------------------------------
    yelp_url = disc.get("yelp_url") or (
        listing.get("yelp_url") if listing else None)
    yelp = fetch_yelp(firm_name, yelp_url, town=town)
    out["yelp"] = yelp

    # --- Google ---------------------------------------------------------
    # The Google Business Profile page is a JavaScript app. It is read
    # with the headless renderer (fetch_google_listing); the direct
    # fetcher gets no usable HTML and the browser page-text service
    # returns no extractable content. In this environment the renderer
    # cannot reach the network (the egress proxy refuses its traffic),
    # so this is Not accessible with that reason until the platform
    # allows it — recorded as Not accessible, never estimated.
    out["google"] = fetch_google_listing(firm_name, town=town)

    # --- Reviews (C1.3) -------------------------------------------------
    reviews = fetch_birdeye(firm_name, town=town)
    source = "birdeye"
    if not reviews.get("accessible"):
        birdeye_reason = reviews.get("reason", "")
        reviews = fetch_firm_reviews_page(home_html or "", home_url or "")
        source = "firm_reviews_page"
        if not reviews.get("accessible"):
            reviews = {
                "accessible": False,
                "reason": "no Birdeye profile (%s); %s"
                % (birdeye_reason,
                   reviews.get("reason", "no reviews page")),
            }
            source = "none"
    reviews["source"] = source
    out["reviews"] = reviews
    return out
