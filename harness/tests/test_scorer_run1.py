#!/usr/bin/env python3
"""Scorer validation against the manual MUSE-SPARK run 1 record.

Runs the LLM scorer on the SAVED run 1 answer (agent-validation/
MUSE-SPARK response — 2026-11-11 — run 1.json) for the four firms the
model named, and checks it reproduces the manual scoring exactly.

Manual record: agent-validation/MUSE-SPARK observation — 2026-11-11 —
run 1.md — 9 Items Pass, 12 Not observed (aggregate, across the four
named firms). The per-firm decomposition below is derived from that
record's stated evidence (which firm each Pass is attributed to):

- Coppell Heating: C2.2 (install/repair separate bullets), C2.4 (phone +
  online estimate form), C6.2 (founded 1983).
- Airmatics: C2.2 (separate bullets), C2.4 (phone), C5.1 (day-by-day
  hours Mon-Sun 00:00-24:00), C6.2 (in Coppell since 2016).
- Eric's: C1.1 (5.0 stars, 81+ Google), C2.2, C2.3 (mini-splits),
  C2.4 (phone), C3.1 (TACLA87910C), C4.2 ($79 diagnostic).
- Quigley: C1.1 (4.9/5 Google), C2.2, C2.3 (Lennox/Trane), C2.4 (phone),
  C3.1 (TACLA23686E), C3.2 (BBB A+), C6.2 (since 1945).

Hard gates (exit non-zero if any fails):
  1. The union of per-firm Passes is exactly the 9 manual Passes.
  2. No firm Passes any of the 12 Items the manual record says are
     Not observed.
  3. Every per-firm Pass set matches the decomposition above.
If the scorer cannot reproduce run 1, the scorer is wrong — the manual
record is never adjusted and the scorer is never fudged to match it.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from aisharc_harness.agent import muse_api, scorer as SC
from aisharc_harness.rules.engine import load_definitions

RUN1_RESPONSE = os.path.expanduser(
    "~/workspace/goals/score-card-audit-product/files/agent-validation/"
    "MUSE-SPARK response — 2026-11-11 — run 1.json")

MANUAL_PASS = {"C1.1", "C2.2", "C2.3", "C2.4", "C3.1", "C3.2",
               "C4.2", "C5.1", "C6.2"}
MANUAL_NOT_OBSERVED = {"C1.2", "C1.3", "C2.1", "C4.1", "C4.3", "C4.4",
                       "C5.2", "C6.1", "C7.1", "C7.2", "C7.3", "C7.4"}

EXPECTED_PER_FIRM = {
    "Coppell Heating and Air Conditioning": {"C2.2", "C2.4", "C6.2"},
    "Airmatics": {"C2.2", "C2.4", "C5.1", "C6.2"},
    "Eric's Home Services": {"C1.1", "C2.2", "C2.3", "C2.4", "C3.1", "C4.2"},
    "Quigley Heating & Air": {"C1.1", "C2.2", "C2.3", "C2.4", "C3.1",
                              "C3.2", "C6.2"},
}


def main() -> int:
    defs = load_definitions()
    with open(RUN1_RESPONSE, encoding="utf-8") as fh:
        body = json.load(fh)
    obs = muse_api._extract_observation(body)
    answer, citations = obs["answer_text"], obs["citations"]
    print("run 1 answer: %d chars, %d citations, response %s"
          % (len(answer), len(citations), body.get("id")))

    ok = True
    per_firm = {}
    total_cost = 0.0
    for firm_name, expected in EXPECTED_PER_FIRM.items():
        print("== scoring %s ==" % firm_name)
        scored = SC.score_firm(answer, citations, firm_name, defs)
        total_cost += scored.get("scorer_cost_usd") or 0.0
        got = {e["item_id"] for e in scored["items"]
               if e["result"] == "Pass"}
        per_firm[firm_name] = got
        print("  Pass (%d): %s" % (len(got), ", ".join(sorted(got)) or "none"))
        print("  expected (%d): %s" % (len(expected), ", ".join(sorted(expected))))
        if scored.get("scorer_corrections"):
            print("  scorer corrections: %s" % scored["scorer_corrections"])
        # Every Pass must carry exact wording + a cited source (code-enforced).
        for e in scored["items"]:
            if e["result"] == "Pass" and (not e.get("exact_wording")
                                          or not e.get("cited_source")):
                print("  FAIL: %s Pass without wording/source" % e["item_id"])
                ok = False
        if got != expected:
            print("  DIVERGENCE: missing %s; extra %s"
                  % (sorted(expected - got), sorted(got - expected)))
            ok = False

    union = set().union(*per_firm.values()) if per_firm else set()
    print("== aggregate ==")
    print("  union of Passes (%d): %s" % (len(union), ", ".join(sorted(union))))
    print("  manual Passes   (%d): %s" % (len(MANUAL_PASS), ", ".join(sorted(MANUAL_PASS))))
    if union != MANUAL_PASS:
        print("  FAIL: aggregate Pass set differs from the manual record")
        ok = False
    bad = union & MANUAL_NOT_OBSERVED
    if bad:
        print("  FAIL: scorer Passed Items the manual record says are "
              "Not observed: %s" % sorted(bad))
        ok = False
    print("scorer calls cost: $%.4f" % total_cost)
    print("SCORER VALIDATION %s" % ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
