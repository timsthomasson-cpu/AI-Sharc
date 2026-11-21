"""AI Sharc observation scorer — LLM-assisted scoring of a MUSE-SPARK answer.

Scores one named firm against the 21 Items and 6 Levers from
definitions.json, using ONLY the agent's saved answer text and the sources
it cited. The scorer never searches the web and never uses outside
knowledge: the call is a plain Responses API call with NO tools, so the
model can only judge what the answer demonstrates.

Hard rules (Design Rev 9 §2.5, Spec §4.3):
- A Pass/Fail requires the agent's exact wording AND a cited source URL.
  Without either, the result is Not observed with the reason recorded.
- A cited source must be one of the answer's url_citation URLs.
- An omission is Not observed, never a Fail.
- Gates are Not observed by rule (a shopping answer is not a Gate check:
  Gates require the auditor's cross-source verification, which the answer
  does not perform — the manual run 1 record's treatment).
- Category results are derived in code from the Item results, never by
  the scorer model.

The API key is never handled here: the call uses the registered
custom.meta-model-api connection via the dynamic-credentials surrogate,
exactly as the connector helper does. No key, token, or surrogate is
ever written to an output file.

Pricing (official): Muse Spark standard $1.25 / 1M input tokens,
$4.25 / 1M output tokens; web search $2.50 / 1,000 queries (not used by
the scorer — no tools). Cost is computed from the response usage and
recorded per call.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from typing import Any, Dict, List, Optional

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

API_URL = "https://api.meta.ai/v1/responses"
MODEL = "muse-spark-1.3"
CONNECTION = "custom.meta-model-api"
ALLOWED_HOSTS = ["api.meta.ai"]

INPUT_PER_M = 1.25    # USD per 1M input tokens
OUTPUT_PER_M = 4.25   # USD per 1M output tokens
SEARCH_PER_1000 = 2.50  # USD per 1,000 web_search queries

ITEM_RESULTS = ("Pass", "Fail", "Not observed", "Not completed")
LEVER_RESULTS = ("Observed", "Recommendation", "Not checked")

# Gates are Not observed by rule. Reasons from the manual run 1 record
# (agent-validation/MUSE-SPARK observation — 2026-11-11 — run 1.md).
GATE_REASONS = {
    "exact_name": "Model quoted names but did not verify name consistency across sources.",
    "services_plain": "Model listed services in its own words, not verified against the firms' service pages as Gate criteria.",
    "area_critical": "Model asserted ZIP 75019 served but did not verify a service-area page against the Gate criteria.",
    "contact_critical": "Model quoted one phone per firm and a booking route but did not verify a unique primary phone across sources.",
    "hours_critical": "Model quoted 24/7 emergency for several firms but did not verify hours against the Gate criteria.",
    "verifiable_listing": "Model cited listings/pages but did not verify a listing against the Gate criteria (name, phone, service area, Primary Business Category).",
}

CATEGORY_ORDER = [
    "Reputation", "Area Coverage", "Credentials and Trust",
    "Pricing and Warranty", "Hours and Active Status",
    "Identity and Contact", "Machine Readability",
]

ITEM_ORDER = ["C1.1", "C1.2", "C1.3", "C2.1", "C2.2", "C2.3", "C2.4",
              "C3.1", "C3.2", "C4.1", "C4.2", "C4.3", "C4.4", "C5.1",
              "C5.2", "C6.1", "C6.2", "C7.1", "C7.2", "C7.3", "C7.4"]
GATE_ORDER = ["G1", "G2", "G3", "G4", "G5", "G6"]
LEVER_ORDER = ["booking_route", "availability", "price", "brand_coverage",
               "dispatch", "llms_txt"]


def items_list(definitions) -> List[Dict[str, Any]]:
    """The 21 Items in C-order, from a Definitions object."""
    return [definitions.items[i] for i in ITEM_ORDER]


def gates_list(definitions) -> List[Dict[str, Any]]:
    """The 6 Gates in G-order, each with its G-id and snake_case id."""
    out = []
    for gid in GATE_ORDER:
        entry = dict(definitions.gates[gid])
        entry["gate_id"] = gid
        out.append(entry)
    return out


def levers_list(definitions) -> List[Dict[str, Any]]:
    """The 6 Levers in definitions order, from a Definitions object."""
    return [definitions.levers[i] for i in LEVER_ORDER]


def cost_from_usage(body: Dict[str, Any], web_searches: int = 0) -> float:
    """USD cost of a Responses API body at the official rates. Cached input
    tokens are counted at the standard input rate (conservative: no
    published cached-token rate is available)."""
    usage = body.get("usage") or {}
    in_tok = usage.get("input_tokens") or 0
    out_tok = usage.get("output_tokens") or 0
    return round(in_tok / 1_000_000 * INPUT_PER_M
                 + out_tok / 1_000_000 * OUTPUT_PER_M
                 + web_searches / 1000 * SEARCH_PER_1000, 4)


def call_model_no_tools(prompt: str, timeout: int = 300) -> Dict[str, Any]:
    """Plain Responses API call with NO tools. Returns the full body.
    The model judges only the prompt it is given — it cannot search."""
    payload = {"model": MODEL, "input": prompt}
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    add_surrogate_to_request(request, CONNECTION,
                             allowed_hosts=ALLOWED_HOSTS)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            raise RuntimeError("redirect refused, verify the endpoint")

    try:
        with urllib.request.build_opener(NoRedirect()).open(
                request, timeout=timeout) as response:
            body = read_json_response(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Meta Model API HTTP %d: %s" % (
            exc.code, exc.read().decode("utf-8", errors="replace")[:2000]))
    return body


def answer_text_from_body(body: Dict[str, Any]) -> str:
    """The answer text from a Responses API body (output_text parts)."""
    texts: List[str] = []
    for item in body.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for part in item.get("content", []) or []:
                if isinstance(part, dict) and part.get("type") == "output_text":
                    texts.append(part.get("text", ""))
    return "\n".join(texts)


def build_scorer_prompt(answer_text: str, citations: List[Dict[str, Any]],
                        firm_name: str, definitions: Dict[str, Any]) -> str:
    """The strict scorer prompt: the 21 Item pass criteria + 6 Lever
    Observed rules from definitions.json, the answer text, and the
    citation URLs the agent actually cited. Nothing else is in scope."""
    items_text = "\n".join(
        "- %s (%s): %s" % (it["id"], it["item"], it["pass_criteria"])
        for it in items_list(definitions))
    levers_text = "\n".join(
        "- %s (%s): Observed only if %s" % (lv["id"], lv["lever"],
                                            lv["observed_only_if"])
        for lv in levers_list(definitions))
    cites_text = "\n".join(
        "- %s" % c.get("url") for c in citations if c.get("url"))
    return (
        "You are scoring a shopping agent's answer against the AI Sharc "
        "audit criteria for ONE firm. You are not searching the web and "
        "you have no tools. Judge ONLY what the answer text below "
        "demonstrates about %(firm)s. Do not use outside knowledge. Do not "
        "infer from other firms in the answer.\n"
        "\n"
        "RULES (hard, no exceptions):\n"
        "1. For each of the 21 Items, return exactly one result: "
        "\"Pass\", \"Fail\", or \"Not observed\".\n"
        "2. \"Pass\" means the answer shows the fact with the agent's exact "
        "wording quoted AND a cited source URL. Both are required. If "
        "either is missing, the result is \"Not observed\", not \"Pass\".\n"
        "3. \"Fail\" means the answer checked the fact and found it absent "
        "or wrong, with exact wording and a cited source. An omission is "
        "NEVER a Fail — it is \"Not observed\".\n"
        "4. Quote the agent's exact wording (a short verbatim quote from "
        "the answer text) and give the cited source URL. The source URL "
        "must be one of the citation URLs listed below — a URL the agent "
        "did not cite is not accepted.\n"
        "5. Score ONLY this firm. Facts the answer gives about other firms "
        "do not count for this firm.\n"
        "6. A phone number the agent quotes for this firm counts as a "
        "booking/contact route.\n"
        "7. Day-by-day hours means hours listed per day (for example "
        "\"Mon, Tue, Wed, Thu, Fri, Sat, Sun: 00:00-24:00\"). A \"24/7 "
        "emergency\" claim alone does NOT demonstrate day-by-day hours.\n"
        "8. Brands and system types: Pass if the agent named at least one "
        "brand (for example Lennox, Trane) or system type (for example "
        "mini-split) actually served by this firm, with exact wording and "
        "a cited source.\n"
        "9. Rating figure: Pass only if the agent quoted a rating figure "
        "from an independent platform (for example Google, Yelp). A claim "
        "on the firm's own site that it has \"5-star reviews\" does not "
        "count.\n"
        "10. Licence: Pass only if the agent quoted a licence NUMBER for "
        "this firm. \"Licensed and insured\" without a number does not "
        "count.\n"
        "11. BBB: Pass only if the agent quoted a BBB accreditation or "
        "rating for this firm.\n"
        "12. Diagnostic fee: Pass only if the agent quoted a fee in "
        "dollars for this firm.\n"
        "13. Warranty card: Pass only if the agent quoted all six warranty "
        "lines (parts years/manufacturer; labour years/installer; repair "
        "parts and labour years; registration; transferability; claim "
        "line). Mentioning financing is not a warranty card.\n"
        "14. Free-estimate status: Pass only if the agent stated "
        "separately whether install estimates (or repair estimates) are "
        "free. Mentioning an estimate form without stating free/paid "
        "does not count.\n"
        "15. Machine readability (C7.1-C7.4: crawler access, key facts "
        "without JavaScript, JSON-LD, sitemap): these are technical checks "
        "the answer does not address. Return \"Not observed\" unless the "
        "answer explicitly discusses them with exact wording and a cited "
        "source.\n"
        "16. Levers: \"Observed\" only if the stated rule is met; the "
        "agent's claim alone is never Observed. Otherwise "
        "\"Recommendation\" (or \"Not checked\" for llms.txt when the "
        "answer does not address it at all).\n"
        "17. Consistency Items — C1.2 (rating figures consistent across "
        "sources), C5.2 (hours consistent across sources), C6.1 (one "
        "unique primary phone everywhere): these ask whether the fact is "
        "the SAME across sources. Pass only if the answer shows the fact "
        "from MORE THAN ONE independent source and they agree. A single "
        "source — one phone, one rating figure, one set of hours — does "
        "NOT demonstrate consistency. If the answer shows only one "
        "source, return \"Not observed\".\n"
        "18. C2.1 (service-area page naming the town and ZIP): Pass only "
        "if the answer identifies a specific service-area page and quotes "
        "the town name AND the ZIP from it. A general assertion that the "
        "firm serves the ZIP, or a citation to a firm's page in general, "
        "does not count — even if the cited page happens to be a service "
        "page. The answer must show the service-area page, not merely "
        "quote facts from a page.\n"
        "19. C1.1 (rating figure): Pass if the agent quoted a rating "
        "figure from an independent platform for this firm, with exact "
        "wording and a cited source. A review count is not required for "
        "the observation.\n"
        "20. Founding year (C6.2): Pass if the agent quoted a founding "
        "year for this firm, with exact wording and a cited source. A "
        "\"since YEAR\" statement (for example \"since 1945\", "
        "\"family-owned since 1945\", \"in Coppell since 2016\") IS a "
        "founding-year statement — the year the firm began. One source "
        "stating the year is enough for the observation; cross-source "
        "consistency is a core-audit check, not an observation check.\n"
        "\n"
        "ITEMS (pass criteria):\n%(items)s\n"
        "\n"
        "LEVERS (Observed only if):\n%(levers)s\n"
        "\n"
        "ANSWER TEXT:\n%(answer)s\n"
        "\n"
        "CITATIONS (the only source URLs you may cite):\n%(cites)s\n"
        "\n"
        "FIRM TO SCORE: %(firm)s\n"
        "\n"
        "Return ONLY a JSON object, no other text:\n"
        "{\n"
        "  \"firm\": \"%(firm)s\",\n"
        "  \"items\": [{\"item_id\": \"C1.1\", \"result\": "
        "\"Pass|Fail|Not observed\", \"exact_wording\": \"...\", "
        "\"cited_source\": \"...\", \"reason\": \"...\"}, ... all 21 Items],\n"
        "  \"levers\": [{\"lever_id\": \"booking_route\", \"result\": "
        "\"Observed|Recommendation|Not checked\", \"note\": \"...\"}, "
        "... all 6 levers]\n"
        "}\n"
        "For \"Not observed\" Items, leave exact_wording and cited_source "
        "empty and give the reason (for example \"not mentioned in the "
        "answer\")."
        % {"firm": firm_name, "items": items_text, "levers": levers_text,
           "answer": answer_text, "cites": cites_text or "(none)"})


def parse_scorer_output(text: str) -> Dict[str, Any]:
    """Parse the scorer model's JSON output, tolerating markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    return json.loads(cleaned)


