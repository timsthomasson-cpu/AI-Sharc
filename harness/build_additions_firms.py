#!/usr/bin/env python3
"""Build the additions firms file for the Texas HVAC correlation study.

Reads runs/2026-11-14-study/agent/agent-named-additions.json (929
entries, one per distinct firm name + town) and dedupes them into
distinct firms for audit, per the additions-audit task (2026-11-14):

- A firm named in several towns is audited ONCE.
- Identity is the normalised firm name + address/phone where available:
  same name with a different street address AND a different phone is a
  distinct firm (a separate branch); same name with the same address or
  the same phone is one firm; an entry with no address/phone merges
  with the same-name firm unless it conflicts.
- Agent-added descriptors are stripped from names ("— Serves 78701",
  "– Best for ...", ": HVAC Department", "Serves 75165: ...").
- Section headings the collector recorded as firms ("For diagnosis-first",
  "Regional specialists ...", "Expertise.com vetted list ...") and
  compound headings ("A + B", "A, B, C") are resolved to the actual
  firms named in the saved answers (verified against the response text).
- Entries flagged cohort_elsewhere are verified against the 861-firm
  cohort (exact name, prefix, or compatible name + address/phone) and
  skipped from audit; so are the 9 Abilene additions already audited
  for 2026-11-14.
- Primary town: the town of the firm's address if that town is one
  where it was named, else the town where it was named most often.
- firm_id: slug of the canonical name, with a -<town> suffix where
  needed (the discovery merge's rule), never colliding with the 861
  cohort firm_ids or the 9 Abilene addition firm_ids.

Outputs (aisharc-harness/):
  study-additions-firms-all.json  the firms file for run_audit.py
  additions-dedupe-log.json       per-firm merge/skip audit trail
  additions-firms-runs.json       per firm: runs_named_in (Phase 2 input)

Usage: python3 build_additions_firms.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ADDITIONS = os.path.join(
    HERE, "runs", "2026-11-14-study", "agent", "agent-named-additions.json")
COHORT_LIST = os.path.join(
    os.path.dirname(HERE),
    "Texas HVAC correlation study — firm list — 2026-11-14 — DRAFT.json")
ABILENE = os.path.join(HERE, "study-additions-firms.json")
OUT_FIRMS = os.path.join(HERE, "study-additions-firms-all.json")
OUT_LOG = os.path.join(HERE, "additions-dedupe-log.json")
OUT_RUNS = os.path.join(HERE, "additions-firms-runs.json")

PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}")
ADDR_RE = re.compile(
    r"(\d{1,5}\s+[A-Za-z0-9][^|\n]{3,80}?TX\s*\d{5})")
ZIP_RE = re.compile(r"\bTX\s*(\d{5})\b")
CITY_RE = re.compile(r",\s*([A-Za-z][A-Za-z .]+?),\s*TX\b")

GENERIC_TOKENS = {
    "heating", "air", "conditioning", "ac", "a", "c", "services",
    "service", "company", "co", "llc", "inc", "hvac", "plumbing",
    "electrical", "electric", "and", "of", "the", "cooling", "heat",
    "refrigeration", "mechanical", "home", "homes", "group", "experts",
    "expert", "solutions", "systems", "pros", "tech", "texas", "tx",
    "corp", "corporation", "ltd", "llp", "dba", "airconditioning",
}

STREET_ABBR = {
    "south": "s", "north": "n", "east": "e", "west": "w",
    "avenue": "ave", "street": "st", "boulevard": "blvd",
    "drive": "dr", "road": "rd", "lane": "ln", "court": "ct",
    "parkway": "pkwy", "highway": "hwy", "circle": "cir",
    "trail": "trl", "place": "pl", "terrace": "ter",
}


def norm(s: str) -> str:
    """Collect script's normalisation, plus possessive handling so
    "Berkey's" and "Berkeys" compare the same, plus camelCase splitting
    so "TemperaturePro" and "Temperature Pro" compare the same."""
    s = (s or "").replace("&", " and ").replace("'s", "")
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    s = s.lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def norm_phone(p: str | None) -> str:
    d = re.sub(r"\D", "", p or "")
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d


def clean_address(addr: str | None) -> str | None:
    """Pull the street-address pattern out of a collector address that
    may carry markdown or a second listed address."""
    if not addr:
        return None
    m = ADDR_RE.search(addr.replace("**", ""))
    if m:
        a = m.group(1).strip().rstrip(".").strip()
        # Drop a trailing "also listed as ..." fragment.
        a = re.split(r"\s+also listed as\s+", a, flags=re.I)[0]
        return a
    return addr.strip() or None


def norm_street(addr: str | None) -> str | None:
    """Street identity: house number + street words, no suite/city/ZIP,
    abbreviations folded ("South Kimball Avenue" == "S Kimball Ave")."""
    a = clean_address(addr)
    if not a:
        return None
    head = a.split(",")[0]
    head = re.sub(r"\s+(ste|suite|unit|#|apt|apartment)\b.*$", "",
                  head, flags=re.I)
    toks = []
    for t in re.sub(r"[^a-z0-9 ]", " ", head.lower()).split():
        toks.append(STREET_ABBR.get(t, t))
    return " ".join(toks) or None


def address_city(addr: str | None) -> str | None:
    a = clean_address(addr)
    if not a:
        return None
    parts = [p.strip() for p in a.split(",")]
    if len(parts) >= 2:
        return parts[-2].strip()
    m = CITY_RE.search(a)
    return m.group(1).strip() if m else None


def address_zip(addr: str | None) -> str | None:
    a = clean_address(addr)
    if not a:
        return None
    m = ZIP_RE.search(a)
    return m.group(1) if m else None


def address_unit(addr: str | None) -> str | None:
    """Suite/building designator, normalised ("Ste 102" == "Suite 102"
    == "#102"). None when the address carries no unit."""
    a = clean_address(addr)
    if not a:
        return None
    m = re.search(
        r"\b(?:ste|suite|unit|apt|apartment|bldg|building|fl|floor)"
        r"\.?\s*([a-z0-9]+)\b", a, re.I)
    if m:
        return m.group(1).lower()
    m = re.search(r"#\s*([a-z0-9]+)\b", a)
    if m:
        return m.group(1).lower()
    return None


def norm_address_full(addr: str | None) -> str | None:
    """Street identity including the suite: two firms in one building
    at different suites are not the same address (One Hour of Kyle,
    Suite 107, and Procure, Ste 102, both at 3225 FM 2001, Buda, are
    different firms)."""
    s = norm_street(addr)
    if not s:
        return None
    u = address_unit(addr)
    return "%s | %s" % (s, u) if u else s


def clean_name(name: str) -> str:
    """Strip agent-added descriptors from a firm name."""
    n = (name or "").strip()
    # Leading "Serves 75165: ", "Smaller 77478 alternative: ",
    # "Nearby Alternative: ".
    n = re.sub(r"^(Serves \d+:|Smaller \d+ alternative:|Nearby Alternative:)\s*",
               "", n)
    # Em/en dash descriptor: "Name — Serves 78701", "Name – Best for ...".
    n = re.split(r"\s+[—–]\s+", n)[0]
    # Colon descriptor: "Longhorn Services: HVAC & Appliance Repair",
    # "Koala Cooling & Plumbing: HVAC Department".
    if ": " in n:
        head, tail = n.split(": ", 1)
        if re.search(r"hvac|repair|department|service|appliance",
                     tail, re.I):
            n = head
    n = n.replace("®", "").replace("™", "").strip().rstrip(".").strip()
    return n


def significant_tokens(name: str) -> set:
    return {t for t in norm(name).split() if t not in GENERIC_TOKENS}


def stem(tok: str) -> str:
    return tok[:-1] if tok.endswith("s") and len(tok) > 3 else tok


PREFIX_EXTRA_OK = GENERIC_TOKENS | {
    "llc", "inc", "co", "corp", "corporation", "ltd", "llp", "pro",
    "a", "an",
}

DESCRIPTIVE_WORDS = {
    "repair", "repairs", "install", "installation", "replacement",
    "replacements", "residential", "commercial", "emergency", "free",
    "estimates", "estimate", "best", "top", "rated", "local", "near",
    "hour", "hours",
}


def token_prefix_ok(shorter_norm: str, longer_norm: str) -> bool:
    """Is the longer name the shorter name plus generic/legal tokens
    only? "Temp Pro Mechanical, Inc." extends "Temp Pro Mechanical"
    (legal suffix); "Aire Serv of Frisco" extends "Aire Serv" with a
    place name, which is a different firm (a franchise location), not
    a name variant."""
    st, lt = shorter_norm.split(), longer_norm.split()
    if len(lt) <= len(st) or lt[:len(st)] != st:
        return False
    return all(t in PREFIX_EXTRA_OK for t in lt[len(st):])


def is_descriptive_name(name: str, town_tokens: set) -> bool:
    """A name made only of generic trade words, a town name and
    descriptive words ("Galveston Air Conditioning Repair Service")
    is a description of a service, not a brand — a shared phone is
    enough to attach it to the firm that owns the number."""
    toks = norm(name).split()
    return bool(toks) and all(
        t in GENERIC_TOKENS or t in town_tokens or t in DESCRIPTIVE_WORDS
        for t in toks)


def names_compatible_phone(a: str, b: str, town_tokens: set) -> bool:
    """Stricter compatibility for a merge whose ONLY shared evidence
    is a phone number: a shared phone alone does not make two firms
    one (call centres, lead-gen numbers, collector misattribution —
    Chrome/Bacon, Abacus/Ace Comfort, Arctic/Duncan). They must share
    a distinctive token stem, or one name must be a generic/descriptive
    form of the other, or one name must be a token-prefix extension of
    the other with generic-only extras."""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    sa = {stem(t) for t in significant_tokens(a)}
    sb = {stem(t) for t in significant_tokens(b)}
    if sa and sb and (sa & sb):
        return True
    if sa and sb and (sa <= sb or sb <= sa):
        return True
    if token_prefix_ok(na, nb) or token_prefix_ok(nb, na):
        return True
    if is_descriptive_name(a, town_tokens) \
            or is_descriptive_name(b, town_tokens):
        return True
    return False


def names_compatible(a: str, b: str) -> bool:
    """Two different name forms for the same firm? They must share a
    distinctive (non-generic) token stem, or share at least two tokens
    once legal suffixes are dropped, or one's significant tokens must
    be a subset of the other's, or one name must be a prefix of the
    other. (Used for shared-address and prefix merges only — a shared
    phone alone is NOT enough evidence for this test; see
    names_compatible_phone.)"""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    if na.startswith(nb) or nb.startswith(na):
        return True
    sa = {stem(t) for t in significant_tokens(a)}
    sb = {stem(t) for t in significant_tokens(b)}
    if sa and sb and (sa & sb):
        return True
    if sa and sb and (sa <= sb or sb <= sa):
        return True
    plain = {"llc", "inc", "co", "corp", "corporation", "ltd", "llp",
             "the", "and", "of", "a"}
    ta = {t for t in na.split() if t not in plain}
    tb = {t for t in nb.split() if t not in plain}
    if len(ta & tb) >= 2:
        return True
    return False


# --- Resolutions for headings / compound entries -------------------------
# Keyed by (original firm_name, town). Each value is a list of
# (resolved name, address, phone, position in the run's list).
# Verified against the saved answer text in
# runs/2026-11-14-study/agent/<town>/<task>/<repeat>/
# muse-spark-response.json (comparison table order = list position).
# The entry's own address/phone are used only where the section ties
# them to that firm; otherwise None. Position is None where the run's
# list order is not recoverable (Phase 2 then takes the position from
# the run's observation file for the firm's proper entry).
RESOLUTIONS = {
    # Midlothian task1-combined/2 comparison bullets -> the firms.
    ("For diagnosis-first", "Midlothian"): [
        ("2L Air Conditioning and Heating", None, "(214) 717-3959", 5)],
    ("For family-owned mid-size with maintenance plans:", "Midlothian"): [
        ("Hardin Heating & Air, LLC", "841 Dividend Rd, Midlothian, TX 76065",
         "(972) 775-8084", 3)],
    ("For highly-rated full-service alternative:", "Midlothian"): [
        ("Heritage Air Services", "1080 Dividend Rd, Midlothian, TX 76065",
         "(817) 330-4156", 2)],
    ("For longest track record + highest review volume:", "Midlothian"): [
        ("Coomes Air Conditioning & Heating",
         "1513 N Hwy 67, Midlothian, TX 76065", "(972) 296-2604", 1)],
    ("For owner-does-the-work boutique:", "Midlothian"): [
        ("Modern HVAC, LLC", None, "469-877-9905", 4)],
    ("Top pick IN 78401", "Corpus Christi"): [
        ("Precision Air", "325 N Staples St, Corpus Christi, TX 78401",
         "361-800-2465", 1)],
    ("What Makes Each Different for Installation + Repair", "Cypress"): [
        ("Texas Star Heating & Cooling", None, "281-686-6861", 1)],
    ("Regional alternative that serves 75455", "Mount Pleasant"): [
        ("Jon Wayne Heating & Air", None, None, 4)],
    ("Regional specialists that expressly serve 77590 for AC install + repair",
     "Texas City"): [
        ("Coastal Eco Heating & Air", "3515 Avenue Q, Galveston, TX 77550",
         "(409) 599-1948", 1),
        ("Clear the Air Cooling & Heating",
         "1918 County Road 130, Pearland, TX 77581", None, 2),
        ("Spears AC & Heating", "324 Grand Creek Dr, League City, TX 77573",
         "(832) 420-2665", 3),
        ("Airtron Houston", None, None, 4),
        ("Texas HVAC Solutions", None, "(512) 957-8142", 5)],
    ("Expertise.com vetted list + physically in 77489", "Missouri City"): [
        ("Prestige Air Conditioning Experts", None, None, 1),
        ("MVP Air Conditioning & Heating LLC", None, None, 2),
        ("Complete Air Services", None, None, 3),
        ("Best HVAC Repair Services Missouri City",
         "14049 S Gessner Rd, Missouri City, TX 77489", None, 4),
        ("Air Duct Cleaning Service Missouri City",
         "2118 Redcliff Dr, Missouri City, TX 77489", "(346) 659-5454", 5)],
    ("Fast-install alternatives: AirCo, Fix My Air DFW, Berkeys",
     "Fort Worth"): [
        ("AirCo Air Conditioning, Heating & Plumbing", None, None, 1),
        ("Fix My Air DFW", None, None, 2),
        ("Berkeys Plumbing, A/C & Electrical", None, None, 3)],
    ("Grizzle Heating & Air + Texas HVAC Solutions — Serve 79101",
     "Amarillo"): [
        ("Grizzle Heating & Air", None, "806-655-7676", 1),
        ("Texas HVAC Solutions", None, "(512) 957-8142", 2)],
    ("Procure Heating & Air + MEND SERVICES", "Buda"): [
        # Entry phone (512) 448-3484 is not attributable to either firm
        # from the section text; left null for both.
        ("Procure Heating & Air", "3225 FM 2001 Ste 102, Buda, TX 78610",
         None, 1),
        ("MEND Services", "12951 Wright Road, Buda, TX 78610", None, 2)],
    ("KCA Services + Super Fresh AC", "Bulverde"): [
        ("KCA Services", "136 Industrial Dr, Boerne, TX 78006",
         "210-675-8366", 1),
        ("Super Fresh AC", None, "(833) 427-1297", 2)],
    ("SoBellas Home Services + EA Heating and Cooling", "El Paso"): [
        ("SoBellas Home Services", "125 Graphite Dr Ste D, El Paso, TX 79932",
         "(915) 348-4999", 1),
        ("EA Heating and Cooling", "6999 Market Ave B, El Paso, TX 79915",
         None, 2)],
    ("DilMak Services Heating & Air Conditioning + Aire Check",
     "Floresville"): [
        ("DilMak Services Heating & Air Conditioning",
         "Floresville, TX 78114", "(210) 273-6127", 1),
        ("Aire Check", None, None, 2)],
    ("Houk Air Conditioning + 6. Eric's Home Services", "Frisco"): [
        # Entry address 1647 Witt Rd #201 is Air Repair Pros', not
        # Houk's or Eric's; entry phone is Eric's. Neither is attached
        # to Houk.
        ("Houk Air Conditioning", None, None, 1),
        ("Eric's Home Services", None, "(214) 466-6465", 2)],
    ("Cool Cat A/C, Heating & Remodeling + Super Fresh AC", "Kyle"): [
        # Entry address 142 Trinity Dr is The AC Guys', not Cool Cat's.
        ("Cool Cat A/C, Heating & Remodeling", None, None, 1),
        ("Super Fresh AC", None, "(833) 427-1297", 2)],
    ("Laredo AC + Twisted Air + Temper Mechanical", "Laredo"): [
        ("Laredo AC", "1312 Houston Street, Suite 8, Laredo, TX 78040",
         "+1 956-436-3122", 1),
        ("Twisted Air Refrigeration & Air Conditioning",
         "2701 Corsican Ln, Laredo, TX 78046", "(956) 646-7957", 2),
        ("Temper Mechanical", "2107 Shiloh Dr a13, Laredo, TX 78045",
         "+1 956-704-0002", 3)],
    ("Champion AC + G1 Air", "Schertz"): [
        # Entry address 2709 Bulverde Rd is Champion Home Services'
        # (the cohort firm); entry phone is not attributable from the
        # section. Champion AC merges with the cohort firm by name.
        ("Champion AC", None, None, 1),
        ("G1 Air", "17325 Bell North Drive, Schertz, TX 78154", None, 2)],
    ("Rabroker Air Conditioning and Plumbing + CTR Services", "Temple"): [
        ("Rabroker Air Conditioning and Plumbing",
         "4218 S General Bruce Dr, Temple, TX 76502", None, 1),
        ("CTR Services", "10620 W State Highway 36 # C4, Temple, TX 76502",
         "(254) 314-8450", 2)],
    # Numeric rating fragments the matcher recorded as firms.
    ("2", "Beaumont"): [
        ("Air Comfort, Inc.", "625 N Main St, Beaumont TX 77701",
         "(409) 241-7133", 1)],
    ("5", "Beaumont"): [
        ("Nance International", "2915 Milam St, Beaumont TX 77701",
         "(409) 234-8222", 2)],
    ("0", "Galveston"): [
        ("Bosworth Air Conditioning and Heating",
         "1213 14th St, Galveston, TX 77550", "(409) 762-5641", 3)],
    ("8", "Galveston"): [
        ("George's Air Conditioning", "1515 31st St, Galveston, TX 77550",
         "(409) 407-7221", 2)],
    ("7", "Pleasanton"): [
        ("Cowboy's Air Conditioning & Heating",
         "6510 Blanco Rd, San Antonio, TX 78216", "210-495-7771", 2)],
    ("0", "Seguin"): [
        ("Rise Service Company", None, "830-243-5318", 1)],
    ("0★", "Midlothian"): [
        ("Modern HVAC, LLC", None, None, 3)],
    # Section headings whose firms the matcher did not extract.
    ("Nearby alternatives that serve Belton (not headquartered in 76513)",
     "Belton"): [
        ("Kane Heating and Air Conditioning",
         "1130 E FM 2410 Rd, Harker Heights, TX 76541",
         "(254) 721-7049", 4),
        ("Ellis Air Systems", None, None, 5)],
    ("Nearby comparators that serve Denton", "Denton"): [
        ("Cogburn's Heating & Air Conditioning",
         "215 S Woodrow Ln, Denton, TX 76205", "(940) 243-9199", 4),
        ("Cote's Heating and Air Conditioning",
         "3500 Shelby Lane, Denton, TX 76207", "(940) 458-4980", 5),
        ("Work Environmental Systems", None, None, 6)],
    ("Nearby comparators that serve Katy", "Katy"): [
        ("Air Tech of Katy", "1402 Vander Wilt Ln, Katy, TX 77449",
         None, 5),
        ("The Katy Plumbing Company Heating & Air", None, None, 6)],
    ("Nearby alternatives that heavily serve 77478", "Sugar Land"): [
        # Entry phone 832-731-5256 is Taurus's, not Jackson's.
        ("Jackson Air & Heat", "15500 Voss Rd, Sugar Land, TX 77498",
         None, 5),
        ("Taurus Mechanical Inc", "6803 Hearthglen Ln, Sugar Land, TX 77479",
         "832-731-5256", 6),
        ("Air Depot Cooling & Heating", None, "281-477-3700", 7)],
    ("Detailed Profiles", "Burleson"): [
        ("American Home Heating & Air Conditioning", None, None, 1),
        ("Airwaves Air Conditioning & Heating", None, None, 2),
        ("AAA Airco Air Conditioning & Heating",
         "2632 Timber Rd, Burleson, TX 76028", "817-905-9033", 3),
        ("Superior AC & Heat", None, None, 4),
        ("Cool Climate Air Conditioning & Heating", None, None, 5),
        ("HVAC Repair Burleson", None, None, 6)],
    ("Detailed Profiles", "San Antonio"): [
        ("Goettl Air Conditioning and Plumbing",
         "7847 Fortune Dr, San Antonio, TX 78250", "210-460-3966", 2),
        ("Cowboys Air Conditioning & Heating",
         "6510 Blanco Rd, San Antonio, TX 78216", "210-495-7771", 3),
        ("Rosenberg Plumbing & Air",
         "4335 Vance Jackson Rd Ste 505, San Antonio, TX 78230",
         "210-503-7388", 4),
        ("Beluga Air", "240 Sherwood Dr, San Antonio, TX 78201",
         "210-468-5977", 5),
        ("Jon Wayne Service Company", None, None, 6)],
    ("Firm Details", "Flower Mound"): [
        ("Eric's Home Services", None, "(214) 466-6465", 1),
        ("Bear Air Services", "2801 Justin Rd, Flower Mound, TX 75028",
         "972-488-3366", 2),
        ("billyGO Air Conditioning & Plumbing", None, None, 3),
        ("Calvin's Climate Air Conditioning & Heating Solutions", None,
         "(972) 691-4000", 4)],
    ("Which to choose for 75028 AC work?", "Flower Mound"): [
        ("Eric's Home Services", None, "(214) 466-6465", 1),
        ("Bear Air Services", "2801 Justin Rd, Flower Mound, TX 75028",
         "972-488-3366", 2),
        ("billyGO Air Conditioning & Plumbing", None, None, 3),
        ("Calvin's Climate Air Conditioning & Heating Solutions", None,
         "(972) 691-4000", 4)],
    ("Pricing, Warranties and Differentiators", "Carrollton"): [
        ("Longhorn Services", "2544 Tarpley Rd #120, Carrollton, TX 75006",
         "469-824-3555", 1),
        ("Greentech Engineering Heating & Air Conditioning", None, None, 2),
        ("Eric's Home Services", None, "(214) 466-6465", 3),
        ("TemperaturePro DFW", None, None, 4),
        ("Calahan Construction & Air", None, None, 5),
        ("Brothers Air Conditioning & Heating", None, None, 6),
        ("On Time Experts", None, None, 7),
        ("Air Patrol Air Conditioning, Heating & Fireplaces", None, None, 8)],
    ("Which to Pick for 75006?", "Carrollton"): [
        ("Longhorn Services", "2544 Tarpley Rd #120, Carrollton, TX 75006",
         "469-824-3555", 1),
        ("Greentech Engineering Heating & Air Conditioning", None, None, 2),
        ("Eric's Home Services", None, "(214) 466-6465", 3),
        ("TemperaturePro DFW", None, None, 4),
        ("Calahan Construction & Air", None, None, 5),
        ("Brothers Air Conditioning & Heating", None, None, 6),
        ("On Time Experts", None, None, 7),
        ("Air Patrol Air Conditioning, Heating & Fireplaces", None, None, 8)],
    ("Details To Help You Choose", "Fort Worth"): [
        ("Fort Worth HVAC Pro", "420 Main St, Fort Worth, TX 76102",
         "(817) 500-0194", 1),
        ("On Point Plumbing Electrical Heating & Air", None, None, 2),
        ("Team Enoch", None, None, 3),
        ("Comfort Experts Inc", None, None, 4),
        ("Baker Brothers Plumbing, Air & Electric", None, None, 5),
        ("Lawrence Air Conditioning & Heat", None, None, 6),
        ("Breeze Air, Heat & Electrical", None, None, 7),
        ("Eric's Home Services", None, "(214) 466-6465", 8)],
    ("Which to pick?", "Brownsville"): [
        ("Texas Air Conditioning", None, None, 1),
        ("Texas Lone Star AC & Heating LLC", None, None, 2),
        ("American AC & Heating", None, None, 3),
        ("Valley Action-Aire", None, None, 4),
        ("Sea Breeze A/C & Heating", None, None, 5),
        ("Cactus Cool", None, None, 6),
        ("Temp Control Inc.", None, None, 7)],
    ("Which fits what need?", "Cedar Park"): [
        ("Excellence HVAC", None, None, 1),
        ("AC Express Air Conditioning & Heating", None, None, 2),
        ("One Hour Heating & Air Conditioning of Cedar Park", None, None, 3),
        ("Advanced Air Conditioning and Heating", None, None, 4),
        ("SALT Plumbing, Air & Electric", None, None, 5),
        ("BRITTON SERVICE GROUP, LLC", None, None, 6)],
    ("Which to Pick?", "Cibolo"): [
        ("Amazing Air Solutions", None, None, 1),
        ("Westerly Air", None, None, 2),
        ("Jon Wayne Service Company", None, None, 3),
        ("Cowboy's Air Conditioning & Heating", None, None, 4),
        ("Stay Cool Air Conditioning & Heating", None, None, 5),
        ("Comfort Reigns Group", None, None, 6),
        ("Classic Air Conditioning & Heating", None, None, 7)],
    ("Which to shortlist?", "Friendswood"): [
        ("Mabry's AC & Heating", None, None, 1),
        ("Captain's Cooling and Technical Services", None, None, 2),
        ("Clear the Air Cooling & Heating",
         "1918 County Road 130, Pearland, TX 77581", "281-992-7866", 3),
        ("Mackey Services", None, None, 4),
        ("Air Systems, Inc.", "1804 Palo Duro St, Friendswood, TX 77546",
         "(281) 842-1125", 5),
        ("Stalwart Air Conditioning And Heating Services", None, None, 6),
        ("Houston HVAC Alliance", None, None, 7)],
    ("Which to call first?", "Nacogdoches"): [
        ("Service Experts Heating & Air Conditioning",
         "163 County Road 303, Nacogdoches, TX 75961", "(936) 564-4047", 1),
        ("McWilliams Heating, Cooling & Plumbing", None, None, 2),
        ("Ferrara's Heating & Air Conditioning, Inc.", None, None, 3),
        ("Texas Air Conditioning, Electric and Plumbing",
         "8200 TX-7, Nacogdoches, TX 75964", "936-462-8030", 4)],
    ("Which fits what need?", "Rockwall"): [
        ("Cool Casa Heating & Air Conditioning, LLC", None, None, 1),
        ("Aire Serv of Rockwall", None, None, 2),
        ("Texas Choice Heating And Air", None, None, 3),
        ("Choice Heating & Air Conditioning, Inc.", None, None, 4),
        ("Lyons Air Conditioning and Heating", None, None, 5),
        ("Neighborhood Heating & Air Conditioning LLC", None, None, 6)],
    ("Which to Pick?", "The Woodlands"): [
        ("Easco Air Conditioning and Heating", None, None, 1),
        ("The A/C Guy, LLC", None, None, 2),
        ("AirNow Services", None, None, 3),
        ("Integrity Comfort Solutions", None, None, 4),
        ("Fix-It AC Repair And Installation", None, None, 5),
        ("The Chill Brothers", None, None, 6)],
    ("Which to pick?", "Pflugerville"): [
        ("Austin Air Conditioning", "13620 Immanuel Rd, Pflugerville, TX 78660",
         None, 1),
        ("Evenaire Heating & Air Conditioning",
         "21424 Martin Ln, Pflugerville, TX 78660", None, 2),
        ("Koala Cooling & Plumbing", None, None, 3),
        ("SALT Plumbing, Air & Electric", None, None, 4),
        ("Hook EM HVAC", None, None, 5),
        ("ABC Austin Service Express", None, None, 6)],
    ("Which Should You Call?", "Cypress"): [
        ("Texas Star Heating & Cooling LLC",
         "14019 Schmidt Road, Cypress, TX 77429", "281-686-6861", 1),
        ("ATS Mechanical Services LLC", None, None, 2),
        ("Doctor Home Experts Electrical Heating and Air", None, None, 3),
        ("NBL Air Conditioning and Heating", None, None, 4),
        ("Zeds Air Conditioning & Heating", None, None, 5)],
    ("Serves 76063", "Mansfield"): [
        ("Eric's Home Services", "115 Springleaf Ln, Mabank, TX 75147",
         "(214) 466-6465", 1)],
    ("Serves 77581 from Houston", "Pearland"): [
        ("75 Degree AC", "4800 W 34th St C50F, Houston, TX 77092",
         "(346) 681-2625", 1)],
    ("Serves 78205", "San Antonio"): [
        ("Super Fresh AC", None, "(833) 427-1297", 2)],
    # Rating fragments the matcher recorded as firms: the rating
    # belongs to the firm in that section of the answer.
    ("5 (531)", "Sugar Land"): [
        ("Abacus Plumbing, Air Conditioning & Electrical", None, None, 3)],
    ("9 (713 reviews)", "Sugar Land"): [
        ("Comfort Squad Heating & Cooling",
         "12425 W Airport Blvd #207, Sugar Land, TX 77478", None, 1)],
    ("0 (746 reviews)", "Sugar Land"): [
        # "5.0 (746 reviews)" is Jackson Air & Heat's rating; the
        # entry's phone (281) 937-7415 is Martin Mechanical's, from
        # the same answer — not attributed here.
        ("Jackson Air & Heat", "15500 Voss Rd, Sugar Land, TX 77498",
         None, 6)],
    # Comparison headings naming two firms each.
    ("Fox Service Company vs ARS/Rescue Rooter", "Austin"): [
        ("Fox Service Company", None, None, 5),
        ("ARS/Rescue Rooter", "2306 West Howard Lane, Austin, TX 78728",
         None, 6)],
    ("Radiant vs Strand Brothers", "Austin"): [
        ("Radiant Plumbing, Air Conditioning, & Electrical", None, None, 2),
        ("Strand Brothers Service Experts", None, None, 3)],
    # Section headings whose firms the matcher did not extract.
    ("Hyper-local 75961 shops", "Nacogdoches"): [
        ("Steve's Air Conditioning",
         "628 NE Stallings Dr, Nacogdoches, TX 75961", None, 6),
        ("ACS Cooling Heating and Refrigeration",
         "1407 N University Dr, Nacogdoches, TX 75961", None, 7),
        ("Ray's Air Conditioning Services Co",
         "2977 FM1275, Nacogdoches, TX 75961", None, 8),
        ("Bobby York Air Conditioning & Heating",
         "8225 North St, Nacogdoches, TX 75965", None, 9)],
    ("Hyper-local 76306 options", "Wichita Falls"): [
        ("Redhawk HVAC Services",
         "3130 Northeast Dr, Wichita Falls, TX 76306", "940-322-0933", 4),
        ("North Texas Air", "1015 Covington St, Wichita Falls, TX 76306",
         None, 5)],
    ("Physically in 78205", "San Antonio"): {
        # The two runs have different content under this heading.
        "san-antonio/task1-combined/2": [
            # §A is a generic directory listing ("AC Installation San
            # Antonio ...", 115 Beal St, 0 reviews) — not a firm;
            # dropped. §B is Super Fresh AC, second item in the run.
            ("Super Fresh AC", None, None, 2)],
        "san-antonio/task2-repair-only/2": [
            # §1 firms in the run's list order. The entry's own
            # address/phone (115 Beal St, (830) 239-5087) belong to
            # the task1-combined/2 generic listing, not to any firm
            # here; not attributed.
            ("Air Texas", "181 Dolorosa, San Antonio, TX 78205",
             "210-343-1027", 1),
            ("Crown Heating & Cooling San Antonio",
             "919 S Alamo St, San Antonio, TX 78205", "7262684631", 2),
            ("San Antonio AC Repairs",
             "546 W Market St, San Antonio, TX 78205", "(210) 460-1191", 3),
            ("Bratton Services HVAC Contractor",
             "194 W Commerce St, San Antonio, TX 78205", None, 4)],
    },    ("Metro-wide shops that list 78205 as served", "San Antonio"): [
        # Positions continue the run's list after the §1 firms
        # (comparison-table order); the agent worker's observation
        # file for this run records no positions.
        ("Super Fresh AC", None, None, 5),
        ("Goettl Air Conditioning and Plumbing",
         "7847 Fortune Dr, San Antonio, TX 78250", None, 6),
        ("Cowboys Air Conditioning & Heating",
         "6510 Blanco Rd, San Antonio, TX 78216", None, 7),
        ("Rosenberg Plumbing & Air",
         "4335 Vance Jackson Rd Ste 505, San Antonio, TX 78230", None, 8),
        ("Beluga Air", "240 Sherwood Dr, San Antonio, TX 78201", None, 9),
        ("Champion AC", None, None, 10)],
    # Proper entries whose address/phone the collector left blank.
    ("Schertz HVAC Contractor Solutions", "Schertz"): [
        ("Schertz HVAC Contractor Solutions",
         "1248 FM78 #100, Schertz, TX 78154", "830-626-9392", None)],
    ("G-1 Heating and Air Conditioning", "Round Rock"): [
        ("G-1 Heating and Air Conditioning",
         "2955 Donnell Dr, Round Rock, TX 78664", None, 4)],
    ("9 (1,005)", "Katy"): [
        ("BVS Home Experts",
         "2717 Commercial Center Blvd E201, Katy, TX 77494", None, 5)],
}


# Addresses to drop from a firm's audit record: the address belongs
# to another firm (collector misattribution), verified against the
# answers. Keyed by (canonical name, address).
ADDRESS_DROP = {
    ("Super Fresh AC", "1248 FM78 #100, Schertz, TX 78154"):
        "address belongs to Schertz HVAC Contractor Solutions "
        "(same answer); Super Fresh AC lists no address",
    ("Super Fresh AC", "401 West Center St Ste A, Kyle TX 78640"):
        "address belongs to Aire Serv of Kyle; Super Fresh AC lists "
        "no address",
}


# Phones to drop from a firm's audit record: the number is another
# firm's (collector misattribution), verified against the answers.
# Keyed by (canonical name, canonical address).
PHONE_DROP = {
    ("Willard Heating, Cooling & Plumbing",
     "4111 Hwy 80 East Suite 401, Mesquite, TX 75149"):
        "recorded phone (214) 466-6465 is Eric's Home Services' "
        "number in the agent answers; dropped as misattributed",
}


def expand_entries(entries):
    """One entry -> one or more mentions (resolved name, address,
    phone, source entry, runs). Returns (mentions, resolution_notes)."""
    mentions = []
    notes = []
    for e in entries:
        key = (e["firm_name"], e["town"])
        runs = sorted(set(e.get("runs_named_in") or []))
        if key in RESOLUTIONS:
            res = RESOLUTIONS[key]
            if isinstance(res, dict):
                # Per-run resolutions: {run: [(name, addr, phone, pos)]}.
                # Only the runs actually on this entry apply.
                pairs = [(run, firm) for run, firms in sorted(res.items())
                         if run in runs for firm in firms]
                all_names = [n for firms in res.values()
                             for (n, _, _, _) in firms]
            else:
                pairs = [(run, firm) for run in runs for firm in res]
                all_names = [n for (n, _, _, _) in res]
            for run, (name, addr, phone, pos) in pairs:
                mentions.append({
                    "name": name, "address": clean_address(addr),
                    "phone": phone, "website": None, "town": e["town"],
                    "runs": [run], "source": e["firm_name"],
                    "positions": {run: pos} if pos is not None else {},
                    "resolved_from": "%s (%s)" % (e["firm_name"], e["town"]),
                })
            notes.append("RESOLVED %r (%s) -> %s" % (
                e["firm_name"], e["town"], "; ".join(all_names)))
        else:
            mentions.append({
                "name": clean_name(e["firm_name"]),
                "address": clean_address(e.get("address")),
                "phone": e.get("phone"),
                "website": clean_website(e.get("website")),
                "town": e["town"],
                "runs": runs, "source": e["firm_name"],
                "positions": {},
                "resolved_from": None,
            })
    return mentions, notes


def clean_website(url: str | None) -> str | None:
    """Strip collector artefacts from a website URL (a trailing
    backtick, or a '/Phone:+1' tel fragment glued onto the URL)."""
    if not url:
        return None
    u = url.strip().rstrip("`").strip()
    u = re.sub(r"/Phone:\+?\d*\s*$", "/", u)
    return u or None


def streets_equal(a: str | None, b: str | None) -> bool:
    """Two street identities are the same if identical, or one token
    list is a prefix of the other (a city name glued onto the street
    by a period, e.g. '2709 Bulverde Rd. Bulverde' vs '2709 Bulverde
    Rd'). Used for the conflict test, where being lenient avoids
    splitting one firm on a punctuation quirk."""
    if not a or not b:
        return False
    ta, tb = a.split(), b.split()
    return ta == tb or (len(ta) > len(tb) and ta[:len(tb)] == tb) or \
        (len(tb) > len(ta) and tb[:len(ta)] == ta)


def mention_conflicts(m, cluster):
    """Identity conflict between a mention and a cluster: both have a
    street address and they differ, AND both have a phone and they
    differ. Anything less is not a conflict (a firm can publish two
    numbers; an entry can lack an address)."""
    m_addr = norm_street(m["address"])
    m_phone = norm_phone(m["phone"])
    c_addrs = {norm_street(a) for a in cluster["addresses"] if a}
    c_phones = {norm_phone(p) for p in cluster["phones"] if p}
    addr_diff = bool(m_addr and c_addrs
                     and not any(streets_equal(m_addr, x)
                                 for x in c_addrs))
    phone_diff = bool(m_phone and c_phones and m_phone not in c_phones)
    return addr_diff and phone_diff


def phone_owners(mentions):
    """A phone number dominated by one firm's mentions (a strict
    majority, at least 3 mentions) belongs to that firm; other firms
    carrying it got it by collector misattribution. Eric's number
    (214) 466-6465 appears on Dallas Heating, Total Air & Plumbing
    and Willard entries, and must not merge those firms together or
    with each other. A phone with no dominant owner stays usable as
    evidence (e.g. Total Air's 972-881-0020, shared by its own name
    variants)."""
    by_phone = defaultdict(Counter)
    for m in mentions:
        p = norm_phone(m["phone"])
        if p:
            by_phone[p][norm(m["name"])] += 1
    owners = {}
    for p, counts in by_phone.items():
        top_name, top_n = counts.most_common(1)[0]
        total = sum(counts.values())
        if top_n >= 3 and top_n > total - top_n:
            owners[p] = top_name
    return owners


def cluster_mentions(mentions, town_tokens, owners):
    """Greedy clustering within each normalised-name group, then
    cross-name merges on shared address/phone with a compatible name.
    Returns (clusters, merge_notes)."""
    # Order: most evidence first, so bare mentions attach to
    # established clusters rather than founding new ones.
    def detail(m):
        return (1 if m["address"] else 0, 1 if m["phone"] else 0,
                len(m["runs"]))
    mentions = sorted(mentions, key=lambda m: (-detail(m)[0],
                                               -detail(m)[1],
                                               -detail(m)[2],
                                               m["name"], m["town"]))
    by_name = defaultdict(list)
    for m in mentions:
        by_name[norm(m["name"])].append(m)
    clusters = []
    notes = []
    for name_key in sorted(by_name):
        group = by_name[name_key]
        group_clusters = []
        for m in group:
            # Prefer a cluster whose address city is this mention's town.
            cands = [c for c in group_clusters
                     if not mention_conflicts(m, c)]
            if cands:
                cands.sort(key=lambda c: (
                    0 if m["town"] in
                    {address_city(a) for a in c["addresses"]} else 1,
                    -len(c["mentions"])))
                target = cands[0]
            else:
                target = {"mentions": [], "addresses": set(),
                          "phones": set()}
                group_clusters.append(target)
            target["mentions"].append(m)
            if m["address"]:
                target["addresses"].add(clean_address(m["address"]))
            if m["phone"]:
                target["phones"].add(m["phone"])
        clusters.extend(group_clusters)
    # Cross-name merges: shared street address or shared phone, with a
    # compatible name, and no identity conflict. Pairs are found via
    # address/phone indexes (not all-pairs), then prefix-name pairs
    # via a sorted name list. Iterate to fixpoint.
    def cluster_sig(c):
        return {
            "names": {norm(m["name"]) for m in c["mentions"]},
            "addrs": {norm_street(x) for x in c["addresses"] if x},
            "full_addrs": {norm_address_full(x) for x in c["addresses"]
                           if x},
            "phones": {norm_phone(p) for p in c["phones"] if p},
        }

    def try_merge_pair(clusters, i, j, notes):
        a, b = clusters[i], clusters[j]
        sa, sb = cluster_sig(a), cluster_sig(b)
        if sa["names"] == sb["names"]:
            return False
        shared_addr = sa["full_addrs"] & sb["full_addrs"]
        # A phone owned by a third firm (see phone_owners) is not
        # evidence that these two clusters are one firm.
        shared_phone = {p for p in sa["phones"] & sb["phones"]
                        if p not in owners
                        or owners[p] in sa["names"]
                        or owners[p] in sb["names"]}
        prefix = any(x.startswith(y) or y.startswith(x)
                     for x in sa["names"] for y in sb["names"])
        if not (shared_addr or shared_phone or prefix):
            return False
        conflict = bool(
            sa["addrs"] and sb["addrs"]
            and not any(streets_equal(x, y)
                        for x in sa["addrs"] for y in sb["addrs"])
            and sa["phones"] and sb["phones"] and not shared_phone)
        if conflict:
            note = ("NOT merged (identity conflict): %s <-> %s"
                    % (sorted(sa["names"]), sorted(sb["names"])))
            if note not in notes:
                notes.append(note)
            return False
        # Evidence gating: what the shared evidence is decides how
        # similar the names must be. Same full address AND same phone
        # still needs a compatible name — the collector can put one
        # firm's address+phone on another firm's entry (Texas Star's
        # details on the Doctor Home Experts entry), so an
        # address+phone match between wholly different names is a
        # collector artefact, not one firm. Same address alone still
        # needs a compatible name (a building can host two firms). A
        # shared phone alone is the weakest — call centres, lead-gen
        # numbers and collector misattribution put one number on two
        # firms — so it needs the strict test.
        names_a = sorted(sa["names"])
        names_b = sorted(sb["names"])
        if shared_addr and shared_phone:
            ok = any(names_compatible(x, y)
                     for x in names_a for y in names_b)
            why = "shared address and phone"
        elif shared_addr:
            ok = any(names_compatible(x, y)
                     for x in names_a for y in names_b)
            why = "shared address"
        elif shared_phone:
            ok = any(names_compatible_phone(x, y, town_tokens)
                     for x in names_a for y in names_b)
            why = "shared phone"
        else:  # prefix name only
            ok = any(names_compatible(x, y)
                     for x in names_a for y in names_b)
            why = "prefix name"
        if not ok:
            note = ("NOT merged (%s only, names differ): %s <-> %s"
                    % (why, names_a, names_b))
            if note not in notes:
                notes.append(note)
            return False
        notes.append("MERGED cross-name: %s <-> %s (%s)"
                     % (names_a, names_b, why))
        a["mentions"].extend(b["mentions"])
        a["addresses"] |= b["addresses"]
        a["phones"] |= b["phones"]
        del clusters[j]
        return True

    changed = True
    while changed:
        changed = False
        sigs = [cluster_sig(c) for c in clusters]
        # Candidate pairs: shared address, shared phone, or prefix name.
        cand = set()
        by_addr, by_phone = defaultdict(list), defaultdict(list)
        for idx, s in enumerate(sigs):
            for a in s["full_addrs"]:
                by_addr[a].append(idx)
            for p in s["phones"]:
                by_phone[p].append(idx)
        for idxs in list(by_addr.values()) + list(by_phone.values()):
            for x in range(len(idxs)):
                for y in range(x + 1, len(idxs)):
                    cand.add((min(idxs[x], idxs[y]),
                              max(idxs[x], idxs[y])))
        ordered_names = sorted(
            (n, idx) for idx, s in enumerate(sigs) for n in s["names"])
        for k in range(len(ordered_names) - 1):
            n1, i1 = ordered_names[k]
            n2, i2 = ordered_names[k + 1]
            if i1 != i2 and (n1.startswith(n2) or n2.startswith(n1)):
                cand.add((min(i1, i2), max(i1, i2)))
        for i, j in sorted(cand):
            if j < len(clusters) and try_merge_pair(clusters, i, j, notes):
                changed = True
                break
    return clusters, notes


def main():
    with open(ADDITIONS, encoding="utf-8") as fh:
        adds = json.load(fh)
    entries = adds["entries"]
    with open(COHORT_LIST, encoding="utf-8") as fh:
        cohort = json.load(fh)
    cohort_firms = cohort["firms"]
    towns = {t["town"]: t for t in cohort["towns"]}
    with open(ABILENE, encoding="utf-8") as fh:
        abilene = json.load(fh)["firms"]
    abilene_ids = {f["firm_id"] for f in abilene}
    abilene_names = {norm(f["name"]): f for f in abilene}
    cohort_by_norm = {norm(f["name"]): f for f in cohort_firms}
    cohort_ids = {f["firm_id"] for f in cohort_firms}
    cohort_norms = [(norm(f["name"]), f) for f in cohort_firms]
    # Cohort firms that share an address/phone with an addition are
    # found via these indexes (the full 861 scan per firm is too slow).
    cohort_by_phone_or_addr = []
    seen_cohort = set()
    for cf in cohort_firms:
        key = (norm_phone(cf.get("phone_recorded")),
               norm_street(cf.get("address")))
        if key not in seen_cohort:
            seen_cohort.add(key)
            cohort_by_phone_or_addr.append(cf)

    mentions, res_notes = expand_entries(entries)
    town_tokens = {t for town in towns for t in norm(town).split()}
    owners = phone_owners(mentions)
    clusters, merge_notes = cluster_mentions(mentions, town_tokens, owners)
    # (street, phone) pairs the collector put on two different firms
    # (e.g. Texas Star's address+phone on the Doctor Home Experts
    # entry) cannot be trusted as either firm's identity evidence.
    pair_clusters = defaultdict(set)
    for ci, cluster in enumerate(clusters):
        for m in cluster["mentions"]:
            if m["address"] and m["phone"]:
                pair_clusters[(norm_street(m["address"]),
                               norm_phone(m["phone"]))].add(ci)
    contaminated_pairs = {p for p, cs in pair_clusters.items()
                          if len(cs) > 1}

    log = {
        "generated": "2026-11-14",
        "source_entries": len(entries),
        "mentions": len(mentions),
        "distinct_firms": len(clusters),
        "resolutions": res_notes,
        "merges": merge_notes,
        "firms": [],
    }
    firms_out = []
    runs_out = {}
    used_ids = set(cohort_ids) | set(abilene_ids)
    skipped = Counter()
    for cluster in sorted(clusters, key=lambda c: (
            min(m["name"].lower() for m in c["mentions"]))):
        ms = cluster["mentions"]
        names = Counter(m["name"] for m in ms)
        canonical = sorted(names, key=lambda n: (-len(n), -names[n], n))[0]
        runs = sorted({r for m in ms for r in m["runs"]})
        positions = {}
        for m in ms:
            for r, p in (m.get("positions") or {}).items():
                positions.setdefault(r, p)
        towns_named = Counter()
        for m in ms:
            towns_named[m["town"]] += len(m["runs"])
        town_list = sorted(towns_named)
        # Address: prefer a complete address whose city is a named town,
        # then the mention with the most runs.
        def addr_rank(a):
            city = address_city(a)
            return (0 if city in towns_named else 1,
                    0 if address_zip(a) else 1, -len(a or ""))
        addresses = sorted({clean_address(a) for a in cluster["addresses"]},
                           key=addr_rank)
        dropped_addrs = [a for a in addresses
                         if (canonical, a) in ADDRESS_DROP]
        if dropped_addrs:
            addresses = [a for a in addresses
                         if (canonical, a) not in ADDRESS_DROP]
        address = addresses[0] if addresses else None
        # Phone: the number used by the most mentions (a firm can
        # publish two numbers; a minority number is often another
        # firm's, attached by the collector — e.g. Eric's number on
        # one Total Air & Plumbing entry).
        phones = Counter(norm_phone(m["phone"]) for m in ms if m["phone"])
        phone = None
        dropped_phone = None
        phone_drop_note = ""
        if phones:
            best = sorted(phones, key=lambda p: (-phones[p], p))[0]
            phone = next(p for p in cluster["phones"]
                         if norm_phone(p) == best)
        if (canonical, address) in PHONE_DROP:
            # The recorded number is another firm's; drop it rather
            # than audit the firm under a wrong phone.
            dropped_phone = phone
            phone_drop_note = PHONE_DROP[(canonical, address)]
            phone = None
        addr_city = address_city(address)
        if addr_city and addr_city in towns_named:
            primary_town = addr_city
            primary_reason = "address town (%s)" % addr_city
        else:
            primary_town = sorted(towns_named,
                                  key=lambda t: (-towns_named[t], t))[0]
            primary_reason = ("most-named town (%d of %d runs)"
                              % (towns_named[primary_town], len(runs)))
        town_rec = towns.get(primary_town)
        if town_rec is None:
            log["firms"].append({
                "firm": canonical, "status": "ERROR no town record",
                "primary_town": primary_town})
            continue
        # Cohort / Abilene checks on the merged firm. A cohort match is
        # rejected on an identity conflict: the cluster and the cohort
        # firm both have a street address and they differ, AND both
        # have a phone and they differ — that is a distinct firm with
        # the same name (Ellis Air Conditioning and Heating, Grand
        # Prairie/Cedar Hill, vs the Dallas cohort firm; R&R Air
        # Conditioning, Grand Prairie, vs Paris; Champion Home
        # Services, Boerne, vs Bulverde). Same town + same name is
        # NOT a conflict: a firm may have moved, or the agent's
        # address/phone may be stale (Bosworth, Galveston). Evidence
        # from a contaminated (address, phone) pair is ignored.
        c_addrs = {norm_street(a) for a in cluster["addresses"] if a}
        # A phone owned by another firm (see phone_owners) is not this
        # cluster's evidence: ignore it in the cohort check.
        cluster_names = {norm(n) for n in names}
        c_phones = {norm_phone(p) for p in cluster["phones"] if p
                    and (norm_phone(p) not in owners
                         or owners[norm_phone(p)] in cluster_names)}
        clean_addrs, clean_phones = set(c_addrs), set(c_phones)
        for ps, pp in contaminated_pairs:
            if ps in c_addrs and pp in c_phones:
                clean_addrs.discard(ps)
                clean_phones.discard(pp)

        def cohort_conflicts(cf):
            if cf["town"] == primary_town:
                return False
            cf_addr = norm_street(cf.get("address"))
            cf_phone = norm_phone(cf.get("phone_recorded"))
            addr_diff = bool(cf_addr and clean_addrs
                             and not any(streets_equal(cf_addr, x)
                                         for x in clean_addrs))
            phone_diff = bool(cf_phone and clean_phones
                              and cf_phone not in clean_phones)
            return addr_diff and phone_diff

        cohort_hit = None
        cohort_note = ""
        cn = norm(canonical)
        if cn in cohort_by_norm:
            cf = cohort_by_norm[cn]
            if cohort_conflicts(cf):
                cohort_note = (
                    "same name as the cohort firm under %s, but a "
                    "different street address AND a different phone — "
                    "treated as a distinct firm" % cf["town"])
            else:
                cohort_hit = cf
        if cohort_hit is None:
            # Prefix match against the cohort (the collect script's
            # second-pass merge can leave a longer agent name), but
            # only when the longer name adds generic/legal tokens:
            # "Aire Serv of Frisco" is a different franchise from the
            # cohort "Aire Serv" (Midland), not a name variant.
            for cfn, cf in cohort_norms:
                if token_prefix_ok(cfn, cn) or token_prefix_ok(cn, cfn):
                    if names_compatible(canonical, cf["name"]) \
                            and not cohort_conflicts(cf):
                        cohort_hit = cf
                        break
        if cohort_hit is None and (c_addrs or c_phones):
            # Compatible name + shared phone/address with a cohort firm.
            for cf in cohort_by_phone_or_addr:
                if not names_compatible(canonical, cf["name"]):
                    continue
                if (norm_street(cf.get("address")) in c_addrs
                        or norm_phone(cf.get("phone_recorded"))
                        in c_phones):
                    cohort_hit = cf
                    break
        abilene_hit = abilene_names.get(cn)
        status = "audit"
        status_note = ""
        if cohort_hit is not None:
            status = "skip-cohort"
            status_note = ("in the 861-firm cohort under %s"
                           % cohort_hit["town"])
            skipped["cohort"] += 1
        elif abilene_hit is not None:
            status = "skip-abilene-audited"
            status_note = ("already audited for Abilene, 2026-11-14 "
                           "(one of the 9 Abilene additions)")
            skipped["abilene"] += 1
        # firm_id (audit firms only need one, but assign for all).
        fid = slug(canonical)
        if fid in used_ids:
            fid = "%s-%s" % (fid, slug(primary_town))
            n = 2
            while fid in used_ids:
                fid = "%s-%s-%d" % (slug(canonical), slug(primary_town), n)
                n += 1
        used_ids.add(fid)
        alt_addrs = [a for a in addresses[1:]] if len(addresses) > 1 else []
        alt_phones = [p for p in sorted(cluster["phones"])
                      if norm_phone(p) != norm_phone(phone)
                      and norm_phone(p) != norm_phone(dropped_phone)] \
            if (phone or dropped_phone) else sorted(cluster["phones"])
        entry_names = sorted({(m["source"], m["town"]) for m in ms})
        note_parts = [
            "Named by the agent in: %s." % ", ".join(runs),
            "Primary town %s (%s)." % (primary_town, primary_reason),
            "Merged from %d addition %s: %s."
            % (len(entry_names), "entry" if len(entry_names) == 1
               else "entries",
               "; ".join("%s (%s)" % (n, t) for n, t in entry_names)),
        ]
        if alt_addrs:
            note_parts.append("Alternate address(es): %s."
                              % "; ".join(alt_addrs))
        if alt_phones:
            note_parts.append("Alternate phone(s): %s."
                              % "; ".join(alt_phones))
        if any(m.get("resolved_from") for m in ms):
            note_parts.append("Name(s) resolved from agent headings: %s."
                              % "; ".join(sorted({m["resolved_from"]
                                                 for m in ms
                                                 if m.get("resolved_from")})))
        if cohort_note:
            note_parts.append("Cohort check: %s." % cohort_note)
        if phone_drop_note:
            note_parts.append("Phone dropped: %s." % phone_drop_note)
        for a in dropped_addrs:
            note_parts.append("Address dropped: %s — %s."
                              % (a, ADDRESS_DROP[(canonical, a)]))
        if status != "audit":
            note_parts.append("SKIPPED from audit: %s." % status_note)
        firm_zip = address_zip(address) or town_rec["town_zip"]
        rec = {
            "firm_id": fid,
            "name": canonical,
            "website": next((m.get("website") for m in ms
                             if m.get("website")), None),
            "website_home": None,
            "address": address,
            "phone_recorded": phone,
            "meta_place_id": None,
            "town": primary_town,
            "county": town_rec["county"],
            "town_zip": town_rec["town_zip"],
            "firm_zip": firm_zip,
            "primary_business_category": "HVAC Contractor",
            "trade": "HVAC",
            "query": "AC installation and repair",
            "discovery_source":
                "Agent-named addition (MUSE-SPARK runs, 2026-11-14)",
            "discovery_note": " ".join(note_parts),
        }
        log["firms"].append({
            "firm_id": fid, "name": canonical, "status": status,
            "status_note": status_note, "cohort_match_note": cohort_note,
            "primary_town": primary_town,
            "towns_named_in": town_list,
            "runs_named_in": runs,
            "positions": positions,
            "mentions": len(ms), "address": address, "phone": phone,
        })
        runs_out[fid] = {
            "name": canonical, "status": status,
            "primary_town": primary_town, "towns_named_in": town_list,
            "runs_named_in": runs, "positions": positions,
        }
        if status == "audit":
            firms_out.append(rec)
    firms_out.sort(key=lambda f: (f["town"], f["name"].lower()))
    with open(OUT_FIRMS, "w", encoding="utf-8") as fh:
        json.dump({"firms": firms_out}, fh, indent=2)
    with open(OUT_LOG, "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=2)
    with open(OUT_RUNS, "w", encoding="utf-8") as fh:
        json.dump(runs_out, fh, indent=2)
    print("entries: %d" % len(entries))
    print("mentions (after heading/compound resolution): %d"
          % len(mentions))
    print("distinct firms: %d" % len(clusters))
    print("to audit: %d" % len(firms_out))
    print("skipped: %s" % dict(skipped))
    print("wrote %s (%d firms)" % (OUT_FIRMS, len(firms_out)))
    print("wrote %s" % OUT_LOG)
    print("wrote %s" % OUT_RUNS)


if __name__ == "__main__":
    main()
