"""Validate the rules engine against the recorded Airtron evidence
(Spec v2.1).

Source: AI Sharc-Sample-Audit-Data — 2026-11-07 — Rev 1.xlsx (Audit Data
sheet, Airtron, 25 Oct 2026, v1.6) + the Top 10 workbook row for Airtron
(2026-10-25). The sample is the only firm with row-level evidence; the other
18 firms have grade/score/High counts only, so they cannot validate per-Item
logic.

What this test proves, and what it does NOT prove:
- PROVES: the engine reproduces the sample's evidence-backed results
  exactly (the only Items with real evidence notes, not derivations):
  C1.1 Missing, C4.2 Not accessible (scored Items); C3.2 Not checked and
  C4.1 Suggested (Section 4 Ranking Suggestions in v2.1 — C3.2 BBB
  accreditation and rating consistent with bbb.org and C4.1 six-line
  warranty card are no longer scored Items).
- PROVES: G1 exact name and G6 verifiable listing, now scored Items, are
  Not accessible with a human-review flag where the listing evidence is
  absent from the record — the engine refuses to assume a Pass (Spec s.4.3).
- DOES NOT reproduce the sample's derived Passes from the recorded data
  alone, and that is CORRECT behaviour, not an engine error: the sample's
  Passes (most Gates and Items) are derived from "no High/Critical issue in
  this Item in the 25 Oct fix list" — i.e. pass by absence of a recorded
  issue. The engine requires positive evidence (source URL, date, exact
  wording/figure, Spec s.4.3) and refuses to assume a Pass. The recorded
  25 Oct data does not contain the positive listing facts (the Top 10 check
  read the listings, but the workbook does not record the listing name,
  services, or phone as separate data points — Place ID and Other Listing
  are "Not accessible" in the workbook). A fresh audit's fetchers WILL
  read and record the listings, so the engine will have the positive
  evidence it needs. This test documents the difference so it is not
  mistaken for an engine error.

Run: python3 tests/test_airtron_validation.py
"""

import sys

sys.path.insert(0, '/home/hatch/workspace/goals/score-card-audit-product/files/aisharc-harness-v2')

from aisharc_harness.rules.engine import (
    score_audit, load_definitions, MISSING, NOT_ACCESSIBLE,
)

DEFS = load_definitions()

# The evidence-backed results from the sample (evidence notes quoted
# verbatim). These are the only results with real evidence, not a
# derivation from the fix list.
EVIDENCE_BACKED_ITEMS = {
    "C1.1": ("Missing",
             "Headline rating is an own-site claim, not independently "
             "corroborated in this pass."),
    "C4.2": ("Not accessible",
             "Diagnostic/service-call fee amount not published."),
}
EVIDENCE_BACKED_SUGGESTIONS = {
    "C3.2": ("Not checked",
             "BBB A+ claim not independently read on bbb.org."),
    "C4.1": ("Suggested",
             "Warranty parts/labour split not published."),
}


def airtron_evidence() -> dict:
    """Evidence for Airtron built from the recorded 25 Oct facts (Top 10
    workbook row + sample evidence notes). Listing facts that the workbook
    does not record are left absent — the engine must not assume them."""
    return {
        "website": {"unreadable": False, "readable": True, "has_website": True},
        "items": {
            "C1.1": {"own_site_rating": "4.8 on 4,565",
                     "rating_platforms": {
                         "google": {"accessible": True, "rating": None, "count": None}}},
            "C1.2": {"website_rating": {"rating": 4.8, "count": 4565},
                     "rating_platforms": {
                         "google": {"accessible": True, "rating": None, "count": None}}},
            "C1.3": {"reviews": {"accessible": True}},
            "C2.1": {"town": "Coppell", "zip": "75019",
                     "service_area_page": {"accessible": True, "names_town_zip": True}},
            "C2.2": {"service_area_page": {"accessible": True, "install_repair_separate": True}},
            "C2.3": {"service_area_page": {"accessible": True, "brands_listed": False}},
            "C2.4": {"service_area_page": {"accessible": True, "phone_and_booking": True}},
            "C3.1": {"licence": {"published": True, "number": "TACLB00097767E",
                                 "register": {"accessible": True, "active": True}}},
            # No listing source is recorded as checked for Airtron.
            "G6": {"listings_checked": [], "matching_listing": None},
            "C3.2": {"bbb": {"claim": "A+ rating presented on Airtron's own pages",
                             "bbb_org_accessible": False,
                             "reason": "not independently read on bbb.org"}},
            "C4.1": {"warranty": {"accessible": True, "lines": {}}},
            "C4.2": {"diagnostic_fee": {"accessible": True}},
            "C4.3": {"free_estimate_install": {"accessible": True, "stated": True,
                                               "text": "Instant Quote offered online"}},
            "C4.4": {"free_estimate_repair": {"accessible": True, "stated": True,
                                              "text": "Instant Quote offered online"}},
            "C5.1": {"hours": {"accessible": True, "day_by_day": True,
                               "text": "Mon-Fri 8:00 AM-5:00 PM"}},
            "C5.2": {"hours_consistency": {"accessible": True}},
            "C6.1": {"phones": ["1-972-468-6479"]},
            "C6.2": {"founding_years": {"website": "52+ years of trusted service"}},
            # Only the website name is recorded; no listing name is in the
            # record (Place ID and Other Listing are "Not accessible").
            "G1": {"names": {"website": "Airtron Heating & Air Conditioning"}},
            # No 25 Oct evidence for the Machine Readability Items (v1.7
            # placeholders in the sample). Left absent -> Not accessible.
            "C7.1": {"robots_txt": {"accessible": False, "reason": "no 25 Oct 2026 evidence"}},
            "C7.2": {"initial_html": {"accessible": False, "reason": "no 25 Oct 2026 evidence"}},
            "C7.3": {"json_ld": {"accessible": False, "reason": "no 25 Oct 2026 evidence"}},
            "C7.4": {"sitemap": {"accessible": False, "reason": "no 25 Oct 2026 evidence"}},
        },
        "levers": {},
    }


