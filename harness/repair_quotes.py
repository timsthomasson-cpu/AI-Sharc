#!/usr/bin/env python3
"""Repair spliced scorer quotes in the study observation files.

The mechanical spot-check found 26 of 1,960 Pass/Fail wordings are
splices of two verbatim fragments (joined with ' ... ', ' / ', ' | ',
'; ', '" and "', '. ') rather than one verbatim span. The underlying
Passes are substantively correct (both fragments are real answer text
with a cited source); only the recorded quote is non-verbatim.

For each case this script finds the longest verbatim prefix and the
longest verbatim suffix of the recorded wording in the answer text.
If the answer span from the prefix start to the suffix end is short
(< 600 chars) and still demonstrates the Item (for C2.2 it must contain
both an install word and a repair word), the wording is replaced with
that exact span. Otherwise the result is downgraded to Not observed
with the reason recorded — never a silent change of result.

Usage:
  python3 repair_quotes.py --dry-run   # print proposed actions
  python3 repair_quotes.py             # apply
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from aisharc_harness.agent import muse_api  # noqa: E402

STUDY_DIR = os.path.join(HERE, "runs", "2026-11-14-study", "agent")
MAX_SPAN = 600


def strip_md(s: str) -> str:
    return s.replace("**", "")


def longest_prefix(wording: str, ans: str) -> tuple:
    """Longest leading substring of wording found verbatim in ans.
    Returns (text, start_index) or ('', -1)."""
    best, best_pos = "", -1
    # Try progressively shorter prefixes (word-boundary cuts only).
    words = wording.split(" ")
    for n in range(len(words), 0, -1):
        cand = " ".join(words[:n])
        pos = ans.find(cand)
        if pos != -1 and len(cand) >= 10:
            return cand, pos
    return "", -1


def longest_suffix(wording: str, ans: str) -> tuple:
    """Longest trailing substring of wording found verbatim in ans."""
    words = wording.split(" ")
    for n in range(len(words), 0, -1):
        cand = " ".join(words[-n:])
        pos = ans.find(cand)
        if pos != -1 and len(cand) >= 10:
            return cand, pos + len(cand)
    return "", -1


def demonstrates(item_id: str, span: str) -> bool:
    low = span.lower()
    if item_id == "C2.2":
        install = any(w in low for w in
                      ("install", "replacement", "replace"))
        repair = "repair" in low
        return install and repair
    if item_id == "C1.2":
        return bool(re.search(r"\d\.\d", span))
    return len(span.strip()) >= 10


def find_cases() -> list:
    cases = []
    for p in sorted(glob.glob(
            os.path.join(STUDY_DIR, "*/*/*/muse-observation-*.json"))):
        with open(p, encoding="utf-8") as fh:
            obs = json.load(fh)
        run = os.path.dirname(p)
        with open(os.path.join(run, "muse-spark-response.json"),
                  encoding="utf-8") as fh:
            body = json.load(fh)
        o = muse_api._extract_observation(body)
        ans, ans_n = o["answer_text"], strip_md(o["answer_text"])
        urls = {c["url"] for c in o["citations"]}
        for it in obs["items"]:
            if it["result"] not in ("Pass", "Fail"):
                continue
            w = it["exact_wording"]
            if w in ans or (strip_md(w) in ans_n
                            and it["cited_source"] in urls):
                continue
            cases.append({"path": p, "obs": obs, "item": it,
                          "answer": ans})
    return cases


def propose(case: dict) -> dict:
    it, ans = case["item"], case["answer"]
    w = it["exact_wording"]
    pre, pre_pos = longest_prefix(w, ans)
    suf, suf_end = longest_suffix(w, ans)
    if pre and suf and pre_pos != -1 and suf_end != -1 \
            and suf_end > pre_pos:
        span = ans[pre_pos:suf_end]
        if len(span) <= MAX_SPAN and demonstrates(it["item_id"], span):
            return {"action": "repair", "new_wording": span}
    if pre and demonstrates(it["item_id"], pre):
        return {"action": "repair", "new_wording": pre}
    if suf and demonstrates(it["item_id"], ans[suf_end - len(suf):suf_end]):
        return {"action": "repair",
                "new_wording": ans[suf_end - len(suf):suf_end]}
    return {"action": "downgrade"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    cases = find_cases()
    print("%d spliced quotes" % len(cases))
    n_repair = n_down = 0
    for case in cases:
        prop = propose(case)
        it = case["item"]
        label = "%s %s %s" % (case["path"].split("agent/")[1],
                              case["obs"]["firm"], it["item_id"])
        if prop["action"] == "repair":
            n_repair += 1
            print("  REPAIR   %s\n           -> %r"
                  % (label, prop["new_wording"][:160]))
        else:
            n_down += 1
            print("  DOWNGRADE %s\n           was %r"
                  % (label, it["exact_wording"][:160]))
        if args.dry_run:
            continue
        if prop["action"] == "repair":
            it["exact_wording"] = prop["new_wording"]
        else:
            it["result"] = "Not observed"
            it["exact_wording"] = ""
            it["cited_source"] = ""
            it["reason"] = ("scorer quote was a splice of two fragments, "
                            "not one verbatim span; result not confirmed")
        with open(case["path"], "w", encoding="utf-8") as fh:
            json.dump(case["obs"], fh, indent=2, sort_keys=False)
    print("repair %d, downgrade %d (dry_run=%s)"
          % (n_repair, n_down, args.dry_run))


if __name__ == "__main__":
    main()
