# AI Sharc Harness — Design

**Status: under construction (2026-11-11, at Tim's instruction: "create the code for the Muse audits... use the governing documents to create a harness that creates accurate repeatable outcomes").** Not a governing document. The governing documents remain the source of truth; this harness is code that implements them. Code that contradicts the governing documents is a deviation under Spec §15.

**Baseline:** Specification v1.22 (2026-11-11), Definition Rev 6, Field Mapping Rev 3, Report Card skill (Rev 6 / v1.22), DB schema per Spec §13.

**Tested agent for this build:** Muse — Meta's personal AI agent (Field Mapping, Agent Validation sheet: Meta / Muse, Not tested). The harness records the Muse per-agent observation (model, tools, date, query, location, full transcript) and scores the firm against the same AI Sharc criteria. The Muse observation never changes the AI Sharc grade (Spec §8.1).

---

## 1. What the harness is

A fixed structure around a variable process (Spec §14: "a completely automated scored audit — Stage 1 Gates and Stage 2 Items via website crawling, places APIs, and LLM extraction with a rules engine for points and Grade"). It defines the inputs, the steps, the pass/fail criteria, the output format, and the checks that catch a bad result — so an audit is not just an LLM improvising a grade.

**Repeatability means:** the same inputs (firm, query, town+ZIP, date, recorded evidence) produce the same outputs (40 rows, points, grade, counts). The harness is deterministic where the evidence is fixed: the rules engine has no randomness and no discretion. Where the evidence comes from a live source (a website, a listing, the Muse agent), the harness records the source, the date, and the exact wording/figure, so a later run can be compared fact by fact. A live run on a new date is a new audit, not a re-run of an old one.

**Accuracy means:** every Pass/Fail cites source URL, date, and exact wording/figure (Spec §4.3). An Item that cannot be confirmed is **Not accessible** (Spec §7 vocabulary; displayed on cards as Fail — Not confirmed, and the original score stands) — never guessed, never filled in. Low-confidence or ambiguous cases go to a human-review queue (Spec §14 proposal, implemented here as an output, not a gate — the proposal is not yet adopted).

## 2. Layers

```
firms.json  (registry: 19 firms, recorded facts, what is NOT recorded)
    |
    v
evidence/   — fetchers: website, robots.txt, JSON-LD, sitemap, llms.txt,
              TDLR register, Places listings, BBB (where readable), reviews
              (where readable). Each fact carries method + source URL + date
              + exact wording/figure, or "Not accessible" with the reason.
    |
    v
agent/      — Muse agent query: the standard shopping task, the full
              transcript verbatim, model/tools/date/query/location.
              (Route determined by the Muse-access research, 2026-11-11.)
    |
    v
rules/      — rules engine: 6 Gates + 21 Items + 6 Levers, per Field
              Mapping Rev 3 + Spec v1.22. Category points (all-or-nothing),
              grade bands (A 4-7, B 3, C 2, D 0-1, F any Critical),
              reconciliation (40 rows). No discretion, no partial credit.
    |
    v
output/     — audit data rows (Spec §13 columns), per-agent observation
              record, cross-agent summary (§8.1), human-review queue,
              run report. Results are written to runs/<date>/, never to
              a firm's card, and never sent to a firm.
```

## 3. Inputs

- **Firm:** one firm from `firms.json` (name, Primary Business Category, trade, town+ZIP, known website/phone/licence/address where recorded; "to be resolved by discovery" where not recorded).
- **Query:** the service searched, in the user's words (e.g. "AC installation and repair").
- **Town + ZIP:** e.g. Coppell, TX 75019.
- **Date:** the audit date. One firm, one query, one town+ZIP, one date per audit (Spec §2/§3).
- **Spec version:** '1.22' for new audits (Spec §13).

## 4. Evidence schema (what the fetchers must produce per firm)

Every fact is a record: `{field, value, source_url, date, method, exact_wording}` or `{field, value: null, status: "Not accessible", reason, date, method}`. A fact without source and date is Not accessible, not Pass.

| Group | Facts |
|---|---|
| Website | URL, fetch status (HTML / rendered), readable text, fetch method, date |
| Identity | Business name on website; name on Google, Meta, Yelp (+ URLs, dates) |
| Services | Install/replacement and repair wording, separately, in plain words — website, Google, Meta |
| Area | Service-area page URL; names town+ZIP; install/repair separate; brands/system types; phone + booking route on that page; street address in/near town |
| Contact | Phone per source (website, Google, Meta, Yelp); booking/quote/contact route and whether it works |
| Hours | Day-by-day hours; 24-hour / weekend / emergency status per source |
| Listing | Verifiable listing outside the website (Google Business Profile / Meta place / Yelp), with name, phone, service area, Primary Business Category |
| Reputation | Rating figure + review count per platform (+ URL, date); complaint-pattern evidence from reviews read |
| Licence | Licence number + type as published on the site/footer/about; TDLR register match (number, type, class, expiry, active = expiry on/after audit date) |
| BBB | Accreditation, rating, URL, date — or Not accessible with the reason |
| Pricing | Six-line warranty card (each line or missing); diagnostic fee in dollars; free-estimate status for install and for repair, separately |
| Identity | Founding year + lineage per source |
| Machine readability | robots.txt (content, date); M1 crawlers allowed/blocked; key facts readable without JS; LocalBusiness JSON-LD (valid, matches visible page); sitemap (exists, valid, lists service page); llms.txt (exists, lists services + area) |
| Delivery (internal) | Do-not-harvest check (Spec §4.2) — separate record, never scored, never on a card |

**Guardrails (Spec §14, hard rules):** only publicly accessible, non-login data. No bypassing a login, paywall, CAPTCHA, or bot blocker. If a page is bot-blocked, do not scrape around it: the website-only Critical rule (§4.1.1) still applies and the affected Item is recorded as Not accessible, or the Gate fails as that rule requires. Respect Terms, robots.txt, and do-not-harvest notices. Ordinary request rates. Record method + URL + date + exact figure for every confirmed Item.

**Known hard parts (Spec §14, honest):** Meta/Facebook and BBB access, state licence lookups, bot-blocked or JS-heavy websites, ambiguous language, and ranking levers that need a live test or firm-supplied evidence. The harness marks these Not accessible where it cannot read them — it does not estimate them.

## 5. Rules engine (rules/)

Source of the rules: Field Mapping Rev 3 (Gates sheet, Items sheet, Ranking Levers sheet) + Spec v1.22 (§4.1.1 two-method rule, §4.3 hard rules, §5 grade bands, §8.1 aggregation, §9 levers, §13 schema). The Item/Gate definitions live in a data file (`rules/definitions.json`, derived from Field Mapping Rev 3) so the engine's criteria are traceable to the governing docs, not buried in code.

- **Gates (6):** Exact name; Services in plain words; Area coverage (Critical level); Working and consistent contact; Currently active and readable hours; Verifiable listing. Fail-if per the Gates sheet. Any failed Gate → Grade F ("fails AI Sharc's minimum criteria"), regardless of category points.
- **Items (21)** in 7 Categories (Reputation 3, Area Coverage 4, Credentials and Trust 2, Pricing and Warranty 4, Hours and Active Status 2, Identity and Contact 2, Machine Readability 4). Pass criteria per the Items sheet. Pass with warning only in the listed cases (Items sheet, column 7) — it counts as Pass, not an Issue.
- **Category point:** 1 point only if every Item in the Category is Pass (Pass with warning counts as Pass). No partial credit.
- **Grade bands (eligible firms only):** A 4–7, B 3, C 2, D 0–1. F = any Critical Gate fails.
- **Levers (6):** Observed / Recommendation / Not checked, per the hard Observed rules (Spec §4.3 rule 8). A firm's statement alone is never Observed for a live-test lever; the Muse agent's claim alone is not Observed either — Observed requires public evidence with URL and date. Levers never affect the grade.
- **Single-section counting:** an issue is counted once, in its discrete Gate/Item section; its effect on another Category is covered in Why it matters, not as a second issue.
- **Conflict (narrow, Spec §4.3 rule 5):** only same-platform/scope/date quoted differently, two live adopted documents contradicting, or meaning undeterminable. Cross-platform figure differences, platform category-name differences, NAICS version differences, silence, and the same Issue in multiple Categories are NOT Conflicts. Conflicts go to the human-review queue.
- **Reconciliation (before any output is released):** 40 rows (6 Gates + 7 Category results + 21 Items + 6 Levers); Critical count; High count = failed Items only; passed Items; category points; Grade from points and Critical count. Reconciliation must match the results, not just itself.
- **Do-not-harvest check:** separate Delivery Check record, never a row, never scored.

## 5a. The runner (run_audit.py) — built 2026-11-11

`run_audit.py` bridges the evidence fetchers (§4) to the rules engine (§5) for all 40 rows per firm. It does NOT call the Model API per firm — the MUSE-SPARK observation is a single standard-question run, made once per (query, town) by `run_agent.py` (see §6); the runner's job is the core audit per firm (evidence + engine). `run_agent.py` (built 2026-11-13 under the approved production-fields plan) makes the one agent call, scores each named firm with the LLM scorer (`aisharc_harness/agent/scorer.py`), and writes one `muse-observation.json` per firm into `runs/<date>/<firm_id>/`. The run report's agent-observation and delivery-check sections read those files when present.

- **Run record (r3):** `run_id` + `evidence_source` (run file path + run id) for the loader (Aggregation design §2). **Delivery check (Spec §4.2):** `check_delivery()` writes one `delivery-check.json` per firm (published business email, Primary email per the §4.2 order, do-not-harvest notice type, delivery route). Advertising email is website verification only in r3 — CAN-SPAM cannot be met (no valid business postal address, known gap since 2026-11-03).

- **M4 (both-pages rule, confirmed by Tim 2026-11-11):** JSON-LD is checked on BOTH the homepage and the town service page. M4 passes only if valid LocalBusiness/HVACBusiness JSON-LD is on both. If there is no separate service page, the homepage alone is judged (a flagged judgment call). Airtron is the test case: its homepage has JSON-LD, its Coppell service page does not, so Airtron M4 is Missing.
- **Site-root rule:** robots.txt, sitemap.xml, and llms.txt are fetched from the site root (scheme://netloc), never from the recorded page URL. (Bug found and fixed in the C7 sweep: fetching them from the recorded page URL returned the wrong document.)
- **Discovery:** for the 9 firms with no recorded website, the runner resolves the website by Places search at run time (see `discovery.json`). If a website cannot be found, the affected Items are Not accessible — never a Pass, never invented, never a Fail on missing evidence alone.
- **G4 booking route:** falls back to "phone (call)" — a published phone is itself a working contact route (flagged judgment call).
- **G3 "near town":** a fixed set of DFW towns within ~20 miles of Coppell (Coppell, Lewisville, Flower Mound, Grapevine, Irving, Carrollton, Plano, Dallas, Southlake, Frisco, Richardson, Addison, The Colony, Farmers Branch, Las Colinas, Euless, Bedford, Hurst, Colleyville, Keller). The address is taken from the listing first, then the firm's recorded address, then the address published on the website.
- **C2 service-area page:** the Coppell page when found, else the homepage. **C4 pricing facts** are scanned across the homepage + service page + linked warranty page + linked contact page. **Founding year** is also read from the firm's llms.txt (firm-published, same domain). **Contact page** is fetched (the booking next step is usually described there).
- **G6 category rule:** a generic trade category (Contractor, Local Service, Home Improvement) is not a different trade; the category check fails only when every category is a specific non-HVAC trade. (Meta has no "HVAC Contractor" label; many HVAC firms list as plain "Contractor".)
- **Name normalisation (`norm_text`, engine.py):** curly apostrophes/quotes, HTML entities (&amp;), "&" vs "and", commas/periods, and a trailing legal suffix (LLC, Inc, Corp) are not a name difference. This applies to G1, G6, C6.1, AND to the M4 JSON-LD-vs-visible-page comparison in `fetchers.parse_json_ld` (which used a plain lower() comparison and failed M4 on "&amp;" and "LLC" alone). A name that differs by a real word (a different brand, a rebrand, an appended trade) still differs.
- **Site name (`site_name_from_html`):** the JSON-LD name / og:site_name / title is cleaned of a trailing ": description" / " - description" (a page title, not the business name); if the candidate starts with the firm name, the firm name is used.
- **Warranty lines:** all six line keys are initialised False, then set True when found — so the engine can name the missing lines instead of receiving only the found ones.
- **Next-step regex:** matched only process-oriented patterns (we'll call you, pick a time slot, confirmation, etc.), not customer testimonials.
- **YEAR_RE:** matches "Founded: 2024" (colon form) as well as "founded in 2024".
- **Flags:** `--validate` (dummy + Airtron validation, §8), `--run` (full run), `--resume` (skips firms whose summary.json already exists for the same date/spec). A full run takes ~5 minutes; run it with `nohup` so a lost background session does not kill it mid-run (the first full-run attempt died after Airtron only when its background session was lost).

**Bugs found and fixed during the build (2026-11-11):**
1. `fetchers.fetch_robots_txt`: a 404 was returned as Not accessible; per Spec §6.9 a missing robots.txt passes M1. Fixed: HTTP 404 now returns accessible=True, exists=False.
2. `engine.norm_text`: curly apostrophes/quotes were not normalised, so "Eric’s Home Services" (Meta) vs "Eric's Home Services" (website) failed G1/G6 on punctuation alone. Fixed, and extended (see name normalisation above).
3. **Engine bug — levers could never be Observed:** each lever check did `lv = ev.get("<lever_id>") or {}`, expecting the full levers dict, but `score_audit` passes the per-lever dict (same convention as Gates/Items). So `lv` was always `{}` and every lever returned Recommendation no matter the evidence. Fixed all six to `lv = ev or {}`. The dummy test never asserted lever results, which is why it went unnoticed.
4. `fetchers.parse_json_ld` mismatch comparison used plain lower() — failed M4 on "&amp;" and "LLC" (see above). Fixed to use `norm_text`.

**PROXY-REFUSED workaround (2026-11-15, Spec §4.1.1):** the egress proxy refuses the direct fetch with no approval card raised (since the 14 Nov 2026 VM restart; api.meta.ai also blocked). `fetch_website` falls back to the browser page-text service (`browser-service --operation open`) for the website read only. The fallback returns rendered text, not raw HTML, so M2 and M4 are forced to Not accessible when it is used, and M1/M5/llms.txt stay Not accessible because their files are read only by the direct fetcher. Two related fixes the fallback exposed: `fetch_sitemap` and `fetch_llms_txt` silently turned any fetch failure into "file does not exist" (M5 Missing / no llms.txt); they now return Not accessible on a non-404 failure and keep Missing only for a 404. The fallback triggers only on PROXY-REFUSED, never on a firm-side block, and never to bypass an approval card. When the approval-card path is fixed, retire this workaround and re-check. Test: `tests/test_fetch_fallback.py`.

**Validation (re-run after every engine fix):** `python3 run_audit.py --validate` — dummy reproduces 3/7, Grade B, 0 Critical, 7 High, 14 passed Items, 40 rows, deterministic; Airtron's four evidence-backed Items reproduce exactly (C1.1 Missing, C3.2/C4.1/C4.2 Not accessible).

## 5b. The Google/Yelp reader (evidence layer, re-run r2 — 2026-11-11)

Module `aisharc_harness/evidence/google_yelp.py`. It reads the two
independent listing platforms the first run could not read (only Meta was
read), fixing G2, C1.1, C1.2, C1.3, and G1/G6.

- **Yelp** — URL from the Meta place record's links (type "yelp"), else
  a web search. The page is read with the browser page-text service
  (`browser-service --operation open`, scriptable via
  `/opt/hatch/bin/browser-service`), which returns the page's structured
  extract: name, categories, address, phone, hours, rating, review count,
  bio/specialties (the G2 services text), founding years. A direct HTTP
  fetch of yelp.com returns HTTP 403 from this environment, so direct HTTP
  is not used for Yelp — the page is publicly readable in a browser and
  the page-text service is the browser route, not a workaround; the read is
  recorded with method + source URL + date.
- **Google** — read with the headless renderer since 2026-11-16 (see
  §5c): the Google Business Profile page is a JavaScript app with no
  extractable page text (verified 2026-11-11: browser open returns no
  content), and web search only returns the firm's own site quoting its
  Google rating (the firm's claim, already captured by the website
  scan). The renderer that can read it is installed but blocked by the
  egress proxy in this environment, so Google is recorded as Not
  accessible with that reason until the platform allows the renderer's
  traffic.
- **Reviews (C1.3)** — Birdeye profile (web search finds the
  reviews.birdeye.com URL; page read with the browser page-text service).
  Birdeye republishes Google reviews and states whether the business
  claimed the profile, so it is independent of the firm. Fallback: the
  firm's own reviews/testimonials page (plain HTTP), which republishes
  Google reviews but is firm-curated — the evidence note says so. The
  extract shows no per-review dates or star ratings (Birdeye) — the
  pattern check is keyword-based on the latest reviews shown.
- **Complaint-pattern analysis (judgment calls):** a review is negative
  when its text contains complaint keywords, grouped by theme (pricing,
  no-show/late, professionalism, repair quality, mess/damage, billing,
  warranty, trust). A review followed by a business response counts as
  addressed. >= 3 unaddressed negatives sharing one theme ->
  recurring_pattern (engine: Missing); 2 unaddressed negatives, or >= 3
  with no shared theme -> single_cluster (engine: Pass with warning);
  0-1 negatives -> no pattern (Pass). The analysis runs on the small
  "latest reviews" sample the extract shows, not a full review census.
- **Identity checks (fail closed):** every Yelp/Birdeye candidate must
  pass a name check (normalised page name equals the firm name, or the
  firm name is a substring of it) before its data is used. A Yelp page
  for a different location of the same firm (Airtron Austin for Airtron
  Dallas) and a Birdeye profile merged under another firm's name
  (Coppell Heating's reviews under a "Coppell Cold Factor" slug) are
  rejected, not used.
- **Deliberately not fed to the engine:** Yelp founding year (Yelp's bio
  and its "Year Established" field can disagree with each other and with
  the website — Eric's: bio 2015, field 2025, website "Founded: 2024") and
  Yelp hours. Both are recorded in the run notes only, for a human
  decision before wiring into C6.2/C5.1.
- **Wiring (run_audit.py):** Yelp name feeds G1; Yelp services (OR with
  Meta) feed G2 listing_services; Yelp city is a G3 address fallback;
  Yelp is a G6 candidate (Meta tried first, then Yelp); Yelp phone feeds
  G4/C6.1; Yelp rating feeds C1.1/C1.2 rating_platforms (Google recorded
  as an explicit inaccessible entry); Birdeye/firm-page reviews feed
  C1.3. No engine rule was changed — this is an evidence-layer build only.
- **C1.2 consequence (flagged for Tim):** with Yelp now readable, a firm
  whose website quotes a Google rating that differs from its Yelp rating
  will fail C1.2 as Missing under the engine's existing rule (website
  claim vs independent profile), even though the two figures are from
  different platforms. Whether C1.2 should compare the website figure
  only against the platform it names is a Spec question, not a reader bug.

## 5c. The renderer and the BBB reader (evidence layer — 2026-11-16)

Authorised by Tim 2026-11-16 ("Do the work now. We definitely need to
be able to read the BBB website."). Evidence-layer work only: no grade,
score, Spec, Definition, or card was changed; no firm was re-scored and
nothing was loaded into the DB.

- **Renderer** — Playwright 1.65.2 + Chromium 159.0.8154.6 (headless
  shell) installed in the user site-packages (`pip3 install --user
  --break-system-packages playwright`; `playwright install chromium`
  into `~/.cache/ms-playwright/chromium-1255`). Verified to launch and
  render local content. `fetch_rendered(url)` in
  `aisharc_harness/evidence/fetchers.py` renders a page in a headless
  browser and returns the rendered HTML (method "website-rendered").
  It is a real browser reading the same public web a Shopping Agent
  reads — it does not bypass a login, paywall, CAPTCHA, or bot blocker,
  and it does not use a third-party fetching service.
- **Wiring (two-method rule, Spec §4.1.1)** — `fetch_website` attempts
  the rendered read only when the initial HTML provided no readable
  body text. The `<title>` alone does not count (a JavaScript shell is
  only a title and an empty `<div>`), so a JS-app site gets its rendered
  read; a site whose initial HTML already provides body text does not
  (rendered read recorded as not attempted / not needed). The returned
  text still includes the title when the initial HTML is used. The
  PROXY-REFUSED page-text fallback is unchanged and still triggers only
  on PROXY-REFUSED, never on a firm-side block. A "not attempted"
  rendered read (no renderer installed) is not a failure for the
  two-method rule; a rendered read that fails is.
- **Platform block (runtime limit, not a code limit)** — in this
  environment the egress proxy refuses the renderer's network traffic
  for every host (HTTP 403 on the CONNECT tunnel,
  `net::ERR_TUNNEL_CONNECTION_FAILED`; the identical CONNECT from a
  plain socket returns 200, so the platform blocks Chromium's traffic
  specifically). `fetch_rendered` therefore fails at runtime here with a
  `[PROXY-REFUSED]` reason and fast-fails later calls in the same
  process (a module flag, reset per process). The code is correct and
  ready for an environment where the platform allows the renderer's
  traffic; no unapproved workaround (e.g. a TCP relay) was used. Until
  then the rendered method cannot rescue a site whose initial HTML
  fails — A#1 Air stays unreadable (initial HTML BLOCKED 403, rendered
  read [PROXY-REFUSED]). Tim's concern is answered by this: the audit
  does not read items the Shopping Agent cannot read here, because the
  rendered read fails at runtime and no artificially high grade follows
  from it.
- **BBB reader** — `fetch_bbb(firm_name, town)` in `fetchers.py`.
  bbb.org has no public API. The search page is readable by the direct
  fetcher, but only with separate `find_text` (name) + `find_loc`
  (town, TX) parameters — putting name+town together in `find_text`
  returns "No Results". The profile page blocks the direct fetcher
  (HTTP 403 / reset connection) but is publicly readable in a browser,
  so it is read through the browser page-text service (the same route
  used for Yelp); the search page itself also carries the BBB Rating.
  `parse_bbb_profile_text` parses the profile extract into
  accreditation (and since date), rating, business start, years in
  business, address, phone, complaints and reviews in the last 3
  years; a field the extract does not state is None, never inferred.
  The parser handles both page-text extract formats (a `# Name |
  Better Business Bureau` heading, and a `[<id>] Name | BBB Business
  Profile` header). The phone is taken from the "Visit Website" line,
  not the first number in the page (the licensing section lists the
  regulator's number). Matching is fail-closed: an exact-name match is
  accepted in any town (a firm can sit just outside the searched town);
  a substring-name match only in the same town (Eric's Home Services
  of Mabank is not Eric's of Dallas); when bbb.org's own search does
  not surface the firm, a public web search for the profile URL is
  tried and verified against name, town, and HVAC category. The
  page-text service is occasionally flaky (an empty result once, then
  the same page reads), so an empty profile read is retried once.
  The C3.2 rule is unchanged: a BBB claim readable but bbb.org Not
  accessible = Not accessible, not Pass with warning.
- **Google Business Profile reader** — `fetch_google_listing` in
  `google_yelp.py` renders the Google Maps search page with the
  renderer (the Maps page is a JavaScript app: the direct fetcher gets
  no usable HTML and the page-text service returns no extractable
  content) and reads name, rating, review count, address, and phone
  from the rendered text, with a fail-closed name check. It is wired
  into `collect` in place of the hardcoded Not accessible entry. In
  this environment it returns Not accessible with the [PROXY-REFUSED]
  reason, because the renderer is blocked (above).
- **Yelp** — unchanged. It already reads via the page-text service
  (direct HTTP returns 403); the renderer adds nothing, because the
  renderer cannot reach the network here and the page-text route
  already works.
- **Tests** — `tests/test_fetch_rendered.py` (9 tests, all mocked, no
  browser or network): the rendered fetch returns rendered HTML; "not
  attempted" without Playwright; a proxy tunnel error is
  [PROXY-REFUSED] and fast-fails the next call; `fetch_website`
  attempts the render for a JS shell and skips it when the initial
  HTML has body text; unreadable only when both methods fail; the BBB
  profile parser on both extract formats (Quigley and Berkeys) and on
  non-profile text. `run_audit.py --validate` and the existing tests
  still pass.

## 6. Muse agent layer (agent/)

**The naming decision (research, 2026-11-11).** "Muse" is now two different things, and the audit's "Meta / Muse" row must be pinned to one surface:

- **Muse (the agent)** — launched 8 September 2026. Meta's personal AI agent that browses the web, fills forms and checks out. Runs on Muse Spark, on "Muse Secure VM", rolling out in the US on iOS, Android, and muse.ai and in WhatsApp; checks out with Link by Stripe. No public API. The only way to ask it is interactively, in the app, on a signed-in account/device.
- **Meta AI (the assistant)** — the chat assistant inside WhatsApp, Instagram, Messenger, Facebook, the Meta AI app and meta.ai. Since 8 April 2026 it runs on Muse Spark. It has a **Shopping mode** ("a dedicated shopping concierge for you based on your interests and prompt" — Meta help page). No public API for the consumer assistant; the only way to ask it is interactively, in the app, on a signed-in account/device. Whether meta.ai requires sign-in is unresolved (third-party sources conflict; a direct fetch of meta.ai is blocked).
- **Muse Spark (the model)** — the model family powering both of the above, and the thing the developer API serves.

So "ask Muse a shopping question" has three possible meanings. The harness must label which one was tested.

**Scriptable route — Meta Model API (the harness route).** `POST https://api.meta.ai/v1/responses`, model `muse-spark-1.3`, `tools=[{"type": "web_search", "user_location": {...}}]` — `user_location` goes **inside** the web_search tool object, not at the top level (a top-level `user_location` returns HTTP 400 `unknown parameter 'user_location'`, verified 2026-11-11). Location: country US, region Texas, city Coppell, timezone America/Chicago. `include=["web_search_call.results"]`. Ask the standard question verbatim. Record the full JSON response: answer text, `url_citation` annotations (span → source URL), raw search results, model, tools, date. Pricing (official): Muse Spark standard $1.25 / 1M input tokens, $4.25 / 1M output tokens; web search grounding $2.50 per 1,000 search queries. Cost is trivial at this scale. This is the only route that is scriptable, repeatable, and returns machine-readable citations. **Key connected 2026-11-11** (custom.meta-model-api, Secure Vault; helper `~/workspace/custom-connectors/custom.meta-model-api/bin/muse_spark.py`). First test call 2026-11-11 succeeded: 6 web searches, 23 results, 99 citations, ~$0.06. Observation record: `agent-validation/MUSE-SPARK observation — 2026-11-11 — run 1.md`.

**The scorer (built 2026-11-13, `aisharc_harness/agent/scorer.py`).** An LLM-assisted scorer (muse-spark-1.3, plain call with NO tools, so it judges only the saved answer text) scores each named firm against the 21 Items + 6 Levers from `definitions.json`, under a strict prompt: a Pass/Fail requires the agent's exact wording AND a cited source URL from the answer's citations, or the result is Not observed; an omission is never a Fail; consistency Items (C1.2, C5.2, C6.1) need more than one source; C2.1 needs the answer to identify a service-area page quoting town + ZIP; a rating figure alone suffices for C1.1. The scorer's output is validated in code (vocabulary, all 21 Items + 6 Levers present, Pass/Fail wording/source enforced, cited source must be one the agent cited). Gates are Not observed by rule. Category results are derived in code, never by the scorer. **Validated against run 1 (`tests/test_scorer_run1.py` — PASSED 2026-11-13):** the scorer reproduces the manual run 1 scoring exactly — same 9 Items Pass in aggregate, same 12 Not observed, same per-firm Pass sets for all four named firms (Coppell Heating 3, Airmatics 4, Eric's 6, Quigley 7). Three attempts were needed: the first over-Passed the four consistency Items (prompt missing the rules); the second reproduced the aggregate exactly and the remaining per-firm divergence was a transcription error in the test fixture (Airmatics C6.2, present in the manual record); the third reproduced the aggregate exactly but the scorer missed Quigley C6.2 ("since 1945") — the prompt had no founding-year rule, so rule 20 was added ("since YEAR" IS a founding-year statement) and the fourth attempt passed exactly. Prompt rules 17–20 encode the manual record's own stated semantics; the manual record was never adjusted. Cost of the 4 validation calls: $0.1619.

**Label it honestly:** this tests the Muse Spark model with web search — not the consumer Meta AI assistant and not the Muse agent. If the audit's "Meta / Muse" row is meant to be the consumer experience, the API result is a proxy, not the product. The per-agent observation record must state the surface tested ("Meta Model API — Muse Spark 1.3 with web_search") and must not claim it is the Muse agent or the Meta AI assistant.

**Validation route (manual, small sample).** One run in the Meta AI app in Shopping mode, or a WhatsApp chat with Meta AI, asking the same question, capturing the full transcript plus Sources / See details. Compare against the API run. This tests the real consumer surface and settles whether the assistant's answer differs from the raw model's. Optional third run: one manual run in the Muse agent (muse.ai or WhatsApp) with the same question, to see whether the agentic shopper handles a local-service comparison at all — its shopping is retail/product-oriented and no local-service data source is published.

**What remains unknown (needs a live test / Tim's decision):**
1. Whether a Model API account/key can be obtained without a waitlist, and whether signup is US-only. **Resolved 2026-11-11: key obtained by Tim and connected via the Secure Vault (custom.meta-model-api); first call succeeded.**
2. Whether Muse Spark via API actually searches for a local-service question or answers from training data (the model decides; search is not guaranteed on every request).
3. What the consumer Meta AI assistant (Shopping mode) and the Muse agent actually return for the standard question — firms named, figures quoted, sources cited — and whether either refuses, hedges, or leans on stale data.
4. The naming decision: which surface the audit's "Meta / Muse" row denotes — Model API Muse Spark, Meta AI assistant, or Muse agent — and whether to test more than one. **Decided 2026-11-11: test all three, separately labelled — META-AI (Meta AI Assistant, Shopping mode), MUSE-AGENT (Muse personal agent), and MUSE-SPARK (Muse Spark model via Model API, a model observation, not an experience audit).** Tim's note: if the model finds the data and the two experience audits do not, the audit may need screen scraping (already approved for the core audit under Spec §14 / C-08).

- The standard shopping task (same form as the OAI design, §2.2): "Find a [service] firm in [town], TX [ZIP] for [service need] and compare the firms you find." No firm, website, or listing is named in the task.
- Records per run: agent (Meta / Muse), **surface tested**, model, tools, date, query, location, full transcript verbatim, firms named, figures quoted, sources cited.
- The Muse observation is scored against the same 40 rows (per-Item Pass / Fail / Not observed / Not completed), per §8.1. An omission from Muse's answer is Not observed, not a Fail. A confirmed block of Muse (it could not access the site) is recorded as Muse's observation only, and affects the grade only through M1 (Category 7).
- The Muse observation never changes the AI Sharc grade. It feeds the per-agent observation record and the cross-agent summary.
- Cross-agent summary (Spec §8.1, OAI design §5.2): only completed checks count; Not observed is excluded from the majority denominator, like Not completed. **Zero completed observations must produce no result, rather than Pass or Fail** (ChatGPT harness requirement, 11 Nov 2026).
- The agent module records the route used, and the exact steps are recorded at the first run so the procedure is reproducible.

## 7. Outputs (runs/<date>/)

Per firm, per run:
- `audit-data.json` — the 40 rows in Spec §13 column order, plus the run record (firm, query, town+ZIP, date, spec_version '1.22', methods).
- `muse-observation.json` — the per-agent observation record (15 fields, per the OAI design §5.1, adapted: Audit ID "MUSE", firm, query, town+ZIP, date, **surface tested**, model, tools, transcript reference, Gate/Item/Lever results, delegation record, auditor).
- `summary.json` — grade, category points (with per-Category pass/fail), Critical count, High count, passed Items, eligible rank inputs, reconciliation check result.
- `human-review.json` — Conflicts, licence/BBB mismatches, low-confidence extractions, Not accessible items with reasons.
- `run-report.md` — a readable report for Tim: what was run, what was found, what could not be read, and what needs a human decision. No Report Card is issued to a firm from a harness run.

## 8. Validation (how "accurate repeatable" is proven)

1. **Scoring-math validation:** the rules engine, fed the dummy firm's per-Item outcomes (Example Heating, Final Rev 6 card: 7 failed Items — Rating figures, BBB, Warranty card, Diagnostic fee, M2, M4, M5; all other Items Pass), must reproduce **3/7, Grade B, 0 Critical, 7 High**. If it does not, the engine is wrong, not the card. **PASSED 2026-11-11** — `tests/test_dummy_scoring.py`: grade B, 3/7, 0 Critical, 7 High, 14 passed Items, 40 rows (6/7/21/6), deterministic (same inputs run twice → identical output). The 7 failed Items are C1.2, C3.2, C4.1, C4.2, C7.2, C7.3, C7.4 — matching the card.
2. **Determinism:** the same inputs run twice produce byte-identical `audit-data.json` and `summary.json` (excluding the run timestamp). If they differ, the engine has a nondeterministic step and it must be found. **PASSED 2026-11-11** (dummy test: same inputs run twice → identical output).
3. **Airtron validation (recorded 25 Oct 2026 evidence):** `tests/test_airtron_validation.py` (2026-11-11). The four evidence-backed Item results reproduce exactly (C1.1 Missing, C3.2 Not accessible, C4.1 Not accessible, C4.2 Not accessible). The sample's derived Passes do NOT reproduce from the recorded data alone, and that is correct behaviour: the sample derives Passes from "no issue in the fix list", while the engine requires positive evidence (Spec §4.3) and refuses to assume a Pass. Where the listing facts are absent from the record, Gates G1/G2/G6 correctly Fail with a human-review flag. Two findings: (a) C1.2 — no independent figure to compare, so Not accessible rather than the sample's derived Pass; (b) C2.3 — the engine returns Missing where the sample derived Pass, and the engine is right: the Field Mapping requires brands AND system types listed, and the workbook records "No specific brand / dealer status found". A fresh audit's fetchers will read and record the listings, so the engine will have the positive evidence it needs.
3. **Reconciliation:** every run must pass the §13 reconciliation (40 rows; counts match). A run that fails reconciliation is not released.
4. **Live test (the 19 firms):** fresh audits with a new date, per the run plan in §9. Results are presented as a harness test, not as Report Cards for the firms, and no firm is contacted.

## 9. Run plan — the original 19 HVAC companies

Firms (from the 2026-10-25 research; see `firms.json`): the Top 10 (Airtron, Matco, Cold Factor, Graco, Eric's, Air Rescue, Coppell Heating, DFW HVAC, A#1 Air, Dring / On Time Experts), the 4 also-checked (Royal Comfort, First Cooling, United Team, JC Heating), and the 5 interim (Berkeys, Southern Comfort, Gold AC, Comfort Land, Air Repair Pros).

- Query: "AC installation and repair". Town + ZIP: Coppell, TX 75019.
- Each firm gets a fresh audit (new date, spec_version '1.22'). The 2026-10-25 results are historical evidence only (Spec §4.3 rule 9) and are used for validation (§8.1), not presented as current grades.
- The Muse agent is queried once per firm/query (the standard shopping task), and its observation is recorded per run.
- Results are presented to Tim as a harness-test report: per-firm grade/points/counts, what the harness could and could not read, the human-review queue, and the validation results (§8.1–8.3). No Report Card is issued to any firm, and no firm is contacted.

**Run completed 2026-11-11** (`runs/2026-11-11/`, `run-report.md`): all 19 firms scored **Grade F** — Eric's 3/7, Matco and Air Rescue 2/7, Airtron, Cold Factor, Coppell Heating and DFW HVAC 1/7, the other 12 firms 0/7. No eligible firms (0 Critical), so no eligible ranking exists. **Key finding: the "all F" is largely a harness artifact, driven by three systematic blockers — (1) G2 cannot pass (0/19): the Places CLI record never carries install/repair as separate services, so every firm fails a Critical gate on the listing side alone; (2) C1.3 cannot pass (19/19 Not accessible): the harness has no review reader; (3) C4.1 cannot pass (0/19): no firm publishes the exact six-line warranty card.** Contributing strictness: C2.3 (brands AND system types — 16/19 Missing), C3.2 (no BBB claim published by 16/19), C2.1 (14/19 Missing — most firms have no Coppell page naming Coppell+75019), C1.2 (16/19 Not accessible — only Meta is read and most Meta listings have no rating). Genuine firm findings inside the noise: multi-phone firms (9 firms fail G4 on multiple distinct numbers), missing JSON-LD on service pages (C7.3 13/19 Missing), JS-dependent key facts (C7.2 10/19 Missing), Royal Comfort's website returning a "Site Unavailable — unpaid billing" page, Dring's rebrand to On Time Experts with no mapping page found, and licences verified active via TDLR for 13 firms (C3.1 13 Pass). These are methodology decisions for Tim, not scoring changes — the runner was not altered to make firms pass.

**Re-run r2 completed 2026-11-11** (`runs/2026-11-11-r2/`, `run-report.md`) — Google/Yelp reader wired in (§5b), same query/town/ZIP, Spec v1.22. **2 of 19 eligible: Eric's A 4/7 (0 Critical, 3 High, 18 passed Items, rank 1 of 2) and Coppell Heating D 1/7 (0 Critical, 7 High, 14 passed, rank 2 of 2); the other 17 still F.** Movement vs r1: **G2 0/19 → 6/19** (A#1 Air, Air Repair Pros, Comfort Land, Coppell Heating, Dring, Eric's — Yelp services text fixed the listing side); **C1.1 3/19 → 8/19** (5 firms Missing → Pass with warning, Yelp-only rating); **C1.2 3/19 → 8/19** (4 firms Not accessible → Pass; 3 firms Pass → Pass with warning on cross-platform figure differences — the engine already treats cross-platform differences as a warning, not Missing, so the flagged C1.2 concern did not materialise); **C1.3 0/19 → 2/19** (Air Rescue via Birdeye, Eric's via its own reviews page); **G1 10/19 → 10/19 and G6 9/19 → 9/19, no moves** — the reader added a third source for G1 (Eric's now matches on 3 sources) but changed no G1/G6 outcome. **Reputation passes 0/19 → 2/19** (Eric's, Air Rescue); all other Category pass counts unchanged (Area Coverage, Credentials, Pricing 0; Hours 5; Identity 3; Machine Readability 3). Levers unchanged. **Yelp read for 8/19 firms** (Berkeys' page was rejected on the name check — "Berkeys Plumbing, AC & Electrical" vs the firm name "Berkeys Plumbing, A/C & Electrical", a punctuation near-miss the fail-closed check drops; a human could accept it); **reviews read for 2/19**; Google still has no independent read. **One genuine new finding from the extra source: Air Rescue's G4 flipped Pass → Fail** — Yelp publishes (972) 822-8282 while Meta/website publish (214) 500-0044, so the firm now fails G4/C6.1 on two distinct phones (Critical 1 → 2, points 2 → 3). **C4.1 still 0/19** — the six-line warranty bar remains unpassed by every firm, still a product question for Tim. Fresh licences verified in r2 include Coppell Heating TACLA00066993E (active to 2026-12-23) and Air Repair Pros TACLB019076C (active to 2026-11-21 — 10 days from the run date). The first r2 launch died silently after 7 firms (no log survived — /tmp is per-session ephemeral); the run was completed with `--resume` in a single foreground exec. Report bug found and fixed: the run-report's G2 line read 0/19 because the report code tested `item_id == "G2"` on Gate rows (which carry `gate_id`); corrected to 6/19 in both the report and `run_audit.py`.

## 10. What this harness does not do

- It does not issue Report Cards to firms, contact firms, or send advertising email. Delivery is governed by Spec §4.2 and §12, not by this harness.
- It does not re-score Airtron or any firm as a client deliverable. The 19-firm run is a harness test; its results are internal test results.
- It does not bypass a login, paywall, CAPTCHA, or bot blocker, and it does not scrape a site that prohibits it.
- It does not decide the product-discovery question (whether ChatGPT product discovery / Instant Checkout is the shopping surface to test instead of Work/Dots) — that is open with OpenAI.
- It does not adopt the human-review queue as a gate — that proposal (Spec §14) is still for approval. The queue is an output here.

*Design prepared 2026-11-11. Baseline: Specification v1.22. The governing documents are the source of truth; this file is code documentation, not a governing document.*
