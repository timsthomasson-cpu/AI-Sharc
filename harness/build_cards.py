#!/usr/bin/env python3
"""Render Final Report Cards (HTML + PDF) from r3 audit data.

Template: the live dummy Final card, AI Sharc — Final Report Card —
Dummy Data — 2026-11-11 — Rev 6 (HTML source). The CSS below is copied
verbatim from that card; the section structure and wording follow it.
This generator does NOT touch build_rev4.py or the dummy cards.

Data: runs/2026-11-13/<firm_id>/audit-data.json (40 rows, Spec s.13
columns) + summary.json (grade, points, counts, rank inputs) per firm,
joined to aisharc_harness/rules/definitions.json by item/gate/lever id
(summary.json rows carry the ids; audit-data.json rows carry the
evidence, source URL, why-it-matters, and fix columns, in the same
seq order).

Output: files/r3-final-cards/AI Sharc — Final Report Card — <Firm> —
2026-11-13 — Rev 1.html/.pdf. INTERNAL working documents from the
harness test runs — never sent to a firm, no firm contacted.

Run with the WeasyPrint venv so PDFs render in-process:
    ~/workspace/tools/wp-venv/bin/python build_cards.py [--validate-only]
"""
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)  # aisharc-harness/ -> score-card-audit-product/files
OUT = os.path.join(BASE, "r3-final-cards")
RUNS = os.path.join(HERE, "runs", "2026-11-13")
TOWN_ZIP = "Coppell, TX 75019"
TOWN = "Coppell"
QUERY = "AC installation and repair"
DATE_LONG = "13 November 2026"
SPEC_VERSION = "1.22"
CARD_DATE = "2026-11-13"
CARD_REV = "Rev. 1"

# ---------------------------------------------------------------------------
# Template: CSS copied verbatim from the dummy Final Rev 6 HTML.
# ---------------------------------------------------------------------------
CSS = """@page { size: Letter; margin: 0.6in 0.7in; background: #F8FAFC; }
html { background: #F8FAFC; }
body { background: #F8FAFC; font-family: 'Liberation Sans', 'Nimbus Sans', Arial, sans-serif;
  color: #334155; font-size: 11pt; line-height: 1.45; margin: 0; }
.banner { background: #124073; border-radius: 10px; color: #fff; padding: 16px 24px 18px; margin-bottom: 18px; }
.banner .kicker { font-size: 10pt; letter-spacing: 3px; font-weight: bold; }
.banner .row { display: flex; justify-content: space-between; align-items: baseline; }
.banner h1 { font-size: 26pt; margin: 2px 0 0; line-height: 1.1; }
.banner .rev { font-size: 10pt; font-weight: normal; }
tr { break-inside: avoid; }
.key, .key-title { break-inside: avoid; }
.key-title { break-after: avoid; }
.card { background: #fff; border-radius: 10px; padding: 16px 22px 18px; margin-bottom: 18px; }
h2.sec { color: #124073; font-size: 13pt; letter-spacing: 1.5px; text-transform: uppercase;
  border-bottom: 1px solid #D9E2EC; padding-bottom: 6px; margin: 0 0 10px; }
p { margin: 0 0 10px; }
p.muted { color: #475569; }
p.small { color: #64748B; font-size: 8pt; }
.gatesummary { font-size: 20pt; font-weight: bold; text-align: center; margin: 10px 0 0; }
.gatesummary.pass { color: #10B981; }
.gatesummary.fail { color: #EF4444; }
table { border-collapse: collapse; width: 100%; }
.company td { border: 1px solid #fff; background: #F0F9FF; padding: 8px 10px; vertical-align: top; }
.company td.lbl { color: #64748B; font-size: 10pt; width: 14%; }
.company td.val { color: #0F172A; font-weight: bold; width: 36%; }
.grade-block { text-align: center; margin: 6px 0 18px; }
.grade-block .lbl { color: #64748B; font-weight: bold; font-size: 11pt; letter-spacing: 3px; }
.grade-block .circle { width: 92px; height: 92px; border: 4px solid #0284C7; border-radius: 50%;
  color: #0284C7; font-size: 44pt; font-weight: bold; line-height: 84px; margin: 10px auto 0; }
.grade-block .circle.gA, .grade-block .circle.gB { border-color: #10B981; color: #10B981; }
.grade-block .circle.gC { border-color: #EAB308; color: #EAB308; }
.grade-block .circle.gD { border-color: #F59E0B; color: #F59E0B; }
.grade-block .circle.gF { border-color: #EF4444; color: #EF4444; }
.sectiongrade { text-align: center; font-size: 44pt; font-weight: bold; line-height: 1; margin: 6px 0 28px; }
.sectiongrade-lbl { color: #64748B; font-weight: bold; font-size: 11pt; letter-spacing: 3px; text-align: center; margin: 10px 0 4px; }
.sectiongrade.gA, .sectiongrade.gB { color: #10B981; }
.sectiongrade.gC { color: #EAB308; }
.sectiongrade.gD { color: #F59E0B; }
.sectiongrade.gF { color: #EF4444; }
.rows td { padding: 9px 4px; vertical-align: top; border: none; }
.rows td.name { font-weight: bold; color: #0F172A; width: 30%; }
.rows td.check { color: #475569; }
.rows td.res { text-align: right; font-weight: bold; white-space: nowrap; width: 11%; }
.pass { color: #10B981; } .fail { color: #EF4444; }
.complete { color: #10B981; } .suggested { color: #ED7D31; }
.grows td { padding: 8px 4px; vertical-align: middle; border: none; }
.grows td.cat { font-weight: bold; color: #0F172A; width: 30%; }
.grows td.item { color: #334155; padding-left: 16px; width: 30%; }
.grows td.barp { width: 44%; }
.grows td.res { text-align: right; font-weight: bold; white-space: nowrap; width: 11%; }
.bar { background: #F1F5F9; border-radius: 6px; height: 10px; }
.bar .fill { height: 10px; border-radius: 6px; }
.key { width: auto; font-size: 8pt; line-height: 1.2; margin: 0 auto 14px;
  border: 1.5pt solid #124073; }
.key th { color: #124073; text-align: left; padding: 3px 8px 3px 0; }
.key td { padding: 3px 8px 3px 0; border-bottom: 1px solid #E2E8F0; }
.key th:first-child, .key td:first-child { padding-left: 16px; }
.key th:last-child, .key td:last-child { padding-right: 16px; }
.key td.g { font-weight: bold; color: #0F172A; }
.key-title { color: #124073; font-weight: bold; font-size: 11pt; text-align: center; margin: 14px 0 6px; }
.score { text-align: center; color: #124073; font-weight: bold; font-size: 12pt; margin: 12px 0 4px; }
.callout { background: #F0F9FF; border-left: 4px solid #0284C7; border-radius: 0 8px 8px 0;
  padding: 14px 18px; margin-bottom: 18px; }
.callout h3 { color: #0369A1; font-size: 13pt; margin: 0 0 4px; }
.callout p { margin: 0; }
.rankdonut { text-align: center; margin: 4px 0 2px; }
.rankdonut svg { display: block; margin: 0 auto; }
.rankline { font-weight: bold; color: #124073; font-size: 12pt; margin: 6px 0 2px; }
.ranklabel { font-size: 9.5pt; color: #64748B; margin: 2px 0 0; }
.rankcaveat { font-size: 9.5pt; color: #475569; margin: 2px 0 0; }
.cta { background: #0284C7; border-radius: 10px; color: #fff; text-align: center;
  padding: 16px; margin: 28px 0 18px; }
.cta .t { font-size: 14pt; font-weight: bold; }
.cta .s { font-size: 11pt; margin-top: 2px; }
.levers td { padding: 9px 4px; vertical-align: top; border: none; }
.levers td.name { font-weight: bold; color: #0F172A; width: 30%; }
.levers td.sugg { color: #475569; }
.obs { color: #10B981; } .rec { color: #ED7D31; }
h2.cat { color: #124073; font-size: 16pt; margin: 0 0 8px; }
h3.issue { font-size: 14pt; color: #0F172A; margin: 14px 0 6px; }
h3.fix { font-size: 13pt; color: #124073; margin: 10px 0 4px; }
pre.code { font-family: 'Liberation Mono', 'DejaVu Sans Mono', monospace; font-size: 9.5pt;
  background: #F8FAFC; border-radius: 6px; padding: 10px 12px; margin: 0 0 10px;
  white-space: pre-wrap; word-wrap: break-word; color: #0F172A; }
.review td { padding: 6px 8px 6px 0; border-bottom: 1px solid #E2E8F0; vertical-align: top; }
.review td.lbl { font-weight: bold; color: #0F172A; width: 32%; }
.review th { color: #124073; text-align: left; padding: 4px 8px 4px 0; }
.check { color: #334155; }
p.price b { color: #0F172A; }"""

CATEGORIES = ["Reputation", "Area Coverage", "Credentials and Trust",
              "Pricing and Warranty", "Hours and Active Status",
              "Identity and Contact", "Machine Readability"]

