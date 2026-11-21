"""Merge discovery results into study-additions-firms.json.

Reads:
  study-additions-firms-all.json  (653 queue firms, pre-discovery record)
  discovery-results.json          (526 discovered, 127 no-listing, 0 ambiguous)
  discovery-queue.json            (653, for order/coverage checks)

Writes:
  study-additions-firms.json      (615 distinct firms after 38 same-firm collapses)
  study-additions-firms-abilene-9.json (backup of the 9-firm file it overwrites)

Rules applied (task + discovery record):
- Each of the 653 queue firms gets its discovered website + meta_place_id
  where found, null where not. Websites without a scheme are normalized to
  https:// (the fetcher's requests.get raises MissingSchema on a bare
  domain, so an un-normalized website would read as Not accessible for
  the wrong reason; the domain itself is unchanged).
- Same-firm queue pairs collapse to ONE audited firm (same place card, or
  same website across branches). The survivor keeps its recorded fields;
  folded entries' runs are merged into the discovery_note.
- Primary town: the town of the (survivor's) address if that town is one
  where the firm was named, else the town where it was named most often.
- The 9 Abilene firms already audited are NOT in this file: they were
  excluded from the discovery queue as already audited/loaded (their
  audits are in the DB). The task's "subset" premise does not hold; the
  9-firm file is preserved as study-additions-firms-abilene-9.json and
  the fact is recorded in the output file's header note.
"""
import json, re, shutil, os

HERE = "/home/hatch/workspace/goals/score-card-audit-product/files/aisharc-harness"
ALL = os.path.join(HERE, "study-additions-firms-all.json")
DISC = os.path.join(HERE, "discovery-results.json")
QUEUE = os.path.join(HERE, "discovery-queue.json")
OUT = os.path.join(HERE, "study-additions-firms.json")
BACKUP = os.path.join(HERE, "study-additions-firms-abilene-9.json")

