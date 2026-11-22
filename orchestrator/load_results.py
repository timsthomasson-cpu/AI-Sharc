#!/usr/bin/env python3
"""Load a finished harness run, or a folder of Shopping Query Return workbooks, into the audit database.

Validation happens twice: in the bundle builders (loader/build_bundle.py, loader/build_observation_bundle.py)
and again inside the database functions load_audit_bundle() / load_observation_bundle(), which also skip a
file whose hash is already loaded and link firms by the matching ladder (Spec v2.12 §13).

Usage:
  load_results.py audits <run_dir> [--dry-run]
  load_results.py observations <folder> [--dry-run]

--dry-run builds and checks the bundle and prints what would load, without connecting to the database.
"""
import argparse
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))


def build(kind, folder):
    out = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    if kind == "audits":
        import build_bundle
        build_bundle.main(folder, out)
    else:
        import build_observation_bundle
        build_observation_bundle.main(folder, out)
    with open(out, encoding="utf-8") as fh:
        bundle = json.load(fh)
    os.unlink(out)
    return bundle


def closed_firms(folder):
    """Firms the harness did not audit because they are closed (Spec v2.13 s.5)."""
    path = os.path.join(folder, "closed-firms.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get("closed", [])


def record_closed(cur, closed):
    """Set firm_status and last_checked_date for closed firms. A firm already recorded
    with a different closed/open status is not changed: the disagreement goes to the
    review queue for a person to decide (Spec v2.13 s.13)."""
    changed = queued = 0
    for c in closed:
        cur.execute("select firm_status from firms where firm_id = %s", (c["firm_id"],))
        row = cur.fetchone()
        if row is None:
            continue
        current = row[0]
        if current in (None, c["firm_status"]):
            cur.execute("update firms set firm_status = %s, last_checked_date = %s where firm_id = %s",
                        (c["firm_status"], c["checked_at"], c["firm_id"]))
            changed += 1
        else:
            cur.execute("insert into firm_review_queue (firm_id, source, reason, values_seen, note) "
                        "values (%s, %s, 'conflict on closed status', %s::jsonb, %s)",
                        (c["firm_id"], c["source"], json.dumps({"recorded": current, "seen": c["firm_status"]}),
                         "Harness status check %s" % c["checked_at"]))
            queued += 1
    return changed, queued


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["audits", "observations"])
    ap.add_argument("folder")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    closed = closed_firms(args.folder) if args.kind == "audits" else []
    if closed:
        print("%d closed firms not audited: %s" % (len(closed), ", ".join(c["firm_id"] for c in closed)))
    bundle = build(args.kind, args.folder)
    items = bundle.get("audits" if args.kind == "audits" else "runs", [])
    if not items and not closed:
        print("nothing to load")
        return
    if args.dry_run:
        print("dry run: %d %s would be sent to the database" % (len(items), args.kind))
        return
    if not items:
        from db import connect
        with connect() as con, con.cursor() as cur:
            print("closed firms: %d status set, %d queued for review" % record_closed(cur, closed))
            con.commit()
        return

    from db import connect
    fn = "load_audit_bundle" if args.kind == "audits" else "load_observation_bundle"
    with connect() as con, con.cursor() as cur:
        cur.execute("select public.%s(%%s::jsonb)" % fn, (json.dumps(bundle, ensure_ascii=False),))
        result = cur.fetchone()[0]
        if closed:
            print("closed firms: %d status set, %d queued for review" % record_closed(cur, closed))
        con.commit()
    print(json.dumps(result, indent=2))
    if result.get("rejected"):
        sys.exit(2)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