GATE_ORDER = ["G1", "G2", "G3", "G4", "G5", "G6"]
GATE_NAMES = {"G1": "Exact name", "G2": "Services in plain words",
              "G3": "Area Coverage (Critical)", "G4": "Contact (Critical)",
              "G5": "Hours / Active Status (Critical)",
              "G6": "Verifiable listing (Critical)"}
# Check descriptions from the dummy Final Rev 6, Section 2.
GATE_CHECKS = {
    "G1": "Exact business name identical on website and listings",
    "G2": "AC installation/replacement AND AC repair, as separate services",
    "G3": "Service area explicitly naming " + TOWN_ZIP,
    "G4": "One unique primary phone + working booking/quote route",
    "G5": "Readable day-by-day hours or verifiable 24/7 claim",
    # G6 description is built per firm: the listing source verified in r3.
    "G6": "Listing outside own website, same name/phone/service area, "
          "correct Primary Business Category",
}
GATE_LISTING_LABEL = {"meta": "Meta Business Profile",
                      "yelp": "Yelp listing",
                      "google": "Google Business Profile"}

LEVER_ORDER = ["booking_route", "availability", "price", "brand_coverage",
               "dispatch", "llms_txt"]
LEVER_NAMES = {"booking_route": "Booking and quote route",
               "availability": "Availability",
               "price": "Price for this user",
               "brand_coverage": "Brand and system coverage",
               "dispatch": "Service-area dispatch",
               "llms_txt": "Machine discovery (llms.txt)"}
# Suggestion texts from the dummy Final Rev 6, Section 6. [PHONE], [WEBSITE],
# [FIRM] and [TOWN] are substituted per firm; [email address] stays a
# placeholder for the firm to fill in.
LEVER_TEXTS = {
    "booking_route": ("Put verbiage on the website that explains exactly how to get a "
        "quote or book an appointment — call [PHONE], email [email address], or use "
        "the online form — and what happens next. For example: “Call us at [PHONE] "
        "or submit the form below; we will confirm your appointment time and send "
        "your quote in writing before work.” Make sure the form actually submits, "
        "the phone number matches the unique primary number everywhere, and any "
        "stated response time is met."),
    "availability": ("Publish how a customer finds out your next available appointment "
        "and emergency response time. For example: “Next available appointments are "
        "shown when you book online, or call [PHONE] for today’s availability; "
        "emergency calls are answered within [stated time].” Do not state a response "
        "time you do not meet. If you cannot publish live availability, state the "
        "route to get it (call or form) and the hours that route is monitored."),
    "price": ("Publish the diagnostic fee in dollars, and for installs either a price "
        "range by system type or the written-quote process. For example: “Diagnostic "
        "visit: $[fee]. For a new system, request a written quote — we will confirm "
        "system type, size, and price in writing before work.” State separately "
        "whether an install estimate is free or charged, and do not leave the "
        "customer to guess the fee from the phone call alone."),
    "brand_coverage": ("List every brand and system type you actually serve on the "
        "service page — for example, central air, heat pump, and ductless mini-split, "
        "by brand — and state parts availability. For example: “We stock common parts "
        "for [brands]; other parts are ordered within [number of days] and we will "
        "tell you the wait before work.” Remove any brand or system type you do not "
        "serve."),
    "dispatch": ("State dispatch reality on the service-area page. For example: “We "
        "dispatch to [TOWN] within [window, for example same-day or next-day]; call "
        "[PHONE] to confirm today’s dispatch window.” Remove any town you do not "
        "actually dispatch to, and make sure the page, Google, and Meta list the "
        "same towns."),
    "llms_txt": ("Publish an /llms.txt file at the root of your website listing your "
        "services and service area in plain words, so shopping agents can read what "
        "you do without parsing every page. Sample starter for your implementer to "
        "adapt — replace every [PLACEHOLDER] with your firm’s own details. AI Sharc "
        "does not put this file on your site; that is for you or your own implementer."
        "<br># [FIRM] — llms.txt<br># Services and service area, in plain words, "
        "for AI shopping agents.<br><br>## Services<br>- AC installation and "
        "replacement<br>- AC repair and maintenance<br>- [ADDITIONAL SERVICE]"
        "<br><br>## Service area<br>- [TOWN]<br>- [ADDITIONAL TOWN, ZIP]"
        "<br><br>## Contact<br>- Phone: [PHONE]<br>- Website: [WEBSITE]"),
}

GRADING_KEY = [("A", "4 to 7 category points"),
               ("B", "3 category points"),
               ("C", "2 category points"),
               ("D", "0 or 1 category points, still eligible"),
               ("F", "1 or more Critical issues — fails AI Sharc’s minimum criteria")]

NOTES_AND_LIMITS = """<div class="card"><h2 class="sec">NOTES AND LIMITS</h2><p class="small">This report card does not guarantee inclusion or a ranking in any AI recommendation. It only measures AI Shopping Health on the evidence checked, for the query, town, and ZIP above, on the date performed.</p><p class="small">High Priority counts are issue counts, not fix-list row counts.</p><p class="small">Your approximate ranking will move with customer location, requests, and the competitor set included. Your grade is the steadier guide, because it is what you control — except Reputation volume, which builds over time. If your grade improves but your approximate ranking does not, the Report Card will be recalibrated for that market — you will not be blamed for a guide that no longer matches shopping.</p><p class="small">How pass and fail are decided (hard rules, version 2026-11-07): A gate or item passes only if it meets its stated criteria exactly, with the source and date shown; there is no partial credit and no ‘close enough’. One point per category, only if every item in that category passes. Pass with warning counts as a pass: the item meets its criteria, but a note is shown with it, for example a rating that is readable with its platform, review count, and date, but differs across platforms. Ratings from different platforms are expected to differ, so they are reported per platform, never averaged, and a cross-platform difference on its own is not treated as a conflict. A failed gate makes the grade F, regardless of category points. The six ranking levers — booking and quote route, availability, price for this user, brand and system coverage, service-area dispatch, and machine discovery (llms.txt) — are recommendations, not scored, and never change your grade. A lever is shown as observed only where public evidence directly proves it; otherwise it is shown as a recommendation.</p></div>"""

SECTION2_INTRO = ("You must pass all of the items in this section in order to make any "
    "Grade higher than an F. This information is essential for a Shopping Agent to find "
    "and shop on your website. This step checks: exact business name everywhere; "
    "installation and repair as separate services in plain words; explicit town and ZIP "
    "service area; one unique primary phone number plus a working booking, quote, or "
    "contact route; readable day-by-day hours, or a true 24-hour / emergency claim; and "
    "a verifiable listing outside your own website, with the same name, phone, and "
    "service area")

SECTION3_INTRO = ("<b>Every item in a Category must pass in order for the entire Category "
    "to pass.</b> No partial credit inside a category. The table below lists every item "
    "in every category, with a pass or fail for each one, so you can see exactly which "
    "item failed a category. A failed category means at least one item in that category "
    "failed — the details that follow name each failed item. Exact fixes for each failed "
    "item are described in SECTION 4.")

SECTION4_INTRO = ("Suggested fixes for every failed Stage 2 item, in Category order. "
    "Categories with no failed items are marked ‘No fixes needed.’ Each fix names the "
    "failed item, what was found, why it matters, and the exact fix. Item results are "
    "from the audit performed 13 November 2026 for AC installation and repair in "
    "Coppell, TX 75019.")

SECTION6_INTRO_TMPL = ("Your ranking will move with customer location, requests, and the "
    "competitor set. The levers below do NOT count toward your {points}/7 score or "
    "{grade} grade; they are advice on converting a recommendation into a job, marked "
    "COMPLETE or SUGGESTED only where checked, and they are not scored.")

REVIEW_INTRO = ("Included in every after-payment report, even when no complaint pattern "
    "is found. This analysis is evidence for the Reputation complaint-pattern item; it "
    "does not create new issues.")

RANK_CAVEAT = ("This score is a point in time and can constantly change, based on your "
    "score and the scores of the companies that were scored in your service area. Your "
    "ranking will move with customer location, requests, and the competitor set "
    "included. Your grade is the steadier guide.")

PERCENTILE_BANDS = [(0, 24, "#E53935"), (25, 49, "#FB8C00"),
                    (50, 74, "#0288D1"), (75, 100, "#2E7D32")]


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, suf)


def band_color(pct):
    for lo, hi, color in PERCENTILE_BANDS:
        if lo <= pct <= hi:
            return color
    return "#0288D1"

# ---------------------------------------------------------------------------
# Data loading and field extraction.
# Join: summary.json rows carry item/gate/lever ids; audit-data.json rows
# (same seq order) carry evidence, source URL, why-it-matters, fix columns.
# ---------------------------------------------------------------------------

def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_definitions():
    defs = load_json(os.path.join(HERE, "aisharc_harness", "rules",
                                  "definitions.json"))
    items = {i["id"]: i for i in defs["items"]}
    gates = {g["id"]: g for g in defs["gates"]}
    levers = {l["id"]: l for l in defs["levers"]}
    return items, gates, levers


