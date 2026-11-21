import json, sys
sys.path.insert(0, '/home/hatch/workspace/goals/score-card-audit-product/files/aisharc-harness-v2')
from aisharc_harness.rules.engine import score_audit, load_definitions

defs = load_definitions()

# Evidence constructed to reproduce the dummy Final Rev 6 (Example Heating &
# Air Conditioning), re-scored under Spec v2.1: 74/100, Grade A, 5 failed
# scored Items, 16 passed. Spec s.11: as it stands the dummy scores 74,
# Grade A, because C3.2 BBB accreditation and rating consistent with
# bbb.org and C4.1 six-line warranty card no longer score and it passes
# G1 exact name and G6 verifiable listing as Items. (The dummy card rebuild
# to Grade C is card work, not a harness change.)
ev = {
  "website": {"unreadable": False, "readable": True, "has_website": True},
  "items": {
    "C1.1": {"rating_platforms": {"google": {"rating": 4.6, "count": 1234, "accessible": True}}},
    "C1.2": {"website_rating": {"rating": 4.9, "count": None}, "rating_platforms": {"google": {"rating": 4.6, "count": 1234, "accessible": True}}},
    "C1.3": {"reviews": {"accessible": True}},
    "C2.1": {"town": "Example Town", "zip": "75000", "service_area_page": {"accessible": True, "names_town_zip": True}},
    "C2.2": {"service_area_page": {"accessible": True, "install_repair_separate": True}},
    "C2.3": {"service_area_page": {"accessible": True, "brands_listed": True}},
    "C2.4": {"service_area_page": {"accessible": True, "phone_and_booking": True}},
    "C3.1": {"licence": {"published": True, "number": "TACLB00012345E", "register": {"accessible": True, "active": True}}},
    "G6": {"listings_checked": ["google"], "matching_listing": {"source": "google", "name": "Example Heating & Air Conditioning"}},
    # C3.2 / C4.1 are Section 4 Ranking Suggestions in v2.1 (not scored,
    # but Audit Data rows, seq 35-36); their evidence is still read for
    # the suggestion status.
    "C3.2": {"bbb": {"claim": "A+ accredited", "bbb_org_accessible": True, "consistent": False, "bbb_org": "B, not accredited"}},
    "C4.1": {"warranty": {"accessible": True, "lines": {"new_parts": True, "new_labour": True, "repair_parts_labour": False, "registration": False, "transferable": False, "claim_line": False}}},
    "C4.2": {"diagnostic_fee": {"accessible": True}},
    "C4.3": {"free_estimate_install": {"accessible": True, "stated": True, "text": "Free estimates on installs"}},
    "C4.4": {"free_estimate_repair": {"accessible": True, "stated": True, "text": "Free estimates on repairs"}},
    "C5.1": {"hours": {"accessible": True, "day_by_day": True, "text": "Mon-Fri 8-5, Sat 9-1"}},
    "C5.2": {"hours_consistency": {"accessible": True}},
    "C6.1": {"phones": ["(555) 555-0100"]},
    "C6.2": {"founding_years": {"website": 2010, "google": 2010}},
    "G1": {"names": {"website": "Example Heating & Air Conditioning", "google": "Example Heating & Air Conditioning", "meta": "Example Heating & Air Conditioning"}},
    "C7.1": {"robots_txt": {"accessible": True, "exists": True, "blocked_tokens": []}},
    "C7.2": {"initial_html": {"accessible": True, "missing_facts": ["phone", "service area"]}},
    "C7.3": {"json_ld": {"accessible": True, "present": False}},
    "C7.4": {"sitemap": {"accessible": True, "present": False, "checked_url": "https://example.com/sitemap.xml"}},
  },
  "levers": {
    "booking_route": {"accessible": True, "route": "form", "next_step": "call within 1 hour", "written_quote": "quote in writing before work"},
    "availability": {"accessible": True},
    "price": {"accessible": True},
    "brand_coverage": {"accessible": True, "brands_listed": "Trane, Carrier"},
    "dispatch": {"accessible": True},
    "llms_txt": {"accessible": True},
  },
}
r1 = score_audit("Example Heating & Air Conditioning", "AC installation and repair", "Example Town, TX 75000", "2026-11-03", ev, defs)
r2 = score_audit("Example Heating & Air Conditioning", "AC installation and repair", "Example Town, TX 75000", "2026-11-03", ev, defs)
print("grade:", r1.grade, "| points:", r1.total_points, "/100 | high:", r1.high_issues, "| passed items:", r1.passed_items, "| spec_version:", r1.spec_version)
print("category scores:", r1.category_scores)
print("category results:", r1.category_results)
print("failed items:", [(x.item_id, x.result, x.points, x.points_available) for x in r1.rows if x.row_type == 'Item' and x.result in ('Missing','Conflict','Not accessible')])
print("section 4 suggestions:", [(x.item_id, x.result) for x in r1.section_4_suggestions])
print("row counts:", len(r1.rows), "| gates:", sum(1 for x in r1.rows if x.row_type=='Gate'), "| cat:", sum(1 for x in r1.rows if x.row_type=='Category result'), "| items:", sum(1 for x in r1.rows if x.row_type=='Item'), "| suggestions:", sum(1 for x in r1.rows if x.row_type=='Ranking Suggestion'))
print("determinism (r1 == r2):", json.dumps(r1.as_dict(), sort_keys=True) == json.dumps(r2.as_dict(), sort_keys=True))
print("vocabulary check — item results used:", sorted({x.result for x in r1.rows if x.row_type=='Item'}))
print("vocabulary check — suggestion results used:", sorted({x.result for x in r1.rows if x.row_type=='Ranking Suggestion'}))
assert r1.spec_version == "2.1", "SPEC_VERSION MUST BE 2.1 (Spec s.13, amended 2026-11-18)"
assert r1.grade == "A" and r1.total_points == 74 and r1.high_issues == 5 and r1.passed_items == 16, "DUMMY MISMATCH"
assert len(r1.rows) == 36
assert sum(1 for x in r1.rows if x.row_type == 'Gate') == 0, "no Gate rows in v2.1"
assert sum(1 for x in r1.rows if x.row_type == 'Ranking Suggestion') == 8, "8 Ranking Suggestion rows (6 Section 6 + C3.2, C4.1)"
assert r1.category_scores == {"Reputation": 13, "Area Coverage": 20, "Credentials and Trust": 10, "Pricing and Warranty": 6, "Hours and Active Status": 7, "Identity and Contact": 15, "Machine Readability": 3}, r1.category_scores
assert {x.item_id: x.result for x in r1.section_4_suggestions} == {"C3.2": "Suggested", "C4.1": "Suggested"}
print("DUMMY VALIDATION PASSED: 74/100, Grade A, 5 High — matches Spec s.11")
