#!/usr/bin/env python3
"""Build a load bundle from Prompt v1 Shopping Query Returns (Tim, 2026-11-24).

Input: a folder (one Inbox date folder) holding, for each run,
  <agent>__<query_id>__r<n>__<YYYYMMDDTHHMMSS-0600>__observation.md   the agent's answer, saved by the agent or by Tim
  <agent>__<query_id>__r<n>__<YYYYMMDDTHHMMSS-0600>__extract.json     Claude's reading of that answer

The .md file is the record and is never changed. The extract holds what Claude read from it: the run details
the file states, each firm named (in the order it appears), the agent's rank, and what the ranking is based on.
This script checks the two against each other and against the file name, and builds
{"runs": [{file, file_hash, run{}, firms[]}]} for public.load_shopping_query_return().

An .md file with no extract yet is listed as waiting for extraction and is not loaded.

Usage: build_return_bundle.py <folder> <out.json>
"""
import hashlib
import json
import os
import re
import sys

PROMPT_VERSIONS = {"v1"}

# agent prefix in the file name -> (vendor, product, agent label)
AGENTS = {
    "meta-muse": ("Meta", "Muse", "MUSE-AGENT"),
    "meta-metaai": ("Meta", "Meta AI", "META-AI"),
    "openai-chatgpt": ("OpenAI", "ChatGPT", "CHATGPT"),
}

# Prompt v1 task wording. {town}, {zip} filled from the query_id.
SERVICES = {1: "AC installation and repair", 2: "AC repair", 3: "AC installation and replacement"}
TASK = "Find all HVAC firms whose service area includes {town}, TX {zip} for {service} and compare the firms you find."
RANK_LINE = {
    "meta-muse": "Rank the firms you find, using Muse ranking.",
    "default": ("Rank the firms you find using your own assessment, not a ranking copied from another site, "
                "and say what the ranking is based on."),
}

NAME_RE = re.compile(r"^(?P<agent>[a-z0-9-]+)__(?P<qid>[a-z]+-[a-z0-9-]+-\d{5}-t[123])__r(?P<rep>\d+)__"
                     r"(?P<ts>\d{8}T\d{6}[+-]\d{4})__observation\.md$")

RUN_KEYS = ["prompt_version", "session_state", "web_search_ran", "ranked", "ranking_origin", "business_contacted",
            "extracted_by", "firms"]
FIRM_KEYS = ["position", "name_as_given"]


class ExtractError(Exception):
    pass


def iso(ts):
    """20261124T200000-0600 -> 2026-11-24T20:00:00-06:00"""
    return "%s-%s-%sT%s:%s:%s%s:%s" % (ts[0:4], ts[4:6], ts[6:8], ts[9:11], ts[11:13], ts[13:15], ts[15:18], ts[18:20])


def town_zip(qid):
    parts = qid.split("-")          # hvac-houston-77002-t1 ; hvac-san-antonio-78217-t2
    zip_code = parts[-2]
    town = " ".join(p.capitalize() for p in parts[1:-2])
    return town, zip_code