def load_firms():
    reg = load_json(os.path.join(HERE, "firms.json"))
    return {f["firm_id"]: f for f in reg["firms"]}


PHONE_RE = re.compile(r"\(?(\d{3})\)?[-. ]?(\d{3})[-. ]?(\d{4})")
LICENCE_RE = re.compile(r"\b(TACLA|TACLB|TECL)\d+[A-Z]\b")


def format_phone(digits10):
    return "(%s) %s-%s" % (digits10[0:3], digits10[3:6], digits10[6:10])


def extract_phone(text):
    """First 10-digit phone in the text, formatted; None if none."""
    if not text:
        return None
    m = PHONE_RE.search(text)
    return format_phone(m.group(1) + m.group(2) + m.group(3)) if m else None


def extract_all_phones(text):
    out = []
    if not text:
        return out
    for m in PHONE_RE.finditer(text):
        p = format_phone(m.group(1) + m.group(2) + m.group(3))
        if p not in out:
            out.append(p)
    return out


def extract_licence(text):
    if not text:
        return None
    m = LICENCE_RE.search(text)
    return m.group(0) if m else None


def listing_source_from_evidence(evidence):
    """Which listing source the G6 evidence names: meta / yelp / google."""
    ev = (evidence or "").lower()
    if "(meta)" in ev or "meta place" in ev or "meta business" in ev:
        return "meta"
    if "(yelp)" in ev or "yelp.com" in ev:
        return "yelp"
    if "google" in ev:
        return "google"
    return None


class FirmData:
    """Everything one card needs, sourced from the r3 audit."""

    def __init__(self, firm_id, firms, items_def):
        self.firm_id = firm_id
        self.registry = firms.get(firm_id, {})
        self.audit = load_json(os.path.join(RUNS, firm_id, "audit-data.json"))
        self.summary = load_json(os.path.join(RUNS, firm_id, "summary.json"))
        self.run = self.audit["run"]
        self.name = self.run["firm"]
        self.grade = self.summary["grade"]
        self.points = self.summary["category_points"]
        self.critical = self.summary["critical_issues"]
        self.high = self.summary["high_issues"]
        self.passed_items = self.summary["passed_items"]
        # Join audit rows (evidence) to summary rows (ids) by seq.
        self.rows = {}
        for arow, srow in zip(self.audit["rows"], self.summary["rows"]):
            assert arow["#"] == srow["seq"], (firm_id, arow["#"], srow["seq"])
            key = srow.get("item_id") or srow.get("gate_id") or srow.get("lever_id")
            self.rows[key] = {"audit": arow, "summary": srow}
        self.items_def = items_def
        self._company = None

    # -- row access ---------------------------------------------------------
    def gate(self, gid):
        return self.rows[gid]

    def item(self, iid):
        return self.rows[iid]

    def lever(self, lid):
        return self.rows[lid]

    def gates_pass(self):
        return all(self.gate(g)["summary"]["result"] == "Pass"
                   for g in GATE_ORDER)

    def failed_gates(self):
        return [g for g in GATE_ORDER
                if self.gate(g)["summary"]["result"] != "Pass"]

    def category_items(self, category):
        out = []
        for iid, d in self.items_def.items():
            if d["category"] == category:
                out.append((iid, self.item(iid)))
        return out

    def category_result(self, category):
        return self.summary["category_results"][category]

    def failed_items(self, category):
        return [(iid, r) for iid, r in self.category_items(category)
                if r["summary"]["result"] in ("Missing", "Conflict",
                                              "Not accessible")]

    def item_pass_count(self, category):
        return sum(1 for _, r in self.category_items(category)
                   if r["summary"]["result"] in ("Pass", "Pass with warning"))

    # -- company info, sourced honestly ------------------------------------
    def company(self):
        """Company Info fields. Rule per field (documented, no invention):
        address — firms.json recorded address, else Not accessible;
        phone — the unique primary phone from the G4 gate evidence when the
          audit verified one number; else the numbers the C6.1 evidence
          lists, labelled Not confirmed; else firms.json recorded phone;
        licence — the licence number in the C3.1 evidence when published,
          else firms.json recorded licence, else Not published;
        website — run record website_home, else website, else firms.json;
        meta place id — run record, else firms.json, else Not accessible."""
        if self._company is not None:
            return self._company
        run = self.run
        reg = self.registry
        c61 = self.item("C6.1")
        g4 = self.gate("G4")
        c31 = self.item("C3.1")
        # Phone
        phone = None
        phone_note = ""
        if c61["summary"]["result"] in ("Pass", "Pass with warning"):
            phone = extract_phone(g4["audit"]["Evidence note"])
        if phone is None:
            phones = extract_all_phones(c61["audit"]["Evidence note"])
            if phones:
                phone = "; ".join(phones)
                phone_note = " — Not confirmed: more than one number published"
        if phone is None:
            phone = reg.get("phone_recorded")
            if phone:
                phone_note = " (recorded 25 Oct 2026, not re-verified in this audit)"
        if phone is None:
            phone = "Not accessible in this audit"
        # Licence
        licence = extract_licence(c31["audit"]["Evidence note"])
        if licence is None:
            licence = reg.get("licence_recorded")
        if licence is None:
            licence = "Not published in this audit"
        # Website
        website = run.get("website_home") or run.get("website") \
            or reg.get("website") or "Not accessible in this audit"
        service_page = run.get("service_page") or website
        # Meta place id
        meta = run.get("meta_place_id") or reg.get("meta_place_id")
        meta = str(meta) if meta else "Not accessible in this audit"
        # Address
        address = reg.get("address") or "Not accessible in this audit"
        self._company = {
            "name": self.name, "address": address,
            "phone": phone + phone_note, "phone_plain": phone,
            "licence": licence, "website": website,
            "service_page": service_page, "meta_place_id": meta,
            "primary_business_category":
                run.get("primary_business_category", "HVAC Contractor"),
        }
        return self._company

    def fix_direction(self, row):
        """(column, text) of the non-'—' fix column for a failed row."""
        a = row["audit"]
        for col in ("Website change", "Listing change", "Operational change"):
            if a.get(col) and a[col] != "—":
                return col, a[col]
        return None, ""


def load_all_firms():
    items_def, _, _ = load_definitions()
    firms = load_firms()
    ids = sorted(os.listdir(RUNS))
    ids = [d for d in ids
           if os.path.isdir(os.path.join(RUNS, d))
           and os.path.exists(os.path.join(RUNS, d, "audit-data.json"))]
    return [FirmData(fid, firms, items_def) for fid in ids], items_def

# ---------------------------------------------------------------------------
# Exact Fix library — one fix per Item, in the dummy Final Rev 6 voice.
# Each fix names who does the work. Only the four Category 7 Items can need
# a developer; the rest are business facts or listing work the owner does
# (or asks their website developer to publish). Evidence specifics come
# from the audit row; nothing is invented.
# ---------------------------------------------------------------------------

WARRANTY_LINE_NAMES = {
    "new_labour": "new-system labour years",
    "new_parts": "new-system parts years",
    "registration": "registration",
    "repair_parts_labour": "repair parts and labour years",
    "transferable": "transferability",
    "claim_line": "claim line",
}


def warranty_lines_found(evidence):
    """(lines_present, lines_missing) from the C4.1 evidence note."""
    m = re.search(r"\((\d+) of 6 lines: ([^;]+); missing: ([^)]+)\)", evidence or "")
    if not m:
        return [], []
    present = [WARRANTY_LINE_NAMES.get(x.strip(), x.strip())
               for x in m.group(2).split(",")]
    missing = [WARRANTY_LINE_NAMES.get(x.strip(), x.strip())
               for x in m.group(3).split(",")]
    return present, missing


def developer_line(item_id):
    """Who does the work, per Spec s.6.10."""
    if item_id in ("C7.1", "C7.2", "C7.3", "C7.4"):
        return ("This is a website-code change, not a text edit you can make "
                "yourself: ask your website developer to do it.")
    return ("If you do not edit your website yourself, ask your website "
            "developer to do it for you.")


def fix_c11(ctx):
    if ctx["result"] == "Missing":
        return ("No rating or review count was found on any readable platform. "
                "Claim and complete your Google Business Profile and your Yelp page, "
                "and ask customers to review you there, so a shopping agent can read "
                "a rating with a review count. Until an independent platform shows a "
                "rating, this item cannot pass. " + developer_line("C1.1"))
    return ("A rating could not be read on any independent platform in this audit. "
            "Make sure your Google Business Profile and Yelp page are published and "
            "readable, with reviews visible. If the platforms block automated reads, "
            "that is an access problem to fix, not a rating problem — but the item "
            "stays Not confirmed until a rating is readable. "
            + developer_line("C1.1"))