# --- collapse groups: (survivor, [folded...], primary_town, town_zip_override, reason)
GROUPS = [
 ("caprock-plbg-htg-a-c", ["8-star-rating-with-33-reviews"], "Plainview", None,
  "Same firm (Caprock Plumbing Heating and Air): identical place card 1230129661083979; queue 470 is a garbled review-snippet name for the same firm at 428 Ash St, Plainview."),
 ("the-a-c-guy-llc", ["the-ac-guy-llc"], "The Woodlands", None,
  "Same firm: identical place card 1282645603229655; name variant 'The AC Guy' vs 'The A/C Guy'."),
 ("fresh-air-cooling-heating", ["fresh-air-lp"], "Richmond", None,
  "Same firm (Fresh Air / Fresh Air L.P.): identical place card 1417468835330719, 5702 Powerline Rd, Richmond."),
 ("rohde-air-conditioning-heating", ["rohde-ac-heating-llc"], "Temple", None,
  "Same firm (Rohde Air Conditioning & Heating): identical place card 1921636478651470, 550 Kevin Reilly Ln, Temple."),
 ("prestige-heating-and-air-conditioning-llc", ["prestige-air-conditioning-experts"], "Spring", None,
  "Same firm: identical place card 1957683994440517; same phone (281) 288-6211."),
 ("berkeys-plumbing-a-c-electrical", ["berkeys-air-conditioning-plumbing-electrical"], "Southlake", None,
  "Same firm (Berkeys): identical place card 2663776350638947, 1070 S Kimball Ave Ste 131, Southlake (HQ, founded 1975)."),
 ("jc-air-conditioning-heating", ["jc-air-llc"], "Edinburg", None,
  "Same firm (JC Air Conditioning and Heating): identical place card 3081350555335874, 1303 E Rogers Rd, Edinburg."),
 ("vortex-air-solutions", ["vortex-heating-air-solutions"], "Waxahachie", None,
  "Same firm: identical place card 3723931271225540, 261 Park Meadows Dr, Waxahachie."),
 ("one-hour-heating-air-conditioning-of-corpus-christi", ["one-hour-air-conditioning-heating-of-corpus-christi"], "Corpus Christi", None,
  "Same firm (One Hour Air Conditioning & Heating of Corpus Christi): identical place card 4510621182594353, 5561 Kingpin Dr, Corpus Christi; the Portland address (901 Austin St) was never corroborated."),
 ("goettl-air-conditioning-and-plumbing", ["goettl-san-antonio"], "San Antonio", None,
  "Same firm (Goettl): identical place card 497243186413508, 7847 Fortune Dr, San Antonio."),
 ("ctr-services-air-conditioning-heating-of-temple", ["ctr-services", "ctr-services-air-conditioning-heating"], "Temple", None,
  "Same firm (CTR Services): Temple pair share place card 574747654304805; Killeen entry shares website ctrairandheat.com and the firm's main number (254) 545-1759."),
 ("medley-heating-air-conditioning-plumbing-carrollton", ["medley-heating-air-conditioning-plumbing"], "Carrollton", None,
  "Same firm (Medley): identical place card 580915533664482, 1711 Briercroft Ct Ste 127, Carrollton."),
 ("alief-ultra-mechanical", ["alief-heating-air-conditioning"], "Missouri City", None,
  "Same firm: identical place card 590765915826516, 9636 Keegan Rd # B, Houston; 'Alief Heating & Air Conditioning' is the trade name."),
 ("rescue-air-and-plumbing", ["rescue-air-heating-and-cooling"], "Dallas", None,
  "Same firm (Rescue Air): identical place card 621270985963309, 9639 Greenville Ave, Dallas (HQ); the Richardson address is the old address."),
 ("procure-llc-dba-procure-heating-air", ["procure-heating-air"], "Buda", None,
  "Same firm (ProCure Heating & Air): identical place card 639495832184073, 3225 FM 2001, Buda."),
 ("jon-wayne-company", ["jon-wayne-heating-air"], "Mount Pleasant", None,
  "Same firm (Jon-Wayne Company): identical place card 749737822970072, 203 I-30, Mt Vernon."),
 ("nathan-lazarine-a-c-heat-electric", ["lazarine-ac"], "Missouri City", None,
  "Same firm: identical place card 932506059488828, 2407 Mountain Run, Missouri City."),
 ("75-degree-ac", ["75-degree-ac-katy"], "Richmond", "77469",
  "Same firm (75 Degree AC): shared website 75degreeac.com; Katy entry is website-only (firm's site confirms Katy service). Primary town Richmond per the address-town rule (card address 20926 Bright Lake Bend Ct, Richmond; Richmond was named) - the dedupe record had Rosenberg by most-named (5 of 10 runs); corrected here."),
 ("abc-home-commercial-services-corpus-christi", ["abc-home-commercial-services"], "Corpus Christi", None,
  "Same firm (ABC Home & Commercial Services): shared website abchomeandcommercial.com; Corpus Christi branch card 3534279040192794 (address+phone exact); Bryan/College Station entry is website-only."),
 ("airtron-houston", ["airtron-heating-air-conditioning"], "Texas City", None,
  "Same firm (Airtron Heating & Air Conditioning): shared website airtron.com; also the same firm as the r3 Coppell sample. Merged name set to 'Airtron Heating & Air Conditioning' so the audit attaches to the existing DB firm. Primary town Texas City (most-named across the combined firm, 6 of 15 runs; also the address town of this entry). Recorded address 606 Gulf Freeway is George's Air Conditioning's address (agent garbling); the firm's real HQ is Houston (16225 Tomball Pkwy, place card 1038470694095047). Parent may still decide to skip this audit."),
 ("billygo-air-conditioning-plumbing-grapevine", ["billygo-air-conditioning-plumbing-flower-mound", "billygo-air-conditioning-plumbing"], "Grapevine", None,
  "Same firm (billyGO): shared website billygo.com; Grapevine HQ card 1623048694778652; Flower Mound and Keller entries are website-only branches."),
 ("bvac-services-college-station", ["bvac-services"], "College Station", None,
  "Same firm (BVAC Services): shared website bvacservices.com; both place cards are in College Station (the Bryan entry's card is 3204 Longmire Dr, College Station; its recorded Bryan address was never corroborated). Primary town College Station per the address-town rule (survivor's address 2110 Southwood Dr, College Station, was named); Bryan was most-named (2 of 3 runs) - judgment call, flagged."),
 ("classic-services-air-conditioning-heating", ["classic-air-conditioning-heating"], "Boerne", None,
  "Same firm (Classic Services Air Conditioning & Heating): shared website classicairconditioningandheating.com; HQ card 1166638091321190 is New Braunfels (1893 State Hwy 46 S); Boerne entry's address/phone confirmed by the firm's own site. Primary town Boerne per the address-town rule (215 W Bandera Rd, Boerne, was named); named runs tie Boerne 3 / New Braunfels 3 - judgment call, flagged."),
 ("dallas-heating-and-air-conditioning-mesquite", ["dallas-heating-and-air-conditioning"], "Mesquite", None,
  "Same firm (Dallas Heating and Air Conditioning): shared website dallasheatingac.com; HQ card 580573347002080 (5050 Quorum Dr, Dallas); Dallas entry is website-only."),
 ("ellis-air-systems-inc", ["ellis-air-systems"], "Killeen", None,
  "Same firm (Ellis Air Systems): shared website ellisairsystems.com; Killeen card 462777242382154 and Temple card 3297300750516266 are two branches of one firm (family-owned since 1988)."),
 ("ferrara-s-heating-air-conditioning-inc", ["ferrara-s-heating-air-conditioning-inc-nacogdoches"], "Lufkin", None,
  "Same firm (Ferrara's): shared website ferrarashvac.com; Lufkin card 585166533050233 (HQ) and Nacogdoches card 5217925514921128."),
 ("george-s-air-conditioning-llc", ["george-s-air-conditioning"], "Texas City", None,
  "Same firm (George's Air Conditioning, LLC): shared website georgesacservice.com; Texas City card 1843549019913510 (address exact); Galveston entry is website-only (firm's site confirms 1515 31st St, Galveston)."),
 ("coldharbour-heating-air", ["cold-harbour-heating-and-air-houston"], "Houston", None,
  "Same firm (Cold Harbour Heating and Air, Houston): shared website heatingandairhouston.com; both website-only (firm's site confirms 1111 Rusk St Ste 172, Houston, phone (832) 371-9862)."),
 ("lex-air-conditioning-and-heating", ["lex-air-conditioning-heating-plumbing-electrical"], "Carrollton", None,
  "Same firm (LEX): shared website lexairconditioning.com; Carrollton HQ confirmed by the firm's own site; Plano card 1293661069070354 is the 'GO Heating, Air and Plumbing' rebrand card at the recorded Plano address."),
 ("mcwilliams-heating-cooling-plumbing", ["mcwilliams-heating-cooling-plumbing-missouri-city", "mcwilliams-heating-cooling-plumbing-nacogdoches"], "Lufkin", None,
  "Same firm (McWilliams Heating, Cooling & Plumbing): shared website mcwilliamsandson.com; Lufkin HQ card 1414186792394758, Richmond branch website-only, Nacogdoches card 572448031833414."),
 ("rosenberg-plumbing-air", ["rosenberg-indoor-comfort-llc"], "San Antonio", None,
  "Same firm (Rosenberg Plumbing & Air): shared website rosenberghvac.com; HQ card 1118318112371150 (4335 Vance Jackson Rd Ste 505) and 'Rosenberg Indoor Comfort' card 644284381820728 (1228 Cornerway Blvd, San Antonio). JUDGMENT CALL - the two cards carry different trade names; merged on the shared website. Flagged for parent review."),
 ("superior-ac-heat", ["superior-ac-heat-arlington"], "Burleson", None,
  "Same firm (Superior AC & Heat): shared website superioracnheat.com; Burleson card 3196123367310079 and Arlington card 631750712040970 are two branches."),
 ("texas-air-repair-llc", ["texas-air-repair-llc-floresville"], "Pleasanton", None,
  "Same firm (Texas Air Repair): shared website texasairrepair.com; San Antonio card 1555980998308935 (13131 Lookout Run); Floresville entry is website-only (firm's site confirms the Floresville address). Primary town Pleasanton (most-named, 3 of 4 runs; the address city San Antonio was not a named town)."),
 ("willard-air-conditioning-plumbing", ["willard-heating-cooling-plumbing", "willard-cooling-heating-plumbing-electrical"], "Waxahachie", None,
  "Same firm (Willard): shared website willardac.com; Waxahachie card 1994000657619524 (address exact), Forney HQ card 770030227535996, Dallas entry website-only."),
]

