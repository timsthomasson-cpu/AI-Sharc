"""AI Sharc rules engine — Spec v2.1 (100-point model).

Implements the scored audit (21 scored Items in 7 Categories) and the
Ranking Suggestions, exactly as defined in the live Specification v2.1
(approved by Tim 2026-11-17) and the Licensed Home Trade Field Mapping.

CONTROLLED VOCABULARY (Spec s.7; enforced by the audit DB CHECK constraint):
  Item:               Pass, Pass with warning, Missing, Conflict, Not accessible
  Category result:    points earned out of points available (e.g. "13 of 22 points")
  Ranking Suggestion: Observed, Recommendation, Not checked (the six
      Section 6 factors S1 Booking and quote route, S2 Availability,
      S3 Price for this user, S4 Brand and system coverage, S5 Service-area
      dispatch, S6 Machine discovery (llms.txt)); Complete, Suggested,
      Not checked (the two Section 4 suggestions C3.2 BBB accreditation
      and rating consistent with bbb.org and C4.1 six-line warranty card —
      Spec s.4.3 rule 8, decided by Tim 2026-11-18)

There is NO "Fail" and NO "Not confirmed" as an Item result. On cards, a Not
accessible Item is displayed as Fail — Not confirmed, and the original score
stands (Spec s.7). Pass with warning counts as Pass for the Item's points
and the Grade, and does not count as a High Priority issue. There is NO
Critical-issue count and NO Gate stage: the six former Gates are merged
into the Items (Spec s.5).

MISSING vs NOT ACCESSIBLE (Spec s.7/s.4.3):
  Missing        — the source WAS read and the evidence shows the Item's
                   criteria are not met.
  Not accessible — the source needed could not be read, OR the required fact
                   is not published on any readable source, so the auditor
                   cannot confirm it.
  Conflict       — the narrow s.4.3 case only.

COUNTING (Spec s.8):
  High Priority issues = count of failed scored Items, i.e. Items with
      result in (Missing, Conflict, Not accessible). Pass with warning is
      NOT High.
  Passed Items = Items with result in (Pass, Pass with warning).
  Item points = full points if passed, 0 if failed. No partial credit.
  Category score = SUM of the points of the Items in it that passed —
      there is no all-or-nothing Category point. A Category result row is
      a points subtotal — never counted as a passed/failed Item or a High
      Priority issue.
  Total score = sum of the Category scores, out of 100.
  Grade (eligible firms only): A = 65+, B = 50-64, C = 30-49, D = below 30.
  F ONLY when the firm fails the minimum condition in Spec s.5 (website
      unreachable on the firm's side, or not in business) — no points are
      given and no letter grade is calculated. A reason on AI Sharc's side
      (APPROVAL-EXPIRED, PROXY-REFUSED) or an undecided rendered read
      (BLOCKED / JS-ONLY) means the audit is UNVERIFIED: no Grade is
      assigned until a re-check verifies the site.

MINIMUM CONDITION — WEBSITE ACCESS (Spec s.5, s.4.1.1 two-method rule):
  F if the website is unreachable on the firm's side (reason CERT-INVALID,
  PARKED, DEAD, SUSPENDED, WRONG-CONTENT, or no website at all) or the
  firm is not in business (closed / permanently closed flag). "Not taking
  on new customers" is NOT an F condition. For an F firm no Items are
  scored and no points are given: the 36 rows are still emitted, with the
  Items recorded as Not accessible and the reason stated, so the audit
  reconciles (Spec s.13) and the card can state the reason in Section 2
  Website Access. The former Gates map: G2 services in plain words ->
  C2.2 install and repair listed separately on that page (service-page
  only); G3 area coverage -> C2.1 service-area page naming town and ZIP;
  G4 contact -> C6.1 one unique primary phone number everywhere (phone
  part) and C2.4 unique primary phone and booking route on that page
  (booking-route part); G5 hours / Active Status -> C5.1 day-by-day hours
  readable (hours part) and the F condition above (Active Status part);
  G1 exact name and G6 verifiable listing become scored Items.

RANKING SUGGESTIONS (Spec s.4.3 rule 8, s.9, s.6.10): never scored, never
affect a Category score, a total, a Grade, or an Issue count. Eight labels:
the six Section 6 suggestions (Booking and quote route, Availability,
Price for this user, Brand and system coverage, Service-area dispatch,
Machine discovery (llms.txt) — S1-S6) plus the two Section 4 suggestions
(C3.2 BBB accreditation and rating consistent with bbb.org and C4.1
six-line warranty card). All eight are Audit Data rows (Spec s.13
reconciliation: 7 Category results + 21 Items + 8 Ranking Suggestions =
36 rows; the two Section 4 suggestions became rows by Tim's decision
2026-11-18, decision 10). On the Final card the six Section 6 suggestions
display as COMPLETE (Observed) or SUGGESTED (Recommendation or Not
checked); the two Section 4 suggestions display as COMPLETE (Complete)
or SUGGESTED (Suggested or Not checked).

Every check returns a Row carrying: the result, the evidence (method +
source URL + date + exact wording/figure, or "Not accessible" with the
reason), the human-review flag, and the why-it-matters text from the Field
Mapping. Nothing is invented: a fact that could not be read is Not
accessible, never estimated.

This engine decides scores from EVIDENCE. It does not fetch anything. The
evidence fetchers (evidence/) supply the Evidence objects; the agent module
(agent/) supplies the Muse observation. See DESIGN.md (v1.22 design; the
v2.1 engine differs as described above).
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Controlled vocabulary (Spec s.7)
# ---------------------------------------------------------------------------

PASS = "Pass"
FAIL = "Fail"
PASS_WITH_WARNING = "Pass with warning"
MISSING = "Missing"
CONFLICT = "Conflict"
NOT_ACCESSIBLE = "Not accessible"

OBSERVED = "Observed"
RECOMMENDATION = "Recommendation"
NOT_CHECKED = "Not checked"

# Section 4 Ranking Suggestion statuses (Spec s.4.3 rule 8, decided by
# Tim 2026-11-18): Complete = the firm already has it; Suggested = the
# firm does not have it; Not checked = the check itself cannot be
# performed. They apply ONLY to C3.2 BBB accreditation and rating
# consistent with bbb.org and C4.1 six-line warranty card. The six
# Section 6 factors keep Observed / Recommendation / Not checked.
COMPLETE = "Complete"
SUGGESTED = "Suggested"

# Item results that count as a failed Item (High Priority issue) — Spec s.8.
FAILED_ITEM_RESULTS = frozenset({MISSING, CONFLICT, NOT_ACCESSIBLE})
# Item results that count as a passed Item — Spec s.8.
PASSED_ITEM_RESULTS = frozenset({PASS, PASS_WITH_WARNING})

# Grade bands on the 100-point total (Spec s.8). F is NOT a band: it is the
# minimum-condition outcome in Spec s.5, and unverified audits get no grade.
GRADE_BANDS = [(65, "A"), (50, "B"), (30, "C"), (0, "D")]


def grade_from_points(total: int) -> str:
    """Grade letter from the 100-point total (Spec s.8). Eligible firms only."""
    for floor, letter in GRADE_BANDS:
        if total >= floor:
            return letter
    return "D"


# Inability to Access Website Reasons (Spec s.4.1.1) that make the Grade F
# (Spec s.5). NO-WEBSITE and NOT-IN-BUSINESS are the s.5 F conditions the
# fetcher cannot classify from an HTTP error (no website at all; closed flag).
FIRM_SIDE_REASONS = frozenset({
    "CERT-INVALID", "PARKED", "DEAD", "SUSPENDED", "WRONG-CONTENT",
    "NO-WEBSITE",
})
# Reasons on AI Sharc's side: the audit is unverified, not F (Spec s.5).
AI_SHARC_SIDE_REASONS = frozenset({"APPROVAL-EXPIRED", "PROXY-REFUSED"})

# Answer/search crawlers + Claude-User whose block fails C7.1 (Spec s.6.9,
# vendor-verified 2026-11-07). Training-only tokens and Meta-ExternalAgent
# alone do NOT fail. Missing robots.txt passes.
M1_BLOCKING_TOKENS = (
    "OAI-SearchBot",
    "Claude-SearchBot",
    "PerplexityBot",
    "Meta-WebIndexer",
    "Applebot",
    "Claude-User",
)
M1_NON_BLOCKING_TOKENS = (
    "GPTBot",
    "ClaudeBot",
    "Google-Extended",
    "Applebot-Extended",
    "Meta-ExternalAgent",
)

# The six Section 6 Ranking Suggestions (Spec s.9). S1-S6 check_id codes
# (renamed from L1-L6 by Tim's instruction 2026-11-18); the six ids are
# unchanged from v1.22 (Spec v2.1 change log).
SUGGESTION_IDS = ("booking_route", "availability", "price", "brand_coverage",
                  "dispatch", "llms_txt")
# Backwards-compatible alias: the v1.22 name for the same six ids.
LEVER_IDS = SUGGESTION_IDS

# The two Section 4 Ranking Suggestions (Spec s.6.3, s.6.4, s.6.7). Not
# scored, and Audit Data rows since Tim's decision 2026-11-18 (decision
# 10): Spec s.13 reconciliation is now 7 Category results + 21 Items +
# 8 Ranking Suggestions = 36 rows.
SECTION_4_SUGGESTION_IDS = ("C3.2", "C4.1")

# Category order (shopping-impact order, Spec s.6).
CATEGORY_ORDER = (
    "Reputation",
    "Area Coverage",
    "Credentials and Trust",
    "Pricing and Warranty",
    "Hours and Active Status",
    "Identity and Contact",
    "Machine Readability",
)

# Points allocation v2 (Spec s.6). 21 scored Items, 100 points. C3.2 and
# C4.1 are NOT scored (Ranking Suggestions, Section 4). The anti-aligned
# Items keep their v2 points (decided by Tim 2026-11-16): C6.1 one unique
# primary phone number everywhere 3, G6 verifiable listing 3, C5.2 hours
# consistency 2.
ITEM_POINTS: Dict[str, int] = {
    "C1.1": 9, "C1.2": 9, "C1.3": 4,
    "C2.1": 7, "C2.2": 6, "C2.3": 4, "C2.4": 3,
    "C3.1": 7, "G6": 3,
    "C4.2": 7, "C4.3": 3, "C4.4": 3,
    "C5.1": 5, "C5.2": 2,
    "C6.1": 3, "C6.2": 6, "G1": 6,
    "C7.1": 3, "C7.2": 3, "C7.3": 5, "C7.4": 2,
}
CATEGORY_POINTS: Dict[str, int] = {
    "Reputation": 22,
    "Area Coverage": 20,
    "Credentials and Trust": 10,
    "Pricing and Warranty": 13,
    "Hours and Active Status": 7,
    "Identity and Contact": 15,
    "Machine Readability": 13,
}

# Item id -> (Category, Item label) per Spec s.6.10. G1 exact name and G6
# verifiable listing are scored Items (Spec s.5); C3.2 and C4.1 are NOT here
# — they are Section 4 Ranking Suggestions (see SECTION_4_SUGGESTIONS).
ITEM_CATALOG: Dict[str, tuple] = {
    "C1.1": ("Reputation", "Rating and review count readable"),
    "C1.2": ("Reputation", "Rating figures consistent across sources"),
    "C1.3": ("Reputation", "No recurring unaddressed complaint pattern"),
    "C2.1": ("Area Coverage", "Service-area page naming town and ZIP"),
    "C2.2": ("Area Coverage", "Install and repair listed separately on that page"),
    "C2.3": ("Area Coverage", "Brands and system types served on that page"),
    "C2.4": ("Area Coverage", "Unique primary phone and booking route on that page"),
    "C3.1": ("Credentials and Trust", "Single consistent applicable state licence number published"),
    "G6": ("Credentials and Trust", "Verifiable listing"),
    "C4.2": ("Pricing and Warranty", "Diagnostic fee in dollars"),
    "C4.3": ("Pricing and Warranty", "Free-estimate status for install, stated separately"),
    "C4.4": ("Pricing and Warranty", "Free-estimate status for repair, stated separately"),
    "C5.1": ("Hours and Active Status", "Day-by-day hours readable"),
    "C5.2": ("Hours and Active Status", "Hours, 24-hour, weekend, and emergency status consistent across sources"),
    "C6.1": ("Identity and Contact", "One unique primary phone number everywhere"),
    "C6.2": ("Identity and Contact", "Founding year and business lineage consistent across sources"),
    "G1": ("Identity and Contact", "Exact name"),
    "C7.1": ("Machine Readability", "AI crawler access"),
    "C7.2": ("Machine Readability", "Key facts readable without JavaScript"),
    "C7.3": ("Machine Readability", "LocalBusiness structured data"),
    "C7.4": ("Machine Readability", "Sitemap"),
}

# Section 4 Ranking Suggestions: id -> (Category, label) (Spec s.6.10).
# The label is the code-plus-description form from Sample Audit Data
# Rev 4 (Tim's text rule: always the code with the description, e.g.
# 'C4.1 six-line warranty card', never a bare code): this is the Item
# text the harness writes into audit-data.json, and the label the
# loader accepts.
SECTION_4_SUGGESTIONS: Dict[str, tuple] = {
    "C3.2": ("Credentials and Trust",
             "C3.2 BBB accreditation and rating consistent with bbb.org"),
    "C4.1": ("Pricing and Warranty", "C4.1 six-line warranty card"),
}

# Section 6 Ranking Suggestions: id -> label (Spec s.9).
SUGGESTION_LABELS: Dict[str, str] = {
    "booking_route": "Booking and quote route",
    "availability": "Availability",
    "price": "Price for this user",
    "brand_coverage": "Brand and system coverage",
    "dispatch": "Service-area dispatch",
    "llms_txt": "Machine discovery (llms.txt)",
}

# ---------------------------------------------------------------------------
# Evidence and rows
# ---------------------------------------------------------------------------


@dataclass
class Evidence:
    """One verified fact, or a recorded failure to read it.

    Every fact carries the method, the source URL, the date, and the exact
    wording or figure — or "Not accessible" with the reason (Spec s.4.3).
    """
    method: str                      # e.g. "website-html", "places-api"
    source_url: Optional[str] = None
    date: Optional[str] = None       # ISO date the fact was read
    exact: Optional[str] = None      # exact wording / figure read
    accessible: bool = True          # False when the source could not be read
    reason: Optional[str] = None     # why Not accessible, when not accessible

    def note(self) -> str:
        if not self.accessible:
            return "Not accessible: %s" % (self.reason or "source could not be read")
        parts = [p for p in (self.source_url, self.date, self.exact) if p]
        return "; ".join(parts) if parts else self.method


@dataclass
class Row:
    seq: int
    row_type: str                    # Category result | Item | Ranking Suggestion
    label: str                       # Category / Item / Suggestion label
    result: str                      # controlled vocabulary for the row type
    evidence: str = ""               # method + source URL + date + exact wording
    why: str = ""                    # why it matters (Field Mapping)
    human_review: bool = False       # needs a human before a card is issued
    review_reason: str = ""
    category: Optional[str] = None   # Stage 2 Category, for Item/Category rows
    item_id: Optional[str] = None
    gate_id: Optional[str] = None    # unused in v2.1; kept so v1.22 row dicts still load
    lever_id: Optional[str] = None   # suggestion id, for Ranking Suggestion rows
    points: int = 0                  # points earned by this row (Items / Category results)
    points_available: int = 0        # points available (Items / Category results)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "row_type": self.row_type,
            "label": self.label,
            "result": self.result,
            "evidence": self.evidence,
            "why_it_matters": self.why,
            "human_review": self.human_review,
            "review_reason": self.review_reason,
            "category": self.category,
            "item_id": self.item_id,
            "gate_id": self.gate_id,
            "lever_id": self.lever_id,
            "points": self.points,
            "points_available": self.points_available,
        }


@dataclass
class Definitions:
    gates: Dict[str, Dict[str, str]] = field(default_factory=dict)
    items: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    levers: Dict[str, Dict[str, str]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str) -> "Definitions":
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        # definitions.json stores lists (generated from the Field Mapping).
        # Gates are in order G1..G6; Items are keyed by their code (C-codes
        # plus G1/G6, which are scored Items in v2.1); Levers are keyed by
        # their snake_case id. The gates list is retained in v2.1 ONLY for
        # the agent-observation scorer path (agent/scorer.py scores Gates
        # as Not observed by rule); the scored audit has no Gates.
        gates: Dict[str, Dict[str, str]] = {}
        gate_ids = ("G1", "G2", "G3", "G4", "G5", "G6")
        for gid, entry in zip(gate_ids, raw.get("gates", [])):
            gates[gid] = dict(entry)
        items = {e["id"]: dict(e) for e in raw.get("items", [])}
        levers = {e["id"]: dict(e) for e in raw.get("levers", [])}
        return cls(gates=gates, items=items, levers=levers)

    def why(self, kind: str, key: str) -> str:
        # The Field Mapping carries no separate "why it matters" column; the
        # pass criteria is the traceable statement of what the check is for.
        table = {"gate": self.gates, "item": self.items, "lever": self.levers}[kind]
        entry = table.get(key) or {}
        return entry.get("pass_criteria", "") or entry.get("observed_only_if", "")


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

_PHONE_DIGITS = re.compile(r"\D+")
_WS = re.compile(r"\s+")


def norm_phone(raw: Optional[str]) -> Optional[str]:
    """Normalise a phone to its last 10 digits, or None if not a phone."""
    if not raw:
        return None
    digits = _PHONE_DIGITS.sub("", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else None


def norm_text(raw: Optional[str]) -> str:
    """Normalise a name for comparison (Spec s.6.6, loosened 2026-11-16).

    Curly apostrophes/quotes are the same character as straight ones; an
    HTML entity (&amp;) is the character it stands for; "&" and "and" are
    the same connector in a trade name; commas and periods are punctuation,
    not part of the name; a trailing legal suffix (LLC, Inc, Corp) is not
    part of the trading name. And 'A/C' compares equal to 'AC': the '/'
    (and periods) inside the abbreviation is part of the abbreviation, not
    a word separator — so "A/C" (or "A.C.") collapses to "AC" before the
    punctuation is stripped. Two names that differ only by one of these
    are the same name. This is normalisation, not a scoring rule change:
    a name that differs by a real word (a different brand, a rebrand, an
    appended trade) still differs."""
    import html as _html
    cleaned = (raw or "").replace("’", "'").replace("‘", "'") \
        .replace("“", '"').replace("”", '"')
    cleaned = _html.unescape(cleaned)
    cleaned = re.sub(r"(?i)\ba[./]\s*c\b", "AC", cleaned)
    cleaned = cleaned.replace("&", " and ")
    cleaned = re.sub(r"[,.;:!?()\"/]", " ", cleaned)
    cleaned = re.sub(r"\band\b", " ", cleaned, flags=re.I)
    cleaned = _WS.sub(" ", cleaned.strip()).lower()
    cleaned = re.sub(
        r"\b(llc|inc|corp|corporation|co|ltd|lp|llp)\s*$", "", cleaned).strip()
    return _WS.sub(" ", cleaned).strip()


def norm_licence(raw: Optional[str]) -> Optional[str]:
    """Strip a TDLR prefix, leading zeros, and the trailing endorsement
    letter; the register's license_number is numeric only. E.g.
    TACLB00097767E -> 97767 (subtype BE: class B, endorsement E)."""
    if not raw:
        return None
    s = re.sub(r"^(TACLA|TACLB|TECL)", "", raw.strip().upper())
    m = re.search(r"\d+", s)
    if not m:
        return None
    return m.group(0).lstrip("0") or "0"


def parse_rating(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    m = re.search(r"(\d(?:\.\d)?)\s*(?:/|out of|of)\s*5", raw)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d\.\d)", raw)
    return float(m.group(1)) if m else None


def parse_count(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    m = re.search(r"([\d,]+)\s*(?:reviews?|ratings?)", raw)
    return int(m.group(1).replace(",", "")) if m else None


# ---------------------------------------------------------------------------
# Scored Items (Pass / Pass with warning / Missing / Conflict / Not accessible)
# ---------------------------------------------------------------------------


def _item(item_id: str, result: str, evidence: str, defs: Definitions,
          human_review: bool = False, review_reason: str = "") -> Row:
    category, label = ITEM_CATALOG[item_id]
    available = ITEM_POINTS[item_id]
    earned = available if result in PASSED_ITEM_RESULTS else 0
    return Row(0, "Item", label, result, evidence, defs.why("item", item_id),
               human_review=human_review, review_reason=review_reason,
               category=category, item_id=item_id,
               points=earned, points_available=available)


def check_g1_exact_name(ev: Dict[str, Any], defs: Definitions) -> Row:
    """G1 exact name — scored Item, Identity and Contact, 6 points (Spec
    s.5, s.6.6). Exact business name identical on website and listings;
    if rebranded, an old-to-new mapping page. Fail-if: name differs on any
    checked source and no mapping page explains it. Name comparison uses
    the s.6.6 normalisation: 'A/C' compares equal to 'AC'."""
    names: Dict[str, str] = {}
    for src, val in (ev.get("names") or {}).items():
        if val:
            names[src] = val
    readable = len(names)
    distinct = {norm_text(v) for v in names.values()}
    if readable < 2:
        return _item("G1", NOT_ACCESSIBLE,
                     "Only %d source(s) readable for the name (%s) — cannot verify "
                     "the name across website and listings."
                     % (readable, ", ".join(sorted(names)) or "none"),
                     defs, human_review=True,
                     review_reason="Name could not be verified across sources; "
                     "access problem, not a found difference.")
    if len(distinct) == 1:
        return _item("G1", PASS,
                     "Name identical on %d checked sources: %s"
                     % (readable, "; ".join("%s: %s" % kv for kv in sorted(names.items()))),
                     defs)
    if ev.get("mapping_page"):
        return _item("G1", PASS,
                     "Name differs across sources but an old-to-new mapping page "
                     "explains it: %s" % ev["mapping_page"],
                     defs)
    return _item("G1", MISSING,
                 "Name differs on checked sources: %s"
                 % "; ".join("%s: %s" % kv for kv in sorted(names.items())),
                 defs)


def check_g6_listing(ev: Dict[str, Any], defs: Definitions) -> Row:
    """G6 verifiable listing — scored Item, Credentials and Trust, 3 points
    (Spec s.5, s.6.3). A listing outside the firm's own website, with the
    same name, phone, and service area, and the correct Primary Business
    Category. Per Spec s.4.3 rule 2, no listing found after checking
    Google, Meta, and Yelp is a Fail (Missing), because the Item requires
    a listing to exist; no listing source readable at all is Not accessible."""
    checked = ev.get("listings_checked") or []
    found = ev.get("matching_listing")
    if not checked:
        return _item("G6", NOT_ACCESSIBLE,
                     "No listing source could be checked (Google, Meta, and "
                     "Yelp all Not accessible).",
                     defs, human_review=True,
                     review_reason="No listing source readable; access problem, "
                     "not a found difference.")
    if not found:
        return _item("G6", MISSING,
                     "No listing outside the firm's own website found after "
                     "checking: %s." % ", ".join(checked),
                     defs)
    if found.get("mismatch"):
        return _item("G6", MISSING,
                     "Listing found (%s) but does not match the website: %s."
                     % (found.get("source", ""), found["mismatch"]),
                     defs)
    return _item("G6", PASS,
                 "Verifiable listing: %s (%s), same name, phone, service area, "
                 "and Primary Business Category." % (
                     found.get("name", ""), found.get("source", "")),
                 defs)


def check_c11_rating_readable(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C1.1 rating and review count readable — 9 points: rating and review
    count readable on an independent platform. Pass with warning: rating
    on one platform only (others Not accessible). Missing: the rating is
    an own-site claim only, not independently corroborated (Airtron v1.6).
    Not accessible: no independent platform could be read."""
    platforms = ev.get("rating_platforms") or {}   # source -> {"rating","count","accessible"}
    read = {s: v for s, v in platforms.items() if v.get("accessible")}
    found = {s: v for s, v in read.items() if v.get("rating") is not None}
    own_site = ev.get("own_site_rating")
    if found:
        if len(found) == 1 and len(platforms) > 1:
            src, v = next(iter(found.items()))
            return _item("C1.1", PASS_WITH_WARNING,
                         "Rating readable on one platform only (%s: %s on %s); "
                         "other platforms Not accessible."
                         % (src, v.get("rating"), v.get("count")),
                         defs)
        desc = "; ".join("%s: %s on %s" % (s, v.get("rating"), v.get("count"))
                         for s, v in sorted(found.items()))
        return _item("C1.1", PASS, "Rating readable: %s." % desc, defs)
    if not read:
        return _item("C1.1", NOT_ACCESSIBLE,
                     "No independent rating platform could be read.",
                     defs, human_review=True,
                     review_reason="No rating platform readable.")
    if own_site:
        return _item("C1.1", MISSING,
                     "Headline rating is an own-site claim only (%s), not "
                     "independently corroborated on a readable platform."
                     % own_site, defs)
    return _item("C1.1", MISSING,
                 "No rating or review count found on any readable platform.",
                 defs)