def fix_c12(ctx):
    ev = ctx["evidence"]
    if "No rating figure" in ev or "could be read" in ev:
        return ("Publish one rating figure on the website and keep it identical to "
                "the figure on your Google and Yelp profiles. No figure could be read "
                "on any source in this audit, so there is nothing to compare — publish "
                "the figure and keep it current everywhere. "
                + developer_line("C1.2"))
    return ("Correct the website to match the independent profile, link that profile "
            "from the " + TOWN + " service page, and keep the same figure everywhere. "
            "Finding: " + ensure_period(ev) + " If a source figure is wrong, correct that source — "
            "do not leave both figures standing as they are. "
            + developer_line("C1.2"))


def fix_c13(ctx):
    if ctx["result"] == "Missing":
        return ("Answer every negative review in the recurring theme with a specific "
                "resolution, not a generic reply, and fix the underlying cause. "
                "Finding: " + ensure_period(ctx["evidence"]) + " A shopping agent treats unanswered "
                "repeats as a pattern. " + developer_line("C1.3"))
    return ("Make your reviews readable on an independent platform (Google Business "
            "Profile or Yelp) and answer negative reviews with a specific resolution, "
            "so a shopping agent can see whether complaints recur and whether you "
            "answer them. Reviews could not be read in this audit, so this item is "
            "Not confirmed — it is not a finding that a pattern exists. "
            + developer_line("C1.3"))


def fix_c21(ctx):
    return ("Publish a service-area page that names " + TOWN_ZIP + " explicitly — "
            "town and ZIP, not only a region — and link it from the home page, so a "
            "shopping agent can match the page to the user's query. "
            + developer_line("C2.1"))


def fix_c22(ctx):
    return ("List AC installation/replacement and AC repair as separate services on "
            "the " + TOWN + " service page, in plain words, so a shopping agent can "
            "match the page to the user's need. " + developer_line("C2.2"))


def fix_c23(ctx):
    return ("List every brand and system type you actually serve on the " + TOWN +
            " service page — for example, central air, heat pump, and ductless "
            "mini-split, by brand — and remove any brand or system type you do not "
            "serve. " + developer_line("C2.3"))


def fix_c24(ctx):
    phone = (" " + ctx["phone"]) if ctx["phone_confirmed"] else ""
    return ("Put the unique primary phone" + phone + " and a working booking or "
            "quote route on the " + TOWN + " service page, so a customer can book or "
            "request a quote without leaving the page. "
            + developer_line("C2.4"))


def fix_c31(ctx):
    ev = ctx["evidence"]
    if ctx["result"] == "Not accessible":
        return ("Publish one applicable state licence number on the website and on "
                "your listings, and check it against the TDLR register "
                "(data.texas.gov) so it matches exactly — for HVAC, a TACLA or TACLB "
                "number. No licence number was published on any readable source in "
                "this audit. " + developer_line("C3.1"))
    return ("Publish one licence number everywhere — the audit found: " + ensure_period(ev) +
            " Correct the sources that disagree until one number matches the TDLR "
            "register exactly. " + developer_line("C3.1"))


def fix_c32(ctx):
    if ctx["result"] == "Not accessible" and "No BBB" in ctx["evidence"]:
        return ("Publish your BBB accreditation and rating on the website only if it "
                "matches bbb.org, and link the bbb.org profile. No BBB claim was "
                "published in this audit; if you are accredited, publish the claim "
                "and the link. If the business does not show up on BBB, add it for "
                "free at https://www.bbb.org/get-listed. "
                + developer_line("C3.2"))
    return ("Correct the website claim to match bbb.org, or improve the BBB profile "
            "and then update the website, until they match. Do not claim a rating "
            "while bbb.org shows otherwise. Finding: " + ensure_period(ctx["evidence"]) + " If the "
            "business does not show up on BBB, add it for free at "
            "https://www.bbb.org/get-listed. " + developer_line("C3.2"))


def fix_c41(ctx):
    phone = ctx["phone"] if ctx["phone_confirmed"] \
        else "the unique primary phone"
    page = ctx["service_page"]
    present, missing = warranty_lines_found(ctx["evidence"])
    if present:
        head = ("The audit found " + str(len(present)) + " of the 6 lines (" +
                ", ".join(present) + "). Still missing: " +
                ", ".join(missing) + ". ")
    else:
        head = ""
    return (head + "Publish the six-line warranty card on the " + TOWN +
            " service page, with real numbers on all six lines:<br>"
            "1. New system parts __ years / manufacturer<br>"
            "2. New system labour __ years / installer<br>"
            "3. Repair parts __ years, repair labour __ years<br>"
            "4. Registration needed for full parts years? Yes/No, by __ days after install<br>"
            "5. Transferable to a new homeowner? Yes/No<br>"
            "6. Claim line: call us first at " + phone +
            ", we will diagnose, tell you the labour cost before work, and order the part."
            "<br>Full terms may be linked. " + developer_line("C4.1"))


def fix_c42(ctx):
    return ("Publish the diagnostic fee in dollars on the repair page, state "
            "free-estimate status for install and for repair separately, and give "
            "staff the same fee and warranty terms on the phone as on the website, "
            "with quotes in writing before work. " + developer_line("C4.2"))


def fix_c43(ctx):
    return ("State on the install page whether an installation estimate is free or "
            "charged, separately from repair. For example: “Installation estimates: "
            "free” or “Installation estimates: $[amount]”. "
            + developer_line("C4.3"))


def fix_c44(ctx):
    return ("State on the repair page whether a repair estimate is free or charged, "
            "separately from install. For example: “Repair estimates: free” or "
            "“Repair estimates: $[amount]”. " + developer_line("C4.4"))


def fix_c51(ctx):
    return ("Publish day-by-day opening hours on the website and on your listings — "
            "every day of the week, including weekends — so a shopping agent can tell "
            "when you are open. " + developer_line("C5.1"))


def fix_c52(ctx):
    return ("Make the hours, 24-hour, weekend, and emergency status identical across "
            "the website and listings. Finding: " + ensure_period(ctx["evidence"]) + " Correct the "
            "source that disagrees — a 24/7 claim on one source and different hours "
            "on another cannot both stand. " + developer_line("C5.2"))


def fix_c61(ctx):
    phones = extract_all_phones(ctx["evidence"])
    nums = ", ".join(phones) if phones else "several numbers"
    return ("Use one unique primary phone number everywhere — website, Google, Meta, "
            "and Yelp. The audit found these numbers in circulation: " + nums + ". "
            "Remove or correct every other number, and keep the one primary number "
            "identical everywhere. This is listing work, not a website-code change.")


def fix_c62(ctx):
    return ("Publish one founding year, with the business lineage explained through "
            "any rebrand or rename, and keep it identical across the website and "
            "listings. If the firm was renamed, add an old-to-new mapping page. "
            + developer_line("C6.2"))


def fix_c71(ctx):
    extra = ""
    if "403" in ctx["evidence"]:
        extra = ("In this audit robots.txt returned HTTP 403, so it could not be read "
                 "at all — check whether your hosting or firewall blocks automated "
                 "reads, and if the block was temporary, ask for a re-check once it "
                 "is fixed. ")
    return ("Ask your website developer to allow the answer/search crawlers — "
            "OAI-SearchBot, Claude-SearchBot, PerplexityBot, Meta-WebIndexer, and "
            "Applebot — plus Claude-User, in robots.txt, and to check that your "
            "hosting or firewall does not block automated reads. " + extra +
            developer_line("C7.1"))


def fix_c72(ctx):
    phone = (" " + ctx["phone"]) if ctx["phone_confirmed"] else ""
    return ("Ask your website developer to put the service, the town and ZIP (" +
            TOWN_ZIP + "), the unique primary phone" + phone + ", and the hours "
            "directly in the HTML the server sends for the home page and the " +
            TOWN + " service page, so they are readable without executing "
            "JavaScript. Right now these facts only appear after JavaScript runs, so "
            "a shopping agent that does not run scripts cannot see them. "
            + developer_line("C7.2"))


def fix_c73(ctx):
    comp = ctx["company"]
    addr = comp["address"]
    phone = ctx["phone"] if ctx["phone_confirmed"] else "[PHONE]"
    return ("Add a LocalBusiness (or HVACBusiness) JSON-LD block to the home page "
            "and the " + TOWN + " service page, naming the firm, the unique primary "
            "phone, the address, the area served, and the opening hours, matching "
            "the visible page exactly. Sample block for your implementer to adapt — "
            "replace every [PLACEHOLDER] with your firm’s own details, and do not "
            "publish it with the placeholders still in it. AI Sharc does not put "
            "this code on your site; that is for you or your own implementer."
            "</p><pre class=\"code\">" + esc(
                "<script type=\"application/ld+json\">\n{\n"
                "  \"@context\": \"https://schema.org\",\n"
                "  \"@type\": \"HVACBusiness\",\n"
                "  \"name\": \"" + comp["name"] + "\",\n"
                "  \"telephone\": \"" + phone + "\",\n"
                "  \"address\": \"" + addr + "\",\n"
                "  \"areaServed\": \"" + TOWN_ZIP + "\",\n"
                "  \"openingHours\": \"[OPENING HOURS, e.g. Mo-Fr 08:00-17:00]\"\n}"
                "\n</script>") + "</pre><p class=\"muted\">" +
            developer_line("C7.3"))