def expected_task(agent, qid):
    town, zip_code = town_zip(qid)
    n = int(qid[-1])
    task = TASK.format(town=town, zip=zip_code, service=SERVICES[n])
    return task, RANK_LINE.get(agent, RANK_LINE["default"])


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def build_run(folder, md_name, m):
    agent, qid, rep, ts = m["agent"], m["qid"], int(m["rep"]), m["ts"]
    if agent not in AGENTS:
        raise ExtractError("unknown agent prefix %r" % agent)
    with open(os.path.join(folder, md_name), "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8", "replace")
    ext_path = os.path.join(folder, md_name.replace("__observation.md", "__extract.json"))
    with open(ext_path, encoding="utf-8") as fh:
        ex = json.load(fh)

    missing = [k for k in RUN_KEYS if k not in ex]
    if missing:
        raise ExtractError("extract missing %s" % ", ".join(missing))
    if ex["prompt_version"] not in PROMPT_VERSIONS:
        raise ExtractError("prompt version %r is not an approved version" % ex["prompt_version"])

    # The exact Prompt v1 wording must appear in the saved answer, so a run made with other wording is caught here.
    task, rank_line = expected_task(agent, qid)
    body = squash(text)
    if squash(task) not in body:
        raise ExtractError("the Prompt v1 task text for %s is not in the file" % qid)
    if squash(rank_line) not in body:
        raise ExtractError("the Prompt v1 ranking line for %s is not in the file" % agent)

    firms = ex["firms"]
    for f in firms:
        miss = [k for k in FIRM_KEYS if not f.get(k)]
        if miss:
            raise ExtractError("a firm is missing %s" % ", ".join(miss))
    positions = [str(f["position"]) for f in firms]
    if positions != [str(i) for i in range(1, len(firms) + 1)]:
        raise ExtractError("firm positions must run 1..%d in the order the firms appear" % len(firms))
    ranks = [f.get("agent_rank") for f in firms if f.get("agent_rank") is not None]
    if ex["ranked"] == "yes" and not ranks:
        raise ExtractError("ranked = yes but no firm has an agent_rank")
    if ex["ranked"] == "no" and ranks:
        raise ExtractError("ranked = no but firms carry an agent_rank")
    if len(ranks) != len(set(ranks)):
        raise ExtractError("two firms share an agent_rank")
    names = [squash(f["name_as_given"]).lower() for f in firms]
    if len(names) != len(set(names)):
        raise ExtractError("the same firm name appears twice; list each firm once")

    vendor, product, label = AGENTS[agent]
    town, zip_code = town_zip(qid)
    run = {
        "run_id": md_name[: -len("__observation.md")],
        "vendor": vendor, "product": product, "agent_label": label,
        "query": task + " " + rank_line, "query_id": qid, "task_number": int(qid[-1]),
        "service": qid.split("-")[0].upper(), "service_query": SERVICES[int(qid[-1])],
        "town_zip": "%s, TX %s" % (town, zip_code),
        "checked_at": iso(ts), "repeat_number": rep,
        "model": ex.get("model"), "tools_used": ex.get("tools_used"),
        "signed_in_account": ex.get("signed_in_account"),
        "fresh_session": "yes", "session_state": ex["session_state"],
        "auditor": "Claude (orchestrator)",
        "prompt_version": ex["prompt_version"], "web_search_ran": ex["web_search_ran"],
        "sources_cited": ex.get("sources_cited") or [], "ranked": ex["ranked"],
        "ranking_basis": ex.get("ranking_basis"), "ranking_origin": ex["ranking_origin"],
        "follow_up": ex.get("follow_up") or "none", "business_contacted": ex["business_contacted"],
        "response_text": text, "drive_file_id": ex.get("drive_file_id"), "extracted_by": ex["extracted_by"],
    }
    return {"file": md_name, "file_hash": hashlib.sha256(raw).hexdigest(), "run": run, "firms": firms}


def main(folder, out):
    runs, waiting, problems = [], [], []
    for name in sorted(os.listdir(folder)):
        if not name.endswith("__observation.md"):
            continue
        m = NAME_RE.match(name)
        if not m:
            problems.append({"file": name, "reason": "file name does not follow the template pattern"})
            continue
        if not os.path.exists(os.path.join(folder, name.replace("__observation.md", "__extract.json"))):
            waiting.append(name)
            continue
        try:
            runs.append(build_run(folder, name, m))
        except (ExtractError, ValueError, KeyError) as exc:
            problems.append({"file": name, "reason": str(exc)})
    bundle = {"runs": runs, "waiting_for_extract": waiting, "problems": problems}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, ensure_ascii=False, indent=1)
    return bundle


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    b = main(sys.argv[1], sys.argv[2])
    print("%d runs built, %d waiting for extract, %d problems" % (len(b["runs"]), len(b["waiting_for_extract"]), len(b["problems"])))
    for p in b["problems"]:
        print("  problem: %s: %s" % (p["file"], p["reason"]))
