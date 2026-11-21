#!/usr/bin/env python3
"""Collect agent-named additions for the Texas HVAC correlation study.

Reads every run's muse-spark-observation.json under
runs/2026-11-14-study/agent/ and merges the firms_named_not_in_cohort
entries into runs/2026-11-14-study/agent/agent-named-additions.json —
the handoff to the audit stage (plan s.4, DECIDED 14 Nov 2026).

One entry per distinct firm (normalised name + town). A firm the agent
named that is in the 861-firm cohort under ANOTHER town is flagged
cohort_elsewhere (it is already audited for its own town; the audit
worker decides whether a second audit for this town is wanted).
A firm the agent names that is outside Texas or not HVAC is recorded as
a lead only (lead_only, with the reason) — it is NOT added for audit.

Website / address / phone come only from the answer section text or the
run's citations — never guessed. Fields stay null when not identifiable.

Usage:
  python3 collect_additions.py
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY_DIR = os.path.join(HERE, "runs", "2026-11-14-study", "agent")
FIRM_LIST = os.path.join(
    os.path.dirname(HERE),
    "Texas HVAC correlation study — firm list — 2026-11-14 — DRAFT.json")
OUT_PATH = os.path.join(STUDY_DIR, "agent-named-additions.json")

PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}")
URL_RE = re.compile(r"https?://[^\s)>\"]+")
ADDR_RE = re.compile(
    r"(\d{1,5}\s+[A-Za-z][^|\n]{3,80}?TX\s*\d{5})")
ADDR_STREET = re.compile(
    r"\b(Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|"
    r"Court|Ct|Parkway|Pkwy|Highway|Hwy|Way|Circle|Cir|Loop|Trail)\b")
# US state abbreviations other than TX, for the outside-Texas check.
OTHER_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI",
    "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
    "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY", "DC",
}
NON_HVAC_MARKERS = (
    "plumbing only", "plumber", "electrician", "electrical only",
    "roofing only", "roofer", "pest control", "landscap", "pool",
    "appliance repair",
)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ",
                                       (s or "").lower()
                                       .replace("&", " and "))).strip()


def extract_details(section: str, citations: list,
                    heading_address=None) -> dict:
    """Address / phone / website identifiable from the heading tail or
    the section text. Address must match a street-number + TX + ZIP
    pattern; anything else stays null (never guessed)."""
    address = heading_address
    if not address:
        for line in (section or "").splitlines():
            clean = re.sub(r"^[\s>*>`]+", "", line).strip()
            m = ADDR_RE.search(clean)
            if m and ("," in m.group(1) or ADDR_STREET.search(m.group(1))):
                address = m.group(1).strip().rstrip(".").strip()
                break
    phone = None
    m = PHONE_RE.search(section or "")
    if m:
        phone = m.group(0)
    website = None
    urls = URL_RE.findall(section or "")
    if urls:
        website = urls[0]
    return {"address": address, "phone": phone, "website": website}


def classify(name: str, section: str, address: str) -> tuple:
    """(lead_only, reason). Default: an addition — the agent was asked
    for HVAC firms in the town. Only a positive signal makes it a lead."""
    text = ((section or "") + " " + (name or "")).lower()
    if address:
        m = re.search(r",\s*([A-Z]{2})\s*\d{5}", address)
        if m and m.group(1) in OTHER_STATES:
            return True, "address outside Texas (%s)" % m.group(1)
        # State name only in the trailing (city, ST ZIP) part — a street
        # named Louisiana St is not the state of Louisiana.
        tail = address.rsplit(",", 1)[-1].strip().lower()
        if re.search(r"\b(oklahoma|new mexico|louisiana|arkansas)\b",
                     tail):
            return True, "address outside Texas"
    for marker in NON_HVAC_MARKERS:
        if marker in text:
            # "plumbing & HVAC" is still HVAC; only a plumbing-only
            # description (no hvac/air/cooling/heating mention) counts.
            if not re.search(r"\bhvac\b|air conditioning|heating|cooling"
                             r"|\ba/?c\b", text):
                return True, "not HVAC (%s)" % marker
    return False, ""


def main() -> None:
    with open(FIRM_LIST, encoding="utf-8") as fh:
        cohort = json.load(fh)["firms"]
    cohort_names = {norm(f["name"]): f for f in cohort}
    merged = {}
    runs_seen = 0
    for town in sorted(os.listdir(STUDY_DIR)):
        town_dir = os.path.join(STUDY_DIR, town)
        if not os.path.isdir(town_dir) or town.startswith("_"):
            continue
        for task in sorted(os.listdir(town_dir)):
            task_dir = os.path.join(town_dir, task)
            if not os.path.isdir(task_dir):
                continue
            for repeat in sorted(os.listdir(task_dir)):
                run_dir = os.path.join(task_dir, repeat)
                obs_path = os.path.join(run_dir, "muse-spark-observation.json")
                if not os.path.exists(obs_path):
                    continue
                runs_seen += 1
                with open(obs_path, encoding="utf-8") as fh:
                    run = json.load(fh)
                for entry in run.get("firms_named_not_in_cohort") or []:
                    name = entry["name"]
                    key = (norm(name), run["town"])
                    details = extract_details(
                        entry.get("section", ""),
                        run.get("citations") or [],
                        entry.get("heading_address"))
                    lead_only, reason = classify(name, entry.get("section", ""),
                                                 details["address"])
                    run_ref = "%s/%s/%s" % (town, task, repeat)
                    if key not in merged:
                        cohort_hit = cohort_names.get(norm(name))
                        merged[key] = {
                            "firm_name": name,
                            "town": run["town"],
                            "town_zip": run["town_zip"].split(", TX ")[-1]
                            if ", TX " in run["town_zip"] else "",
                            "website": details["website"],
                            "address": details["address"],
                            "phone": details["phone"],
                            "lead_only": lead_only,
                            "reason": reason,
                            "cohort_elsewhere": bool(cohort_hit),
                            "cohort_elsewhere_town": (
                                cohort_hit["town"] if cohort_hit else None),
                            "runs_named_in": [run_ref],
                            "evidence_snippet": (entry.get("section", "")[:600]),
                        }
                    else:
                        rec = merged[key]
                        rec["runs_named_in"].append(run_ref)
                        for field in ("website", "address", "phone"):
                            if not rec[field] and details[field]:
                                rec[field] = details[field]
                        if lead_only and not rec["lead_only"]:
                            rec["lead_only"] = True
                            rec["reason"] = reason
    # Second pass: merge same-town entries where one name is a word
    # prefix of the other ("Ace Air Conditioning" vs "Ace Air
    # Conditioning Company", "Pro Flo Heating and Air" vs "... LLC") —
    # the agent varies the name form run to run for the same firm.
    # The longer name is kept; runs and found fields are unioned.
    merged_list = []
    for e in sorted(merged.values(),
                    key=lambda x: (x["town"], len(x["firm_name"]))):
        target = None
        for m in merged_list:
            if m["town"] != e["town"]:
                continue
            nm, ne = norm(m["firm_name"]), norm(e["firm_name"])
            if nm.startswith(ne) or ne.startswith(nm):
                target = m
                break
        if target is None:
            merged_list.append(e)
            continue
        if len(e["firm_name"]) > len(target["firm_name"]):
            target["firm_name"] = e["firm_name"]
        for field in ("website", "address", "phone"):
            if not target[field] and e[field]:
                target[field] = e[field]
        target["runs_named_in"] = sorted(
            set(target["runs_named_in"]) | set(e["runs_named_in"]))
        if e["lead_only"]:
            target["lead_only"] = True
            target["reason"] = e["reason"]
        if e["cohort_elsewhere"]:
            target["cohort_elsewhere"] = True
            target["cohort_elsewhere_town"] = e["cohort_elsewhere_town"]
        if len(e["evidence_snippet"]) > len(target["evidence_snippet"]):
            target["evidence_snippet"] = e["evidence_snippet"]
    entries = sorted(merged_list,
                     key=lambda e: (e["town"], e["firm_name"].lower()))
    additions = [e for e in entries if not e["lead_only"]]
    leads = [e for e in entries if e["lead_only"]]
    out = {
        "generated": "2026-11-14",
        "runs_scanned": runs_seen,
        "distinct_firms_named_not_in_cohort": len(entries),
        "additions_for_audit": len(additions),
        "leads_only": len(leads),
        "note": ("One entry per distinct firm (name + town). Additions are "
                 "HVAC firms the agent named that serve the town and are "
                 "not in the 861-firm cohort; the audit stage audits and "
                 "scores them. cohort_elsewhere means the firm is in the "
                 "861 under another town. lead_only entries are outside "
                 "Texas or not HVAC and are NOT added. Website/address/"
                 "phone are only what the answer or its citations showed — "
                 "null means not identifiable, never guessed."),
        "entries": entries,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("runs scanned: %d" % runs_seen)
    print("distinct non-cohort firms: %d (%d additions, %d leads only)"
          % (len(entries), len(additions), len(leads)))
    print("wrote %s" % OUT_PATH)


if __name__ == "__main__":
    main()
