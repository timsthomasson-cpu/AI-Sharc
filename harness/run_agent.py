#!/usr/bin/env python3
"""AI Sharc harness — MUSE-SPARK agent run step (Spec v1.22, Design Rev 9).

One MUSE-SPARK call per (query, town) — the standard shopping task — then
the LLM-assisted scorer scores each named cohort firm from the saved
answer. Writes the run-level agent files and one muse-observation.json
per firm into runs/<date>/<firm_id>/.

Usage:
  python3 run_agent.py --validate-scorer
      Score the saved run 1 answer and check it against the manual record.
  python3 run_agent.py --run [--out-dir runs/2026-11-13] [--no-agent-call]
      Make the agent call (unless --no-agent-call, which reuses an existing
      muse-spark-response.json), score the named firms, write the outputs.

The agent call uses the connector helper (muse_spark.py) as a subprocess —
the connector's own code path, so no key is handled here. The scorer uses
the same registered connection via the dynamic-credentials surrogate
(scorer.call_model_no_tools). No key, token, or surrogate is ever written
to an output file.

The observation NEVER changes the AI Sharc grade (Design §9.3).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from aisharc_harness.agent import muse_api, scorer as SC
from aisharc_harness.rules.engine import load_definitions

RUN_DATE = "2026-11-13"
SPEC_VERSION = "1.22"
QUERY = "AC installation and repair"
TOWN = "Coppell"
ZIP = "75019"
TOWN_ZIP = "Coppell, TX 75019"
PRIMARY_CATEGORY = "HVAC Contractor"

HELPER = os.path.expanduser(
    "~/workspace/custom-connectors/custom.meta-model-api/bin/muse_spark.py")

# Distinctive short names for matching a cohort firm in the agent's answer.
# Normalised (lowercase, punctuation stripped) substring match on the
# answer text. A firm is "named" when its short name appears.
SHORT_NAMES = {
    "airtron": "airtron",
    "matco": "matco",
    "cold-factor": "cold factor",
    "graco": "graco",
    "erics": "eric",
    "air-rescue": "air rescue",
    "coppell-heating": "coppell heating",
    "dfw-hvac": "dfw hvac",
    "a1-air": "a1 air",
    "dring": "dring",
    "royal-comfort": "royal comfort",
    "first-cooling": "first cooling",
    "united-team": "united team",
    "jc-heating": "jc heating",
    "berkeys": "berkeys",
    "southern-comfort": "southern comfort",
    "gold-ac": "gold ac",
    "comfort-land": "comfort land",
    "air-repair-pros": "air repair pros",
}


def norm(s: str) -> str:
    # "&" vs "and" is not a name difference (engine norm_text rule).
    return re.sub(r"[^a-z0-9 ]", " ",
                  (s or "").lower().replace("&", " and ")).strip()


def norm_compact(s: str) -> str:
    return re.sub(r"\s+", " ", norm(s)).strip()


def agent_call(out_path: str) -> dict:
    """Make the one standard-question agent call via the connector helper.
    Saves the raw Responses API JSON verbatim. Returns the body."""
    question = muse_api.standard_question(service="HVAC", town=TOWN,
                                          zip_code=ZIP,
                                          need="AC installation and repair")
    proc = subprocess.run(
        [sys.executable, HELPER, "--question", question,
         "--town", TOWN, "--zip", ZIP, "--out", out_path],
        capture_output=True, text=True, timeout=400)
    if proc.returncode != 0:
        raise RuntimeError("agent call failed: %s" % proc.stderr.strip()[:2000])
    with open(out_path, encoding="utf-8") as fh:
        return json.load(fh)


def extract_run_meta(body: dict, out_dir: str) -> dict:
    """Run-level observation metadata from the Responses API body."""
    obs = muse_api._extract_observation(body)
    searches = obs["web_search_calls"]
    n_results = sum(len(s.get("results") or []) for s in searches)
    distinct = []
    for c in obs["citations"]:
        if c.get("url") and c["url"] not in distinct:
            distinct.append(c["url"])
    cost = SC.cost_from_usage(body, web_searches=len(searches))
    return {
        "audit_id": "MUSE-SPARK",
        "agent_label": "MUSE-SPARK",
        "query": QUERY,
        "town_zip": TOWN_ZIP,
        "date_checked": RUN_DATE,
        "spec_version": SPEC_VERSION,
        "primary_business_category": PRIMARY_CATEGORY,
        "model": body.get("model", muse_api.MODEL),
        "tools": ["web_search"],
        "surface_tested": muse_api.SURFACE,
        "transcript_ref": os.path.join(out_dir, "muse-spark-response.json"),
        "response_id": body.get("id"),
        "web_search_calls": len(searches),
        "web_search_results": n_results,
        "url_citation_count": len(obs["citations"]),
        "distinct_urls": distinct,
        "cost_usd": cost,
        "usage": body.get("usage") or {},
        "answer_text": obs["answer_text"],
        "citations": obs["citations"],
        "searched": obs["searched"],
    }


def named_firms(answer_text: str, firms: list) -> tuple:
    """Which cohort firms the answer named (short-name match), and the
    firm headings the answer gave that are NOT in the cohort (discovery
    leads, from the answer's '### N. Name' headings)."""
    flat = norm_compact(answer_text)
    named = []
    for firm in firms:
        short = SHORT_NAMES.get(firm["firm_id"], norm_compact(firm["name"]))
        # Word-boundary match: "eric" must not match inside "generic".
        if short and re.search(r"\b" + re.escape(short) + r"\b", flat):
            named.append(firm)
    cohort_names = {norm_compact(f["name"]) for f in firms}
    headings = re.findall(r"^#{1,3}\s*\d+\.?\s*(.+)$", answer_text, re.M)
    new_firms = []
    for h in headings:
        # Strip the descriptive suffix (" - Only firm physically in
        # 75019") and any alternate spelling ("Airmatics / AirMatics").
        name = h.strip().split(" - ")[0].split(" / ")[0].strip()
        if not name:
            continue
        n = norm_compact(name)
        if n and not any(n.startswith(cn) or cn.startswith(n)
                         for cn in cohort_names):
            # Skip generic headings (comparison tables, next steps).
            if any(k in n for k in ("comparison", "next step", "quick")):
                continue
            new_firms.append(name)
    return named, new_firms


def run_agent(out_dir: str, agent_call_needed: bool = True) -> dict:
    """The agent step: one call, then score each named cohort firm, then
    write the run-level files and one muse-observation.json per firm."""
    defs = load_definitions()
    with open(os.path.join(HERE, "firms.json"), encoding="utf-8") as fh:
        firms = json.load(fh)["firms"]
    os.makedirs(out_dir, exist_ok=True)
    response_path = os.path.join(out_dir, "muse-spark-response.json")
    if agent_call_needed:
        print("== agent call (one standard question, %s) ==" % TOWN_ZIP)
        body = agent_call(response_path)
    else:
        with open(response_path, encoding="utf-8") as fh:
            body = json.load(fh)
        print("== reusing saved agent response %s ==" % body.get("id"))
    meta = extract_run_meta(body, out_dir)
    print("response %s: %d web_search calls, %d results, %d citations, "
          "%d distinct URLs, cost $%.4f"
          % (meta["response_id"], meta["web_search_calls"],
             meta["web_search_results"], meta["url_citation_count"],
             len(meta["distinct_urls"]), meta["cost_usd"]))
    answer = meta["answer_text"]
    named, new_firms = named_firms(answer, firms)
    print("named cohort firms (%d of %d): %s"
          % (len(named), len(firms), ", ".join(f["name"] for f in named)))
    print("named, not in cohort: %s" % (new_firms or "none"))

    run_meta = {
        "primary_business_category": PRIMARY_CATEGORY,
        "query": QUERY,
        "town_zip": TOWN_ZIP,
        "date_checked": RUN_DATE,
        "model": meta["model"],
        "transcript_ref": meta["transcript_ref"],
        "response_id": meta["response_id"],
        "web_search_calls": meta["web_search_calls"],
        "web_search_results": meta["web_search_results"],
        "url_citation_count": meta["url_citation_count"],
        "distinct_urls": meta["distinct_urls"],
        "cost_usd": meta["cost_usd"],
    }
    named_ids = {f["firm_id"] for f in named}
    observations = {}
    scorer_total = 0.0
    for firm in firms:
        is_named = firm["firm_id"] in named_ids
        if is_named:
            print("== scoring %s ==" % firm["name"])
            scored = SC.score_firm(answer, meta["citations"], firm["name"], defs)
            scorer_total += scored.get("scorer_cost_usd") or 0.0
            if scored.get("scorer_corrections"):
                print("  scorer corrections: %s" % scored["scorer_corrections"])
            passed = [e["item_id"] for e in scored["items"]
                      if e["result"] == "Pass"]
            print("  Items Pass (%d): %s" % (len(passed), ", ".join(passed) or "none"))
        else:
            scored = None
        obs = SC.build_observation(firm, scored, run_meta, defs, is_named)
        observations[firm["firm_id"]] = obs
        firm_dir = os.path.join(out_dir, firm["firm_id"])
        os.makedirs(firm_dir, exist_ok=True)
        with open(os.path.join(firm_dir, "muse-observation.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(obs, fh, indent=2, sort_keys=False)

    run_obs = dict(meta)
    run_obs["firms_named"] = [f["name"] for f in named]
    run_obs["firms_not_named"] = [f["name"] for f in firms
                                  if f["firm_id"] not in named_ids]
    run_obs["firms_named_not_in_cohort"] = new_firms
    run_obs["scorer_total_cost_usd"] = round(scorer_total, 4)
    run_obs["total_cost_usd"] = round(meta["cost_usd"] + scorer_total, 4)
    with open(os.path.join(out_dir, "muse-spark-observation.json"),
              "w", encoding="utf-8") as fh:
        json.dump(run_obs, fh, indent=2, sort_keys=False)
    print("agent call cost $%.4f + scorer calls $%.4f = total $%.4f"
          % (meta["cost_usd"], scorer_total, run_obs["total_cost_usd"]))
    return run_obs


def main() -> None:
    parser = argparse.ArgumentParser(description="MUSE-SPARK agent run step")
    parser.add_argument("--validate-scorer", action="store_true",
                        help="score the saved run 1 answer and check it "
                        "against the manual record")
    parser.add_argument("--run", action="store_true",
                        help="make the agent call and score the firms")
    parser.add_argument("--out-dir", default="",
                        help="output root (default runs/<RUN_DATE>)")
    parser.add_argument("--no-agent-call", action="store_true",
                        help="reuse an existing muse-spark-response.json "
                        "in the output dir instead of calling the API")
    args = parser.parse_args()
    if args.validate_scorer:
        import subprocess as sp
        proc = sp.run([sys.executable, "tests/test_scorer_run1.py"],
                      capture_output=True, text=True, cwd=HERE)
        print(proc.stdout)
        if proc.returncode != 0:
            print(proc.stderr)
        sys.exit(proc.returncode)
    if args.run:
        out_dir = args.out_dir or os.path.join(HERE, "runs", RUN_DATE)
        run_agent(out_dir, agent_call_needed=not args.no_agent_call)
        return
    parser.print_help()
    sys.exit(2)


if __name__ == "__main__":
    main()