def validate_scored_items(scored: Dict[str, Any], definitions: Dict[str, Any],
                          cited_urls: set) -> List[str]:
    """Enforce the hard rules in code (Design §2.5). Returns a list of
    corrections applied (empty when the scorer output was already clean).
    A Pass/Fail without exact wording or a cited source, or with a source
    the agent did not cite, is downgraded to Not observed."""
    corrections: List[str] = []
    want_items = [it["id"] for it in items_list(definitions)]
    got_items = {it.get("item_id"): it for it in scored.get("items", [])}
    for item_id in want_items:
        entry = got_items.get(item_id)
        if entry is None:
            scored.setdefault("items", []).append({
                "item_id": item_id, "result": "Not observed",
                "exact_wording": "", "cited_source": "",
                "reason": "scorer did not return this Item"})
            corrections.append("%s: missing from scorer output, set Not observed" % item_id)
            continue
        result = entry.get("result")
        if result not in ITEM_RESULTS:
            entry["result"] = "Not observed"
            entry["exact_wording"] = ""
            entry["cited_source"] = ""
            entry["reason"] = "scorer returned out-of-vocabulary result %r" % (result,)
            corrections.append("%s: bad result %r, set Not observed" % (item_id, result))
            continue
        if result in ("Pass", "Fail"):
            wording = (entry.get("exact_wording") or "").strip()
            source = (entry.get("cited_source") or "").strip()
            if not wording or not source:
                entry["result"] = "Not observed"
                entry["exact_wording"] = ""
                entry["cited_source"] = ""
                entry["reason"] = "no agent wording / cited source recorded"
                corrections.append("%s: Pass/Fail without wording/source, downgraded to Not observed" % item_id)
            elif source not in cited_urls:
                entry["result"] = "Not observed"
                entry["exact_wording"] = ""
                entry["cited_source"] = ""
                entry["reason"] = "cited source was not cited by the agent"
                corrections.append("%s: source not in agent citations, downgraded to Not observed" % item_id)
    want_levers = [lv["id"] for lv in levers_list(definitions)]
    got_levers = {lv.get("lever_id"): lv for lv in scored.get("levers", [])}
    for lever_id in want_levers:
        entry = got_levers.get(lever_id)
        if entry is None:
            scored.setdefault("levers", []).append({
                "lever_id": lever_id, "result": "Not checked",
                "note": "scorer did not return this lever"})
            corrections.append("%s: missing from scorer output, set Not checked" % lever_id)
            continue
        if entry.get("result") not in LEVER_RESULTS:
            entry["result"] = "Recommendation"
            entry["note"] = "scorer returned out-of-vocabulary result %r" % (entry.get("result"),)
            corrections.append("%s: bad result, set Recommendation" % lever_id)
    return corrections


