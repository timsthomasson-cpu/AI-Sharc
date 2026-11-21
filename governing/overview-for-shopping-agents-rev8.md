# AI Sharc — What we need from Shopping Agents

**Date:** 2026-11-21 — Rev 8 (Spec v2.10)
**Rev 8 (2026-11-21) (Spec v2.10):** §2 task text now names the service area — "Find a [service] firm whose service area includes [town], TX [ZIP] for …" — instead of the town, so the comparison covers the firms that serve the ZIP, not only the firms located in it (wording decided by Tim 2026-11-21). No shopping query has been run with this wording yet (as of 2026-11-21). No other change.
**Rev 7 (2026-11-19) (Spec v2.9):** §3.2 first two bullets aligned with Specification §4.3 rule 2 — a result that cannot be tied to a source is Not accessible, not Missing; Missing requires citing the page where the fact should appear. Accompanies Field Mapping for Shopping Agents Rev 4 (2026-11-19). No other change.
**Rev 6 (2026-11-19) (Spec v2.8):** §3.2 contradiction fixed — the two bullets that told directed-audit agents to record Not observed now use Missing / Not completed; Not observed stays for shopping-query observations only (§3.1). Accompanies Field Mapping for Shopping Agents Rev 4 (2026-11-19). No other change.
**From:** AI Sharc (aisharc.com)
**Accompanies:** AI Sharc — Field Mapping for Shopping Agents (the audit rubric)

## 1. Who we are

AI Sharc produces the AI Shopping Health Audit Report Card. We audit local service firms' websites — starting with HVAC in Texas, then Plumbing, Electrical, and Roofing — so that a Shopping Agent can find, identify, match, trust, price, and read a firm. The audit is diagnosis plus a fix list only; we do not do implementation for firms.

A Report Card grades a firm on 21 Items in 7 Categories (Reputation, Area Coverage, Credentials and Trust, Pricing and Warranty, Hours and Active Status, Identity and Contact, Machine Readability), worth 100 points in total. Grades run A–D by points; F applies only when the firm's website is unreachable on the firm's side, or the firm is not in business. The grade is what a firm can control, and a firm also controls access to its own site, by keeping it reachable and readable. Where a firm appears in a shopping result is separate context, never a permanent rank and never something that overrules the grade.

We need Shopping Agents to do two things for us, as two separate pieces of work. This overview describes both. The Field Mapping that accompanies it is the rubric for the AI Sharc Audit.

## 2. The shopping query

We ask you to run the shopping query: three standard shopping tasks, as a fresh ordinary conversation, with no rubric and no AI Sharc context. Each task names a service, a town, and a ZIP, and asks for a comparison. It does not name a firm, a website, or a listing.

| # | Task | Form |
|---|---|---|
| 1 | Combined | "Find a [service] firm whose service area includes [town], TX [ZIP] for [service need] installation and repair and compare the firms you find." |
| 2 | Repair only | "Find a [service] firm whose service area includes [town], TX [ZIP] for [service need] repair and compare the firms you find." |
| 3 | Installation / replacement only | "Find a [service] firm whose service area includes [town], TX [ZIP] for [service need] installation and replacement and compare the firms you find." |

Example (HVAC, Houston, TX 77002, AC):

- Task 1 — combined (installation and repair): "Find an HVAC firm whose service area includes Houston, TX 77002 for AC installation and repair and compare the firms you find."
- Task 2 — repair: "Find an HVAC firm whose service area includes Houston, TX 77002 for AC repair and compare the firms you find."
- Task 3 — installation and replacement: "Find an HVAC firm whose service area includes Houston, TX 77002 for AC installation and replacement and compare the firms you find."

No shopping query has been run with this wording yet (as of 2026-11-21). Runs made before Rev 8 used the earlier wording ("Find an HVAC firm in [town], TX [ZIP] for …") and keep it.

For the shopping query:

- Discover firms yourself. We do not send you a firm list for the shopping query.
- Run each task as a separate fresh session.
- Do not use the audit rubric in this run. What you do with the plain shopping request is the point.

**What to return for the shopping query.** Return the full answer, in this format:

- The full answer verbatim — the complete response as returned, including every firm you named, every figure you quoted, and every source you cited.
- The date and time of the run.
- The model you used.
- The tools you used.
- The Vendor — the corporation supplying the Shopping Agent (for example Meta, OpenAI, Anthropic, Google, Perplexity, xAI, AI Sharc).
- The Product — the actual tool or agent used (for example Meta AI, ChatGPT, Claude, Gemini, harness).
- The signed-in account used for the run.
- The session state and mode of the run.

AI Sharc records, from your answer, what you actually checked for each Item. You do not need to score the answer — just return it as it came back.

## 3. The AI Sharc Audit

Separately, we ask you to perform an AI Sharc Audit for a specific firm, using the Field Mapping rubric that accompanies this overview. For this run we do direct you to a firm: AI Sharc names the firm, the service, the town and ZIP, and the query.

For the AI Sharc Audit:

