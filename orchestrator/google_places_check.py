#!/usr/bin/env python3
"""One-off: look up the Muse records held out of the firm list (no Meta place ID, no own website) in Google Places.

For each distinct name + town, a Google Places (New) Text Search runs for "<name>, <town or county>, TX".
A result counts as the firm only when its phone matches the record's phone (Spec v2.13 §13: a name match
alone never sets a Google place ID). Results are written to staging.google_place_check as place IDs,
our outcome and the date only — Google's listing content is not stored (Spec v2.13 §4). Nothing is
written to public.firms.

Needs DATABASE_URL and GOOGLE_PLACES_API_KEY. Run: python google_places_check.py [--limit N]
"""
import argparse
import os
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.businessStatus"


def digits(p):
    d = re.sub(r"\D", "", p or "")
    return d[-10:] if len(d) >= 10 else None


def norm(s):
    s = (s or "").lower().replace("a/c", "ac").replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\b(llc|inc|corp|co|ltd|lp|llp|company|the)\b", " ", s)
    return " ".join(s.split())


def classify(rec, places):
    phone = digits(rec["phone"])
    town = (rec["town"] or "").lower()
    by_phone = [p for p in places if phone and digits(p.get("nationalPhoneNumber")) == phone]
    if len(by_phone) == 1:
        return "phone match", by_phone
    if len(by_phone) > 1:
        return "several matches", by_phone
    named = [p for p in places if norm((p.get("displayName") or {}).get("text")) == norm(rec["name"])
             and (not town or town in (p.get("formattedAddress") or "").lower())]
    if not named:
        return "no match", []
    if len(named) > 1:
        return "several matches", named
    if not phone:
        return "name and town match, no phone to confirm", named
    return "name and town match, phone differs", named


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    key = os.environ["GOOGLE_PLACES_API_KEY"]
    from db import connect
    with connect() as con, con.cursor() as cur:
        cur.execute("""
          select distinct on (norm_name, lower(coalesce(eff_town, addr_town, county, '')))
                 cand_id, name, coalesce(eff_town, addr_town) town, county, phone
          from staging.muse_candidates c
          where entity_key is null and name is not null
            and basis in ('discovery','licence on firm source','licence (roster-derived)','name-based')
            and not exists (select 1 from staging.google_place_check g where g.cand_id = c.cand_id)
          order by norm_name, lower(coalesce(eff_town, addr_town, county, '')), (phone is null), cand_id""")
        recs = [dict(zip(("cand_id", "name", "town", "county", "phone"), r)) for r in cur.fetchall()]
        if args.limit:
            recs = recs[:args.limit]
        print("records to check: %d" % len(recs), flush=True)
        counts = {}
        for i, rec in enumerate(recs, 1):
            where = rec["town"] or (rec["county"] + " County" if rec["county"] else "")
            q = "%s, %s, TX" % (rec["name"], where) if where else "%s, TX" % rec["name"]
            try:
                r = requests.post(URL, json={"textQuery": q, "maxResultCount": 5},
                                  headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": FIELDS}, timeout=30)
                if r.status_code != 200:
                    raise RuntimeError("HTTP %d %s" % (r.status_code, r.text[:200]))
                places = r.json().get("places", [])
                outcome, hits = classify(rec, places)
                cur.execute("insert into staging.google_place_check (cand_id, query, n_results, outcome, google_place_ids, business_status) "
                            "values (%s,%s,%s,%s,%s,%s) on conflict (cand_id) do nothing",
                            (rec["cand_id"], q, len(places), outcome, [p["id"] for p in hits] or None,
                             hits[0].get("businessStatus") if len(hits) == 1 else None))
            except Exception as exc:  # noqa: BLE001
                outcome = "error"
                cur.execute("insert into staging.google_place_check (cand_id, query, outcome, error) values (%s,%s,'error',%s) "
                            "on conflict (cand_id) do nothing", (rec["cand_id"], q, str(exc)[:500]))
            counts[outcome] = counts.get(outcome, 0) + 1
            if i % 50 == 0:
                con.commit()
                print("%d done: %s" % (i, counts), flush=True)
            time.sleep(0.1)
        con.commit()
        print("finished: %s" % counts, flush=True)


if __name__ == "__main__":
    main()