def category_summary(scored_items: List[Dict[str, Any]],
                     definitions: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Reference Category summary, derived in code (all-or-nothing):
    Pass only if every Item in the Category is Pass; otherwise
    Not demonstrated. Never the official Category result."""
    by_id = {it["item_id"]: it for it in scored_items}
    out = []
    for cat in CATEGORY_ORDER:
        ids = [it["id"] for it in items_list(definitions)
               if it["category"] == cat]
        passed = all(by_id.get(i, {}).get("result") == "Pass" for i in ids)
        out.append({
            "category": cat,
            "result": "Pass" if passed else "Not demonstrated",
            "note": ("All %d Items Pass" % len(ids)) if passed else
                    "Reference summary only — not the official Category result.",
        })
    return out


def score_firm(answer_text: str, citations: List[Dict[str, Any]],
               firm_name: str, definitions: Dict[str, Any]) -> Dict[str, Any]:
    """Score one firm with the LLM scorer. Returns the scored Items and
    Levers plus the scorer call's response id and cost. Raises on API
    failure or unparseable output (the caller retries or reports)."""
    prompt = build_scorer_prompt(answer_text, citations, firm_name,
                                 definitions)
    body = call_model_no_tools(prompt)
    text = answer_text_from_body(body)
    if not text.strip():
        raise RuntimeError("scorer call returned no answer text (id %s)"
                           % body.get("id"))
    scored = parse_scorer_output(text)
    cited_urls = {c.get("url") for c in citations if c.get("url")}
    corrections = validate_scored_items(scored, definitions, cited_urls)
    # Order the Items C1.1..C7.4 and the levers as in definitions.json.
    order = {i: n for n, i in enumerate(ITEM_ORDER)}
    scored["items"] = sorted(scored["items"],
                             key=lambda e: order.get(e.get("item_id"), 99))
    lorder = {i: n for n, i in enumerate(LEVER_ORDER)}
    scored["levers"] = sorted(scored["levers"],
                              key=lambda e: lorder.get(e.get("lever_id"), 99))
    scored["category_results"] = category_summary(scored["items"], definitions)
    scored["scorer_response_id"] = body.get("id")
    scored["scorer_cost_usd"] = cost_from_usage(body)
    scored["scorer_corrections"] = corrections
    scored["scorer_usage"] = body.get("usage") or {}
    return scored


def gates_by_rule(definitions) -> List[Dict[str, Any]]:
    """All six Gates Not observed by rule, with the manual run 1 reasons."""
    return [{
        "gate_id": g["gate_id"],
        "label": g["gate"],
        "result": "Not observed",
        "reason": GATE_REASONS.get(g["id"], "Shopping answer is not a Gate check."),
        "exact_wording": "",
        "cited_source": "",
    } for g in gates_list(definitions)]


def build_observation(firm: Dict[str, Any], scored: Dict[str, Any],
                      run_meta: Dict[str, Any],
                      definitions: Dict[str, Any],
                      named: bool) -> Dict[str, Any]:
    """Assemble one per-firm muse-observation.json record per the schema.
    `named` is False when the agent did not name the firm: every Item is
    then Not observed with the reason recorded."""
    if not named:
        items = [{
            "item_id": it["id"],
            "category": it["category"],
            "label": it["item"],
            "result": "Not observed",
            "exact_wording": "",
            "cited_source": "",
            "reason": "firm not named in the agent's answer",
        } for it in items_list(definitions)]
        levers = [{
            "lever_id": lv["id"],
            "label": lv["lever"],
            "result": "Not checked",
            "note": "firm not named in the agent's answer",
        } for lv in levers_list(definitions)]
        cats = category_summary(items, definitions)
        scorer_info = {"method": "not scored — firm not named in the answer",
                       "scorer_response_id": None, "scorer_cost_usd": 0.0}
    else:
        item_meta = {it["id"]: it for it in items_list(definitions)}
        items = [{
            "item_id": e["item_id"],
            "category": item_meta[e["item_id"]]["category"],
            "label": item_meta[e["item_id"]]["item"],
            "result": e["result"],
            "exact_wording": e.get("exact_wording") or "",
            "cited_source": e.get("cited_source") or "",
            "reason": e.get("reason") or "",
        } for e in scored["items"]]
        lever_meta = {lv["id"]: lv for lv in levers_list(definitions)}
        levers = [{
            "lever_id": e["lever_id"],
            "label": lever_meta[e["lever_id"]]["lever"],
            "result": e["result"],
            "note": e.get("note") or "",
        } for e in scored["levers"]]
        cats = scored["category_results"]
        scorer_info = {
            "method": "LLM-assisted scorer (muse-spark-1.3, no tools) over the saved answer text and citations",
            "scorer_response_id": scored.get("scorer_response_id"),
            "scorer_cost_usd": scored.get("scorer_cost_usd"),
            "scorer_corrections": scored.get("scorer_corrections", []),
        }
    return {
        "audit_id": "MUSE-SPARK",
        "agent_label": "MUSE-SPARK",
        "firm": firm["name"],
        "firm_id": firm["firm_id"],
        "primary_business_category": run_meta["primary_business_category"],
        "query": run_meta["query"],
        "town_zip": run_meta["town_zip"],
        "date_checked": run_meta["date_checked"],
        "model": run_meta["model"],
        "tools": ["web_search"],
        "transcript_ref": run_meta["transcript_ref"],
        "response_id": run_meta["response_id"],
        "web_search_calls": run_meta["web_search_calls"],
        "web_search_results": run_meta["web_search_results"],
        "url_citation_count": run_meta["url_citation_count"],
        "distinct_urls": run_meta["distinct_urls"],
        "cost_usd": run_meta["cost_usd"],
        "scorer": scorer_info,
        "gates": gates_by_rule(definitions),
        "items": items,
        "category_results": cats,
        "levers": levers,
        "delegation": {"from": None, "to": None, "what": None,
                       "note": "No visible delegation in a MUSE-SPARK run."},
        "auditor": "AI Sharc harness (automated)",
    }