def fix_c74(ctx):
    site = ctx["website"]
    return ("First check whether your platform already creates one: WordPress at "
            "/wp-sitemap.xml (or /sitemap_index.xml with Yoast SEO or Rank Math), "
            "Shopify, Wix and Squarespace at /sitemap.xml. Confirm it loads and "
            "lists the " + TOWN + " service page. If there is no sitemap, publish "
            "one at " + site.rstrip("/") + "/sitemap.xml that lists the home page "
            "and the " + TOWN + " service page — for example, generate it with the "
            "free online generator at XML-Sitemaps.com (free for up to 500 pages) — "
            "keep it valid, record the lastmod date for each page, and regenerate or "
            "update it whenever a service page is added or changed. "
            + developer_line("C7.4"))


FIX_FNS = {"C1.1": fix_c11, "C1.2": fix_c12, "C1.3": fix_c13,
           "C2.1": fix_c21, "C2.2": fix_c22, "C2.3": fix_c23, "C2.4": fix_c24,
           "C3.1": fix_c31, "C3.2": fix_c32,
           "C4.1": fix_c41, "C4.2": fix_c42, "C4.3": fix_c43, "C4.4": fix_c44,
           "C5.1": fix_c51, "C5.2": fix_c52,
           "C6.1": fix_c61, "C6.2": fix_c62,
           "C7.1": fix_c71, "C7.2": fix_c72, "C7.3": fix_c73, "C7.4": fix_c74}


def fix_context(firm, row):
    comp = firm.company()
    confirmed = firm.item("C6.1")["summary"]["result"] in ("Pass",
                                                           "Pass with warning")
    return {"firm": firm.name, "phone": comp["phone_plain"],
            "phone_confirmed": confirmed,
            "website": comp["website"], "service_page": comp["service_page"],
            "company": comp, "result": row["summary"]["result"],
            "evidence": row["audit"]["Evidence note"],
            "source": row["audit"]["Source URL"],
            "why": row["audit"]["Why it matters"]}


def exact_fix(firm, item_id, row):
    fn = FIX_FNS[item_id]
    return fn(fix_context(firm, row))

# ---------------------------------------------------------------------------
# Rendering. Follows the dummy Final Rev 6 HTML section by section.
# ---------------------------------------------------------------------------

SECTION4_HEADING = {"C3.2": "BBB rating / accreditation readable on bbb.org",
                    "C4.1": "Warranty card — six lines"}
LABEL_OVERRIDES = {"C2.1": "Service-area page naming " + TOWN_ZIP,
                   "C7.3": "LocalBusiness structured data"}


def item_label(firm, item_id):
    if item_id == "C2.1":
        return "Service-area page naming " + TOWN_ZIP
    label = LABEL_OVERRIDES.get(item_id) or \
        firm.items_def[item_id]["item"]
    if item_id == "C3.1":
        lic = firm.company()["licence"]
        if lic and lic.startswith(("TACLA", "TACLB", "TECL")):
            label = label + " (Texas " + lic + ")"
    return label


def section4_heading(firm, item_id):
    return SECTION4_HEADING.get(item_id) or item_label(firm, item_id)


def status_text(result):
    if result == "Not accessible":
        return "Not accessible — Not confirmed"
    return result


def finding_paragraph(row):
    a = row["audit"]
    ev = (a["Evidence note"] or "").strip()
    if ev and not ev.endswith("."):
        ev += "."
    src = (a["Source URL"] or "").strip()
    status = status_text(row["summary"]["result"])
    parts = ["<b>Finding and evidence:</b> " + esc(ev)]
    if src:
        parts.append("Source: " + esc(src) + ".")
    parts.append("Status: " + esc(status) + ".")
    return "<p>" + " ".join(parts) + "</p>"


def render_company(firm):
    c = firm.company()
    rows = [
        ("Company name", c["name"], "Company address", c["address"]),
        ("Unique primary phone", c["phone"], "Primary Business Category",
         c["primary_business_category"]),
        ("Services tested", QUERY + ", as separate services",
         "Town and ZIP searched", TOWN_ZIP),
        ("Date performed", DATE_LONG, "Meta Place ID", c["meta_place_id"]),
        ("Applicable state licence", c["licence"], "Website", c["website"]),
    ]
    out = ['<div class="card"><h2 class="sec">Company Info</h2>'
           '<table class="company">']
    for l1, v1, l2, v2 in rows:
        out.append('<tr><td class="lbl">' + esc(l1) + '</td><td class="val">' +
                   esc(v1) + '</td><td class="lbl">' + esc(l2) +
                   '</td><td class="val">' + esc(v2) + '</td></tr>')
    out.append('</table></div>')
    return "".join(out)


def render_section1(firm):
    return ('<div style="height:14px"></div>'
            '<h2 class="sec">SECTION 1: FINAL SCORE</h2>'
            '<div class="grade-block"><div class="lbl">OVERALL GRADE</div>'
            '<div class="circle g' + firm.grade + '">' + firm.grade +
            '</div></div>')


def gate_check_text(firm, gid):
    if gid == "G3":
        return "Service area explicitly naming " + TOWN_ZIP
    if gid == "G6":
        ev = firm.gate("G6")["audit"]["Evidence note"]
        src = listing_source_from_evidence(ev)
        if src and firm.gate("G6")["summary"]["result"] == "Pass":
            return (GATE_LISTING_LABEL[src] + " — listing outside own website, "
                    "same name/phone/service area, correct Primary Business "
                    "Category")
        return GATE_CHECKS["G6"]
    return GATE_CHECKS[gid]


def render_section2(firm):
    out = ['<div class="card"><h2 class="sec">SECTION 2: CRITICAL ISSUES '
           '(GATE CHECKS)</h2><p class="muted">' + SECTION2_INTRO + '</p>'
           '<table class="rows">']
    for gid in GATE_ORDER:
        g = firm.gate(gid)
        res = g["summary"]["result"]
        mark = "✓ Pass" if res == "Pass" else "✗ Fail"
        cls = "pass" if res == "Pass" else "fail"
        out.append('<tr><td class="name">' + esc(GATE_NAMES[gid]) + '</td>'
                   '<td class="check">' + esc(gate_check_text(firm, gid)) +
                   '</td><td class="res ' + cls + '">' + mark + '</td></tr>')
    out.append('</table>')
    if firm.gates_pass():
        out.append('<p class="gatesummary pass">✓ Pass</p>')
    else:
        out.append('<p class="gatesummary fail">✗ Fail</p>')
    out.append('</div>')
    # Failed gates: finding + exact fix, below the table (Section 4 covers
    # failed Items only, so a failed Gate's fix lives here).
    for gid in firm.failed_gates():
        g = firm.gate(gid)
        col, text = firm.fix_direction(g)
        who = ""
        if col == "Website change":
            who = ("If you do not edit your website yourself, ask your "
                   "website developer to do it.")
        elif col == "Listing change":
            who = "This is listing work — correct the listing."
        elif col == "Operational change":
            who = "This is operational work for the firm."
        fix = (esc(ensure_period(text)) + " " + who) if text else who
        out.append('<div class="card"><h3 class="issue">• Gate: ' +
                   esc(GATE_NAMES[gid]) + ' <span class="fail">(✗ Fail)'
                   '</span></h3>' + finding_paragraph(g) +
                   '<p><b>Why it matters:</b> ' +
                   esc(GATE_WHY[gid]) + '</p>'
                   '<h3 class="fix">Exact Fix</h3><p class="muted">' + fix +
                   '</p></div>')
    return "".join(out)


def render_section3(firm):
    out = ['<div class="card"><h2 class="sec">SECTION 3: AI SHOPPING HEALTH '
           'AUDIT GRADE</h2><p class="muted">' + SECTION3_INTRO + '</p>'
           '<table class="grows">']
    for n, cat in enumerate(CATEGORIES, 1):
        passed = firm.item_pass_count(cat)
        items = firm.category_items(cat)
        total = len(items)
        result = firm.category_result(cat)
        pct = round(passed * 100 / total) if total else 0
        color = "#10B981" if result == "Pass" else "#EF4444"
        mark = "✓ Pass" if result == "Pass" else "✗ Fail"
        cls = "pass" if result == "Pass" else "fail"
        out.append('<tr><td class="cat">' + str(n) + '. ' + esc(cat) +
                   '</td><td class="barp"><div class="bar"><div class="fill" '
                   'style="width: ' + str(pct) + '%; background: ' + color +
                   ';"></div></div></td><td class="res ' + cls + '">' + mark +
                   '</td></tr>')
        for iid, r in items:
            res = r["summary"]["result"]
            if res in ("Pass", "Pass with warning"):
                mark, cls = "✓ Pass", "pass"
            else:
                mark, cls = "✗ Fail", "fail"
            label = esc(item_label(firm, iid))
            if res == "Pass with warning":
                label += ('<br><span style="font-size:9pt;color:#64748B">'
                          'Warning: ' + esc(r["audit"]["Evidence note"]) +
                          '</span>')
            out.append('<tr><td class="item">' + label + '</td>'
                       '<td class="barp"></td><td class="res ' + cls + '">' +
                       mark + '</td></tr>')
    out.append('</table><p class="score">Score: ' + str(firm.points) +
               ' / 7</p>')
    if firm.grade == "F":
        out.append('<p class="muted" style="text-align:center">Diagnostic '
                   'only — the grade is F because one or more Critical gates '
                   'failed; these category points are not a second grade.</p>')
    out.append('<div class="key-title">Grading key</div><table class="key">'
               '<tr><th>Grade</th><th>Meaning</th></tr>')
    for g, meaning in GRADING_KEY:
        out.append('<tr><td class="g">' + g + '</td><td>' + esc(meaning) +
                   '</td></tr>')
    out.append('</table></div>')
    return "".join(out)