- Work through the 21 Items in the Field Mapping, in the 7 Categories, and record the evidence for each Item.
- Record the eight ranking suggestions: the six Section 6 factors — S1 Booking and quote route, S2 Availability, S3 Price for this user, S4 Brand and system coverage, S5 Service-area dispatch, S6 Machine discovery (llms.txt) — as Observed, Recommendation, or Not checked; and the two Section 4 Ranking Suggestions — C3.2 BBB accreditation and rating consistent with bbb.org and C4.1 six-line warranty card — as Complete, Suggested, or Not checked.
- Return raw data only. Do not calculate a grade and do not build a Report Card. AI Sharc computes grades centrally from the raw audit data.
- The shopping query and the AI Sharc Audit must stay separate. Run the shopping query first, as a fresh ordinary conversation with no rubric and no AI Sharc context. Then run the AI Sharc Audit as a separate run, where you are given the rubric and the specific firm. The rubric must not contaminate the neutral shopping query.

### 3.1 What to return

For each Item, return a row with:

- The Item (code and description, e.g. C4.2 diagnostic fee in dollars).
- The result: Pass, Pass with warning, Missing, Conflict, Not accessible, or Not completed (the official Spec §7 statuses, plus Not completed when a tool was unavailable). Not observed and reason codes (a)/(b) stay for shopping-query observations only.
- The source URL where you found the evidence.
- The exact wording or figure you found.
- The date and time you checked it (checked_at), in ISO 8601 format with seconds and time-zone offset.

Status mapping for the consolidation majority: Pass and Pass with warning count as pass, Missing and Conflict count as fail, and Not accessible and Not completed are left out.

For the run, also return:

- The Vendor — the corporation supplying the Shopping Agent (for example Meta, OpenAI, Anthropic, Google, Perplexity, xAI, AI Sharc).
- The Product — the actual tool or agent used (for example Meta AI, ChatGPT, Claude, Gemini, harness).

For each ranking suggestion, return its result with the evidence where it was observed: Observed, Recommendation, or Not checked for the six Section 6 factors (S1 Booking and quote route, S2 Availability, S3 Price for this user, S4 Brand and system coverage, S5 Service-area dispatch, S6 Machine discovery (llms.txt)); Complete, Suggested, or Not checked for the two Section 4 Ranking Suggestions (C3.2 BBB accreditation and rating consistent with bbb.org and C4.1 six-line warranty card).

The Field Mapping — a separate document that will be supplied with this overview — specifies the exact table format. Follow it, so your audit can be validated and imported without rework.

### 3.2 The rules that matter

- **Evidence for every result.** Every result cites the source URL you checked and checked_at. A Pass, Pass with warning or Conflict also cites the exact wording or figure you found. Missing means you read the page where the fact should appear and it is not there; cite that page. A result you cannot tie to a source is recorded as Not accessible, never as a Pass and never as Missing by inference. (One exception: for G6 verifiable listing, no listing found after checking Google, Meta and Yelp is Missing, because the Item requires a listing to exist.)
- **Not accessible is not a fail.** If you could not find or read the evidence for an Item, record Not accessible, or Not completed if a tool you needed was unavailable. Both are left out of the consolidation majority. Do not guess, estimate, or fill it in.
- **No partial credit, no provisional Pass.** An Item passes only when the evidence meets its pass criteria in full.
- **A firm's own statement alone is not evidence** for a ranking suggestion that needs a live test, and it does not change a score.
- **If you cannot access a site, record that.** Mark the Item Not accessible (the Spec's status for an unreadable site), with the reason (for example, the site would not load, or the page could not be read). If a tool you needed was unavailable, mark it Not completed instead. Do not invent the missing fact.
- **One issue, one place.** An issue is recorded once, in the one section it belongs to.
- **Do not contact the firm.** The audit uses public evidence only. Do not call, email, or message a firm about the audit.
- **Do not share the rubric.** The Field Mapping and this overview are provided for the audit purpose. Do not share them with a firm or outside party.

### 3.3 What happens with your audit

AI Sharc's orchestrator validates your raw audit table, imports it, and compares and consolidates the parallel audits from the Shopping Agents. The grade and the Report Card are computed centrally from that evidenced raw data — by AI Sharc, not by any single agent — and the website serves the centrally derived grade and card. Your raw table, with its source URLs, exact wording or figures, and dates, is the audit trail.

When the orchestrator requests a run, the AI Sharc auditor returns the documents for the requested firms; the orchestrator handles versioning.

A firm the shopping query names enters the audit universe and gets graded. A firm in the universe the shopping query never names is the invisibility signal: it was not found. That is why the shopping query and the AI Sharc Audit are separate — the first shows what a shopper actually finds, the second checks what the firm publishes.

## 4. Documents

Two documents come with this overview:

- **This overview** — what we need you to do.
- **AI Sharc — Field Mapping for Shopping Agents** — the audit rubric: what to check, the pass criteria, and the evidence to record for each Item.

We do not send the full AI Sharc Audit Specification (it carries commercial terms and internal reasoning) or the Observation Design (it governs how AI Sharc runs observations and is internal to AI Sharc). The Field Mapping is the rubric you need.

## 5. Next step

The Orchestrator will direct each run. It will identify the city, the schedule, the firm, the service, and the query. For the shopping query, that means the three standard tasks for a town and ZIP. For the AI Sharc Audit, that means one named firm and the Field Mapping. Send back the raw audit table in the format the Field Mapping specifies, and the full shopping-query answers as returned.