# place_id to carry from a folded entry when the survivor has none
FOLDED_PLACE_ID = {
    "classic-services-air-conditioning-heating": ("1166638091321190",
        "place card 1166638091321190 (firm HQ, New Braunfels) taken from the folded Cibolo entry; survivor is website-only"),
    "lex-air-conditioning-and-heating": ("1293661069070354",
        "place card 1293661069070354 (Plano 'GO Heating' rebrand card) taken from the folded Plano entry; survivor is website-only"),
}

# merged name overrides (firm's real name, so the loader attaches to the existing DB firm)
NAME_OVERRIDE = {
    "airtron-houston": "Airtron Heating & Air Conditioning",
}

def norm_website(w):
    if not w:
        return None
    w = w.strip()
    if w.startswith(("http://", "https://")):
        return w
    return "https://" + w

def parse_runs(note):
    m = re.search(r"Named by the agent in: (.+?)\. Primary town", note or "")
    if not m:
        return []
    return [r.strip() for r in m.group(1).split(",") if r.strip()]

def run_towns(runs):
    from collections import Counter
    return Counter(r.split("/")[0] for r in runs)

def main():
    allf = json.load(open(ALL))["firms"]
    disc = json.load(open(DISC))
    queue = json.load(open(QUEUE))["firms"]
    by_id = {f["firm_id"]: f for f in allf}
    qorder = {f["firm_id"]: i for i, f in enumerate(queue)}
    found = disc.get("discovered", {})
    nl = {}
    for e in disc.get("no_listing", []):
        if isinstance(e, dict):
            nl[e["firm_id"]] = e
        else:
            nl[e] = {"firm_id": e, "town": "", "note": ""}

    # coverage assertions
    qset = set(qorder)
    assert set(found) | set(nl) == qset, "coverage gap: %s" % (qset - set(found) - set(nl),)
    assert not (set(found) & set(nl)), "overlap: %s" % (set(found) & set(nl),)
    assert len(allf) == 653 and len(queue) == 653

    # collapse bookkeeping
    folded_to_survivor = {}
    group_by_survivor = {}
    for survivor, folded, town, tzip, reason in GROUPS:
        assert survivor in by_id, survivor
        for fid in folded:
            assert fid in by_id, fid
            assert fid not in folded_to_survivor, fid
            folded_to_survivor[fid] = survivor
        group_by_survivor[survivor] = (folded, town, tzip, reason)
    n_folded = len(folded_to_survivor)
    print("collapse groups: %d, folded entries: %d, merged firms: %d"
          % (len(GROUPS), n_folded, 653 - n_folded))
    assert 653 - n_folded == 615, "expected 615 merged firms"

    def discovery_outcome(fid):
        """(website, place_id, outcome_text) for one queue firm."""
        d = found.get(fid)
        if d:
            w = norm_website(d.get("website"))
            pid = d.get("place_id")
            if pid:
                return w, str(pid), "place card %s, website %s." % (pid, w or "none")
            return w, None, "no place card; website-only record, website %s." % (w or "none")
        n = nl.get(fid, {})
        note = (n.get("note") or "")[:400]
        return None, None, "no place card/website found - %s" % note

    out_firms = []
    for f in allf:
        fid = f["firm_id"]
        if fid in folded_to_survivor:
            continue
        entry = dict(f)
        runs = parse_runs(f.get("discovery_note"))
        if fid in group_by_survivor:
            folded, town, tzip, reason = group_by_survivor[fid]
            for ffid in folded:
                runs.extend(parse_runs(by_id[ffid].get("discovery_note")))
            runs = sorted(set(runs))
            counts = run_towns(runs)
            total = len(runs)
            # primary-town reason text: the decided town is the address town
            # if it appears in the survivor's recorded address AND was a
            # named town; else it is the most-named town. (A regex on the
            # address is unreliable here: several recorded addresses have no
            # comma between street and city, e.g. "428 Ash St, Plainview TX".)
            addr = f.get("address") or ""
            named_towns = set(counts)
            if town.lower().replace(" ", "-") in named_towns and town.lower() in addr.lower():
                town_reason = "address town (%s)" % town
            else:
                top = counts.most_common(1)[0]
                town_reason = "most-named town (%d of %d runs)" % (top[1], total)
            if fid in NAME_OVERRIDE:
                entry["name"] = NAME_OVERRIDE[fid]
            entry["town"] = town
            if tzip:
                entry["town_zip"] = tzip
            # website / place_id: survivor's own, else folded entry's place_id
            w, pid, outcome = discovery_outcome(fid)
            if pid is None and fid in FOLDED_PLACE_ID:
                pid, extra = FOLDED_PLACE_ID[fid]
                outcome = "%s (%s)." % (outcome.rstrip("."), extra)
            entry["website"] = w
            entry["website_home"] = w
            entry["meta_place_id"] = pid
            n_src = 1 + len(folded)
            entry["discovery_note"] = (
                "Named by the agent in: %s. Primary town %s (%s). "
                "Merged from %d addition entries (same-firm collapse of %s). "
                "Collapse: %s "
                "Discovery 2026-11-14: %s"
                % (", ".join(runs), town, town_reason, n_src,
                   ", ".join([fid] + folded), reason, outcome))
        else:
            w, pid, outcome = discovery_outcome(fid)
            entry["website"] = w
            entry["website_home"] = w
            entry["meta_place_id"] = pid
            entry["discovery_note"] = (f.get("discovery_note") or "") + \
                " Discovery 2026-11-14: " + outcome
        out_firms.append(entry)

    # order by queue position of the survivor
    out_firms.sort(key=lambda e: qorder[e["firm_id"]])
    assert len(out_firms) == 615
    assert len({e["firm_id"] for e in out_firms}) == 615
    n_web = sum(1 for e in out_firms if e["website"])
    n_pid = sum(1 for e in out_firms if e["meta_place_id"])
    print("merged firms: %d, with website: %d, with place_id: %d, website null: %d"
          % (len(out_firms), n_web, n_pid, 615 - n_web))
    # every website must carry a scheme now
    bad = [e["firm_id"] for e in out_firms if e["website"] and not e["website"].startswith(("http://", "https://"))]
    assert not bad, bad

    # back up the 9-firm file, then overwrite
    if os.path.exists(OUT) and not os.path.exists(BACKUP):
        shutil.copy2(OUT, BACKUP)
        print("backed up 9-firm file to", BACKUP)

    header_note = (
        "AI Sharc Texas HVAC correlation study - agent-named additions firms file, merged 2026-11-14. "
        "Source: study-additions-firms-all.json (653 queue firms, pre-discovery record) + discovery-results.json "
        "(526 discovered, 127 no-listing, 0 ambiguous; browser.search place cards, fail-closed identity checks). "
        "Same-firm queue pairs collapsed to one audited firm: 653 queue firms -> 615 distinct firms (38 folded entries, "
        "34 collapse groups; see each survivor's discovery_note for the collapse evidence). "
        "Each firm is audited ONCE, for its primary town (town of its address if that town is one where it was named, "
        "else the town where it was named most often; choice recorded in discovery_note). "
        "Websites without a scheme were normalized to https:// (the fetcher raises MissingSchema on a bare domain; "
        "the domain itself is unchanged). "
        "NOTE - the 9 Abilene firms previously in this file are NOT in this merged file: they were excluded from the "
        "discovery queue as already audited and loaded into the DB (their audits are in runs/2026-11-14-study/audits/); "
        "the 9-firm file is preserved as study-additions-firms-abilene-9.json. The task's 'subset' premise does not hold. "
        "NOT collapsed (kept separate, flagged in the run report): Commercial Air / Way Maker (different place cards, "
        "shared phone only); Ken's Air / Kens Air (both no-listing, no evidence they are the same firm); Hart (473) / "
        "Chilton / Hart Lubbock (no evidence of same firm beyond a phone number); Heavenly / Stay Cool MTX (different "
        "firms, different websites; the agent conflated their details)."
    )
    out = {
        "note": header_note,
        "generated": "2026-11-14",
        "source": "study-additions-firms-all.json + discovery-results.json (2026-11-14)",
        "counts": {"queue_firms": 653, "distinct_firms": 615, "folded": 38,
                   "discovered": 526, "no_listing": 127},
        "firms": out_firms,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print("wrote", OUT)

if __name__ == "__main__":
    main()
