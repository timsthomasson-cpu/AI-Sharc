"""Spec v2.1 engine tests: 100-point model, bands, F rule, 36 rows.

Covers what the v1.22 suite cannot: Allocation v2 points (21 scored Items,
100 points), the A 65+ / B 50-64 / C 30-49 / D below-30 bands, F ONLY for
Website Access / not in business (Spec s.5), the unverified outcome for
AI Sharc-side reasons, 36 rows with no Gate rows, 'Ranking Suggestion'
terminology, C2.2 service-page only, C5.1 24-hour-claim Pass, G1/G6 as
scored Items, C3.2/C4.1 as un-scored Section 4 Ranking Suggestions, and
the norm_text 'A/C' = 'AC' loosening (Spec s.6.6).

Deterministic: pure engine calls on fixture evidence, no network.
Run: python3 tests/test_v21_scoring.py
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aisharc_harness.rules.engine import (
    ITEM_POINTS, ITEM_CATALOG, CATEGORY_POINTS, grade_from_points,
    norm_text, score_audit, load_definitions,
)

DEFS = load_definitions()


def all_pass_evidence() -> dict:
    """Evidence on which every scored Item passes (100 points)."""
    return {
        "website": {"unreadable": False, "readable": True, "has_website": True},
        "items": {
            "C1.1": {"rating_platforms": {
                "google": {"rating": 4.6, "count": 1234, "accessible": True},
                "meta": {"rating": 4.6, "count": 1200, "accessible": True}}},
            "C1.2": {"website_rating": {"rating": 4.6, "count": 1234},
                     "rating_platforms": {
                         "google": {"rating": 4.6, "count": 1234, "accessible": True}}},
            "C1.3": {"reviews": {"accessible": True}},
            "C2.1": {"town": "Coppell", "zip": "75019",
                     "service_area_page": {"accessible": True, "names_town_zip": True}},
            "C2.2": {"service_area_page": {"accessible": True, "install_repair_separate": True}},
            "C2.3": {"service_area_page": {"accessible": True, "brands_listed": True}},
            "C2.4": {"service_area_page": {"accessible": True, "phone_and_booking": True}},
            "C3.1": {"licence": {"published": True, "number": "TACLB00012345E",
                                 "register": {"accessible": True, "active": True}}},
            "G6": {"listings_checked": ["google", "meta"],
                   "matching_listing": {"source": "google", "name": "Example Heating"}},
            "C3.2": {"bbb": {"claim": "A+ accredited", "bbb_org_accessible": True,
                             "accredited": True, "consistent": True}},
            "C4.1": {"warranty": {"accessible": True, "lines": {
                "new_parts": True, "new_labour": True, "repair_parts_labour": True,
                "registration": True, "transferable": True, "claim_line": True}}},
            "C4.2": {"diagnostic_fee": {"accessible": True, "amount": 79,
                                        "text": "$79 diagnostic fee"}},
            "C4.3": {"free_estimate_install": {"accessible": True, "stated": True,
                                               "text": "Free estimates on installs"}},
            "C4.4": {"free_estimate_repair": {"accessible": True, "stated": True,
                                              "text": "Free estimates on repairs"}},
            "C5.1": {"hours": {"accessible": True, "day_by_day": True,
                               "text": "Mon-Fri 8-5, Sat 9-1"}},
            "C5.2": {"hours_consistency": {"accessible": True}},
            "C6.1": {"phones": ["(555) 555-0100"]},
            "C6.2": {"founding_years": {"website": 2010, "google": 2010}},
            "G1": {"names": {"website": "Example Heating",
                             "google": "Example Heating",
                             "meta": "Example Heating"}},
            "C7.1": {"robots_txt": {"accessible": True, "exists": True,
                                    "blocked_tokens": []}},
            "C7.2": {"initial_html": {"accessible": True, "missing_facts": []}},
            "C7.3": {"json_ld": {"accessible": True, "present": True}},
            "C7.4": {"sitemap": {"accessible": True, "present": True,
                                 "valid": True, "url": "https://example.com/sitemap.xml"}},
        },
        "levers": {
            "booking_route": {"accessible": True, "route": "form",
                             "next_step": "call within 1 hour",
                             "written_quote": "quote in writing before work"},
            "availability": {"accessible": True, "next_appointment": "tomorrow 9am"},
            "price": {"accessible": True, "diagnostic_fee": 79,
                      "price_range": "$79-$149"},
            "brand_coverage": {"accessible": True, "brands_listed": "Trane, Carrier"},
            "dispatch": {"accessible": True, "disclosed_test": "test booking confirmed"},
            "llms_txt": {"accessible": True, "exists": True,
                         "lists_services": True, "lists_area": True},
        },
    }


# Per-Item mutation that makes the Item fail (Missing or Not accessible).
def _fail(ev: dict, item_id: str) -> None:
    it = ev["items"]
    if item_id == "C1.1":
        it["C1.1"] = {"rating_platforms": {}}
    elif item_id == "C1.2":
        it["C1.2"]["website_rating"] = {"rating": 4.9, "count": None}
    elif item_id == "C1.3":
        it["C1.3"] = {"reviews": {"accessible": True,
                                  "recurring_pattern": "no-shows"}}
    elif item_id in ("C2.1", "C2.2", "C2.3", "C2.4"):
        field = {"C2.1": "names_town_zip", "C2.2": "install_repair_separate",
                 "C2.3": "brands_listed", "C2.4": "phone_and_booking"}[item_id]
        it[item_id]["service_area_page"][field] = False
    elif item_id == "C3.1":
        it["C3.1"] = {"licence": {"published": False}}
    elif item_id == "G6":
        it["G6"] = {"listings_checked": ["google"], "matching_listing": None}
    elif item_id == "C4.2":
        it["C4.2"] = {"diagnostic_fee": {"accessible": True}}
    elif item_id == "C4.3":
        it["C4.3"] = {"free_estimate_install": {"accessible": True, "stated": False}}
    elif item_id == "C4.4":
        it["C4.4"] = {"free_estimate_repair": {"accessible": True, "stated": False}}
    elif item_id == "C5.1":
        it["C5.1"] = {"hours": {"accessible": True, "day_by_day": False,
                                "partial": True, "text": "Open weekdays"}}
    elif item_id == "C5.2":
        it["C5.2"] = {"hours_consistency": {"accessible": True,
                                            "conflict": "24-hour claim differs"}}
    elif item_id == "C6.1":
        it["C6.1"] = {"phones": ["(555) 555-0100", "(555) 555-0200"]}
    elif item_id == "C6.2":
        it["C6.2"] = {"founding_years": {"website": 2010, "google": 2005}}
    elif item_id == "G1":
        it["G1"] = {"names": {"website": "Example Heating",
                              "google": "Example Heating & Air"}}
    elif item_id == "C7.1":
        it["C7.1"] = {"robots_txt": {"accessible": True, "exists": True,
                                     "blocked_tokens": ["OAI-SearchBot"]}}
    elif item_id == "C7.2":
        it["C7.2"] = {"initial_html": {"accessible": True,
                                       "missing_facts": ["phone"]}}
    elif item_id == "C7.3":
        it["C7.3"] = {"json_ld": {"accessible": True, "present": False}}
    elif item_id == "C7.4":
        it["C7.4"] = {"sitemap": {"accessible": True, "present": False}}
    else:  # pragma: no cover
        raise KeyError(item_id)


def score_with_failures(fail_ids) -> object:
    ev = all_pass_evidence()
    for iid in fail_ids:
        _fail(ev, iid)
    return score_audit("Example Heating", "AC installation and repair",
                       "Coppell, TX 75019", "2026-11-17", ev, DEFS)


class TestAllocation(unittest.TestCase):
    def test_allocation_v2_totals_100(self):
        self.assertEqual(len(ITEM_POINTS), 21)
        self.assertEqual(sum(ITEM_POINTS.values()), 100)
        self.assertEqual(len(ITEM_CATALOG), 21)
        for cat, pts in CATEGORY_POINTS.items():
            got = sum(ITEM_POINTS[i] for i, (c, _l) in ITEM_CATALOG.items()
                      if c == cat)
            self.assertEqual(got, pts, cat)
        # Anti-aligned Items keep their v2 points (decided 2026-11-16).
        self.assertEqual(ITEM_POINTS["C6.1"], 3)
        self.assertEqual(ITEM_POINTS["G6"], 3)
        self.assertEqual(ITEM_POINTS["C5.2"], 2)
        # C3.2 / C4.1 are not scored Items.
        self.assertNotIn("C3.2", ITEM_POINTS)
        self.assertNotIn("C4.1", ITEM_POINTS)

    def test_all_pass_is_100_A(self):
        r = score_with_failures(())
        self.assertEqual(r.total_points, 100)
        self.assertEqual(r.grade, "A")
        self.assertEqual(r.passed_items, 21)
        self.assertEqual(r.high_issues, 0)
        self.assertEqual(r.spec_version, "2.1")


class TestBands(unittest.TestCase):
    def test_grade_from_points_boundaries(self):
        self.assertEqual(grade_from_points(100), "A")
        self.assertEqual(grade_from_points(65), "A")
        self.assertEqual(grade_from_points(64), "B")
        self.assertEqual(grade_from_points(50), "B")
        self.assertEqual(grade_from_points(49), "C")
        self.assertEqual(grade_from_points(30), "C")
        self.assertEqual(grade_from_points(29), "D")
        self.assertEqual(grade_from_points(0), "D")

    def test_band_edges_via_engine(self):
        # 65 (A): fail 35 points.
        r = score_with_failures(["C1.1", "C1.2", "C2.1", "C2.2", "C2.3"])
        self.assertEqual(r.total_points, 65)
        self.assertEqual(r.grade, "A")
        # 64 (B): fail 36 points.
        r = score_with_failures(["C1.1", "C1.2", "C2.1", "C2.2", "C2.4", "C7.4"])
        self.assertEqual(r.total_points, 64)
        self.assertEqual(r.grade, "B")
        # 50 (B): fail 50 points.
        r = score_with_failures(["C1.1", "C1.2", "C2.1", "C2.2", "C2.3",
                                 "C2.4", "C3.1", "G6", "C7.4"])
        self.assertEqual(r.total_points, 50)
        self.assertEqual(r.grade, "B")
        # 49 (C): fail 51 points.
        r = score_with_failures(["C1.1", "C1.2", "C2.1", "C2.2", "C2.3",
                                 "C2.4", "C3.1", "G6", "C7.1"])
        self.assertEqual(r.total_points, 49)
        self.assertEqual(r.grade, "C")
        # 30 (C): pass only C1.1 + C1.2 + C2.1 + C5.1.
        keep = {"C1.1", "C1.2", "C2.1", "C5.1"}
        r = score_with_failures([i for i in ITEM_POINTS if i not in keep])
        self.assertEqual(r.total_points, 30)
        self.assertEqual(r.grade, "C")
        # 29 (D): pass only C1.1 + C1.2 + C2.1 + C2.3.
        keep = {"C1.1", "C1.2", "C2.1", "C2.3"}
        r = score_with_failures([i for i in ITEM_POINTS if i not in keep])
        self.assertEqual(r.total_points, 29)
        self.assertEqual(r.grade, "D")


class TestRows(unittest.TestCase):
    def test_36_rows_no_gates(self):
        r = score_with_failures(())
        self.assertEqual(len(r.rows), 36)
        types = [x.row_type for x in r.rows]
        self.assertEqual(types.count("Category result"), 7)
        self.assertEqual(types.count("Item"), 21)
        self.assertEqual(types.count("Ranking Suggestion"), 8)
        self.assertEqual(types.count("Gate"), 0)
        self.assertEqual(types.count("Ranking lever"), 0)
        self.assertEqual(types.count("Ranking Lever"), 0)
        # Row order: Items grouped by Category, then Category results,
        # then the six Section 6 Ranking Suggestions, then the two
        # Section 4 Ranking Suggestions (C3.2, C4.1) as rows.
        sugg = [x for x in r.rows if x.row_type == "Ranking Suggestion"]
        self.assertEqual([x.item_id for x in sugg[-2:]], ["C3.2", "C4.1"])
        self.assertEqual(
            {x.item_id: x.result for x in r.section_4_suggestions},
            {x.item_id: x.result for x in sugg[-2:]})
        self.assertEqual([x.item_id for x in r.rows if x.row_type == "Item"],
                         ["C1.1", "C1.2", "C1.3", "C2.1", "C2.2", "C2.3",
                          "C2.4", "C3.1", "G6", "C4.2", "C4.3", "C4.4",
                          "C5.1", "C5.2", "C6.1", "C6.2", "G1",
                          "C7.1", "C7.2", "C7.3", "C7.4"])
        # Category result rows carry points subtotals, not Pass/Fail.
        cat_rows = [x for x in r.rows if x.row_type == "Category result"]
        self.assertEqual(cat_rows[0].result, "22 of 22 points")
        self.assertEqual(cat_rows[0].points, 22)

    def test_item_rows_carry_points(self):
        r = score_with_failures(["C1.2"])
        by_item = {x.item_id: x for x in r.rows if x.row_type == "Item"}
        self.assertEqual(by_item["C1.1"].points, 9)
        self.assertEqual(by_item["C1.1"].points_available, 9)
        self.assertEqual(by_item["C1.2"].points, 0)
        self.assertEqual(by_item["C1.2"].points_available, 9)
        self.assertEqual(r.category_scores["Reputation"], 13)


class TestMinimumCondition(unittest.TestCase):
    def _website_ev(self, **website):
        ev = all_pass_evidence()
        ev["website"] = website
        return ev

    def test_firm_side_dead_is_F(self):
        ev = self._website_ev(unreadable=True, reason="DEAD", readable=False,
                              has_website=True)
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        self.assertEqual(r.grade, "F")
        self.assertEqual(r.f_reason, "DEAD")
        self.assertEqual(r.total_points, 0)
        self.assertEqual(len(r.rows), 36)
        self.assertTrue(all(x.result == "Not accessible"
                            for x in r.rows if x.row_type == "Item"))
        self.assertEqual(r.high_issues, 0)  # no Items are scored for an F firm
        # The two Section 4 Ranking Suggestions are rows too, Not checked.
        sugg = [x for x in r.rows if x.row_type == "Ranking Suggestion"]
        self.assertEqual(len(sugg), 8)
        self.assertTrue(all(x.result == "Not checked" for x in sugg))
        self.assertEqual([x.item_id for x in sugg[-2:]], ["C3.2", "C4.1"])

    def test_no_website_is_F(self):
        ev = self._website_ev(unreadable=False, reason="", readable=False,
                              has_website=False)
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        self.assertEqual(r.grade, "F")
        self.assertEqual(r.f_reason, "NO-WEBSITE")

    def test_closed_is_never_an_F_reason(self):
        # Spec v2.13 s.5: a closed firm is not audited (the runner skips it);
        # closure is no longer an F reason in the engine.
        ev = self._website_ev(unreadable=False, reason="", readable=True,
                              has_website=True, closed_permanently=True,
                              closed_flag="permanently closed (Meta listing)")
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        self.assertNotEqual(r.f_reason, "NOT-IN-BUSINESS")

    def test_temporarily_closed_is_not_F(self):
        ev = self._website_ev(unreadable=False, reason="", readable=True,
                              has_website=True, closed_permanently=False,
                              closed_flag="temporarily closed (Meta listing)")
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        self.assertEqual(r.grade, "A")
        self.assertEqual(r.total_points, 100)

    def test_proxy_refused_is_unverified_not_F(self):
        ev = self._website_ev(unreadable=True, reason="PROXY-REFUSED",
                              readable=False, has_website=True)
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        self.assertEqual(r.grade, "")  # no grade assigned
        self.assertTrue(r.unverified)
        self.assertEqual(r.unverified_reason, "PROXY-REFUSED")
        self.assertEqual(r.total_points, 0)
        self.assertEqual(len(r.rows), 36)

    def test_blocked_unreadable_is_unverified_not_F(self):
        ev = self._website_ev(unreadable=True, reason="BLOCKED", readable=False,
                              has_website=True)
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        self.assertEqual(r.grade, "")
        self.assertTrue(r.unverified)

    def test_no_readable_text_render_undecided_is_unverified(self):
        ev = self._website_ev(unreadable=False, reason="", readable=False,
                              has_website=True)
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        self.assertEqual(r.grade, "")
        self.assertTrue(r.unverified)


class TestItemRules(unittest.TestCase):
    def test_norm_text_ac_loosening(self):
        self.assertEqual(norm_text("Texas A/C Pro"), norm_text("Texas AC Pro"))
        self.assertEqual(norm_text("A.C. Pro"), norm_text("AC Pro"))
        self.assertEqual(norm_text("A/C Heating & Air"), norm_text("AC Heating and Air"))
        # A real-word difference still fails.
        self.assertNotEqual(norm_text("Texas A/C Pro"),
                            norm_text("Texas A/C Repair"))
        self.assertNotEqual(norm_text("Example Heating"),
                            norm_text("Example Heating & Air"))
        # Trailing legal suffixes still ignored.
        self.assertEqual(norm_text("Example Heating LLC"),
                         norm_text("Example Heating"))

    def test_g1_ac_loosening_passes(self):
        ev = all_pass_evidence()
        ev["items"]["G1"] = {"names": {"website": "Texas A/C Pro",
                                       "google": "Texas AC Pro"}}
        r = score_audit("Texas A/C Pro", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        by_item = {x.item_id: x for x in r.rows if x.row_type == "Item"}
        self.assertEqual(by_item["G1"].result, "Pass")
        self.assertEqual(by_item["G1"].points, 6)

    def test_g1_real_word_difference_fails(self):
        r = score_with_failures(["G1"])
        by_item = {x.item_id: x for x in r.rows if x.row_type == "Item"}
        self.assertEqual(by_item["G1"].result, "Missing")
        self.assertEqual(by_item["G1"].points, 0)
        self.assertEqual(r.total_points, 94)

    def test_g6_is_scored_item(self):
        r = score_with_failures(["G6"])
        by_item = {x.item_id: x for x in r.rows if x.row_type == "Item"}
        self.assertEqual(by_item["G6"].result, "Missing")
        self.assertEqual(by_item["G6"].points_available, 3)
        self.assertEqual(r.total_points, 97)
        self.assertEqual(r.category_scores["Credentials and Trust"], 7)

    def test_c22_service_page_only(self):
        # No listing evidence at all: C2.2 still passes on the service page.
        ev = all_pass_evidence()
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        by_item = {x.item_id: x for x in r.rows if x.row_type == "Item"}
        self.assertEqual(by_item["C2.2"].result, "Pass")

    def test_c51_24h_claim_passes_without_day_by_day(self):
        ev = all_pass_evidence()
        ev["items"]["C5.1"] = {"hours": {"accessible": True, "day_by_day": False,
                                         "partial": False, "text": "",
                                         "emergency_claim_verified": True,
                                         "emergency_claim": "24/7 emergency service"}}
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        by_item = {x.item_id: x for x in r.rows if x.row_type == "Item"}
        self.assertEqual(by_item["C5.1"].result, "Pass")
        self.assertEqual(by_item["C5.1"].points, 5)

    def test_c71_training_only_block_passes(self):
        ev = all_pass_evidence()
        ev["items"]["C7.1"] = {"robots_txt": {"accessible": True, "exists": True,
                                              "blocked_tokens": ["GPTBot", "Meta-ExternalAgent"]}}
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        by_item = {x.item_id: x for x in r.rows if x.row_type == "Item"}
        self.assertEqual(by_item["C7.1"].result, "Pass")


class TestSection4Suggestions(unittest.TestCase):
    def test_c32_c41_are_suggestion_rows_not_items(self):
        r = score_with_failures(())
        self.assertNotIn("C3.2", [x.item_id for x in r.rows
                                  if x.row_type == "Item"])
        self.assertNotIn("C4.1", [x.item_id for x in r.rows
                                  if x.row_type == "Item"])
        # ... but they ARE Ranking Suggestion rows (since Tim's decision
        # 2026-11-18, decision 10), with the code-plus-description labels
        # from Sample Audit Data Rev 4.
        sugg = {x.item_id: x for x in r.rows
                if x.row_type == "Ranking Suggestion"}
        self.assertEqual(sugg["C3.2"].label,
                         "C3.2 BBB accreditation and rating consistent with bbb.org")
        self.assertEqual(sugg["C4.1"].label, "C4.1 six-line warranty card")
        got = {x.item_id: x.result for x in r.section_4_suggestions}
        self.assertEqual(got, {"C3.2": "Complete", "C4.1": "Complete"})
        for row in r.section_4_suggestions:
            self.assertEqual(row.row_type, "Ranking Suggestion")
            self.assertEqual(row.points, 0)
            self.assertEqual(row.points_available, 0)

    def test_c32_c41_status_mapping(self):
        ev = all_pass_evidence()
        ev["items"]["C3.2"] = {"bbb": {"claim": "A+ accredited",
                                       "bbb_org_accessible": True,
                                       "consistent": False,
                                       "bbb_org": "B, not accredited"}}
        ev["items"]["C4.1"] = {"warranty": {"accessible": True, "lines": {
            "new_parts": True, "new_labour": True, "repair_parts_labour": False,
            "registration": False, "transferable": False, "claim_line": False}}}
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        got = {x.item_id: x.result for x in r.section_4_suggestions}
        self.assertEqual(got, {"C3.2": "Suggested",
                               "C4.1": "Suggested"})
        # ... and they cost no points either way.
        self.assertEqual(r.total_points, 100)

    def test_c32_not_checked_when_bbb_unreadable(self):
        ev = all_pass_evidence()
        ev["items"]["C3.2"] = {"bbb": {"claim": "A+ accredited",
                                       "bbb_org_accessible": False,
                                       "reason": "not independently read on bbb.org"}}
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        got = {x.item_id: x.result for x in r.section_4_suggestions}
        self.assertEqual(got["C3.2"], "Not checked")

    def test_c32_complete_needs_accreditation(self):
        # Spec s.4.3 rule 8 (decided by Tim 2026-11-18): C3.2 BBB
        # accreditation and rating consistent with bbb.org is Complete
        # only if the firm is BBB accredited AND its rating on bbb.org is
        # consistent. A matching rating with accreditation not confirmed
        # on bbb.org is Suggested, not Complete — a firm's own claim
        # alone is never Complete.
        ev = all_pass_evidence()
        ev["items"]["C3.2"] = {"bbb": {"claim": "A+ accredited",
                                       "bbb_org_accessible": True,
                                       "accredited": False,
                                       "consistent": True,
                                       "bbb_org": "A+ rating, not accredited"}}
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        got = {x.item_id: x.result for x in r.section_4_suggestions}
        self.assertEqual(got["C3.2"], "Suggested")
        # ... and a rating match with accreditation simply not stated in
        # the evidence is Suggested too: Complete needs the positive
        # accreditation fact, not the absence of a contradiction.
        ev["items"]["C3.2"] = {"bbb": {"claim": "A+ accredited",
                                       "bbb_org_accessible": True,
                                       "consistent": True}}
        r = score_audit("Example", "AC installation and repair",
                        "Coppell, TX 75019", "2026-11-17", ev, DEFS)
        got = {x.item_id: x.result for x in r.section_4_suggestions}
        self.assertEqual(got["C3.2"], "Suggested")


if __name__ == "__main__":
    unittest.main(verbosity=2)
