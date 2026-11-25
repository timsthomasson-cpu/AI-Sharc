#!/usr/bin/env python3
"""Run the Prompt v1 shopping queries through the OpenAI Responses API with web search.

For each task: turn 0 sends the exact Prompt v1 task text (ChatGPT ranking line); turn 1 sends the matching
follow-up from document revision 2 in the same conversation. Both turns are stored in staging.api_returns
(test database); Claude extracts them into Shopping Query Returns.

Settings:
  OPENAI_API_KEY   required
  OPENAI_MODEL     optional; otherwise the first available of PREFERRED_MODELS
  QUERY_IDS        optional, comma separated (default: hvac-houston-77002-t1,t2,t3)
The key is never printed.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "loader"))

import build_return_bundle as prompts  # noqa: E402  (task wording lives in one place)

API = "https://api.openai.com/v1"
PREFERRED_MODELS = ["gpt-5.5", "gpt-5.2", "gpt-5.1", "gpt-5", "gpt-4.1", "gpt-4o"]
FOLLOW_UP = "List the phone number and website for each firm you named."
CENTRAL = timezone(timedelta(hours=-6))


def call(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError("HTTP %d from OpenAI: %s" % (exc.code, detail))


def pick_model():
    if os.environ.get("OPENAI_MODEL"):
        return os.environ["OPENAI_MODEL"]
    ids = {m.get("id") for m in call("GET", "/models").get("data", [])}
    for m in PREFERRED_MODELS:
        if m in ids:
            return m
    raise RuntimeError("none of %s is available to this key" % PREFERRED_MODELS)


def text_and_citations(resp):
    texts, cites = [], []
    for item in resp.get("output", []):
        if item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if part.get("type") == "output_text":
                texts.append(part.get("text", ""))
                for a in part.get("annotations", []) or []:
                    if a.get("type") == "url_citation":
                        cites.append({"url": a.get("url"), "title": a.get("title")})
    return "\n".join(texts), cites


def main():
    from db import connect
    model = pick_model()
    location = {"type": "approximate", "country": "US", "region": "Texas", "city": "Houston"}
    qids = [q.strip() for q in os.environ.get("QUERY_IDS", "").split(",") if q.strip()] or \
        ["hvac-houston-77002-t1", "hvac-houston-77002-t2", "hvac-houston-77002-t3"]
    print("OpenAI shopping query run: model %s, %d tasks, location Houston TX (approximate)" % (model, len(qids)))
    failures = 0
    with connect() as con:
        for qid in qids:
            task, rank_line = prompts.expected_task("openai-api", qid)
            prompt = task + " " + rank_line
            started = datetime.now(CENTRAL).replace(microsecond=0)
            run_id = "openai-api__%s__r1__%s" % (qid, started.strftime("%Y%m%dT%H%M%S%z"))
            prev = None
            for turn, text in ((0, prompt), (1, FOLLOW_UP)):
                body = {"model": model, "input": text,
                        "tools": [{"type": "web_search", "user_location": location}]}
                if prev:
                    body["previous_response_id"] = prev
                at = datetime.now(CENTRAL).replace(microsecond=0)
                out, cites, resp, err = None, None, None, None
                try:
                    resp = call("POST", "/responses", body)
                    out, cites = text_and_citations(resp)
                    prev = resp.get("id")
                except Exception as exc:  # noqa: BLE001 — record the failure and carry on
                    err = str(exc)[:1000]
                    failures += 1
                with con.cursor() as cur:
                    cur.execute(
                        "insert into staging.api_returns (run_id, agent, query_id, turn, requested_at, model, location, "
                        "prompt, output_text, citations, response, error) values (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb,%s) "
                        "on conflict (run_id, turn) do nothing",
                        (run_id, "openai-api", qid, turn, at.isoformat(), model, json.dumps(location), text, out,
                         json.dumps(cites), json.dumps(resp) if resp else None, err))
                con.commit()
                print("%s turn %d: %s" % (run_id, turn, "ERROR " + err if err else "%d chars, %d citations" % (len(out or ""), len(cites or []))))
                if err:
                    break
    print("done, %d failures" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
