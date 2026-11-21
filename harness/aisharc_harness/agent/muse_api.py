"""AI Sharc Muse agent module — Meta Model API route (Spec v1.22, s.8.1).

Queries the Muse Spark model with web-search grounding as the scriptable,
repeatable proxy for the Meta / Muse per-agent observation. See DESIGN.md s.6
for the naming decision and the honest labelling rule.

IMPORTANT — what this tests: the Muse Spark model (muse-spark-1.3) with web
search, via Meta's Model API. It is NOT the consumer Meta AI assistant and
NOT the Muse agent (muse.ai / WhatsApp). The observation record must state
the surface tested ("Meta Model API — Muse Spark 1.3 with web_search") and
must not claim it is the Muse agent or the Meta AI assistant. If the audit's
"Meta / Muse" row is meant to be the consumer experience, this result is a
proxy, not the product. The manual validation route (Meta AI app, Shopping
mode, or a WhatsApp chat with Meta AI) tests the real consumer surface.

The API key is read from the environment (META_MODEL_API_KEY) — set from the
Secure Vault, never hardcoded, never logged, never written to an output file.
Without a key the module reports that it cannot run; it does not fake a result.

Endpoint: POST https://api.meta.ai/v1/responses
Model: muse-spark-1.3 (current default per dev.meta.ai docs)
Tools: [{"type": "web_search"}] — search grounding; the response carries
  web_search_call, url_citation annotations, and (opt-in) raw results.
user_location: country US, region Texas, city Coppell, timezone America/Chicago.
Pricing (official, dev.meta.ai/docs/pricing-rate-limits): Muse Spark standard
  $1.25 / 1M input tokens, $4.25 / 1M output tokens; web search grounding
  $2.50 per 1,000 search queries. Cost is trivial at this scale.

The standard shopping task (same form as the OAI design, s.2.2): no firm,
website, or listing is named in the task.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any, Dict, List, Optional

import requests

API_BASE = "https://api.meta.ai/v1"
MODEL = "muse-spark-1.3"
SURFACE = "Meta Model API — Muse Spark 1.3 with web_search"

STANDARD_TASK = (
    "Find a {service} firm in {town}, TX {zip} for {need} and compare "
    "the firms you find."
)


def standard_question(service: str = "HVAC", town: str = "Coppell",
                      zip_code: str = "75019",
                      need: str = "AC installation and repair") -> str:
    """The standard shopping task. No firm, website, or listing is named."""
    return STANDARD_TASK.format(service=service, town=town, zip=zip_code,
                                need=need)


def _api_key() -> Optional[str]:
    return os.environ.get("META_MODEL_API_KEY") or None


def query_muse(question: str, town: str = "Coppell",
               zip_code: str = "75019") -> Dict[str, Any]:
    """Ask the Muse Spark model the standard question with web-search
    grounding. Returns the observation record (or a cannot-run record when
    no API key is present). The full JSON response is preserved verbatim."""
    key = _api_key()
    record: Dict[str, Any] = {
        "agent": "Meta / Muse",
        "surface_tested": SURFACE,
        "model": MODEL,
        "tools": ["web_search"],
        "date": date.today().isoformat(),
        "query": question,
        "location": {"country": "US", "region": "Texas", "city": town,
                     "zip": zip_code, "timezone": "America/Chicago"},
    }
    if not key:
        record.update({
            "ran": False,
            "reason": "No Meta Model API key. Set META_MODEL_API_KEY from "
                      "the Secure Vault (dev.meta.ai dashboard). The harness "
                      "does not fake an agent observation.",
        })
        return record
    payload = {
        "model": MODEL,
        "input": question,
        "tools": [{"type": "web_search", "user_location": {
            "country": "US", "region": "Texas", "city": town,
            "timezone": "America/Chicago",
        }}],
        "include": ["web_search_call.results"],
    }
    try:
        resp = requests.post(
            API_BASE + "/responses", json=payload,
            headers={"Authorization": "Bearer " + key,
                     "Content-Type": "application/json"},
            timeout=120)
    except requests.exceptions.RequestException as exc:
        record.update({"ran": False,
                       "reason": "Model API request failed: %s" % exc})
        return record
    if resp.status_code != 200:
        record.update({"ran": False,
                       "reason": "Model API HTTP %d: %s" % (
                           resp.status_code, resp.text[:500])})
        return record
    body = resp.json()
    record.update({"ran": True, "response": body})
    record.update(_extract_observation(body))
    return record


def _extract_observation(body: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the answer text, citations, and search calls out of a Responses
    API body. The full body is kept in the record under 'response'."""
    texts: List[str] = []
    citations: List[Dict[str, Any]] = []
    searches: List[Dict[str, Any]] = []
    for item in body.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for part in item.get("content", []) or []:
                if isinstance(part, dict) and part.get("type") == "output_text":
                    texts.append(part.get("text", ""))
                    for ann in part.get("annotations", []) or []:
                        if ann.get("type") == "url_citation":
                            citations.append({
                                "url": ann.get("url"),
                                "title": ann.get("title"),
                                "start_index": ann.get("start_index"),
                                "end_index": ann.get("end_index"),
                            })
        elif item.get("type") == "web_search_call":
            searches.append({
                "query": item.get("query"),
                "status": item.get("status"),
                "results": item.get("results"),
            })
    return {
        "answer_text": "\n".join(texts),
        "citations": citations,
        "web_search_calls": searches,
        "searched": bool(searches),
    }


def observation_to_json(record: Dict[str, Any]) -> str:
    """Serialise an observation record. The API key is never in a record."""
    return json.dumps(record, indent=2, sort_keys=True)
