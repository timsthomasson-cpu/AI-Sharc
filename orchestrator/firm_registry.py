#!/usr/bin/env python3
"""Write the harness's firm registry for one shopping query, from the central firm list.

Spec v2.12 §13: a firm is audited under each query whose run named it. This reads the firms that the
shopping runs for <query_id> linked to (agent_run_firms.firm_id), or an explicit list of firm_ids, and
writes them in the registry format run_audit.py reads (the format of the harness's firms.json):

  {"firms": [{"firm_id", "name", "website", "meta_place_id", "phone_recorded", "address",
              "trade", "town", "town_zip", "first_task"}, ...],
   "query": {"query_id", "task_text", "town", "zip", "task"}}

town and town_zip are the QUERY's town and ZIP, not the firm's own address: the audit checks whether the
firm serves the searched town (C2.1). first_task is the query's task number, so the output file name
carries the right query_id.

Usage:
  firm_registry.py --query-id hvac-houston-77002-t2 --out firms-hvac-houston-77002-t2.json
  firm_registry.py --query-id hvac-houston-77002-t2 --firm-ids tempertech,ethanclark --out f.json
"""
import argparse
import json
import re

QUERY_ID = re.compile(r"^(hvac|plumbing|electrical|roofing)-([a-z0-9]+)-(\d{5})-t([123])$")
# Spec v2.12 §3: the three standard tasks, service-area wording (decided by Tim 2026-11-21).
TASK_TEXT = {
    1: "Find an HVAC firm whose service area includes {town}, TX {zip} for AC installation and repair and compare the firms you find.",
    2: "Find an HVAC firm whose service area includes {town}, TX {zip} for AC repair and compare the firms you find.",
    3: "Find an HVAC firm whose service area includes {town}, TX {zip} for AC installation and replacement and compare the firms you find.",
}
TRADE = {"hvac": "HVAC", "plumbing": "Plumbing", "electrical": "Electrical", "roofing": "Roofing"}


def parse_query_id(query_id):
    m = QUERY_ID.match(query_id or "")
    if not m:
        raise SystemExit("query_id %r does not match <trade>-<town>-<zip>-t<task> (Spec §13)" % query_id)
    return m.group(1), m.group(2), m.group(3), int(m.group(4))


def query_context(cur, query_id):
    """The query's task text, town and ZIP. Taken from the shopping run that used it, so the audit
    carries the exact wording the agents were given; otherwise built from the Spec v2.12 §3 wording."""
    trade, town_slug, zip_code, task = parse_query_id(query_id)
    cur.execute("select query, town_zip from agent_runs where query_id = %s order by checked_at desc limit 1", (query_id,))
    row = cur.fetchone()
    if row:
        task_text, town_zip = row
        m = re.match(r"^(.*), TX (\d{5})$", town_zip or "")
        town = m.group(1) if m else town_slug.title()
    else:
        town = town_slug.title()
        task_text = TASK_TEXT[task].format(town=town, zip=zip_code)
    return {"query_id": query_id, "task_text": task_text, "town": town, "zip": zip_code, "task": task,
            "trade": TRADE[trade]}


def build_registry(rows, ctx):
    """rows: (firm_id, name, website_url, meta_place_id, unique_primary_phone, address, trade) tuples."""
    firms = []
    for firm_id, name, website, place_id, phone, address, trade in rows:
        firms.append({
            "firm_id": firm_id, "name": name, "website": website, "meta_place_id": place_id,
            "phone_recorded": phone, "address": address, "trade": trade or ctx["trade"],
            "town": ctx["town"], "town_zip": ctx["zip"], "first_task": ctx["task"],
        })
    return {"firms": firms, "query": ctx}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query-id", required=True)
    ap.add_argument("--firm-ids", default="", help="comma-separated firm_ids; default: every firm the query's runs named")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    from db import connect
    with connect() as con, con.cursor() as cur:
        ctx = query_context(cur, args.query_id)
        cols = "f.firm_id, f.name, f.website_url, f.meta_place_id, f.unique_primary_phone, f.address, f.trade"
        if args.firm_ids:
            ids = [x.strip() for x in args.firm_ids.split(",") if x.strip()]
            cur.execute("select %s from firms f where f.firm_id = any(%%s) order by f.firm_id" % cols, (ids,))
        else:
            cur.execute("select distinct %s from firms f join agent_run_firms m on m.firm_id = f.firm_id "
                        "join agent_runs r on r.run_id = m.run_id where r.query_id = %%s order by f.firm_id" % cols,
                        (args.query_id,))
        reg = build_registry(cur.fetchall(), ctx)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=2)
    print("%d firms for %s written to %s" % (len(reg["firms"]), args.query_id, args.out))


if __name__ == "__main__":
    main()
