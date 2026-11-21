#!/usr/bin/env python3
"""Validate the Google/Yelp reader on three firms: Eric's, Airtron,
Coppell Heating. Prints what the reader returns for each (listing found?
rating? services? reviews?). The October 2026 workbook figures are a
sanity check only (Eric's 5.0/81+ Google; Airtron 4.8/4,565 own site;
Coppell Heating 5.0/23) — fresh reads are the evidence."""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from aisharc_harness.evidence import fetchers as F
from aisharc_harness.evidence import google_yelp as GY


def main() -> None:
    firms = {f["firm_id"]: f for f in json.load(open("firms.json"))["firms"]}
    disc = json.load(open("discovery.json")).get("discovered", {})
    for fid in ("erics", "airtron", "coppell-heating"):
        firm = firms[fid]
        d = disc.get(fid, {})
        print("=" * 70)
        print("== %s (%s) ==" % (firm["name"], fid))
        # Meta listing (for the yelp link) — same route as the runner.
        listing = None
        pid = d.get("place_id") or firm.get("meta_place_id")
        if pid:
            res = F.places_details(pid)
            if res.get("accessible"):
                rec = (res.get("record") or {}).get("details") or {}
                links = {l.get("type"): l.get("url")
                         for l in rec.get("links", [])}
                listing = {"yelp_url": links.get("yelp"),
                           "name": rec.get("name")}
                print("Meta place %s; yelp link: %s"
                      % (pid, links.get("yelp") or "NONE"))
            else:
                print("Meta place %s not readable: %s"
                      % (pid, res.get("reason", "")))
        else:
            print("No Meta place ID")
        # Homepage HTML for the reviews-page fallback.
        home_html = ""
        home_url = d.get("website") or firm.get("website") or ""
        if home_url:
            home = F.fetch_website(home_url)
            home_html = (home.get("initial_html").exact
                         if home.get("initial_html") and
                         home["initial_html"].accessible else "")
            print("Homepage %s readable: %s" % (home_url, bool(home_html)))
            F.polite_sleep()
        out = GY.collect(firm, d, listing, home_html, home_url, "2026-11-11")
        y = out["yelp"]
        print("YELP: accessible=%s" % y.get("accessible"))
        if y.get("accessible"):
            print("  name=%r address=%r city=%r phone=%r" % (
                y.get("name"), y.get("address"), y.get("city"), y.get("phone")))
            print("  categories=%s rating=%s count=%s" % (
                y.get("categories"), y.get("rating"), y.get("count")))
            print("  install=%s repair=%s found_by=%s" % (
                y.get("has_install"), y.get("has_repair"), y.get("found_by")))
            print("  founding field=%s bio=%s" % (
                y.get("founding_year_field"), y.get("founding_year_bio")))
            print("  services text: %s" % (y.get("services_text") or "")[:200])
        else:
            print("  reason: %s" % y.get("reason"))
        g = out["google"]
        print("GOOGLE: accessible=%s reason=%s" % (
            g.get("accessible"), g.get("reason", "")[:100]))
        r = out["reviews"]
        print("REVIEWS: source=%s accessible=%s" % (
            r.get("source"), r.get("accessible")))
        if r.get("accessible"):
            print("  url=%s reviews_read=%d negative=%d" % (
                r.get("url"), r.get("reviews_read"), r.get("negative_count")))
            print("  recurring=%s single=%s" % (
                r.get("recurring_pattern"), r.get("single_cluster")))
            for rv in r.get("reviews", [])[:3]:
                print("  - [%s] %s" % (
                    "addressed" if rv.get("addressed") else "unaddressed",
                    rv.get("text", "")[:160]))
        else:
            print("  reason: %s" % r.get("reason"))


if __name__ == "__main__":
    main()