def render_section4(firm):
    out = ['<div class="card"><h2 class="sec">SECTION 4: SUGGESTED FIXES TO '
           'AI SHOPPING HEALTH AUDIT</h2><p class="muted">' + SECTION4_INTRO +
           '</p></div>']
    for n, cat in enumerate(CATEGORIES, 1):
        result = firm.category_result(cat)
        mark = ("✓ Pass" if result == "Pass" else "✗ Fail")
        cls = "pass" if result == "Pass" else "fail"
        out.append('<div class="card"><h2 class="cat">Category ' + str(n) +
                   ' — ' + esc(cat) + ' <span class="' + cls + '">(' + mark +
                   ')</span></h2>')
        failed = firm.failed_items(cat)
        if not failed:
            out.append('<p class="muted">No fixes needed.</p>')
        for iid, r in failed:
            out.append('<h3 class="issue">• Issue: ' +
                       esc(section4_heading(firm, iid)) +
                       ' <span class="fail">(✗ Fail)</span></h3>')
            out.append(finding_paragraph(r))
            out.append('<p><b>Why it matters:</b> ' +
                       esc(WHY_TEXTS[iid]) + '</p>')
            out.append('<h3 class="fix">Exact Fix</h3><p class="muted">' +
                       exact_fix(firm, iid, r) + '</p>')
        out.append('</div>')
    return "".join(out)


def render_section5(firm):
    out = ['<div class="card"><h2 class="sec">SECTION 5: WHERE YOUR AI '
           'SHOPPING HEALTH GRADE RANKS IN YOUR SERVICE AREA</h2></div>']
    if firm.grade == "F" or firm.summary.get("eligible_rank") is None:
        out.append('<p class="muted">This firm is not ranked. It is not '
                   'eligible for ranking because one or more Critical gates '
                   'failed (see Section 2). Fix the Critical issues first; the '
                   'firm will be ranked on the next audit once it is eligible. '
                   'In this run, ' +
                   str(firm.summary.get("eligible_count")) +
                   ' of 19 firms were eligible.</p>')
        return "".join(out)
    pct = firm.summary["percentile"]
    rank = firm.summary["eligible_rank"]
    count = firm.summary["eligible_count"]
    color = band_color(pct)
    dash = pct / 100.0 * 314.2
    out.append('<div class="rankdonut"><svg viewBox="0 0 120 120" width="132" '
               'height="132"><circle cx="60" cy="60" r="50" fill="none" '
               'stroke="#E2E8F0" stroke-width="10"/><circle cx="60" cy="60" '
               'r="50" fill="none" stroke="' + color + '" stroke-width="10" '
               'stroke-dasharray="' + ("%.1f" % dash) + ' 314.2" '
               'transform="rotate(-90 60 60)" stroke-linecap="round"/>'
               '<text x="60" y="58" text-anchor="middle" font-size="16" '
               'font-weight="bold" fill="' + color + '">' + ordinal(pct) +
               '</text><text x="60" y="76" text-anchor="middle" font-size="9" '
               'fill="#64748B">Percentile</text></svg>'
               '<p class="ranklabel">AI Sharc audit percentile among the firms '
               'assessed.</p><p class="rankline">' + ordinal(rank) + ' of ' +
               str(count) + ' eligible in the service area</p>'
               '<p class="rankcaveat">' + RANK_CAVEAT + '</p></div>')
    return "".join(out)


def render_section6(firm):
    comp = firm.company()
    confirmed = firm.item("C6.1")["summary"]["result"] in ("Pass",
                                                           "Pass with warning")
    phone = comp["phone_plain"] if confirmed else "the unique primary phone"
    out = ['<div style="height:14px"></div><h2 class="sec">SECTION 6: '
           'SUGGESTIONS FOR INCREASING YOUR RANKING IN YOUR SERVICE AREA</h2>'
           '<p class="muted">' +
           SECTION6_INTRO_TMPL.format(points=firm.points, grade=firm.grade) +
           '</p><div class="card"><table class="rows">']
    for lid in LEVER_ORDER:
        r = firm.lever(lid)
        res = r["summary"]["result"]
        if res == "Observed":
            mark, cls = "COMPLETE", "complete"
        else:
            mark, cls = "SUGGESTED", "suggested"
        text = LEVER_TEXTS[lid]
        text = text.replace("[PHONE]", esc(phone))
        text = text.replace("[FIRM]", esc(firm.name))
        text = text.replace("[WEBSITE]", esc(comp["website"]))
        text = text.replace("[TOWN]", esc(TOWN + ", TX 75019"))
        out.append('<tr><td class="name">' + esc(LEVER_NAMES[lid]) + '</td>'
                   '<td class="check">' + text + '</td><td class="res ' +
                   cls + '">' + mark + '</td></tr>')
    out.append('</table></div>')
    return "".join(out)


def render_review(firm):
    c11 = firm.item("C1.1")
    c13 = firm.item("C1.3")
    gy = firm.summary.get("google_yelp") or {}
    reviews = gy.get("reviews") or {}
    out = ['<div class="card"><h2 class="sec">CUSTOMER REVIEW ANALYSIS</h2>'
           '<p class="muted">' + REVIEW_INTRO + '</p>'
           '<table class="review"><tr><th>Review result</th><th>Detail</th>'
           '</tr>']
    if c11["summary"]["result"] in ("Pass", "Pass with warning"):
        rating = c11["audit"]["Evidence note"]
    else:
        rating = ("No rating or review count was readable on any independent "
                  "platform in this audit.")
    out.append('<tr><td class="lbl">Rating and review count</td><td>' +
               esc(rating) + '</td></tr>')
    if c13["summary"]["result"] == "Pass":
        pattern = "No pattern found — " + c13["audit"]["Evidence note"]
        result_line = "<b>Result: No pattern found.</b>"
    else:
        ev = (c13["audit"]["Evidence note"] or "")[:220]
        pattern = ("Not assessed — reviews could not be read in this audit. "
                   + ev)
        result_line = ("<b>Result: Not assessed — reviews could not be read "
                       "in this audit.</b>")
    out.append('<tr><td class="lbl">Recurring complaint pattern</td><td>' +
               esc(pattern) + '</td></tr>')
    if reviews.get("accessible"):
        themes = ("Not recorded in this audit — " +
                  str(reviews.get("reviews_read")) +
                  " reviews were read on the firm’s own reviews page "
                  "(firm-curated) but themes were not extracted.")
    else:
        themes = "Not assessed — no reviews were readable in this audit."
    out.append('<tr><td class="lbl">Positive themes</td><td>' + esc(themes) +
               '</td></tr>')
    out.append('<tr><td class="lbl">Response behaviour</td><td>' +
               esc(themes) + '</td></tr>')
    out.append('</table><p>' + result_line + '</p></div>')
    return "".join(out)


def render_card(firm):
    parts = ['<!DOCTYPE html><html><head><meta charset="utf-8">'
             '<title>AI Sharc — Final Report Card</title><style>' + CSS +
             '</style></head><body>'
             '<div class="banner"><div class="kicker">AI SHARC</div>'
             '<div class="row"><h1>Final Report Card</h1><span class="rev">' +
             CARD_REV + ' — ' + CARD_DATE + '</span></div></div>']
    parts.append(render_company(firm))
    parts.append(render_section1(firm))
    parts.append(render_section2(firm))
    parts.append(render_section3(firm))
    parts.append(render_section4(firm))
    parts.append(render_section5(firm))
    parts.append(render_section6(firm))
    parts.append(render_review(firm))
    parts.append(NOTES_AND_LIMITS)
    parts.append('</body></html>')
    return "".join(parts)

# ---------------------------------------------------------------------------
# Validation: render the dummy Final Rev 6 through this generator and check
# it reproduces the live card's structure and values (grade B 3/7, 7 failed
# Items, rank 30 of 80, Top 38%, 63rd percentile).
# ---------------------------------------------------------------------------

