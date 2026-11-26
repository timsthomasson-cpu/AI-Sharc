#!/usr/bin/env python3
"""Run the Prompt v1 shopping queries through an OpenAI-compatible Responses API with web search.

Providers:
  openai  OpenAI API (agent prefix openai-api), key OPENAI_API_KEY, https://api.openai.com/v1
  meta    Meta Model API (agent prefix meta-api), key META_MODEL_API_KEY, https://api.meta.ai/v1

For each task: turn 0 sends the exact Prompt v1 task text (default ranking line); turn 1 sends the matching
follow-up from document revision 2 in the same conversation. Both turns are stored in staging.api_returns
(test database); Claude extracts them into Shopping Query Returns.

If a provider refuses the approximate Houston user_location on the web_search tool, the run is retried without
it and the stored location says so. If it refuses previous_response_id, turn 1 resends the conversation instead.

Settings:
  PROVIDER         optional: openai (default) or meta
  MODEL            optional; otherwise the first available of the provider's preferred models
                   (OPENAI_MODEL is still read for the openai provider)
  QUERY_IDS        optional, comma separated (default: hvac-houston-77002-t1,t2,t3)
Keys are never printed.
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

PROVIDERS = {
    "openai": {"api": "https://api.openai.com/v1", "key": "OPENAI_API_KEY", "agent": "openai-api",
               "models": ["gpt-5.5", "gpt-5.2", "gpt-5.1", "gpt-5", "gpt-4.1", "gpt-4o"]},
    "meta": {"api": "https://api.meta.ai/v1", "key": "META_MODEL_API_KEY", "agent": "meta-api",
             "models": ["muse-spark-1.3", "muse-spark-1.2", "muse-spark-1.1"]},
}
FOLLOW_UP = "List the phone number and website for each firm you named."
CENTRAL = timezone(timedelta(hours=-6))
HOUSTON = {"type": "approximate", "country": "US", "region": "Texas", "city": "Houston"}


class ApiError(RuntimeError):
    def __init__(self, code, detail):
        super().__init__("HTTP %d: %s" % (code, detail))
        self.code, self.detail = code, detail


def call(cfg, method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(cfg["api"] + path, data=data, method=method, headers={
        "Authorization": "Bearer " + os.environ[cfg["key"]], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ApiError(exc.code, exc.read().decode("utf-8", "replace")[:500])


def pick_model(cfg, provider):
    chosen = os.environ.get("MODEL") or (os.environ.get("OPENAI_MODEL") if provider == "openai" else None)
    if chosen:
        return chosen
    try:
        ids = {m.get("id") for m in call(cfg, "GET", "/models").get("data", [])}
    except ApiError:
        ids = set()
    for m in cfg["models"]:
        if m in ids or any(i and i.endswith("/" + m) for i in ids):
            return m
    if not ids:
        return cfg["models"][-1]
    raise RuntimeError("none of %s is available to this key" % cfg["models"])


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
    if not texts and resp.get("output_text"):
        texts.append(resp["output_text"])
    return "\n".join(texts), cites


def refused(exc, word):
    return isinstance(exc, ApiError) and exc.code in (400, 422) and word in exc.detail


def ask(cfg, model, text, history, prev, use_location):
    """One turn. Returns (response, use_location, used_prev)."""
    tool = {"type": "web_search"}
    if use_location:
        tool["user_location"] = HOUSTON
    body = {"model": model, "tools": [tool]}
    if prev:
        body.update(input=text, previous_response_id=prev)
    else:
        body["input"] = history + [{"role": "user", "content": text}] if history else text
    try:
        return call(cfg, "POST", "/responses", body), use_location, bool(prev)
    except ApiError as exc:
        if use_location and refused(exc, "location"):
            return ask(cfg, model, text, history, prev, False)
        if prev and refused(exc, "previous_response"):
            return ask(cfg, model, text, history, None, use_location)
        raise


def main():
    from db import connect
    provider = os.environ.get("PROVIDER", "openai").strip() or "openai"
    cfg = PROVIDERS[provider]
    model = pick_model(cfg, provider)
    qids = [q.strip() for q in os.environ.get("QUERY_IDS", "").split(",") if q.strip()] or \
        ["hvac-houston-77002-t1", "hvac-houston-77002-t2", "hvac-houston-77002-t3"]
    print("%s shopping query run: model %s, %d tasks, location Houston TX (approximate)" % (provider, model, len(qids)))
    failures, use_location = 0, True
    with connect() as con:
        for qid in qids:
            task, rank_line = prompts.expected_task(cfg["agent"], qid)
            prompt = task + " " + rank_line
            started = datetime.now(CENTRAL).replace(microsecond=0)
            run_id = "%s__%s__r1__%s" % (cfg["agent"], qid, started.strftime("%Y%m%dT%H%M%S%z"))
            prev, history = None, []
            for turn, text in ((0, prompt), (1, FOLLOW_UP)):
                at = datetime.now(CENTRAL).replace(microsecond=0)
                out, cites, resp, err = None, None, None, None
                try:
                    resp, use_location, _ = ask(cfg, model, text, history, prev, use_location)
                    out, cites = text_and_citations(resp)
                    prev = resp.get("id")
                    history += [{"role": "user", "content": text}, {"role": "assistant", "content": out or ""}]
                except Exception as exc:  # noqa: BLE001 — record the failure and carry on
                    err = str(exc)[:1000]
                    failures += 1
                location = dict(HOUSTON) if use_location else {"type": "none", "note": "provider refused user_location"}
                with con.cursor() as cur:
                    cur.execute(
                        "insert into staging.api_returns (run_id, agent, query_id, turn, requested_at, model, location, "
                        "prompt, output_text, citations, response, error) values (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb,%s) "
                        "on conflict (run_id, turn) do nothing",
                        (run_id, cfg["agent"], qid, turn, at.isoformat(), model, json.dumps(location), text, out,
                         json.dumps(cites), json.dumps(resp) if resp else None, err))
                con.commit()
                print("%s turn %d: %s" % (run_id, turn, "ERROR " + err if err else "%d chars, %d citations" % (len(out or ""), len(cites or []))))
                if err:
                    break
    print("done, %d failures" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
