"""AI Sharc loader v2 — harness run JSON -> v2.1 audit DB (orchestrator's
import step, Aggregation design Rev 2, s.2-s.3; Spec v2.6 s.13 (accepts legacy v2.1/v2.3/v2.5 files).

Loads, per firm in a run directory:
  <prefix>__audit-data.json     -> firms (if missing) + audits + audit_rows (36 rows)
  <prefix>__delivery-check.json -> delivery_checks (one record per audit, Spec s.4.2)
  <prefix>__summary.json        -> read ONLY for the Spec s.5 Website Access reason
                         (f_reason / unverified_reason); NEVER for grade,
                         points, or counts (those are derived by the
                         audit_summary view from audit_rows).
  (Spec v2.6 s.13 file naming, unchanged from v2.5: <firm_id>__<query_id>__<vendor>-<product>__
  <YYYYMMDDTHHMMSS±hhmm> is the shared prefix. Pre-v2.5 files keep the
  plain audit-data.json / delivery-check.json / summary.json names and
  still load exactly as before, with NO filename check applied to them.)

v2.1 changes from the v1.22 loader:
  * 36 rows per audit: 7 Category results + 21 Items + 8 Ranking
    Suggestions (the six Spec s.9 factors plus C3.2 BBB accreditation
    and rating consistent with bbb.org and C4.1 six-line warranty card,
    which became rows by Tim's decision 2026-11-18, decision 10). NO
    Gate rows (G1 exact name and G6 verifiable listing are scored
    Items; the other four former Gates were absorbed into Items).
    Row type is 'Ranking Suggestion', never 'Ranking lever'.
  * Points are loaded into audit_rows (points_available / points_earned),
    derived from the allocation in definitions.json (aisharc_harness/rules/
    definitions.json): a passed Item (Pass, Pass with warning) earns its
    full allocation; a failed Item earns 0. Category result rows carry the
    Category subtotal (points_available = Category total, points_earned =
    Item-derived subtotal, result 'N of M' or 'N of M points'). Ranking
    Suggestion rows are 0 / 0. Grade / total points / counts are still
    NEVER loaded — they are derived by audit_summary from audit_rows.
  * spec_version must be '2.6' for new audits (Spec v2.6 s.13). Legacy
    '2.1', '2.3' and '2.5' files still load (the 36-row format is a data-format
    change from the 34-row v2.0 format, Spec v2.1 s.13 as amended
    2026-11-18). A v2.6 file carries query_id and checked_at in its run
    record and a Spec v2.6 s.13 filename; the loader checks the filename
    against the run record (firm_id, query_id, vendor, product,
    checked_at as the same instant) and rejects on any mismatch — see
    check_v25_filename. A v2.6 run record carries NO separate
    date_checked / time_checked / timezone fields: checked_at (ISO 8601
    with seconds and offset) is the single identity field. Legacy 2.1/2.3
    files carry no query_id/checked_at and no v2.5 filename, and NO
    filename check is applied to them; their checked_at is stored as
    NULL (seconds were never recorded — never invented). Legacy 2.5
    files carry query_id and checked_at and those are stored as recorded.
  * audits.file_hash is the sha256 of the audit-data.json file bytes
    (loader/DB-side only — the harness cannot hash a file before writing
    it). It is stored on every insert. The duplicate check runs first:
    an exact re-load and a renamed copy (same contents, same identity)
    are both recognised as "already loaded" (no-op, never a second
    audit row) — that is the Spec v2.6 s.13 renamed-copy rule's outcome
    ("even a renamed copy is recognised as already loaded"), and it
    holds for v2.5/v2.6 files exactly as for legacy files, so the 25
    already-loaded Houston audits still re-load as 'already loaded'.
    For a v2.5/v2.6 file whose identity is new, the loader then rejects a
    file whose hash is already present in the DB (guard against the
    same bytes loaded under a different identity). Legacy files get
    no hash or filename check.
  * run.vendor and run.product must be present and non-empty (Tim's
    decision 2026-11-18): which Shopping Agent gathered the audit data.
    Vendor = the corporation (Meta, OpenAI, Anthropic, Google,
    Perplexity, xAI, AI Sharc); Product = the actual tool/agent
    (MUSE-SPARK, Meta AI, ChatGPT Work, ChatGPT Dots, Claude, Gemini,
    harness). Open text, not a closed enum. They are stored on
    audits.vendor / audits.product.
  * audits.website_access_reason is set from summary.json (f_reason /
    unverified_reason), because the grade derivation depends on it: a
    firm-side reason means Grade F, an AI Sharc-side / undecided reason
    means no grade until a re-check. The engine's NOT-IN-BUSINESS maps to
    the DB's CLOSED; UNKNOWN / RENDER-UNDECIDED are stored EXACTLY, not
    mapped to BLOCKED (Spec v2.2 s.4.1.1, Tim's decision 2026-11-19: a
    transient firm-side failure combined with an AI Sharc-side
    rendered-read refusal is unverified, not a firm-side block). The
    exact engine reason is also preserved in evidence_source. A missing
    summary.json leaves the reason NULL with a warning note (the audit
    loads as readable).
  * audit-data.json carries no points and no access reason; the loader
    derives both (points from definitions.json, access reason from
    summary.json) and verifies the harness's Category subtotals against
    the Item rows before inserting.
  * The v2.1 DB has NO agent_observations / agent_observation_rows
    tables, so muse-observation.json is NOT loaded (reported as skipped).
    Observation records stay as files until the Field Mapping Rev 6
    contradiction is settled.
  * Row order (seq_no) is stored verbatim. The harness writes Items first
    (seq 1-21), then Category results (22-28), then Ranking Suggestions
    (29-36: the six Spec s.9 factors, then C3.2 and C4.1); the DB build
    script's test data uses Category-first order.
    Reconciliation counts by row type, not seq order, so either is fine.
  * The M3 Ranking Suggestion label is "Machine discovery (llms.txt)"
    (Spec s.9, definitions.json, and the engine since the 2026-11-18
    alignment). The loader still accepts the old engine form
    ('Machine discovery / llms.txt') as an alias, for runs generated
    before that fix, and stores the harness's exact text.

Rules (Aggregation s.3, enforced here):
  1. All-or-nothing per audit: 1 audits row + exactly 36 audit_rows rows
     in one transaction, then the reconciliation view must read OK for
     that audit. Any mismatch rolls the whole audit back.
  2. A re-check is a new audit (UNIQUE firm_id, query, town_zip,
     checked_at, run_id). A same-day re-run carries a time-qualified
     run_id (date + time, Tim's decision 2026-11-18), so it loads as a
     distinct audit; loading the same run twice is a no-op, never a
     second audit row. audit-data.json files written before the
     time-qualified change carry the date-only run_id (e.g.
     2026-11-18-v21) and no time_checked field; they still load, and
     their run_id is what the duplicate check matches.
  3. Grade / points / counts are NEVER loaded from summary.json. They are
     derived by the audit_summary view from audit_rows. This loader reads
     summary.json ONLY for the Website Access reason (see above).
  4. evidence_source comes from the run record (run file path + run id).
  5. The orchestrator validates before it imports (s.3 rule 7): schema,
     controlled vocabulary (the DB CHECK constraints fail loudly),
     row counts, uniqueness. A file that fails validation is rejected
     with the reason recorded — never imported partially.

Usage:
  python3 load_run.py --db <path-to-aisharc-audit-v2.sqlite> \
      --run-dir runs/2026-11-17 [--dry-run]
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime

EXPECTED = {"Category result": 7, "Item": 21, "Ranking Suggestion": 8}

# Section 4 Ranking Suggestion labels, code-plus-description form
# (Sample Audit Data Rev 4; Spec s.13; Tim's text rule: always the code
# with the description). These are the canonical labels the loader
# expects for C3.2 / C4.1 rows; the plain description forms
# (definitions.json "item" text, no code) are accepted as aliases.
SECTION4_SUGGESTION_LABELS = {
    "C3.2": "C3.2 BBB accreditation and rating consistent with bbb.org",
    "C4.1": "C4.1 six-line warranty card",
}

ITEM_RESULTS = ("Pass", "Pass with warning", "Missing", "Conflict",
                "Not accessible")
CATEGORY_RESULT_RE = re.compile(r"^(\d+) of (\d+)( points)?$")
LEVER_RESULTS = ("Observed", "Recommendation", "Not checked")
# Section 4 Ranking Suggestion results (Spec s.4.3 rule 8, decided by
# Tim 2026-11-18): Complete = the firm already has it; Suggested = the
# firm does not have it; Not checked = the check itself cannot be
# performed. They apply ONLY to C3.2 BBB accreditation and rating
# consistent with bbb.org and C4.1 six-line warranty card. The six
# Section 6 factors keep LEVER_RESULTS.
SECTION4_RESULTS = ("Complete", "Suggested", "Not checked")

# Spec s.5 / DB CHECK values for audits.website_access_reason.
# UNKNOWN / RENDER-UNDECIDED are stored exactly (Spec v2.2 s.4.1.1,
# Tim's decision 2026-11-19): an undecided engine reason must NOT be
# mapped to BLOCKED — a transient firm-side failure combined with an
# AI Sharc-side rendered-read refusal is unverified, not a firm-side
# block. (Before v2.2 the loader mapped them to BLOCKED as "the closest
# undecided code"; audit 16 keeps its recorded BLOCKED value, the new
# rule applies going forward.)
DB_ACCESS_REASONS = ("CERT-INVALID", "PARKED", "DEAD", "SUSPENDED",
                     "WRONG-CONTENT", "NO-WEBSITE", "CLOSED",
                     "APPROVAL-EXPIRED", "PROXY-REFUSED", "BLOCKED",
                     "JS-ONLY", "UNKNOWN", "RENDER-UNDECIDED")


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _slug_segment(value: str) -> str:
    """Lowercase, all non-alphanumerics removed (e.g. 'AI Sharc' ->
    'aisharc'). MUST match run_audit._slug_segment: the loader checks a
    v2.5/v2.6 filename's vendor-product segment against the run record's
    vendor/product through this same rule."""
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


# Spec v2.6 s.13 filename (unchanged from v2.5):
# <firm_id>__<query_id>__<vendor>-<product>__<YYYYMMDDTHHMMSS±hhmm>__audit-data.json
# The timestamp keeps the ISO 'T' separator (never lowercased); the
# query_id is all lowercase. firm_id / query_id / vendor / product slugs
# carry no underscores, so '__' splits the four segments exactly.
V25_FILENAME_RE = re.compile(
    r"^(?P<firm_id>[^_]+)__(?P<query_id>[^_]+)__"
    r"(?P<vendor>[^-]+)-(?P<product>[^_]+)__"
    r"(?P<timestamp>\d{8}T\d{6}[+-]\d{4})__audit-data\.json$")
QUERY_ID_RE = re.compile(r"^[a-z]+-[a-z0-9]+-\d{5}-t[123]$")


def parse_v25_filename(filename: str) -> dict:
    """Parse a Spec v2.6 s.13 audit-data filename into its segments.
    Raises ValueError when the name is not a v2.6 filename. (Kept the
    v25 name: the filename scheme was introduced in v2.5 and is
    unchanged in v2.6.)"""
    m = V25_FILENAME_RE.match(os.path.basename(filename or ""))
    _check(m is not None,
           "filename %r is not a Spec v2.6 s.13 audit-data filename "
           "(expected <firm_id>__<query_id>__<vendor>-<product>__"
           "<YYYYMMDDTHHMMSS±hhmm>__audit-data.json)" % filename)
    try:
        ts = datetime.strptime(m.group("timestamp"), "%Y%m%dT%H%M%S%z")
    except ValueError:
        raise ValueError(
            "filename %r has an unparseable timestamp %r"
            % (filename, m.group("timestamp")))
    return {"firm_id": m.group("firm_id"), "query_id": m.group("query_id"),
            "vendor": m.group("vendor"), "product": m.group("product"),
            "timestamp": ts, "timestamp_raw": m.group("timestamp")}


def check_v25_filename(filename: str, run: dict) -> None:
    """Check a v2.5/v2.6 audit-data filename against its run record. Each
    segment must agree with the file's contents: firm_id, query_id,
    vendor, product, and the timestamp as the same instant as
    checked_at. A v2.5 run record also carries date_checked, which must
    fall on the checked_at date; a v2.6 run record carries no separate
    date_checked (checked_at is the single identity field), so that
    cross-check runs only when the field is present. Raises
    ValueError naming the mismatched field on any disagreement. Applies
    to spec_version 2.5 and 2.6 files ONLY — legacy files are never checked."""
    parsed = parse_v25_filename(filename)
    _check(parsed["firm_id"] == run["firm_id"],
           "filename firm_id %r != run firm_id %r"
           % (parsed["firm_id"], run["firm_id"]))
    _check(QUERY_ID_RE.match(run.get("query_id") or "") is not None,
           "run query_id %r is not a Spec v2.5/v2.6 query_id "
           "(<trade>-<town>-<zip>-t<task>, all lowercase)"
           % run.get("query_id"))
    _check(parsed["query_id"] == run["query_id"],
           "filename query_id %r != run query_id %r"
           % (parsed["query_id"], run["query_id"]))
    _check(parsed["vendor"] == _slug_segment(run.get("vendor")),
           "filename vendor %r != run vendor %r (slug %r)"
           % (parsed["vendor"], run.get("vendor"),
              _slug_segment(run.get("vendor"))))
    _check(parsed["product"] == _slug_segment(run.get("product")),
           "filename product %r != run product %r (slug %r)"
           % (parsed["product"], run.get("product"),
              _slug_segment(run.get("product"))))
    try:
        checked_at = datetime.fromisoformat(run.get("checked_at") or "")
    except ValueError:
        raise ValueError("run checked_at %r is not ISO 8601"
                         % run.get("checked_at"))
    _check(checked_at.tzinfo is not None,
           "run checked_at %r carries no UTC offset" % run.get("checked_at"))
    _check(parsed["timestamp"] == checked_at,
           "filename timestamp %r != run checked_at %r (not the same instant)"
           % (parsed["timestamp_raw"], run.get("checked_at")))
    if run.get("date_checked") not in (None, ""):
        # v2.5 files only: v2.6 run records carry no date_checked.
        _check(run.get("date_checked") == checked_at.date().isoformat(),
               "run date_checked %r != checked_at date %r"
               % (run.get("date_checked"), checked_at.date().isoformat()))


def find_named_file(firm_dir: str, kind: str) -> str | None:
    """The path of one per-firm file, new (v2.5/v2.6) name first, legacy name
    as fallback. kind is one of 'audit-data', 'summary', 'human-review',
    'delivery-check'. Returns None when neither exists."""
    if os.path.isdir(firm_dir):
        new_names = sorted(
            f for f in os.listdir(firm_dir)
            if f.endswith("__%s.json" % kind))
        if new_names:
            return os.path.join(firm_dir, new_names[0])
    legacy = os.path.join(firm_dir, "%s.json" % kind)
    return legacy if os.path.exists(legacy) else None


def find_all_named_files(firm_dir: str, kind: str) -> list:
    """Every per-firm file of one kind, new (v2.5/v2.6) names first.

    Audit-per-query (Spec v2.6 s.13): a firm named in several queries has
    one <prefix>__<kind>.json per query in its dir; all of them are
    returned, sorted, so each query audit is loaded as its own audit. A
    legacy single <kind>.json is returned on its own when no new-named
    files exist. Returns [] when neither exists."""
    if os.path.isdir(firm_dir):
        new_names = sorted(
            f for f in os.listdir(firm_dir)
            if f.endswith("__%s.json" % kind))
        if new_names:
            return [os.path.join(firm_dir, f) for f in new_names]
    legacy = os.path.join(firm_dir, "%s.json" % kind)
    return [legacy] if os.path.exists(legacy) else []


def _prefix_of(path: str, kind: str) -> str:
    """The <prefix> of a <prefix>__<kind>.json name ('' for a legacy name)."""
    base = os.path.basename(path)
    suffix = "__%s.json" % kind
    if base.endswith(suffix):
        return base[: -len(suffix)]
    return ""


def find_file_for_prefix(firm_dir: str, kind: str, prefix: str) -> str | None:
    """The <prefix>__<kind>.json in a firm dir (legacy <kind>.json when
    the prefix is ''), or None when it does not exist."""
    if prefix:
        path = os.path.join(firm_dir, "%s__%s.json" % (prefix, kind))
        return path if os.path.exists(path) else None
    legacy = os.path.join(firm_dir, "%s.json" % kind)
    return legacy if os.path.exists(legacy) else None


def _summarise_statuses(statuses: list) -> str:
    """One status string for a firm's audits: the single status when they
    all agree, otherwise each distinct status with its count."""
    if not statuses:
        return "skipped"
    counts = {}
    for s in statuses:
        counts[s] = counts.get(s, 0) + 1
    if len(counts) == 1:
        return statuses[0]
    return ", ".join("%s x%d" % (s, c) for s, c in sorted(counts.items()))


def load_allocation(defs_path: str) -> dict:
    """Allocation v2 from the harness's definitions.json.

    Returns item_points {item_id: points}, item_category {item_id:
    category}, category_points {category: total}, and suggestion_labels
    (the eight Spec s.6.10 Ranking Suggestion labels, in order: the six
    Spec s.9 factors from "levers", then the two un-scored Section 4
    suggestions in their canonical code-plus-description form —
    "C3.2 BBB accreditation and rating consistent with bbb.org" and
    "C4.1 six-line warranty card" (Sample Audit Data Rev 4). The two
    Section 4 ids are validated against definitions.json "items" where
    scored=False and type='Ranking Suggestion'.)"""
    with open(defs_path, encoding="utf-8") as fh:
        defs = json.load(fh)
    item_points = {}
    item_category = {}
    for it in defs.get("items", []):
        if it.get("scored"):
            _check(it["id"] not in item_points,
                   "duplicate scored Item %r" % it["id"])
            item_points[it["id"]] = it["points"]
            item_category[it["id"]] = it["category"]
    _check(len(item_points) == 21,
           "expected 21 scored Items, got %d" % len(item_points))
    _check(sum(item_points.values()) == 100,
           "allocation total %d != 100" % sum(item_points.values()))
    category_points = {}
    for item_id, points in item_points.items():
        cat = item_category[item_id]
        category_points[cat] = category_points.get(cat, 0) + points
    _check(len(category_points) == 7,
           "expected 7 Categories, got %d" % len(category_points))
    suggestion_labels = [lv["lever"] for lv in defs.get("levers", [])]
    _check(len(suggestion_labels) == 6,
           "expected 6 Spec s.9 Ranking Suggestions, got %d"
           % len(suggestion_labels))
    # The two Section 4 Ranking Suggestions (C3.2, C4.1) became Audit Data
    # rows by Tim's decision 2026-11-18 (decision 10): they are un-scored
    # Items in definitions.json (scored=False, type 'Ranking Suggestion',
    # 0 points). Their labels are the code-plus-description form from
    # Sample Audit Data Rev 4 (Tim's text rule: always the code with the
    # description, never a bare code): "C3.2 BBB accreditation and rating
    # consistent with bbb.org" and "C4.1 six-line warranty card". The
    # plain description forms (definitions.json "item" text, no code)
    # are accepted as aliases and stored as written; the set check below
    # canonicalises through the alias map.
    section4_ids = [it["id"] for it in defs.get("items", [])
                    if not it.get("scored")
                    and it.get("type") == "Ranking Suggestion"]
    _check(len(section4_ids) == 2,
           "expected 2 Section 4 Ranking Suggestions, got %d"
           % len(section4_ids))
    _check(sorted(section4_ids) == ["C3.2", "C4.1"],
           "Section 4 Ranking Suggestions are %s, expected C3.2/C4.1"
           % sorted(section4_ids))
    suggestion_labels = suggestion_labels + [
        SECTION4_SUGGESTION_LABELS[i] for i in ("C3.2", "C4.1")]
    _check(len(suggestion_labels) == 8,
           "expected 8 Ranking Suggestions, got %d"
           % len(suggestion_labels))
    # The M3 Ranking Suggestion label is "Machine discovery (llms.txt)"
    # (Spec s.9, definitions.json, and the engine since the 2026-11-18
    # alignment to the Spec form). The old engine form ("Machine discovery
    # / llms.txt") is kept as an accepted alias so runs generated before
    # the fix still load; the stored label is the harness's exact text.
    # Likewise the plain description forms of the Section 4 suggestions
    # (no code) are accepted as aliases of the canonical
    # code-plus-description labels.
    suggestion_label_aliases = {
        "Machine discovery / llms.txt": "Machine discovery (llms.txt)",
        "BBB accreditation and rating consistent with bbb.org":
            "C3.2 BBB accreditation and rating consistent with bbb.org",
        "Six-line warranty card": "C4.1 six-line warranty card",
    }
    return {"item_points": item_points, "item_category": item_category,
            "category_points": category_points,
            "suggestion_labels": suggestion_labels,
            "suggestion_label_aliases": suggestion_label_aliases,
            "suggestion_labels_accepted":
                set(suggestion_labels) | set(suggestion_label_aliases)}


def validate_audit_data(data: dict, alloc: dict) -> list:
    """Schema + vocabulary + row-count + points validation for
    audit-data.json. Returns the 36 rows normalised to audit_rows
    columns (with points_available / points_earned derived)."""
    run = data.get("run") or {}
    for field in ("firm", "firm_id", "query", "town_zip",
                  "spec_version", "evidence_source", "run_id"):
        _check(run.get(field) not in (None, ""),
               "run record missing %s" % field)
    _check(run["spec_version"] in ("2.1", "2.3", "2.5", "2.6"),
           "spec_version %r is not a v2.1, v2.3, v2.5 or v2.6 audit "
           "(expected '2.1', '2.3', '2.5' or '2.6')"
           % run["spec_version"])
    if run["spec_version"] in ("2.1", "2.3", "2.5"):
        # Legacy run records carry a separate date_checked (a v2.6 run
        # record does not: checked_at is its single identity field).
        _check(run.get("date_checked") not in (None, ""),
               "run record missing date_checked")
    if run["spec_version"] in ("2.5", "2.6"):
        # A v2.5/v2.6 run record carries query_id and checked_at (Spec
        # v2.5/v2.6 s.13). Checked here, after spec_version, so a pre-2.5
        # file is still rejected on spec_version first, not on these fields.
        _check(run.get("query_id") not in (None, ""),
               "run record missing query_id (Spec v2.5/v2.6 s.13: "
               "<trade>-<town>-<zip>-t<task>, all lowercase)")
        _check(QUERY_ID_RE.match(run.get("query_id") or "") is not None,
               "run query_id %r is not a Spec v2.5/v2.6 query_id "
               "(<trade>-<town>-<zip>-t<task>, all lowercase)"
               % run.get("query_id"))
        _check(run.get("checked_at") not in (None, ""),
               "run record missing checked_at (Spec v2.5/v2.6 s.13: ISO 8601 "
               "with seconds and offset, e.g. 2026-11-18T17:13:00-06:00)")
        try:
            _checked = datetime.fromisoformat(run["checked_at"])
        except ValueError:
            raise ValueError("run checked_at %r is not ISO 8601"
                             % run.get("checked_at"))
        _check(_checked.tzinfo is not None,
               "run checked_at %r carries no UTC offset"
               % run.get("checked_at"))
    # Vendor / Product (Tim's decision 2026-11-18): which Shopping Agent
    # gathered the audit data. Checked AFTER spec_version, so a pre-2.1
    # file is still rejected on spec_version first, not on vendor.
    _check(run.get("vendor") not in (None, ""),
           "run record missing vendor (Vendor = the corporation that "
           "gathered this audit, e.g. Meta, OpenAI, AI Sharc)")
    _check(run.get("product") not in (None, ""),
           "run record missing product (Product = the tool/agent that "
           "gathered this audit, e.g. MUSE-SPARK, Meta AI, harness)")
    rows = data.get("rows") or []
    _check(len(rows) == 36, "expected 36 rows, got %d" % len(rows))
    counts = {"Category result": 0, "Item": 0, "Ranking Suggestion": 0}
    seen_seq = set()
    seen_items = set()
    seen_categories = set()
    seen_suggestions = set()
    item_points = alloc["item_points"]
    item_category = alloc["item_category"]
    category_points = alloc["category_points"]
    earned_by_category = {cat: 0 for cat in category_points}
    normalised = []
    for row in rows:
        rt = row.get("Row type")
        _check(rt in counts, "unknown Row type %r" % (rt,))
        counts[rt] += 1
        seq = row.get("#")
        _check(isinstance(seq, int) and 1 <= seq <= 36,
               "seq_no %r out of range 1-36" % (seq,))
        _check(seq not in seen_seq, "duplicate seq_no %d" % seq)
        seen_seq.add(seq)
        result = row.get("Item result")
        cat_gate = row.get("Report Card Category / Gate")
        item = row.get("Item")
        _check(isinstance(cat_gate, str) and cat_gate,
               "row seq %d missing Report Card Category / Gate" % seq)
        _check(isinstance(item, str) and item,
               "row seq %d missing Item" % seq)
        if rt == "Item":
            _check(result in ITEM_RESULTS,
                   "Item result %r (seq %d)" % (result, seq))
            item_id = item.split()[0]
            _check(item_id in item_points,
                   "unknown scored Item %r (seq %d)" % (item_id, seq))
            _check(item_id not in seen_items,
                   "duplicate Item %s" % item_id)
            seen_items.add(item_id)
            _check(cat_gate == item_category[item_id],
                   "Item %s in Category %r, expected %r"
                   % (item_id, cat_gate, item_category[item_id]))
            available = item_points[item_id]
            earned = available if result in ("Pass", "Pass with warning") \
                else 0
            earned_by_category[cat_gate] += earned
            points_available, points_earned = available, earned
        elif rt == "Category result":
            _check(cat_gate in category_points,
                   "unknown Category %r (seq %d)" % (cat_gate, seq))
            _check(cat_gate not in seen_categories,
                   "duplicate Category result %s" % cat_gate)
            seen_categories.add(cat_gate)
            m = CATEGORY_RESULT_RE.match(result or "")
            _check(m is not None,
                   "Category result %r is not 'N of M' (seq %d)"
                   % (result, seq))
            earned, available = int(m.group(1)), int(m.group(2))
            _check(available == category_points[cat_gate],
                   "Category %s available %d, expected %d"
                   % (cat_gate, available, category_points[cat_gate]))
            _check(0 <= earned <= available,
                   "Category %s earned %d out of %d"
                   % (cat_gate, earned, available))
            points_available, points_earned = available, earned
        else:  # Ranking Suggestion
            _check(cat_gate == "Ranking Suggestion",
                   "Ranking Suggestion row seq %d has Category %r"
                   % (seq, cat_gate))
            _check(item in alloc["suggestion_labels_accepted"],
                   "unknown Ranking Suggestion %r (seq %d)" % (item, seq))
            _check(item not in seen_suggestions,
                   "duplicate Ranking Suggestion %r" % item)
            seen_suggestions.add(item)
            # The two vocabularies are enforced per row (Spec s.4.3 rule 8,
            # s.7): the Section 4 rows (C3.2 BBB accreditation and rating
            # consistent with bbb.org, C4.1 six-line warranty card) use
            # Complete / Suggested / Not checked; the six Section 6 factors
            # use Observed / Recommendation / Not checked.
            canonical = alloc["suggestion_label_aliases"].get(item, item)
            if canonical in SECTION4_SUGGESTION_LABELS.values():
                _check(result in SECTION4_RESULTS,
                       "Section 4 Ranking Suggestion result %r (seq %d); "
                       "expected Complete, Suggested, or Not checked"
                       % (result, seq))
            else:
                _check(result in LEVER_RESULTS,
                       "Ranking Suggestion result %r (seq %d)"
                       % (result, seq))
            points_available, points_earned = 0, 0
        normalised.append({
            "seq_no": seq,
            "stage": row.get("Stage", ""),
            "row_type": rt,
            "category_or_gate": cat_gate,
            "item": item,
            "result": result,
            "points_available": points_available,
            "points_earned": points_earned,
            "source_url": row.get("Source URL", ""),
            "evidence_note": row.get("Evidence note", ""),
            "why_it_matters": row.get("Why it matters", ""),
            "website_change": row.get("Website change", ""),
            "listing_change": row.get("Listing change", ""),
            "operational_change": row.get("Operational change", ""),
            "fix_priority": row.get("Fix priority", ""),
            "counts_toward": row.get("Counts toward", ""),
            "populates": row.get("Populates", ""),
        })
    _check(counts == EXPECTED, "row composition %s != %s" % (counts, EXPECTED))
    _check(seen_items == set(item_points),
           "Item set mismatch: missing %s, extra %s"
           % (sorted(set(item_points) - seen_items),
              sorted(seen_items - set(item_points))))
    _check(seen_categories == set(category_points),
           "Category set mismatch: %s" % sorted(seen_categories))
    _check({alloc["suggestion_label_aliases"].get(s, s)
            for s in seen_suggestions}
           == set(alloc["suggestion_labels"]),
           "Ranking Suggestion set mismatch: %s"
           % sorted(seen_suggestions))
    # The harness's Category subtotals must match the Item rows.
    for cat, earned in earned_by_category.items():
        stored = next(r for r in normalised
                      if r["row_type"] == "Category result"
                      and r["category_or_gate"] == cat)
        _check(stored["points_earned"] == earned,
               "Category %s subtotal %d, Item rows give %d"
               % (cat, stored["points_earned"], earned))
    return normalised


def map_access_reason(f_reason: str, unverified_reason: str) -> tuple:
    """Map the engine's access reason to the DB's website_access_reason.

    Returns (db_reason, exact_engine_reason). The engine's
    NOT-IN-BUSINESS is the DB's CLOSED; every other engine reason is
    stored exactly as the engine reported it. In particular UNKNOWN /
    RENDER-UNDECIDED are stored as UNKNOWN / RENDER-UNDECIDED, NOT
    mapped to BLOCKED (Spec v2.2 s.4.1.1, Tim's decision 2026-11-19:
    an undecided reason is unverified, not a firm-side block). The
    caller preserves the exact engine reason in evidence_source."""
    if f_reason:
        if f_reason == "NOT-IN-BUSINESS":
            return "CLOSED", f_reason
        if f_reason in DB_ACCESS_REASONS:
            return f_reason, f_reason
        raise ValueError("unknown f_reason %r" % f_reason)
    if unverified_reason:
        if unverified_reason in DB_ACCESS_REASONS:
            return unverified_reason, unverified_reason
        raise ValueError("unknown unverified_reason %r"
                         % unverified_reason)
    return None, ""


def read_access_reason(firm_dir: str, prefix: str | None = None) -> tuple:
    """Website Access reason for one firm, from summary.json.

    summary.json is read ONLY for f_reason / unverified_reason (Spec
    s.5); grade / points / counts are never read from it. Returns
    (website_access_reason, exact_engine_reason, warning_note). A
    missing summary.json leaves the reason NULL (assumed readable) with
    a warning note. The v2.5/v2.6 name (<prefix>__summary.json) is looked up
    first, the legacy summary.json second. When a prefix is given (a firm
    with several query audits), the summary with that prefix is read, so
    each query audit gets its own access reason."""
    if prefix is None:
        path = find_named_file(firm_dir, "summary")
    else:
        path = find_file_for_prefix(firm_dir, "summary", prefix)
    if path is None:
        return (None, "",
                "summary.json missing; website_access_reason left NULL "
                "(assumed readable)")
    with open(path, encoding="utf-8") as fh:
        summary = json.load(fh)
    f_reason = (summary.get("f_reason") or "").strip()
    unverified_reason = (summary.get("unverified_reason") or "").strip()
    reason, exact = map_access_reason(f_reason, unverified_reason)
    return reason, exact, ""


def load_firm(db_path: str, run_dir: str, firm_id: str,
              registry: dict, alloc: dict, dry_run: bool = False) -> dict:
    """Load one firm's outputs. Returns a report dict.

    Audit-per-query (Spec v2.6 s.13): a firm named in several queries has
    one audit-data.json per query in its dir; every one is loaded as its
    own audit (distinct query / checked_at / run_id), each with its own
    delivery check and access reason matched by filename prefix. A firm
    with a single audit behaves exactly as before."""
    firm_dir = os.path.join(run_dir, firm_id)
    report = {"firm_id": firm_id, "audit": "skipped", "delivery": "skipped",
              "observation": "skipped", "notes": []}
    audit_paths = find_all_named_files(firm_dir, "audit-data")
    if not audit_paths:
        report["notes"].append(
            "no audit-data.json (neither <prefix>__audit-data.json nor "
            "audit-data.json)")
        return report
    # Read + validate every audit file up front, so a bad file fails fast
    # before any DB write. Each item carries its own run record, rows,
    # file hash, and the access reason from its matching summary.json.
    parsed = []
    for audit_path in audit_paths:
        with open(audit_path, "rb") as fh:
            audit_bytes = fh.read()
        # file_hash: sha256 of the audit-data.json file bytes (Spec v2.6
        # s.13, loader/DB-side only). Computed for every file, stored on
        # every insert; the duplicate-hash rejection below applies to v2.5
        # and v2.6 files only (legacy files keep their existing no-op
        # re-load).
        file_hash = hashlib.sha256(audit_bytes).hexdigest()
        data = json.loads(audit_bytes.decode("utf-8"))
        rows = validate_audit_data(data, alloc)
        run = data["run"]
        prefix = _prefix_of(audit_path, "audit-data")
        website_access_reason, exact_reason, warning = read_access_reason(
            firm_dir, prefix)
        if warning:
            report["notes"].append(warning)
        parsed.append({
            "audit_path": audit_path, "prefix": prefix,
            "file_hash": file_hash, "rows": rows, "run": run,
            "website_access_reason": website_access_reason,
            "exact_reason": exact_reason,
        })
    if len(parsed) > 1:
        report["notes"].append(
            "queries: %s" % ", ".join(p["run"].get("query_id", "?")
                                      for p in parsed))

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        # Resolve the firm once, from the first audit's run record. (All
        # of one firm's query audits carry the same firm name.)
        first_run = parsed[0]["run"]
        firm_row = con.execute(
            "SELECT firm_id FROM firms WHERE name = ?", (first_run["firm"],)
        ).fetchone()
        db_firm_id = firm_row[0] if firm_row else None
        if firm_row is None:
            reg = registry.get(firm_id, {})
            if not dry_run:
                con.execute(
                    "INSERT INTO firms (name, primary_business_category, "
                    "trade, website_url, meta_place_id) VALUES (?,?,?,?,?)",
                    (first_run["firm"],
                     first_run.get("primary_business_category"),
                     reg.get("trade", "HVAC"), first_run.get("website"),
                     first_run.get("meta_place_id")))
                firm_row = con.execute(
                    "SELECT firm_id FROM firms WHERE name = ?",
                    (first_run["firm"],)).fetchone()
            report["notes"].append("firm inserted (was not in firms)")
            db_firm_id = firm_row[0] if firm_row else None

        audit_statuses = []
        delivery_statuses = []
        for item in parsed:
            audit_path = item["audit_path"]
            file_hash = item["file_hash"]
            rows = item["rows"]
            run = item["run"]
            website_access_reason = item["website_access_reason"]
            exact_reason = item["exact_reason"]
            # Duplicate check FIRST, before the v2.5/v2.6 hash/filename
            # checks: an exact re-load and a renamed copy (same contents,
            # same identity) are both recognised as "already loaded"
            # (no-op), which is the Spec v2.6 s.13 renamed-copy rule's
            # outcome ("even a renamed copy is recognised as already
            # loaded"). Loader idempotency is preserved for v2.5/v2.6
            # files exactly as for legacy files. The hash check below is
            # a guard for the case where the identity is new but the hash
            # is already present.
            # checked_at is the DB identity field (Spec v2.6 s.13): the
            # run record's checked_at for v2.5/v2.6 files, NULL for
            # v2.1/v2.3 files (seconds were never recorded — never
            # invented). The comparison is NULL-safe: `checked_at = NULL`
            # never matches in SQL, so a legacy re-load must match on IS
            # NULL instead.
            checked_at = run.get("checked_at") or None
            existing = None
            if db_firm_id is not None:
                existing = con.execute(
                    "SELECT audit_id FROM audits WHERE firm_id = ? AND query = ? "
                    "AND town_zip = ? AND (checked_at = ? OR (checked_at IS NULL "
                    "AND ? IS NULL)) AND run_id = ?",
                    (db_firm_id, run["query"], run["town_zip"],
                     checked_at, checked_at, run["run_id"])).fetchone()
            if existing is None and run["spec_version"] in ("2.5", "2.6"):
                dup_hash = con.execute(
                    "SELECT audit_id FROM audits WHERE file_hash = ?",
                    (file_hash,)).fetchone()
                _check(dup_hash is None,
                       "file hash %s already present in the DB (audit %d): "
                       "this file is a copy of an audit already loaded "
                       "(renamed-copy rule, Spec v2.6 s.13)"
                       % (file_hash, dup_hash[0] if dup_hash else -1))
                check_v25_filename(audit_path, run)
            if existing is not None:
                audit_statuses.append("already loaded")
                audit_id = existing[0]
            else:
                if dry_run:
                    audit_statuses.append("would load")
                    audit_id = None
                else:
                    evidence_source = "%s (run %s)" % (
                        run["evidence_source"], run["run_id"])
                    if exact_reason and exact_reason != website_access_reason:
                        evidence_source += ("; engine access reason: %s"
                                            % exact_reason)
                    # Spec v2.8 s.13: a loaded audit is a raw audit by
                    # definition — one agent's or the harness's own audit,
                    # as loaded. audit_role='raw' and an empty
                    # consolidated_from are written explicitly here, not
                    # left to the column default; consolidated_from is set
                    # only when an official (consolidated) audit is
                    # created, never by the loader.
                    cur = con.execute(
                        "INSERT INTO audits (firm_id, query, query_id, town_zip, "
                        "checked_at, run_id, spec_version, vendor, product, "
                        "website_access_reason, file_hash, "
                        "evidence_source, audit_role, consolidated_from) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (db_firm_id, run["query"], run.get("query_id"),
                         run["town_zip"], checked_at, run["run_id"],
                         run["spec_version"],
                         run["vendor"], run["product"],
                         website_access_reason, file_hash, evidence_source,
                         "raw", None))
                    audit_id = cur.lastrowid
                    for r in rows:
                        con.execute(
                            "INSERT INTO audit_rows (audit_id, seq_no, stage, "
                            "row_type, category_or_gate, item, result, "
                            "points_available, points_earned, source_url, "
                            "evidence_note, why_it_matters, website_change, "
                            "listing_change, operational_change, fix_priority, "
                            "counts_toward, populates) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (audit_id, r["seq_no"], r["stage"], r["row_type"],
                             r["category_or_gate"], r["item"], r["result"],
                             r["points_available"], r["points_earned"],
                             r["source_url"], r["evidence_note"],
                             r["why_it_matters"], r["website_change"],
                             r["listing_change"], r["operational_change"],
                             r["fix_priority"], r["counts_toward"],
                             r["populates"]))
                    rec = con.execute(
                        "SELECT reconciliation FROM reconciliation "
                        "WHERE audit_id = ?", (audit_id,)).fetchone()
                    if not rec or rec[0] != "OK":
                        raise ValueError(
                            "reconciliation %s for audit %d"
                            % (rec[0] if rec else "missing", audit_id))
                    audit_statuses.append("loaded")

            # Delivery check (one record per audit, never scored), matched
            # to this audit by filename prefix.
            dc_path = find_file_for_prefix(firm_dir, "delivery-check",
                                           item["prefix"])
            if dc_path is not None and (audit_id is not None or dry_run):
                with open(dc_path, encoding="utf-8") as fh:
                    dc = json.load(fh)
                has = None
                if audit_id is not None:
                    has = con.execute(
                        "SELECT 1 FROM delivery_checks WHERE audit_id = ?",
                        (audit_id,)).fetchone()
                if has:
                    delivery_statuses.append("already loaded")
                elif dry_run:
                    delivery_statuses.append("would load")
                else:
                    con.execute(
                        "INSERT INTO delivery_checks (audit_id, "
                        "published_business_email, collection_method, "
                        "do_not_harvest_notice_present, notice_wording_page, "
                        "notice_type, can_spam_requirements_met, "
                        "delivery_route, note) VALUES (?,?,?,?,?,?,?,?,?)",
                        (audit_id, dc.get("published_business_email", ""),
                         dc.get("collection_method", ""),
                         dc.get("do_not_harvest_notice_present", ""),
                         dc.get("notice_wording_page", ""),
                         dc.get("notice_type", ""),
                         dc.get("can_spam_requirements_met", ""),
                         dc.get("delivery_route", ""),
                         dc.get("note", "")))
                    delivery_statuses.append("loaded")

        report["audit"] = _summarise_statuses(audit_statuses)
        report["delivery"] = _summarise_statuses(delivery_statuses)

        # Per-agent observation: NOT loaded. The v2.1 DB has no
        # agent_observations / agent_observation_rows tables; observation
        # records stay as files until the Field Mapping Rev 6
        # contradiction is settled.
        obs_path = os.path.join(firm_dir, "muse-observation.json")
        if os.path.exists(obs_path):
            report["notes"].append(
                "muse-observation.json present but not loaded "
                "(no observation tables in v2.1 DB)")
        if not dry_run:
            con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True,
                        help="path to aisharc-audit-v2.sqlite")
    parser.add_argument("--run-dir", required=True,
                        help="run directory, e.g. runs/2026-11-17")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate only, write nothing")
    args = parser.parse_args()
    if not os.path.exists(args.db):
        print("DB not found: %s" % args.db)
        sys.exit(2)
    if not os.path.isdir(args.run_dir):
        print("run dir not found: %s" % args.run_dir)
        sys.exit(2)
    harness_dir = os.path.dirname(os.path.abspath(__file__))
    alloc = load_allocation(os.path.join(
        harness_dir, "aisharc_harness", "rules", "definitions.json"))
    with open(os.path.join(harness_dir, "firms.json"),
              encoding="utf-8") as fh:
        registry = {f["firm_id"]: f for f in json.load(fh)["firms"]}
    firm_ids = sorted(d for d in os.listdir(args.run_dir)
                      if os.path.isdir(os.path.join(args.run_dir, d)))
    print("loading %d firm dirs from %s (dry_run=%s)"
          % (len(firm_ids), args.run_dir, args.dry_run))
    failed = 0
    for fid in firm_ids:
        try:
            rep = load_firm(args.db, args.run_dir, fid, registry, alloc,
                            dry_run=args.dry_run)
            print("  %-16s audit=%-14s delivery=%-14s observation=%s%s"
                  % (fid, rep["audit"], rep["delivery"], rep["observation"],
                     (" (%s)" % "; ".join(rep["notes"])) if rep["notes"] else ""))
        except Exception as exc:  # noqa: BLE001 - report and continue
            failed += 1
            print("  %-16s FAILED: %s" % (fid, exc))
    print("done: %d firms, %d failed" % (len(firm_ids), failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