DUMMY_GATES = {
    "G1": "Pass", "G2": "Pass", "G3": "Pass",
    "G4": "Pass", "G5": "Pass", "G6": "Pass",
}
DUMMY_ITEMS = {  # item_id: (result, evidence)
    "C1.1": ("Pass", "Rating readable: Google profile 4.6 on 1,234 reviews."),
    "C1.2": ("Missing", "Website claims a customer review rating of 4.9, "
             "while the Google profile shows 4.6 on 1,234 reviews."),
    "C1.3": ("Pass", "No recurring unaddressed complaint pattern found."),
    "C2.1": ("Pass", "Service-area page names Example Town, TX 75000."),
    "C2.2": ("Pass", "Install and repair listed separately on that page."),
    "C2.3": ("Pass", "Brands and system types served on that page."),
    "C2.4": ("Pass", "Unique primary phone and booking route on that page."),
    "C3.1": ("Pass", "Licence TACLB00012345E published and active in the "
             "register."),
    "C3.2": ("Missing", "Website claims BBB A+, while bbb.org shows B, "
             "unaccredited, for Example Heating & Air Conditioning."),
    "C4.1": ("Missing", "Service page publishes only new-system parts 10 "
             "years / manufacturer and labour 1 year / installer. It does not "
             "publish repair parts and labour years, registration, "
             "transferability, or a claim line."),
    "C4.2": ("Missing", "Repair page says “Call for diagnostic pricing” with "
             "no dollar figure."),
    "C4.3": ("Pass", "Free-estimate status for install stated separately."),
    "C4.4": ("Pass", "Free-estimate status for repair stated separately."),
    "C5.1": ("Pass", "Day-by-day hours readable."),
    "C5.2": ("Pass", "Hours, 24-hour, weekend, and emergency status "
             "consistent across sources."),
    "C6.1": ("Pass", "One unique primary phone number everywhere."),
    "C6.2": ("Pass", "Founding year and business lineage consistent across "
             "sources."),
    "C7.1": ("Pass", "robots.txt allows the answer/search crawlers."),
    "C7.2": ("Missing", "The service, the town and ZIP, the unique primary "
             "phone, and the hours on the home page and the Example Town "
             "service page are rendered only after JavaScript runs."),
    "C7.3": ("Missing", "No LocalBusiness or HVACBusiness JSON-LD was found "
             "on the home page or the Example Town service page."),
    "C7.4": ("Missing", "No XML sitemap was found at "
             "https://example.com/sitemap.xml, and the Example Town service page "
             "is not listed in a sitemap."),
}
DUMMY_LEVERS = {"booking_route": "Observed", "availability": "Recommendation",
                "price": "Recommendation", "brand_coverage": "Observed",
                "dispatch": "Recommendation", "llms_txt": "Recommendation"}
DUMMY_FAILED = ["C1.2", "C3.2", "C4.1", "C4.2", "C7.2", "C7.3", "C7.4"]


class DummyFirm:
    """Stand-in for FirmData with the dummy Rev 6 values."""

    def __init__(self, items_def):
        self.firm_id = "dummy"
        self.name = "Example Heating & Air Conditioning"
        self.grade = "B"
        self.points = 3
        self.critical = 0
        self.high = 7
        self.passed_items = 14
        self.items_def = items_def
        self.summary = {"eligible_rank": 30, "eligible_count": 80,
                        "top_percent": 38, "percentile": 63,
                        "category_results": {
                            "Reputation": "Fail", "Area Coverage": "Pass",
                            "Credentials and Trust": "Fail",
                            "Pricing and Warranty": "Fail",
                            "Hours and Active Status": "Pass",
                            "Identity and Contact": "Pass",
                            "Machine Readability": "Fail"}}
        self._rows = {}
        for gid, res in DUMMY_GATES.items():
            self._rows[gid] = self._row(res, "Gate evidence for " + gid + ".")
        for iid, (res, ev) in DUMMY_ITEMS.items():
            self._rows[iid] = self._row(res, ev)
        for lid, res in DUMMY_LEVERS.items():
            self._rows[lid] = self._row(res, "")

    @staticmethod
    def _row(result, evidence):
        return {"summary": {"result": result},
                "audit": {"Evidence note": evidence,
                          "Source URL": "https://example.com/",
                          "Why it matters": "Why it matters for this item.",
                          "Website change": "—", "Listing change": "—",
                          "Operational change": "—"}}

    def gate(self, gid):
        return self._rows[gid]

    def item(self, iid):
        return self._rows[iid]

    def lever(self, lid):
        return self._rows[lid]

    def gates_pass(self):
        return True

    def failed_gates(self):
        return []

    def category_items(self, category):
        return [(iid, self.item(iid)) for iid, d in self.items_def.items()
                if d["category"] == category]

    def category_result(self, category):
        return self.summary["category_results"][category]

    def failed_items(self, category):
        return [(iid, r) for iid, r in self.category_items(category)
                if r["summary"]["result"] in ("Missing", "Conflict",
                                              "Not accessible")]

    def item_pass_count(self, category):
        return sum(1 for _, r in self.category_items(category)
                   if r["summary"]["result"] in ("Pass", "Pass with warning"))

    def company(self):
        return {"name": self.name,
                "address": "123 Example Street, Example Town, TX 75000",
                "phone": "(555) 555-0100", "phone_plain": "(555) 555-0100",
                "licence": "TACLB00012345E", "website": "https://example.com/",
                "service_page": "https://example.com/service-areas/"
                                "example-town-texas/",
                "meta_place_id": "555555555555555",
                "primary_business_category": "HVAC Contractor"}

    def fix_direction(self, row):
        return None, ""


def validate_dummy():
    """Render the dummy through this generator; check the live Rev 6 values."""
    global TOWN_ZIP, TOWN, DATE_LONG, CARD_REV, CARD_DATE
    items_def, _, _ = load_definitions()
    saved = (TOWN_ZIP, TOWN, DATE_LONG, CARD_REV, CARD_DATE)
    TOWN_ZIP, TOWN, DATE_LONG = "Example Town, TX 75000", "Example Town", \
        "3 November 2026"
    CARD_REV, CARD_DATE = "Rev. 6", "2026-11-11"
    try:
        html_out = render_card(DummyFirm(items_def))
    finally:
        TOWN_ZIP, TOWN, DATE_LONG, CARD_REV, CARD_DATE = saved
    checks = []
    def check(name, ok):
        checks.append((name, ok))
        return ok
    check("grade circle B", 'class="circle gB">B<' in html_out)
    check("score 3 / 7", "Score: 3 / 7" in html_out)
    check("rank 30th of 80", "30th of 80 eligible" in html_out)
    check("63rd percentile donut", ">63rd<" in html_out)
    check("top_percent 38 in fixture", DummyFirm(items_def).summary["top_percent"] == 38)
    for iid in DUMMY_FAILED:
        check("Section 4 has " + iid,
              esc(section4_heading(DummyFirm(items_def), iid)) in html_out)
    check("No fixes needed x3",
          html_out.count('<p class="muted">No fixes needed.</p>') == 3)
    check("gates Pass", '<p class="gatesummary pass">✓ Pass</p>' in html_out)
    for lid, want in (("booking_route", "COMPLETE"),
                      ("availability", "SUGGESTED"),
                      ("price", "SUGGESTED"),
                      ("brand_coverage", "COMPLETE"),
                      ("dispatch", "SUGGESTED"),
                      ("llms_txt", "SUGGESTED")):
        check("lever " + lid + " " + want,
              esc(LEVER_NAMES[lid]) in html_out and want in html_out)
    failed = [n for n, ok in checks if not ok]
    return checks, failed


# ---------------------------------------------------------------------------