def main() -> None:
    ev = airtron_evidence()
    result = score_audit("Airtron Heating & Air Conditioning",
                         "AC installation and repair", "Coppell, TX 75019",
                         "2026-10-25", ev, DEFS)
    by_item = {r.item_id: r for r in result.rows if r.row_type == "Item"}
    by_s4 = {r.item_id: r for r in result.section_4_suggestions}

    print("== Evidence-backed Items (must reproduce the sample exactly) ==")
    ok = True
    for item_id, (expected, note) in EVIDENCE_BACKED_ITEMS.items():
        got = by_item[item_id].result
        status = "OK " if got == expected else "MISMATCH"
        if got != expected:
            ok = False
        print("  %s %s: engine=%s sample=%s  (%s)"
              % (status, item_id, got, expected, note))
    assert ok, "evidence-backed Items did not reproduce the sample"

    print()
    print("== Evidence-backed Section 4 Ranking Suggestions ==")
    for item_id, (expected, note) in EVIDENCE_BACKED_SUGGESTIONS.items():
        got = by_s4[item_id].result
        status = "OK " if got == expected else "MISMATCH"
        if got != expected:
            ok = False
        print("  %s %s: engine=%s sample=%s  (%s)"
              % (status, item_id, got, expected, note))
    assert ok, "evidence-backed Section 4 suggestions did not reproduce"

    print()
    print("== G1 / G6 Items where the listing evidence is absent ==")
    print("  The sample records these as Pass by derivation from the")
    print("  fix list; the record does not contain the listing facts, so the")
    print("  engine correctly refuses to assume a Pass (Spec s.4.3).")
    for iid in ("G1", "G6"):
        row = by_item[iid]
        print("  %s: engine=%s human_review=%s — %s"
              % (iid, row.result, row.human_review, row.evidence[:100]))
        assert row.result == NOT_ACCESSIBLE and row.human_review, iid

    print()
    print("== Counting on the v2.1 composition (21 scored Items) ==")
    high = sum(1 for r in result.rows
               if r.row_type == "Item" and r.result in (MISSING, NOT_ACCESSIBLE))
    print("  Items: 21 | High: %d | passed: %d | total points: %d/100 | grade: %s"
          % (high, result.passed_items, result.total_points, result.grade))
    # The engine is stricter than the sample's derivation on C1.2 (no
    # independent figure to compare -> Not accessible, not a derived Pass)
    # and on C2.3 (no brand/dealer status found in the sources checked ->
    # Missing, not a derived Pass). Both are documented method differences.
    print("  C1.2 engine=%s (sample Pass by derivation; no independent figure"
          " to compare -> Not accessible)" % by_item["C1.2"].result)
    print("  C2.3 engine=%s (Field Mapping pass criteria: 'Brands and system"
          " types actually served listed'. Workbook: system types listed,"
          " but 'No specific brand / dealer status found' -> brands not"
          " listed, so the Item does not meet its pass criteria. The"
          " sample's derived Pass is not supported by the recorded"
          " evidence; the engine is right here.)"
          % by_item["C2.3"].result)

    print()
    print("== Engine result on the recorded 25 Oct evidence (v2.1) ==")
    print("  grade=%s points=%d/100 high=%d passed_items=%d rows=%d"
          % (result.grade, result.total_points,
             result.high_issues, result.passed_items, len(result.rows)))
    print("  (Differs from the sample's v1.6 Grade B / 3/6 / 0 Critical /")
    print("   4 High because the engine requires positive evidence and the")
    print("   v2.1 composition scores G1/G6 as Items, moves C3.2/C4.1 to")
    print("   Ranking Suggestions, and adds 4 Machine Readability Items")
    print("   with no 25 Oct evidence. The v1.6 record stands as")
    print("   historical only.)")
    assert result.spec_version == "2.1"
    assert len(result.rows) == 36
    assert result.grade == "C" and result.total_points == 49, result.as_dict()
    assert result.high_issues == 10 and result.passed_items == 11
    # C3.2 / C4.1 are Ranking Suggestion rows as well as section_4 entries.
    by_sugg = {r.item_id: r for r in result.rows
               if r.row_type == "Ranking Suggestion"}
    assert by_sugg["C3.2"].result == "Not checked"
    assert by_sugg["C4.1"].result == "Suggested"
    print()
    print("AIRTRON VALIDATION DONE: evidence-backed results reproduce exactly;")
    print("method differences (derived Passes vs positive evidence) documented.")


if __name__ == "__main__":
    main()