def check_c12_rating_figures(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C1.2 rating figures consistent across sources — 9 points.
    Missing: the website claims a figure that contradicts the independent
    profile — the firm must correct the wrong source, not leave both standing
    (dummy Final Rev 6: website 4.9 vs Google 4.6 on 1,234).
    Conflict: the SAME platform / scope / date quoted differently (s.4.3).
    Pass with warning: cross-platform differences between independent
    platforms (not averaged). Not accessible: no figure could be read."""
    website = ev.get("website_rating")          # {"rating","count"}
    profiles = ev.get("rating_platforms") or {}
    read = {s: v for s, v in profiles.items()
            if v.get("accessible") and v.get("rating") is not None}
    if ev.get("same_platform_conflict"):
        return _item("C1.2", CONFLICT,
                     "Same platform quoted differently: %s"
                     % ev["same_platform_conflict"], defs,
                     human_review=True,
                     review_reason="Conflict (s.4.3) — needs a human decision.")
    if website and read:
        # Website claim vs each independent profile figure.
        for src, v in sorted(read.items()):
            wr, pr = website.get("rating"), v.get("rating")
            if wr is not None and pr is not None and wr != pr:
                return _item("C1.2", MISSING,
                             "Website claims a customer review rating of %s, "
                             "while the %s profile shows %s on %s reviews. "
                             "The figures conflict, so a Shopping Agent cannot "
                             "tell which is current."
                             % (wr, src, pr, v.get("count")),
                             defs)
        return _item("C1.2", PASS,
                     "Website figure matches the independent profile(s).", defs)
    if len(read) > 1:
        ratings = {v.get("rating") for v in read.values()}
        if len(ratings) > 1:
            desc = "; ".join("%s: %s on %s" % (s, v.get("rating"), v.get("count"))
                             for s, v in sorted(read.items()))
            return _item("C1.2", PASS_WITH_WARNING,
                         "Cross-platform figures differ (not averaged): %s."
                         % desc, defs)
        return _item("C1.2", PASS,
                     "Independent profile figures agree.", defs)
    if read:
        return _item("C1.2", PASS,
                     "Only one independent figure readable; nothing to "
                     "contradict it.", defs)
    return _item("C1.2", NOT_ACCESSIBLE,
                 "No rating figure could be read on any source.", defs)


def check_c13_complaints(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C1.3 no recurring unaddressed complaint pattern — 4 points. Pass
    with warning: a single recent complaint cluster (no Issue). Missing: a
    recurring unaddressed pattern is visible. Not accessible: reviews
    could not be read."""
    reviews = ev.get("reviews") or {}
    if not reviews.get("accessible", True):
        return _item("C1.3", NOT_ACCESSIBLE,
                     "Reviews could not be read: %s"
                     % reviews.get("reason", ""), defs)
    if reviews.get("recurring_pattern"):
        return _item("C1.3", MISSING,
                     "Recurring unaddressed complaint pattern: %s"
                     % reviews["recurring_pattern"], defs)
    if reviews.get("single_cluster"):
        return _item("C1.3", PASS_WITH_WARNING,
                     "Single recent complaint cluster, no recurring pattern: %s"
                     % reviews["single_cluster"], defs)
    return _item("C1.3", PASS, "No recurring unaddressed complaint pattern found.",
                 defs)


def _page_item(item_id: str, page: Dict[str, Any], field: str,
               present_text: str, absent_text: str, defs: Definitions) -> Row:
    """Shared shape for service-area-page Items: page Not accessible -> Not
    accessible; page read and the fact absent -> Missing; present -> Pass."""
    if not page.get("accessible", True):
        return _item(item_id, NOT_ACCESSIBLE,
                     "Service-area page could not be read: %s"
                     % page.get("reason", ""), defs)
    if page.get(field):
        return _item(item_id, PASS, present_text, defs)
    return _item(item_id, MISSING, absent_text, defs)


def check_c21_area_page(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C2.1 service-area page naming town and ZIP — 7 points. Absorbs the
    former G3 area coverage Gate: the town being in the service area is
    evidenced by the page naming the town and ZIP (Spec s.6.2)."""
    page = ev.get("service_area_page") or {}
    return _page_item("C2.1", page, "names_town_zip",
                      "Service-area page names %s, TX %s."
                      % (ev.get("town", ""), ev.get("zip", "")),
                      "Service-area page does not name %s, TX %s."
                      % (ev.get("town", ""), ev.get("zip", "")),
                      defs)


def check_c22_install_repair(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C2.2 install and repair listed separately on that page — 6 points.
    Absorbs the former G2 services in plain words Gate. Service-page only
    (decided 2026-11-16); the listings requirement is dropped (Spec s.6.2)."""
    page = ev.get("service_area_page") or {}
    return _page_item("C2.2", page, "install_repair_separate",
                      "Install and repair listed separately on the service-area page.",
                      "Install and repair not listed separately on the service-area page.",
                      defs)


def check_c23_brands(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C2.3 brands and system types served on that page — 4 points."""
    page = ev.get("service_area_page") or {}
    return _page_item("C2.3", page, "brands_listed",
                      "Brands and system types served are listed on the service-area page.",
                      "Brands and system types served are not listed on the service-area page.",
                      defs)


def check_c24_phone_booking(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C2.4 unique primary phone and booking route on that page — 3 points.
    Absorbs the booking-route part of the former G4 contact Gate."""
    page = ev.get("service_area_page") or {}
    return _page_item("C2.4", page, "phone_and_booking",
                      "Unique primary phone and booking route on the service-area page.",
                      "Unique primary phone and booking route not both on the service-area page.",
                      defs)


def check_c31_licence(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C3.1 single consistent applicable state licence number published —
    7 points. Pass with warning (plumbing only): licence Current in the
    register but the COI expiry is unpublished. Missing: no licence
    published, or the register says it is not active. Not accessible:
    licence published but the register could not be read."""
    lic = ev.get("licence") or {}
    if not lic.get("published"):
        return _item("C3.1", NOT_ACCESSIBLE,
                     "No applicable state licence number published on the "
                     "website or listings.", defs)
    reg = lic.get("register") or {}
    if not reg.get("accessible", True):
        return _item("C3.1", NOT_ACCESSIBLE,
                     "Licence %s published but the register could not be read: %s"
                     % (lic.get("number", ""), reg.get("reason", "")),
                     defs, human_review=True,
                     review_reason="Licence published but not verified against "
                     "the register.")
    if not reg.get("active"):
        return _item("C3.1", MISSING,
                     "Licence %s published but the register does not show it "
                     "active: %s" % (lic.get("number", ""), reg.get("note", "")),
                     defs)
    if lic.get("coi_expiry_unpublished") and ev.get("trade") == "Plumbing":
        return _item("C3.1", PASS_WITH_WARNING,
                     "Licence %s Current in the register; COI expiry unpublished."
                     % lic.get("number", ""), defs)
    return _item("C3.1", PASS,
                 "Licence %s published and active in the register."
                 % lic.get("number", ""), defs)


def check_c42_diagnostic_fee(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C4.2 diagnostic fee in dollars — 7 points. Not accessible: the fee
    amount is not published on any readable source (Airtron v1.6).
    Missing: the fee is described but no dollar figure is given."""
    fee = ev.get("diagnostic_fee") or {}
    if not fee.get("accessible", True):
        return _item("C4.2", NOT_ACCESSIBLE,
                     "Diagnostic fee page could not be read: %s"
                     % fee.get("reason", ""), defs)
    if fee.get("amount") is not None:
        return _item("C4.2", PASS,
                     "Diagnostic fee in dollars: %s." % fee.get("text", ""), defs)
    if fee.get("mentioned"):
        return _item("C4.2", MISSING,
                     "Diagnostic fee mentioned but no dollar figure given: %s"
                     % fee.get("text", ""), defs)
    return _item("C4.2", NOT_ACCESSIBLE,
                 "Diagnostic/service-call fee amount not published.", defs)


def check_c43_free_estimate_install(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C4.3 free-estimate status for install, stated separately — 3 points."""
    st = ev.get("free_estimate_install") or {}
    if not st.get("accessible", True):
        return _item("C4.3", NOT_ACCESSIBLE,
                     "Free-estimate status for install could not be read: %s"
                     % st.get("reason", ""), defs)
    if st.get("stated"):
        return _item("C4.3", PASS,
                     "Free-estimate status for install stated: %s."
                     % st.get("text", ""), defs)
    return _item("C4.3", NOT_ACCESSIBLE,
                 "Free-estimate status for install not stated.", defs)


def check_c44_free_estimate_repair(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C4.4 free-estimate status for repair, stated separately — 3 points."""
    st = ev.get("free_estimate_repair") or {}
    if not st.get("accessible", True):
        return _item("C4.4", NOT_ACCESSIBLE,
                     "Free-estimate status for repair could not be read: %s"
                     % st.get("reason", ""), defs)
    if st.get("stated"):
        return _item("C4.4", PASS,
                     "Free-estimate status for repair stated: %s."
                     % st.get("text", ""), defs)
    return _item("C4.4", NOT_ACCESSIBLE,
                 "Free-estimate status for repair not stated.", defs)


def check_c51_hours_readable(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C5.1 day-by-day hours readable — 5 points. Absorbs the hours part
    of the former G5 hours / Active Status Gate: Pass on readable
    day-by-day hours OR a verifiable 24-hour / 7-day claim (Spec s.6.5).
    A closed flag is NOT an Item fail — a firm that is not in business is
    F under Spec s.5 (Spec s.4.3 rule 7)."""
    h = ev.get("hours") or {}
    if not h.get("accessible", True):
        return _item("C5.1", NOT_ACCESSIBLE,
                     "Hours could not be read: %s" % h.get("reason", ""), defs)
    if h.get("day_by_day"):
        return _item("C5.1", PASS,
                     "Day-by-day hours readable: %s." % h.get("text", ""), defs)
    if h.get("emergency_claim_verified"):
        return _item("C5.1", PASS,
                     "Verifiable 24-hour / emergency claim: %s."
                     % h.get("emergency_claim", h.get("text", "")), defs)
    if h.get("partial"):
        return _item("C5.1", MISSING,
                     "Hours published but not day-by-day: %s."
                     % h.get("text", ""), defs)
    return _item("C5.1", NOT_ACCESSIBLE,
                 "Day-by-day hours not published.", defs)


def check_c52_hours_consistent(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C5.2 hours, 24-hour, weekend, and emergency status consistent
    across sources — 2 points. Anti-aligned Item; kept as a baseline, no
    tightening (decided 2026-11-16, Spec s.6.5)."""
    h = ev.get("hours_consistency") or {}
    if not h.get("accessible", True):
        return _item("C5.2", NOT_ACCESSIBLE,
                     "Hours could not be compared across sources: %s"
                     % h.get("reason", ""), defs)
    if h.get("conflict"):
        return _item("C5.2", MISSING,
                     "Hours, 24-hour, weekend, or emergency status differs "
                     "across sources: %s" % h["conflict"], defs)
    if h.get("verified_24h_claim"):
        return _item("C5.2", PASS_WITH_WARNING,
                     "Hours readable; a verifiable 24-hour claim exists "
                     "elsewhere: %s" % h["verified_24h_claim"], defs)
    return _item("C5.2", PASS,
                 "Hours, 24-hour, weekend, and emergency status consistent "
                 "across sources.", defs)


def check_c61_phone(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C6.1 one unique primary phone number everywhere — 3 points. Absorbs
    the phone part of the former G4 contact Gate. Anti-aligned Item; kept
    scored at 3 points (decided 2026-11-16). Missing: more than one
    distinct number read. Not accessible: no phone readable."""
    phones = {norm_phone(p) for p in (ev.get("phones") or [])}
    phones.discard(None)
    if not phones:
        return _item("C6.1", NOT_ACCESSIBLE,
                     "No phone number readable on any checked source.", defs)
    if len(phones) > 1:
        return _item("C6.1", MISSING,
                     "More than one distinct phone number: %s."
                     % ", ".join(sorted(phones)), defs)
    return _item("C6.1", PASS,
                 "One unique primary phone number everywhere: %s."
                 % next(iter(phones)), defs)


def check_c62_founding_year(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C6.2 founding year and business lineage consistent across sources —
    6 points. Pass with warning: founding year on one source only.
    Missing: years differ and no lineage explains it. Not accessible: no
    founding year published anywhere readable."""
    years = ev.get("founding_years") or {}   # source -> year
    if not years:
        return _item("C6.2", NOT_ACCESSIBLE,
                     "No founding year published on any readable source.", defs)
    distinct = set(years.values())
    if len(distinct) == 1:
        if len(years) == 1:
            src, yr = next(iter(years.items()))
            return _item("C6.2", PASS_WITH_WARNING,
                         "Founding year on one source only (%s: %s)."
                         % (src, yr), defs)
        return _item("C6.2", PASS,
                     "Founding year consistent across sources: %s."
                     % next(iter(distinct)), defs)
    if ev.get("lineage_explained"):
        return _item("C6.2", PASS,
                     "Founding years differ (%s) but the lineage is explained: %s"
                     % (years, ev["lineage_explained"]), defs)
    return _item("C6.2", MISSING,
                 "Founding year differs across sources (%s) with no lineage "
                 "explaining it." % years, defs)


def check_c71_m1(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C7.1 AI crawler access (M1) — 3 points. Missing: robots.txt blocks
    an answer/search crawler or Claude-User. Pass: robots.txt missing, or
    no blocking token disallows a blocking crawler. Not accessible:
    robots.txt could not be read."""
    robots = ev.get("robots_txt") or {}
    if not robots.get("accessible", True):
        return _item("C7.1", NOT_ACCESSIBLE,
                     "robots.txt could not be read: %s"
                     % robots.get("reason", ""), defs)
    if not robots.get("exists", True):
        return _item("C7.1", PASS,
                     "No robots.txt — nothing blocks the answer/search crawlers.",
                     defs)
    blocked = [t for t in (robots.get("blocked_tokens") or [])
               if t in M1_BLOCKING_TOKENS]
    if blocked:
        return _item("C7.1", MISSING,
                     "robots.txt blocks: %s." % ", ".join(blocked), defs)
    only_non_blocking = [t for t in (robots.get("blocked_tokens") or [])
                         if t in M1_NON_BLOCKING_TOKENS]
    if only_non_blocking:
        return _item("C7.1", PASS,
                     "robots.txt blocks only training-only / non-answer tokens "
                     "(%s); the answer/search crawlers are not blocked."
                     % ", ".join(only_non_blocking), defs)
    return _item("C7.1", PASS,
                 "robots.txt does not block the answer/search crawlers or "
                 "Claude-User.", defs)


def check_c72_m2(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C7.2 key facts readable without JavaScript (M2) — 3 points. Missing:
    a key fact is not in the initial HTML. Not accessible: the initial HTML
    could not be read. (If the initial HTML fails but the rendered page
    reads, the site is readable and the minimum condition does NOT fail —
    Spec s.4.1.1 — but C7.2 fails.)"""
    html = ev.get("initial_html") or {}
    if not html.get("accessible", True):
        return _item("C7.2", NOT_ACCESSIBLE,
                     "Initial HTML could not be read: %s"
                     % html.get("reason", ""), defs)
    missing = html.get("missing_facts") or []
    if missing:
        return _item("C7.2", MISSING,
                     "Key facts not in the initial HTML (require JavaScript): %s."
                     % ", ".join(missing), defs)
    return _item("C7.2", PASS,
                 "Key facts readable in the initial HTML without JavaScript.",
                 defs)


def check_c73_m4(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C7.3 LocalBusiness structured data (M4) — 5 points. Missing: no
    valid JSON-LD, or it mismatches the visible page. Not accessible: the
    page could not be read."""
    ld = ev.get("json_ld") or {}
    if not ld.get("accessible", True):
        return _item("C7.3", NOT_ACCESSIBLE,
                     "Page could not be read for structured data: %s"
                     % ld.get("reason", ""), defs)
    if not ld.get("present"):
        return _item("C7.3", MISSING,
                     "No LocalBusiness JSON-LD found.", defs)
    if ld.get("mismatch"):
        return _item("C7.3", MISSING,
                     "LocalBusiness JSON-LD does not match the visible page: %s"
                     % ld["mismatch"], defs)
    return _item("C7.3", PASS,
                 "LocalBusiness JSON-LD present and consistent with the visible page.",
                 defs)


def check_c74_m5(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C7.4 sitemap (M5) — 2 points. Missing: no sitemap, or the sitemap
    is invalid. Not accessible: the sitemap URL could not be read."""
    sm = ev.get("sitemap") or {}
    if not sm.get("accessible", True):
        return _item("C7.4", NOT_ACCESSIBLE,
                     "Sitemap could not be read: %s" % sm.get("reason", ""), defs)
    if not sm.get("present"):
        return _item("C7.4", MISSING,
                     "No sitemap found at %s." % sm.get("checked_url", "the usual locations"),
                     defs)
    if not sm.get("valid"):
        return _item("C7.4", MISSING,
                     "Sitemap found but invalid: %s" % sm.get("reason", ""), defs)
    return _item("C7.4", PASS,
                 "Sitemap present and valid: %s." % sm.get("url", ""), defs)


ITEM_CHECKS = {
    "C1.1": check_c11_rating_readable,
    "C1.2": check_c12_rating_figures,
    "C1.3": check_c13_complaints,
    "C2.1": check_c21_area_page,
    "C2.2": check_c22_install_repair,
    "C2.3": check_c23_brands,
    "C2.4": check_c24_phone_booking,
    "C3.1": check_c31_licence,
    "G6": check_g6_listing,
    "C4.2": check_c42_diagnostic_fee,
    "C4.3": check_c43_free_estimate_install,
    "C4.4": check_c44_free_estimate_repair,
    "C5.1": check_c51_hours_readable,
    "C5.2": check_c52_hours_consistent,
    "C6.1": check_c61_phone,
    "C6.2": check_c62_founding_year,
    "G1": check_g1_exact_name,
    "C7.1": check_c71_m1,
    "C7.2": check_c72_m2,
    "C7.3": check_c73_m4,
    "C7.4": check_c74_m5,
}

# ---------------------------------------------------------------------------
# Section 6 Ranking Suggestions (Observed / Recommendation / Not checked)
# — Spec s.4.3 rule 8, s.9. Never scored, never affect the Grade. Display
# words on the Final card are COMPLETE (Observed) or SUGGESTED
# (Recommendation or Not checked). A firm's statement alone is never
# Observed for a live-test suggestion.
# ---------------------------------------------------------------------------


def _suggestion(suggestion_id: str, result: str, evidence: str,
                defs: Definitions, category: Optional[str] = None) -> Row:
    return Row(0, "Ranking Suggestion", SUGGESTION_LABELS[suggestion_id],
               result, evidence, defs.why("lever", suggestion_id),
               category=category, lever_id=suggestion_id)


def check_suggestion_booking_route(ev: Dict[str, Any], defs: Definitions) -> Row:
    lv = ev or {}
    if not lv.get("accessible", True):
        return _suggestion("booking_route", NOT_CHECKED,
                           "Booking route could not be checked: %s" % lv.get("reason", ""),
                           defs)
    if (lv.get("route") and lv.get("next_step") and lv.get("written_quote")):
        return _suggestion("booking_route", OBSERVED,
                           "Route (%s), what happens next (%s), and a quote in writing "
                           "before work (%s)." % (lv["route"], lv["next_step"], lv["written_quote"]),
                           defs)
    return _suggestion("booking_route", RECOMMENDATION,
                       "Booking route shown but the next step or a written quote before "
                       "work is not published.", defs)


def check_suggestion_availability(ev: Dict[str, Any], defs: Definitions) -> Row:
    lv = ev or {}
    if not lv.get("accessible", True):
        return _suggestion("availability", NOT_CHECKED,
                           "Availability could not be checked: %s" % lv.get("reason", ""),
                           defs)
    if lv.get("next_appointment") or lv.get("emergency_window") or lv.get("disclosed_test"):
        return _suggestion("availability", OBSERVED,
                           "Next appointment / emergency window published or proven by "
                           "a disclosed test: %s." % (lv.get("next_appointment")
                           or lv.get("emergency_window") or lv.get("disclosed_test")),
                           defs)
    return _suggestion("availability", RECOMMENDATION,
                       "No next appointment or emergency window published.",
                       defs)


def check_suggestion_price(ev: Dict[str, Any], defs: Definitions) -> Row:
    lv = ev or {}
    if not lv.get("accessible", True):
        return _suggestion("price", NOT_CHECKED,
                           "Price could not be checked: %s" % lv.get("reason", ""),
                           defs)
    if lv.get("diagnostic_fee") is not None and (lv.get("price_range") or lv.get("written_quote_process")):
        return _suggestion("price", OBSERVED,
                           "Diagnostic fee %s and %s."
                           % (lv["diagnostic_fee"], lv.get("price_range") or lv.get("written_quote_process")),
                           defs)
    return _suggestion("price", RECOMMENDATION,
                       "No diagnostic fee in dollars with a price range or written-quote "
                       "process published.", defs)


def check_suggestion_brand_coverage(ev: Dict[str, Any], defs: Definitions) -> Row:
    lv = ev or {}
    if not lv.get("accessible", True):
        return _suggestion("brand_coverage", NOT_CHECKED,
                           "Brand coverage could not be checked: %s" % lv.get("reason", ""),
                           defs)
    if lv.get("brands_listed"):
        return _suggestion("brand_coverage", OBSERVED,
                           "Brands / system types actually served are listed: %s."
                           % lv["brands_listed"], defs)
    return _suggestion("brand_coverage", RECOMMENDATION,
                       "No brands or system types actually served are listed.",
                       defs)


def check_suggestion_dispatch(ev: Dict[str, Any], defs: Definitions) -> Row:
    lv = ev or {}
    if not lv.get("accessible", True):
        return _suggestion("dispatch", NOT_CHECKED,
                           "Dispatch could not be checked: %s" % lv.get("reason", ""),
                           defs)
    if lv.get("disclosed_test") or lv.get("firm_evidence"):
        return _suggestion("dispatch", OBSERVED,
                           "Dispatch proven by a disclosed test or firm evidence: %s."
                           % (lv.get("disclosed_test") or lv.get("firm_evidence")),
                           defs)
    return _suggestion("dispatch", RECOMMENDATION,
                       "Service-area page alone does not prove dispatch.",
                       defs)


def check_suggestion_llms_txt(ev: Dict[str, Any], defs: Definitions) -> Row:
    lv = ev or {}
    if not lv.get("accessible", True):
        return _suggestion("llms_txt", NOT_CHECKED,
                           "llms.txt could not be checked: %s" % lv.get("reason", ""),
                           defs)
    if lv.get("exists") and lv.get("lists_services") and lv.get("lists_area"):
        return _suggestion("llms_txt", OBSERVED,
                           "/llms.txt exists, is reachable, and lists services and the "
                           "service area.", defs)
    if lv.get("exists"):
        return _suggestion("llms_txt", RECOMMENDATION,
                           "/llms.txt exists but does not list services and the service area.",
                           defs)
    return _suggestion("llms_txt", RECOMMENDATION,
                       "No /llms.txt found.", defs)


SUGGESTION_CHECKS = {
    "booking_route": check_suggestion_booking_route,
    "availability": check_suggestion_availability,
    "price": check_suggestion_price,
    "brand_coverage": check_suggestion_brand_coverage,
    "dispatch": check_suggestion_dispatch,
    "llms_txt": check_suggestion_llms_txt,
}

# v1.22 names, kept as aliases: run_c7_sweep.py (a v1.22 study script)
# imports check_lever_llms_txt from this module.
check_lever_booking_route = check_suggestion_booking_route
check_lever_availability = check_suggestion_availability
check_lever_price = check_suggestion_price
check_lever_brand_coverage = check_suggestion_brand_coverage
check_lever_dispatch = check_suggestion_dispatch
check_lever_llms_txt = check_suggestion_llms_txt
LEVER_CHECKS = SUGGESTION_CHECKS


# ---------------------------------------------------------------------------
# Section 4 Ranking Suggestions (Spec s.6.3, s.6.4, s.6.7) — not scored.
# Since Tim's decision 2026-11-18 (decision 10) they ARE Audit Data rows
# (seq 35-36, after the six Section 6 suggestions), as well as being
# carried on the result object for the Final card's Section 4. Status
# vocabulary (Spec s.4.3 rule 8, decided by Tim 2026-11-18): Complete /
# Suggested / Not checked — NOT Observed / Recommendation / Not checked,
# which is the vocabulary of the six Section 6 factors only.
#   Complete  = the firm already has it: C3.2 BBB accreditation and rating
#               consistent with bbb.org — the firm is BBB accredited AND
#               its rating on bbb.org is consistent with the rating shown
#               on the firm's site or listings; C4.1 six-line warranty
#               card — the six-line warranty card is present on the site
#               with all six lines and real numbers.
#   Suggested = the firm does not have it — the suggestion is made to the
#               firm in Section 4 of the Final card.
#   Not checked = the check itself cannot be performed (bbb.org cannot be
#               read for C3.2 BBB accreditation and rating consistent with
#               bbb.org, or the site cannot be read for C4.1 six-line
#               warranty card). A firm with no BBB profile found on bbb.org
#               is Not checked, not Suggested: there is no profile to read
#               the accreditation and rating from.
# On the Final card Section 4 rows display as COMPLETE (Complete) or
# SUGGESTED (Suggested or Not checked).
# ---------------------------------------------------------------------------


def check_section4_bbb(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C3.2 BBB accreditation and rating consistent with bbb.org —
    Ranking Suggestion, Section 4, not scored (Spec s.6.3, s.4.3 rule 8).
    Complete only if the firm is BBB accredited AND its rating on bbb.org
    is consistent with the rating shown on the firm's site or listings.
    The evidence carries "accredited" (True / False / None) from the
    bbb.org read (run_audit._bbb_evidence); accreditation not confirmed
    on bbb.org is Suggested, not Complete — a firm's own claim alone is
    never Complete."""
    bbb = ev.get("bbb") or {}
    category, label = SECTION_4_SUGGESTIONS["C3.2"]
    if not bbb.get("claim"):
        return Row(0, "Ranking Suggestion", label, SUGGESTED,
                   "No BBB accreditation or rating published — add the claim "
                   "to the website and the BBB profile (a business not on BBB "
                   "can add itself for free at https://www.bbb.org/get-listed).",
                   defs.why("item", "C3.2"), category=category, item_id="C3.2")
    if not bbb.get("bbb_org_accessible", True):
        return Row(0, "Ranking Suggestion", label, NOT_CHECKED,
                   "BBB claim (%s) not independently read on bbb.org: %s"
                   % (bbb["claim"], bbb.get("reason", "")),
                   defs.why("item", "C3.2"), category=category, item_id="C3.2")
    if bbb.get("consistent") and bbb.get("accredited") is True:
        return Row(0, "Ranking Suggestion", label, COMPLETE,
                   "BBB accredited; claim (%s) consistent with bbb.org."
                   % bbb["claim"], defs.why("item", "C3.2"),
                   category=category, item_id="C3.2")
    if bbb.get("consistent"):
        return Row(0, "Ranking Suggestion", label, SUGGESTED,
                   "BBB rating consistent with bbb.org but accreditation "
                   "not confirmed on bbb.org — claim the BBB profile so "
                   "rating and accreditation are readable on bbb.org.",
                   defs.why("item", "C3.2"), category=category, item_id="C3.2")
    return Row(0, "Ranking Suggestion", label, SUGGESTED,
               "BBB claim (%s) does not match bbb.org (%s) — correct the "
               "claim on the website."
               % (bbb["claim"], bbb.get("bbb_org", "")),
               defs.why("item", "C3.2"), category=category, item_id="C3.2")


def check_section4_warranty(ev: Dict[str, Any], defs: Definitions) -> Row:
    """C4.1 six-line warranty card — Ranking Suggestion, Section 4, not
    scored (Spec s.6.7, s.4.3 rule 8). All six lines with real numbers
    are required for Complete."""
    w = ev.get("warranty") or {}
    category, label = SECTION_4_SUGGESTIONS["C4.1"]
    if not w.get("accessible", True):
        return Row(0, "Ranking Suggestion", label, NOT_CHECKED,
                   "Warranty page could not be read: %s"
                   % w.get("reason", ""), defs.why("item", "C4.1"),
                   category=category, item_id="C4.1")
    lines = w.get("lines") or {}
    present = [k for k, v in lines.items() if v]
    if len(present) == 6:
        return Row(0, "Ranking Suggestion", label, COMPLETE,
                   "Six-line warranty card present: %s."
                   % "; ".join(sorted(present)), defs.why("item", "C4.1"),
                   category=category, item_id="C4.1")
    if not present:
        return Row(0, "Ranking Suggestion", label, SUGGESTED,
                   "Six-line warranty card not published — publish the six "
                   "lines on the service page.", defs.why("item", "C4.1"),
                   category=category, item_id="C4.1")
    return Row(0, "Ranking Suggestion", label, SUGGESTED,
               "Warranty card published but incomplete (%d of 6 lines: %s; "
               "missing: %s) — publish the missing lines."
               % (len(present), ", ".join(sorted(present)),
                  ", ".join(sorted(set(lines) - set(present)))),
               defs.why("item", "C4.1"), category=category, item_id="C4.1")


SECTION_4_SUGGESTION_CHECKS = {
    "C3.2": check_section4_bbb,
    "C4.1": check_section4_warranty,
}

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


@dataclass
class AuditResult:
    firm: str
    query: str
    town_zip: str
    date_checked: str
    spec_version: str
    rows: List[Row] = field(default_factory=list)
    grade: str = ""              # "" = no grade assigned (unverified audit)
    total_points: int = 0        # sum of Category scores, out of 100
    high_issues: int = 0
    passed_items: int = 0
    website_unreadable: bool = False
    unverified: bool = False     # AI Sharc-side / undecided reason: no grade
    unverified_reason: str = ""  # e.g. PROXY-REFUSED, BLOCKED, JS-ONLY
    f_reason: str = ""           # Spec s.5 F reason when grade == "F"
    human_review: List[Row] = field(default_factory=list)
    category_results: Dict[str, str] = field(default_factory=dict)
    category_scores: Dict[str, int] = field(default_factory=dict)
    section_4_suggestions: List[Row] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "firm": self.firm,
            "query": self.query,
            "town_zip": self.town_zip,
            "date_checked": self.date_checked,
            "spec_version": self.spec_version,
            "grade": self.grade,
            "total_points": self.total_points,
            "high_issues": self.high_issues,
            "passed_items": self.passed_items,
            "website_unreadable": self.website_unreadable,
            "unverified": self.unverified,
            "unverified_reason": self.unverified_reason,
            "f_reason": self.f_reason,
            "category_results": self.category_results,
            "category_scores": self.category_scores,
            "rows": [r.as_dict() for r in self.rows],
            "section_4_suggestions": [r.as_dict()
                                      for r in self.section_4_suggestions],
            "human_review": [r.as_dict() for r in self.human_review],
        }


def _minimum_condition(website: Dict[str, Any]) -> tuple:
    """The Spec s.5 minimum condition. Returns (outcome, reason) where
    outcome is "ok", "F", or "unverified".

    website keys (from the runner): unreadable (bool), reason (the
    Inability to Access Website Reason code, e.g. DEAD / PROXY-REFUSED /
    BLOCKED, or ""), readable (bool — some method produced text),
    has_website (bool), closed_permanently (bool), closed_flag (str).
    A firm with no website at all is F. A closed firm (permanently or
    temporarily) is not audited at all since Spec v2.13 s.5 — the runner
    skips it before scoring — so closure is never an F reason here.
    """
    if not website.get("has_website", True):
        return "F", "NO-WEBSITE"
    if website.get("unreadable"):
        reason = website.get("reason") or ""
        if reason in FIRM_SIDE_REASONS:
            return "F", reason
        return "unverified", reason or "UNKNOWN"
    if not website.get("readable", True):
        # No method produced text and the rendered read did not decide it
        # (not attempted, or BLOCKED / JS-ONLY): do not treat it as a
        # failure until the rendered read also fails (Spec s.4.1.1).
        return "unverified", website.get("reason") or "RENDER-UNDECIDED"
    return "ok", ""


def score_audit(firm: str, query: str, town_zip: str, date_checked: str,
                evidence: Dict[str, Any], defs: Definitions,
                spec_version: str = "2.1") -> AuditResult:
    """Score one audit from its evidence. Returns the 36 rows (7 Category
    results, 21 Items, 8 Ranking Suggestions) plus the grade and counts.
    Spec s.13: new audits record spec_version '2.1' with 36 rows
    (0/7/21/8) since Tim's decision 2026-11-18 (decision 10): the two
    Section 4 Ranking Suggestions (C3.2, C4.1) are rows as well as being
    carried on the result for the Final card's Section 4."""
    result = AuditResult(firm=firm, query=query, town_zip=town_zip,
                         date_checked=date_checked, spec_version=spec_version)
    rows: List[Row] = []
    seq = 0

    website = evidence.get("website") or {}
    result.website_unreadable = bool(website.get("unreadable"))
    outcome, reason = _minimum_condition(website)

    # --- Section 4 Ranking Suggestions (evaluated, then rows) -----------
    section_4: List[Row] = []
    for item_id in SECTION_4_SUGGESTION_IDS:
        row = SECTION_4_SUGGESTION_CHECKS[item_id](
            evidence.get("items", {}).get(item_id, {}), defs)
        section_4.append(row)
    result.section_4_suggestions = section_4

    if outcome in ("F", "unverified"):
        # No Items are scored and no points are given (Spec s.5). The 36
        # rows are still emitted so the audit reconciles (Spec s.13), with
        # the Items recorded as Not accessible and the reason stated.
        if outcome == "F":
            result.grade = "F"
            result.f_reason = reason
            not_scored_note = (
                "Not scored — firm is F under Spec s.5 (Website Access: %s); "
                "no points are given." % _f_reason_text(reason, website))
        else:
            result.grade = ""  # no grade assigned until a re-check verifies
            result.unverified = True
            result.unverified_reason = reason
            not_scored_note = (
                "Not scored — audit unverified (%s); no grade is assigned "
                "until a re-check verifies the site." % reason)
        item_rows: List[Row] = []
        for category in CATEGORY_ORDER:
            for item_id in sorted(ITEM_CATALOG):
                cat, _label = ITEM_CATALOG[item_id]
                if cat != category:
                    continue
                seq += 1
                row = _item(item_id, NOT_ACCESSIBLE, not_scored_note, defs,
                            human_review=True,
                            review_reason="Website Access outcome (%s); Item "
                            "not scored." % outcome)
                row.seq = seq
                item_rows.append(row)
                rows.append(row)
        for category in CATEGORY_ORDER:
            seq += 1
            result.category_scores[category] = 0
            result.category_results[category] = "0 of %d points" % CATEGORY_POINTS[category]
            rows.append(Row(seq, "Category result", category,
                            result.category_results[category],
                            "No points — %s" % ("firm is F" if outcome == "F"
                                                else "audit unverified"),
                            "A Category's score is the sum of the points of "
                            "the Items in it that passed (Spec s.8).",
                            category=category, points=0,
                            points_available=CATEGORY_POINTS[category]))
        for suggestion_id in SUGGESTION_IDS:
            seq += 1
            row = _suggestion(suggestion_id, NOT_CHECKED, not_scored_note, defs)
            row.seq = seq
            rows.append(row)
        # Section 4 Ranking Suggestions: Not checked like the six Section 6
        # suggestions above (the website could not be verified, so neither
        # the BBB claim nor the warranty card can be confirmed). The
        # evaluated rows are replaced on the result so section_4_suggestions
        # matches the rows.
        section_4_not_checked: List[Row] = []
        for item_id in SECTION_4_SUGGESTION_IDS:
            seq += 1
            category, label = SECTION_4_SUGGESTIONS[item_id]
            row = Row(seq, "Ranking Suggestion", label, NOT_CHECKED,
                      not_scored_note, defs.why("item", item_id),
                      category=category, item_id=item_id)
            section_4_not_checked.append(row)
            rows.append(row)
        result.section_4_suggestions = section_4_not_checked
        result.rows = rows
        result.total_points = 0
        result.high_issues = 0
        result.passed_items = 0
        result.human_review = [r for r in rows if r.human_review]
        assert len(rows) == 36, "expected 36 rows, got %d" % len(rows)
        return result

    # --- Scored Items, grouped by Category -------------------------------
    item_rows = []
    for category in CATEGORY_ORDER:
        for item_id in sorted(ITEM_CATALOG):
            cat, _label = ITEM_CATALOG[item_id]
            if cat != category:
                continue
            seq += 1
            row = ITEM_CHECKS[item_id](evidence.get("items", {}).get(item_id, {}), defs)
            row.seq = seq
            item_rows.append(row)
            rows.append(row)

    # --- Category results: points subtotals, never counted as Items -------
    for category in CATEGORY_ORDER:
        seq += 1
        cat_items = [r for r in item_rows if r.category == category]
        earned = sum(r.points for r in cat_items)
        available = CATEGORY_POINTS[category]
        result.category_scores[category] = earned
        result.category_results[category] = "%d of %d points" % (earned, available)
        passed_n = sum(1 for r in cat_items if r.result in PASSED_ITEM_RESULTS)
        failed_labels = ["%s (%s)" % (r.item_id, r.label) for r in cat_items
                         if r.result in FAILED_ITEM_RESULTS]
        evidence_text = "%d of %d Items passed; %d of %d points." % (
            passed_n, len(cat_items), earned, available)
        if failed_labels:
            evidence_text += " Failed Items: %s." % "; ".join(failed_labels)
        rows.append(Row(seq, "Category result", category,
                        result.category_results[category],
                        evidence_text,
                        "A Category's score is the sum of the points of the "
                        "Items in it that passed (Spec s.8).",
                        category=category, points=earned,
                        points_available=available))

    # --- Ranking Suggestions (Section 6) ----------------------------------
    for suggestion_id in SUGGESTION_IDS:
        seq += 1
        row = SUGGESTION_CHECKS[suggestion_id](
            evidence.get("levers", {}).get(suggestion_id, {}), defs)
        row.seq = seq
        rows.append(row)

    # --- Ranking Suggestions (Section 4): C3.2, C4.1 -----------------------
    # The same rows already evaluated above (carried on the result for the
    # Final card's Section 4); they are rows now (seq 35-36), un-scored.
    for row in section_4:
        seq += 1
        row.seq = seq
        rows.append(row)

    result.rows = rows
    result.total_points = sum(result.category_scores.values())
    result.high_issues = sum(
        1 for r in item_rows if r.result in FAILED_ITEM_RESULTS)
    result.passed_items = sum(
        1 for r in item_rows if r.result in PASSED_ITEM_RESULTS)
    result.human_review = [r for r in rows if r.human_review]
    result.grade = grade_from_points(result.total_points)

    # Reconciliation (Spec s.13): 7 Category results + 21 Items + 8 Ranking
    # Suggestions = 36 rows. Points reconcile against the allocation.
    assert len(rows) == 36, "expected 36 rows, got %d" % len(rows)
    assert len(item_rows) == 21
    assert len(result.category_results) == 7
    assert len([r for r in rows if r.row_type == "Ranking Suggestion"]) == 8
    assert result.total_points == sum(
        r.points for r in item_rows), "total points do not match Item rows"
    assert sum(ITEM_POINTS.values()) == 100, "allocation must total 100"
    return result


def _f_reason_text(reason: str, website: Dict[str, Any]) -> str:
    """Human-readable text for an F reason (Spec s.5)."""
    texts = {
        "NO-WEBSITE": "the firm has no website at all",
        "NOT-IN-BUSINESS": "the firm is not in business (%s)"
        % (website.get("closed_flag") or "closed flag"),
        "CERT-INVALID": "the site's TLS certificate is expired or invalid",
        "PARKED": "the domain serves a parking / domain-for-sale page",
        "DEAD": "the domain does not resolve or the server does not respond",
        "SUSPENDED": "the hosting account is suspended",
        "WRONG-CONTENT": "the URL returns content for a different business",
    }
    return texts.get(reason, reason)


def percentile_rank(rank: int, eligible_count: int) -> int:
    """Percentile = share of eligible firms below this firm, rounded up
    (Spec s.8). Rank counts down from the top: rank 30 of 80 -> 63rd."""
    if eligible_count <= 1:
        return 100
    below = eligible_count - rank
    return math.ceil(below / eligible_count * 100)


def top_percent(rank: int, eligible_count: int) -> int:
    """Top percent = eligible rank / eligible firm count, rounded up (Spec s.8)."""
    return math.ceil(rank / eligible_count * 100)


def load_definitions(path: Optional[str] = None) -> Definitions:
    if path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "definitions.json")
    return Definitions.load(path)
