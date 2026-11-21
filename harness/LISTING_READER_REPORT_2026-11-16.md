# Listing-reader / renderer work — per-firm report (2026-11-16)

Authorised by Tim 2026-11-16. Evidence-layer work only: no grade, score,
Spec, Definition, or card changed; no firm re-scored; nothing loaded into
the DB. Code: `aisharc_harness/evidence/fetchers.py` (`fetch_rendered`,
`fetch_bbb`, `bbb_search`, `parse_bbb_profile_text`), `aisharc_harness/
evidence/google_yelp.py` (`fetch_google_listing`), `run_audit.py` (note
wording only). Design note: `DESIGN.md` §5c. Tests:
`tests/test_fetch_rendered.py` (9 tests, mocked). `run_audit.py
--validate` and all existing tests pass.

## What was built

- **Renderer:** Playwright 1.65.2 + Chromium 159.0.8154.6, verified to
  launch and render local content. `fetch_rendered` is wired into
  `fetch_website` as the rendered method of the two-method rule (Spec
  §4.1.1), attempted only when the initial HTML provides no readable
  body text (a title alone does not count). The PROXY-REFUSED page-text
  fallback is unchanged.
- **BBB reader:** search via the direct fetcher (separate `find_text` +
  `find_loc` — the old combined parameter returned "No Results"), profile
  via the browser page-text service, parsed into accreditation/rating/
  address/phone/business start/complaints/reviews. Fail-closed matching
  (exact name any town; substring only same town; web-search fallback
  verified by name/town/HVAC). C3.2 rule unchanged.
- **Google Business Profile reader:** via the renderer (Maps is a JS app).
  Wired into `collect`. Yelp unchanged (already reads via page-text).

## Runtime limit (affects every firm below)

The egress proxy refuses the renderer's network traffic for every host
(HTTP 403 on the CONNECT tunnel, `net::ERR_TUNNEL_CONNECTION_FAILED`),
while the identical CONNECT from a plain socket returns 200. The
renderer therefore fails at runtime in this environment with a
[PROXY-REFUSED] reason and fast-fails later calls in the same process.
The code is correct and ready for an environment where the platform
allows the renderer's traffic; no unapproved workaround was used. This
answers Tim's concern directly: the audit does **not** read items the
Shopping Agent cannot read here — the rendered read fails at runtime, so
no firm gets an artificially high grade from it.

## Per firm — what is now readable, what still is not, and why

### New Braunfels Air Systems (firm 596, swiftbreezesystems.com)
- **Website: no change.** Already readable via the unchanged
  PROXY-REFUSED page-text fallback (3,678 chars); the rendered read is
  correctly not attempted (not needed). Unreadable: False.
- **BBB: no profile exists.** "No BBB profile found" — a true negative,
  not a read failure.
- **Google listing: still Not accessible** — the renderer is blocked
  (platform, above).

### A#1 Air (firm 2, anumber1air.com)
- **Website: the rendered read is now genuinely attempted — but it
  fails, so the site stays unreadable.** Before, the rendered read was
  recorded "not attempted — no renderer". Now: initial HTML [BLOCKED]
  HTTP 403 (the site/WAF blocks the direct fetcher; the PROXY-REFUSED
  fallback does not trigger on a firm-side block, per Tim's instruction),
  rendered read attempted and refused by the egress proxy
  ([PROXY-REFUSED]). Both methods failed, so unreadable: True, text
  empty. This is the two-method rule working as specified — the failure
  is now recorded with its reason instead of "not attempted".
- **BBB: no profile found** for "A#1 Air" or "A#1 Air Conditioning"
  near Coppell, TX. (The Eric's caveat below applies in general: a
  profile could exist yet be undiscoverable; the reader reports it
  rather than guessing.)
- **Google listing: still Not accessible** — renderer blocked (platform).

### Quigley Heating & Air (Farmers Branch)
- **BBB: NOW READABLE — the main win.** The old reader returned "No
  Results" (combined `find_text` parameter). Now the full profile reads:
  accredited since 12/1/1958, rating A+, 80 years in business, business
  started 1/1/1946, 0 complaints in the last 3 years, 10 customer
  reviews, 13720 Diplomat Dr, Farmers Branch, TX 75234-8916,
  (972) 992-1450. Every figure verified against the live profile.
- Website and Google listing were not re-tested for this firm (not an
  evidence-access problem case).

### Berkeys (Dallas)
- **BBB: NOW READABLE.** Accredited since 11/1/1992, rating A+, 51
  years, business started 7/9/1975, 4311 Belmont Ave STE 125, Dallas,
  TX 75204-3032, (214) 612-0133. Complaints and review counts are not
  stated in this profile's extract, so they are recorded as unknown,
  not invented.
- **Yelp: no change** — already readable via the page-text service
  (rating 2.9, 442 reviews). The renderer adds nothing for Yelp.
- **Google listing: still Not accessible** — renderer blocked (platform).

### Airtron (Dallas)
- **BBB: NOW READABLE.** Accredited since 11/19/2025, rating A+, 105
  years, business started 1/1/1921, 10440 Olympic Dr, Dallas, TX
  75220-4426, (972) 276-2117.
- **Website: no change** — still unreadable (expired TLS certificate,
  CERT-INVALID). The renderer cannot help a certificate failure.

### Eric's (Dallas)
- **BBB: NOT readable — a genuine limit, and a false negative.** The
  firm has a BBB profile (rating B, not BBB accredited, verified by
  direct browser read of
  `bbb.org/us/tx/dallas/profile/air-conditioning-contractors/
  erics-1075-90294375`), but neither bbb.org's own search nor a web
  search surfaces it for "Eric's near Dallas, TX" — the search returns
  other Eric businesses and Eric's Home Services of Mabank. The reader
  reports "no BBB profile found" rather than returning the wrong firm's
  profile (the Mabank firm is explicitly rejected: a substring-name
  match is accepted only in the same town). This is a limit of BBB's
  own search/indexing, not of the reader — the profile is findable only
  if its URL is already known.

## Limits found

1. **Renderer blocked by the egress proxy (platform).** Every rendered
   read fails in this environment. The rendered method, the Google
   Business Profile reader, and any JS-app site rescue all wait on the
   platform allowing the renderer's traffic. No workaround was used.
2. **BBB search is fuzzy.** A profile can exist yet not appear in
   bbb.org's search results (Eric's of Dallas) or in web search, so the
   reader can produce a false "no profile found". It fails closed
   (never the wrong firm) rather than guessing.
3. **BBB profile pages need the page-text service** (direct fetcher gets
   HTTP 403 / reset). The service is occasionally flaky (an empty
   result once, then the same page reads); the profile read retries once
   on an empty result.
4. **The page-text extract format varies between profiles** (two header
   formats; some profiles do not state complaints/review counts). The
   parser handles both formats and records unstated fields as unknown.
5. **Google Business Profile has no other independent read.** Web search
   only returns the firm's own site quoting its Google rating (the
   firm's claim, not independent). The renderer is the only route, and
   it is blocked (limit 1).

## Operational costs

- Playwright + Chromium install: one-off, no ongoing cost.
- Per firm, the BBB reader adds: 1 direct BBB search fetch (free), 1
  page-text service read (free, same service already used for Yelp),
  and only when bbb.org's search does not surface the firm, 1 web
  search ($2.50/1,000 queries = $0.0025). The rendered read, when it
  can run, is a local browser launch — no per-call API cost.