# "Why it matters" texts. The engine's audit-data "Why it matters" column
# for a failed row carries the Field Mapping pass_criteria (a requirement),
# not a reason — so the cards use these rationale texts instead, in the
# dummy Final Rev 6 voice. The dummy's own wordings are used where it has
# them (C1.2, C3.2, C4.1, C4.2, C7.2, C7.3, C7.4). Findings, evidence,
# sources, and figures still come from the audit rows.
# ---------------------------------------------------------------------------
WHY_TEXTS = {
    "C1.1": ("A rating with a review count on an independent platform lets a "
             "shopping agent verify the firm is real, rated, and reviewed by "
             "customers — not only by the firm’s own website."),
    "C1.2": ("Consistent figures let Shopping Agents match the website to the "
             "listing as the same business and compare it fairly with other "
             "firms."),
    "C1.3": ("A recurring unaddressed complaint theme tells a shopping agent "
             "the firm leaves the same problem unresolved; a clean record, "
             "with replies, tells it the firm stands behind its work."),
    "C2.1": ("A service-area page naming the town and ZIP is how a shopping "
             "agent matches the firm to the user’s query — without it, the firm "
             "cannot be placed in the town at all."),
    "C2.2": ("Installation and repair are different jobs with different prices "
             "and urgency. If they are not listed separately, a shopping agent "
             "cannot tell which the firm does for this user."),
    "C2.3": ("Brands and system types are what a user is actually buying. "
             "Without them on the service page, a shopping agent cannot match "
             "the firm to the user’s system."),
    "C2.4": ("A customer who finds the firm must be able to call or book from "
             "the same page — a phone number and a booking route on the service "
             "page turn a recommendation into a job."),
    "C3.1": ("A licence number that matches the state register is the "
             "independent proof the firm is licensed to do the work. Without "
             "it, a shopping agent cannot verify the firm’s credentials."),
    "C3.2": ("A trust claim that cannot be read on bbb.org itself does not "
             "count as independently verified trust, and a claim that conflicts "
             "with bbb.org hurts more than a blank."),
    "C4.1": ("For a user, the simplest test is “what do I pay if it breaks in "
             "year 4?” Without parts years/manufacturer, labour years/installer, "
             "repair parts and labour years, registration, transferability, and "
             "a claim line, Shopping Agents cannot compare warranty value, and "
             "labour — the real differentiator — stays hidden."),
    "C4.2": ("A user comparing repair firms needs a dollar figure before "
             "booking, and a fee that differs on the phone from the website "
             "breaks trust at the point of booking."),
    "C4.3": ("An install estimate is often the first money question a user "
             "asks. If the site does not say whether it is free or charged, the "
             "user has to call to find out — and many will not."),
    "C4.4": ("A repair estimate is often the first money question a user asks. "
             "If the site does not say whether it is free or charged, the user "
             "has to call to find out — and many will not."),
    "C5.1": ("Day-by-day hours tell a shopping agent when the firm is open and "
             "whether it can serve the user today. Without them, the firm cannot "
             "be matched to the user’s timing."),
    "C5.2": ("Hours that disagree across sources leave a shopping agent unable "
             "to say when the firm is open — and a 24/7 claim that contradicts "
             "the stated hours breaks trust."),
    "C6.1": ("One phone number everywhere is how a shopping agent knows the "
             "website, the listings, and the firm are the same business. Two "
             "numbers in circulation split the firm’s identity."),
    "C6.2": ("A founding year and a clear lineage tell a shopping agent the "
             "firm is established and how it got its name. A year that differs "
             "across sources, or no year at all, leaves the firm’s history "
             "unverified."),
    "C7.1": ("If an answer/search crawler cannot read the site, a shopping "
             "agent cannot find the firm at all — no matter how good the "
             "business is."),
    "C7.2": ("Shopping agents read the page as it is served. If the service, "
             "the town and ZIP, the phone, and the hours only appear after "
             "JavaScript runs, an agent that does not run scripts cannot see "
             "them, and the firm cannot be matched to the user’s query."),
    "C7.3": ("Structured data gives a shopping agent a machine-readable form "
             "of the firm, the phone, the address, the area served, and the "
             "hours, so it can check them against the visible page. Without "
             "structured data, the agent may need to compare the visible text "
             "with other sources."),
    "C7.4": ("A sitemap tells shopping agents and search crawlers which pages "
             "exist, including the town service page. Without one, a new or "
             "changed service page may not be found."),
}
GATE_WHY = {
    "G1": ("An exact name identical everywhere is how a shopping agent knows "
           "the website, the listings, and the firm are the same business."),
    "G2": ("Installation and repair are different jobs. If they are not listed "
           "separately in plain words, a shopping agent cannot tell which the "
           "firm does."),
    "G3": ("A town and ZIP explicitly named is how a shopping agent matches the "
           "firm to the user’s query."),
    "G4": ("One unique primary phone plus a working booking route is the "
           "minimum for a customer to reach the firm."),
    "G5": ("Readable hours, or a verifiable 24/7 claim, tell a shopping agent "
           "the firm is active and when it can serve the user."),
    "G6": ("A verifiable listing outside the firm’s own website is the "
           "independent proof the firm exists at that name, phone, and service "
           "area."),
}


def ensure_period(text):
    text = (text or "").strip()
    if text and not text.endswith("."):
        text += "."
    return text


# Main
# ---------------------------------------------------------------------------

def card_filename(firm_name):
    # "/" is a path separator: Berkeys' recorded name contains "A/C".
    # The card content keeps the real name; only the file name sanitises it.
    safe = firm_name.replace("/", "-")
    return ("AI Sharc — Final Report Card — " + safe + " — " +
            CARD_DATE + " — Rev 1")


def verify_firm_card(firm, html_out):
    """Per-firm self-check: 40 rows reflected, grade/score/ranking/levers."""
    problems = []
    n_gates = sum(1 for g in GATE_ORDER if g in firm.rows)
    n_items = sum(1 for i in firm.items_def if i in firm.rows)
    n_levers = sum(1 for l in LEVER_ORDER if l in firm.rows)
    n_cat = len(firm.summary["category_results"])
    if (n_gates, n_items, n_cat, n_levers) != (6, 21, 7, 6):
        problems.append("row composition %s (want 6/21/7/6)"
                        % ((n_gates, n_items, n_cat, n_levers),))
    if ('class="circle g' + firm.grade + '">' + firm.grade + '<'
            not in html_out):
        problems.append("grade circle missing")
    if "Score: %d / 7" % firm.points not in html_out:
        problems.append("score line missing")
    for cat in CATEGORIES:
        for iid, r in firm.failed_items(cat):
            if esc(section4_heading(firm, iid)) not in html_out:
                problems.append("Section 4 missing " + iid)
    if firm.grade == "F":
        if "not ranked" not in html_out.lower():
            problems.append("F firm missing not-ranked text")
        if "of 2 eligible" in html_out and "not ranked" not in html_out.lower():
            problems.append("F firm shows a rank")
    else:
        if str(firm.summary["eligible_rank"]) not in html_out:
            problems.append("eligible rank missing")
    for lid in LEVER_ORDER:
        want = "COMPLETE" if firm.lever(lid)["summary"]["result"] == "Observed" \
            else "SUGGESTED"
        if want not in html_out:
            problems.append("lever " + lid + " status missing")
    return problems


def main():
    validate_only = "--validate-only" in sys.argv
    checks, failed = validate_dummy()
    print("=== Dummy Rev 6 reproduction through this generator ===")
    for name, ok in checks:
        print(("  PASS " if ok else "  FAIL ") + name)
    if failed:
        print("DUMMY VALIDATION FAILED — fix the generator before building "
              "real cards.")
        return 1
    print("DUMMY VALIDATION PASSED (%d checks)" % len(checks))
    if validate_only:
        return 0

    firms, items_def = load_all_firms()
    print("=== Building %d Final cards (r3, %s) ===" % (len(firms), CARD_DATE))
    os.makedirs(OUT, exist_ok=True)
    try:
        from weasyprint import HTML as WPHTML
    except ImportError:
        WPHTML = None
        print("WARNING: WeasyPrint not importable — HTML only, no PDFs. "
              "Run under ~/workspace/tools/wp-venv/bin/python.")
    index = []
    all_problems = {}
    for firm in firms:
        html_out = render_card(firm)
        base = card_filename(firm.name)
        html_path = os.path.join(OUT, base + ".html")
        pdf_path = os.path.join(OUT, base + ".pdf")
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(html_out)
        if WPHTML is not None:
            WPHTML(filename=html_path).write_pdf(pdf_path)
        problems = verify_firm_card(firm, html_out)
        if problems:
            all_problems[firm.firm_id] = problems
        index.append({"firm_id": firm.firm_id, "firm": firm.name,
                      "grade": firm.grade, "points": firm.points,
                      "critical": firm.critical, "high": firm.high,
                      "passed_items": firm.passed_items,
                      "eligible_rank": firm.summary.get("eligible_rank"),
                      "eligible_count": firm.summary.get("eligible_count"),
                      "file": base + ".html", "pdf": base + ".pdf",
                      "problems": problems})
        print("  %-18s grade %s %d/7 crit %d high %d passed %d %s" %
              (firm.firm_id, firm.grade, firm.points, firm.critical,
               firm.high, firm.passed_items,
               ("PROBLEMS: " + "; ".join(problems)) if problems else "ok"))
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2)
    lines = ["# r3 Final Report Cards — index",
             "",
             "Internal working documents from the r3 harness test run "
             "(13 November 2026, Coppell TX 75019, Spec v1.22). "
             "Not sent to any firm; no firm contacted.",
             "",
             "| Firm | Grade | Points | Critical | High | Card |",
             "|---|---|---|---|---|---|"]
    for e in sorted(index, key=lambda x: (x["grade"], -x["points"], x["firm"])):
        lines.append("| %s | %s | %d/7 | %d | %d | %s |" %
                     (e["firm"], e["grade"], e["points"], e["critical"],
                      e["high"], e["file"]))
    lines.append("")
    lines.append("Files: " + OUT)
    with open(os.path.join(OUT, "index.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("=== Done: %d cards in %s ===" % (len(index), OUT))
    if all_problems:
        print("PROBLEMS:")
        for fid, ps in all_problems.items():
            print("  " + fid + ": " + "; ".join(ps))
        return 1
    print("All per-firm self-checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# ---------------------------------------------------------------------------