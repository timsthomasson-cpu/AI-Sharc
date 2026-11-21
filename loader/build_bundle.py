#!/usr/bin/env python3
"""Validate harness audit files and build a load bundle for public.load_audit_bundle().

Usage: build_bundle.py <run_dir> <out.json>
  <run_dir> holds, per audit, <prefix>__audit-data.json, __summary.json and __delivery-check.json
  (any folder layout; files are found by name).

Checks (Spec v2.9 §13): filename pattern, query_id pattern, checked_at ISO 8601 with seconds and
offset equal to the filename timestamp, vendor/product/spec_version present, 36 rows (7/21/8),
controlled vocabulary, a source URL on every Item row except Not accessible / Not completed.
A file that fails any check is rejected and reported; it is not put in the bundle.
"""
import hashlib, json, pathlib, re, sys

PAT = re.compile(r'^([a-z0-9-]+)__([a-z]+-[a-z0-9]+-\d{5}-t[123])__([a-z0-9-]+)-([a-z0-9-]+)__(\d{8}T\d{6}[+-]\d{4})__audit-data\.json$')
ISO = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$')
ITEM = {"Pass", "Pass with warning", "Missing", "Conflict", "Not accessible", "Not completed"}
RS = {"Observed", "Recommendation", "Not checked", "Complete", "Suggested"}
COLS = [("seq_no", "#"), ("stage", "Stage"), ("row_type", "Row type"), ("category_or_gate", "Report Card Category / Gate"),
        ("item", "Item"), ("result", "Item result"), ("source_url", "Source URL"), ("evidence_note", "Evidence note"),
        ("why_it_matters", "Why it matters"), ("website_change", "Website change"), ("listing_change", "Listing change"),
        ("operational_change", "Operational change"), ("fix_priority", "Fix priority"), ("counts_toward", "Counts toward"),
        ("populates", "Populates")]
TRADES = {"hvac": "HVAC", "plumbing": "Plumbing", "electrical": "Electrical", "roofing": "Roofing"}

def compact(ts):
    return ts[:10].replace('-', '') + 'T' + ts[11:19].replace(':', '') + ts[19:].replace(':', '')

def check(path, d):
    p, m = [], PAT.match(path.name)
    if not m:
        return ["filename does not match <firm_id>__<query_id>__<vendor>-<product>__<ts>__audit-data.json"]
    r = d.get("run", {})
    for k in ("vendor", "product", "spec_version", "checked_at", "firm_id", "query_id"):
        if not str(r.get(k) or "").strip():
            p.append(f"run.{k} missing or empty")
    ca = str(r.get("checked_at") or "")
    if not ISO.match(ca):
        p.append(f"checked_at not ISO 8601 with seconds and offset: {ca!r}")
    elif compact(ca) != m.group(5):
        p.append(f"checked_at {ca} does not match filename timestamp {m.group(5)}")
    if r.get("firm_id") != m.group(1): p.append("run.firm_id differs from filename")
    if r.get("query_id") != m.group(2): p.append("run.query_id differs from filename")
    rows = d.get("rows", [])
    n = {t: sum(1 for x in rows if x.get("Row type") == t) for t in ("Category result", "Item", "Ranking Suggestion")}
    if len(rows) != 36 or n != {"Category result": 7, "Item": 21, "Ranking Suggestion": 8}:
        p.append(f"row counts {len(rows)} {n}, expected 36 (7/21/8)")
    for x in rows:
        t, res = x.get("Row type"), x.get("Item result")
        if t == "Item":
            if res not in ITEM: p.append(f"row {x.get('#')}: Item result {res!r} not allowed")
            elif res not in ("Not accessible", "Not completed") and not str(x.get("Source URL") or "").strip("—- "):
                p.append(f"row {x.get('#')}: {res} with no source URL")
        elif t == "Ranking Suggestion" and res not in RS:
            p.append(f"row {x.get('#')}: Ranking Suggestion result {res!r} not allowed")
        elif t == "Category result" and not re.match(r'^\d+ of \d+ points$', str(res)):
            p.append(f"row {x.get('#')}: Category result {res!r} not 'N of M points'")
    return p

def main(run_dir, out):
    run_dir, audits, rejected = pathlib.Path(run_dir), [], []
    for f in sorted(run_dir.rglob("*__audit-data.json")):
        raw = f.read_bytes()
        d = json.loads(raw)
        probs = check(f, d)
        prefix = f.name[: -len("__audit-data.json")]
        summ = next(f.parent.glob(prefix + "__summary.json"), None) or next(run_dir.rglob(prefix + "__summary.json"), None)
        dc = next(f.parent.glob(prefix + "__delivery-check.json"), None) or next(run_dir.rglob(prefix + "__delivery-check.json"), None)
        if summ is None: probs.append("no matching __summary.json (website-access status)")
        if probs:
            rejected.append({"file": f.name, "problems": probs}); continue
        s = json.loads(summ.read_bytes())
        r = d["run"]
        audits.append({
            "file": f.name, "file_hash": hashlib.sha256(raw).hexdigest(),
            "firm": {"firm_id": r["firm_id"], "name": r["firm"], "primary_business_category": r.get("primary_business_category"),
                     "website_url": r.get("website"), "meta_place_id": r.get("meta_place_id"),
                     "trade": TRADES.get(r["query_id"].split("-")[0])},
            "audit": {k: r.get(k) for k in ("run_id", "query", "town_zip", "query_id", "checked_at", "spec_version", "vendor",
                                            "product", "evidence_source", "primary_email", "primary_email_source",
                                            "website_home", "service_page", "harness")}
                     | {"website_unreadable": bool(s.get("website_unreadable")), "unverified": bool(s.get("unverified")),
                        "unverified_reason": s.get("unverified_reason") or None, "f_reason": s.get("f_reason") or None},
            "rows": [{k: x.get(src) for k, src in COLS} for x in d["rows"]],
            "delivery_check": json.loads(dc.read_bytes()) if dc else None,
        })
    json.dump({"audits": audits}, open(out, "w"), ensure_ascii=False)
    print(f"{len(audits)} audits bundled, {len(rejected)} rejected")
    for x in rejected: print("REJECTED", x["file"], "; ".join(x["problems"]))

if __name__ == "__main__":
    main(*sys.argv[1:3])
