# Shopping Agent Observation Design — Shared Instructions, Execution Profiles, and Results Format

**Status: DRAFT — Rev 17, prepared 2026-11-20 (change approved by Tim 2026-11-20), applying Specification v2.9 (approved by Tim 2026-11-19). Working procedure document, not a governing document — kept per Tim's decision 2026-11-18, path (a).**

**Rev 17 — 2026-11-20: §9.4 brought into step with Licensed Home Trade Field Mapping Rev 10 and the database as built. The observation tables are no longer documentation only: they are built in the test database (Test AI Sharc Orchestrator) and loaded with the three Meta AI Houston runs of 2026-11-19; AI Sharc Orchestrator East stays the live target and is not built yet. `agent_runs` gains task_number, service, checked_at_text, source_file, file_hash and loaded_at, and session_state is limited to logged in / logged out / incognito. `agent_run_firms` gains figure_quoted, source_cited and notes. Match status is a join, refreshed when firms are added; the observation content never changes (Tim, 2026-11-20). A workbook already loaded under the same file hash is skipped. Rev 16 stays untouched.**

**Rev 16 — 2026-11-19: §9.4 `agent_run_firms` gains cited_url, cited_own_domain, mention_type, total_firms_shown and turn, matching Field Mapping Rev 9 and Shopping Query Return Template Rev 7. Baseline re-based to Specification v2.9 (wording corrections only). Rev 15 stays untouched.**

**Rev 15 — 2026-11-19: applies Specification v2.8 — §9.4 agent_runs re-based to checked_at/query_id (date_checked, time_checked and timezone dropped; query_id, checked_at, repeat_number, session_state, location_setting added); cross-references Field Mapping Rev 9 and Shopping Query Return Template Rev 7 (2026-11-19). Rev 14 stays untouched.**

**Rev 3 — 2026-11-19 (Rev 14 in the running sequence): applies Specification v2.5 — file naming (Spec §13 'File naming and folder layout'): observation files are per-run (one workbook and one .md per shopping query, covering all firms in that run), not per-firm, so the per-firm '__' audit-file pattern does not apply to them; §9.4 adds the observation-file naming line. Cross-references: Field Mapping Rev 5 and Shopping Query Return Template Rev 3 (2026-11-19). Rev 2 stays untouched.**

**Rev 2 — 2026-11-19 (Rev 13 in the running sequence): applies Specification v2.4 — observation reason codes (Spec §7.1): (a) Not mentioned, (b) Mentioned, not demonstrated; neither is a Fail; both are excluded from the cross-agent majority; observation rows only, never audit rows. §2.5 applies Claude's replacement verbatim and aligns the (a)/(b) definitions to Spec §7.1 (Not completed takes no code); §9.1 field 11 requires a reason code (a) or (b) and a reason field for any Item recorded as Not observed, and still requires a reason field for any Item recorded as Not completed. Cross-references: Field Mapping Rev 4 (internal Licensed-Home-Trade-Field-Mapping 2026-11-19 Rev 4) and Shopping Query Return Template Rev 2 (2026-11-19). Rev 1 stays untouched.**

**Rev 1 — 2026-11-19 (Rev 12 in the running sequence): applies Specification v2.2 and Tim's decisions of 2026-11-18/19 — three-table observation design (agent_runs / agent_run_firms / agent_observation_rows); run metadata fields; follow-up rule amended; sources-panel rule; review status per row; reason codes (a)/(b) defined; firm aliases and match status; re-baseline to Spec v2.2. Rev 11 stays untouched.**

**Amendment 2026-11-18 — contradiction fix and path (a) (Tim's decision, 2026-11-18):** (1) The contradiction with Field Mapping Rev 6 is fixed: observation records ARE stored in the audit DB, in the observation tables `agent_observations` / `agent_observation_rows` (Spec §13; §9.4) — the "whether observation records get a database table is undecided" language is removed and superseded. The Agent Validation record (files) and transcripts stay as the human-readable audit trail. Observation records are NOT AI Sharc audit rows and do NOT enter the scored audit tables. (2) This design is KEPT as a working procedure document — it is not retired and it is not a governing document; the 13 Nov 2026 "governing document / Latest folder" placement is superseded. (3) The stale §6.1 cross-reference is corrected to §9.1. Rev 9 stays untouched.

**Rev 11 — draft changes (18 Nov 2026, applying Tim's decision of 18 Nov 2026):** adds Vendor and Product fields to the run record (§2.1), the per-agent observation record (§9.1, fields 16–17) and the `agent_observations` table (§9.4), per Specification v2.1 §3/§13 — Vendor is the corporation supplying the Shopping Agent, Product is the actual tool or agent used, both open text; the harness's own scored audits write Vendor "AI Sharc", Product "harness". Existing field numbering in §9.1 is unchanged. Uniqueness key for `agent_observations` is (vendor, product, agent_label, firm_id, query, town_zip, date_checked), per Tim's decision of 18 Nov 2026, aligning with Field Mapping Rev 7. Rev 10 stays untouched.

**Rev 10 — draft changes (17 Nov 2026, applying Specification v2.0):** the six Stage 1 Gates are merged into the 21 scored Items (Spec v2.0 §5–§6) — there are no Gate rows; the per-agent observation record drops Gate results for the Website Access minimum condition (field 10, §9.1); audit rows 40 → 34 (7 Category reference summaries, 21 Items, 6 Levers); the AI crawler access check (former M1) is the scored Item C7.1 AI crawler access (M1), Category 7; F is the Website Access minimum condition only (Spec v2.0 §5); cross-references updated to Field Mapping Rev 5 and Definition Rev 8; the return format follows the Shopping Query Return Template Rev 2 (34 rows). Rev 9 stays untouched.

**Rev 9 — approved version. Content unchanged from Rev 8; only the status changed from DRAFT to APPROVED at Tim's approval (13 Nov 2026).**

**Rev 8 — draft changes (13 Nov 2026, applying Tim's decisions of 13 Nov 2026):** adds the three Meta profiles (META-AI, MUSE-AGENT, MUSE-SPARK) as sections 6–8, in that order, MUSE-SPARK as a model observation, not an experience audit; observation records get database tables in the audit DB (§9.4); placement decided — this design is a governing document (new governing document in the Latest folder). Sections renumbered: results format §6→§9, pilot §7→§10, undecided §8→§11, traceability §9→§12; all cross-references updated to the new numbering.

**Purpose and scope.** This design is **internal to AI Sharc**. It tells the AI Sharc auditor how to run an observation of a shopping agent and record what it demonstrates. It is **not** a guide for the agent: the agent only ever receives the neutral shopping task in §2.2 and never sees this design, the rubric, or the criteria. This document never leaves AI Sharc. The design covers shopping-agent observation generally — one shared set of instructions (§2) and results format (§9), with one execution profile per surface. The profiles in sections 3–8 are the three OpenAI profiles (sections 3–5) and the three Meta profiles (sections 6–8). Further profiles are added the same way.

**Rev 6 — draft changes (12 Nov 2026, applying Tim's review notes on Rev 5):** generalizes the title and scope from OAI-only to all shopping agents (decided 12 Nov 2026); adds the purpose and scope paragraph above; defines the three **standard shopping tasks** in §2.2 (combined, repair only, installation/replacement only — the run pack's three runs; three for now, more only by a further decision); generalizes the candidate-set reference in section 3 from "the original 19 companies" to the firms with recorded evidence for that query and town; notes the OAI-LOCAL Agent Validation row added in Field Mapping Rev 4 (§10.4).

**Rev 5 — draft changes (12 Nov 2026, for Tim's approval):** adds **OAI-LOCAL** (ChatGPT local-business discovery/search) as the **primary** OpenAI profile, per ChatGPT's product-discovery answer received 12 Nov 2026; closes the §1.4 product-discovery open question (also listed in §7 in Rev 4); names **Airtron** as the pilot firm (decided by Tim, 12 Nov 2026); adds the separate fresh-session repair / installation tests, the discovery–comparison–next-step measurements, and Get Quote recorded separately, never a prerequisite for passing.

**Rev 4 — approved version. Content unchanged from Rev 3; only the status changed from DRAFT to APPROVED at Tim's approval (11 Nov 2026).**

**Rev 3 — three ChatGPT-review fixes applied and the §9.2 Not observed majority rule adopted, at Tim's decision (11 Nov 2026):** neutral observation stated explicitly (§2.2); Category results wording clarified (§2.4, §9.1 field 12); "Not confirmed" mapped to Not observed with a reason field (§2.5, §9.1 fields 10–11); §9.2 rule adopted (Not observed excluded from the majority denominator).

**Rev 2 — delegation visibility rule added at Tim's decision (11 Nov 2026):** delegation matters only when it is visible. See 2.7.

**Baseline:** AI Sharc Audit Specification v2.9 (2026-11-19, approved 2026-11-19; v2.9 changes wording only, so all v2.8 section references stand). Every rule below cites the Spec section it comes from. The six Stage 1 Gates are merged into the 21 scored Items (Spec v2.8 §5–§6); there are no Gate rows. No Item, Lever, score, or grade changes beyond the v2.0 merge (carried into v2.8).

**Audits covered:** this design covers observation audits of any shopping-agent surface. The profiles defined here are six: the three OpenAI profiles — AI Sharc — ChatGPT Local-Service Discovery Audit (internal ID **OAI-LOCAL**, the **primary** OpenAI test), AI Sharc — OpenAI ChatGPT Work Audit (internal ID **OAI-WORK**), and AI Sharc — OpenAI Dots Audit (internal ID **OAI-DOTS**) — and the three Meta profiles — AI Sharc — Meta AI Assistant Audit (internal ID **META-AI**, Shopping mode), AI Sharc — Muse Personal Agent Audit (internal ID **MUSE-AGENT**), and AI Sharc — Muse Spark Model Observation (internal ID **MUSE-SPARK**, a model observation, not an experience audit). OAI-LOCAL, OAI-WORK, OAI-DOTS and MUSE-AGENT stay **Not tested** until their first documented runs; META-AI has one standard-mode observation (Shopping mode Not tested); MUSE-SPARK has one documented model observation (Spec §8.1; Field Mapping Rev 1 (2026-11-19), Agent Validation sheet — the META-AI and MUSE-SPARK rows are in Rev 1).

---

## 1. What these audits are

1.1. OAI-LOCAL, OAI-WORK, OAI-DOTS, META-AI and MUSE-AGENT are **separately labeled experience audits** using the same AI Sharc criteria and output structure; MUSE-SPARK is a **model observation**, not an experience audit (see section 8). They identify the experience tested, without claiming any is a dedicated shopping product (Spec §8.1, answered 11 Nov 2026). **OAI-LOCAL is the primary OpenAI test** (see 1.4); OAI-WORK and OAI-DOTS are additional experience tests of what those experiences do with the same shopping request. Each profile in this design tests one experience (Definition Rev 8, 'Experience'); the shared instructions in section 2 and the results format in section 9 are the same for every profile.

1.2. **Classification.** OpenAI Work and Dots are classified **by experience, not as shopping agents**. OAI-LOCAL tests ChatGPT local-business discovery/search — a fresh ordinary ChatGPT conversation with web search — which ChatGPT's 12 Nov 2026 answer identifies as the primary test for a local-service firm; it is likewise classified by experience, not claimed to be a dedicated shopping product. A shopping agent, for AI Sharc's purposes, is an AI agent that helps a user discover, compare, and select products or services, and the ability to complete a purchase is NOT a requirement for that classification (Spec §8.1; Definition Rev 8, 'Shopping Agent'). Work and Dots are general agents that may carry out a shopping task if delegated to them; the audit tests what the experience actually did with the task. The same classification applies to the Meta surfaces: the Meta AI assistant and the Muse personal agent are general agents classified by experience, not as shopping agents; MUSE-SPARK is classified as a model observation, not an experience at all (see section 8).

1.3. **What they test.** Whether a firm can be found and compared by that experience (or, for MUSE-SPARK, by that model), against the same criteria as the AI Sharc audit: the 21 Items in seven Categories, the 7 Category reference summaries, and the 8 Ranking Suggestions — 36 rows in total (Spec §13). There are no Stage 1 Gates in Spec v2.8; the former Gates are merged into the Items (see §1.5). For OAI-LOCAL, discovery, comparison and next-step capability are recorded separately (see section 3).

1.4. **Product discovery / Instant Checkout — answered 12 Nov 2026, question closed.** ChatGPT's product-discovery answer (pasted by Tim 12 Nov 2026; saved as `ChatGPT product-discovery answer — 2026-11-12.md` in this folder) recommends **ChatGPT local-business discovery/search as the primary OpenAI test**, with Work and Dots as additional experience tests. Product discovery through merchant catalogs / ACP is for catalog merchandise; it does not establish how an HVAC contractor is discovered. **Instant Checkout has no documented support for ordinary HVAC installation or repair** — ACP checkout is approved-partner only and its plugin checkout documentation describes physical-goods eligibility. The documented local-service conversion is **Get Quote**: eligible business cards can open a partner's quote-request widget — an approved-partner beta, backed by business-feed data and a configured plugin, and a quote request, **not** confirmation of a purchase, appointment or completed service. Get Quote / checkout availability is recorded separately (see section 3) and is **never a prerequisite for passing** the discovery-and-comparison audit. This design therefore tests OAI-LOCAL as the primary profile (section 3) and retains OAI-WORK and OAI-DOTS as additional experience tests; it does not claim any of the three is a dedicated shopping product.

1.5. **What happened to the Gates (Spec v2.8 §5–§6).** There are no Stage 1 Critical Gates in Spec v2.8. The six former Gates are merged into the 21 scored Items, or into the F minimum condition:

| Former Gate | Now |
|---|---|
| G1 exact name | Scored Item G1 exact name, 6 points, Category 6 Identity and Contact |
| G2 services in plain words | C2.2 install and repair listed separately on that page, 6 points, Category 2 Area Coverage (service-page only; the listings requirement is dropped) |
| G3 area coverage | C2.1 service-area page naming town and ZIP, 7 points, Category 2 (town and ZIP only; the street-address alternative was not carried into v2.0 or v2.2) |
| G4 contact | C6.1 one unique primary phone number everywhere, 3 points, Category 6 (phone part), and C2.4 unique primary phone and booking route on that page, 3 points, Category 2 (booking-route part) |
| G5 hours / Active Status | C5.1 day-by-day hours readable, 5 points, Category 5 (hours part); the Active Status part is the F minimum condition in §5 (a firm not in business is F) |
| G6 verifiable listing | Scored Item G6 verifiable listing, 3 points, Category 3 Credentials and Trust |

**F rule (Spec v2.8 §5).** F applies only when the firm's website is unreachable on the firm's side (CERT-INVALID, PARKED, DEAD, SUSPENDED, WRONG-CONTENT, or no website at all) or the firm is not in business (closed flag). A failed Item is never F. For an F firm, no Items are scored, no points are given, and the firm is not ranked. A reason on AI Sharc's side (APPROVAL-EXPIRED, PROXY-REFUSED) means the audit is unverified, not F, and no Grade is assigned until a re-check verifies the site.

The AI crawler access check, formerly a seventh Critical Gate (M1, v1.7–v1.18), is the scored Item C7.1 AI crawler access (M1), 3 points, Category 7 Machine Readability (Spec v2.8 §6.9). A blocked crawler fails that Item (0 of its 3 points), not the whole Grade.

## 2. Shared audit instructions (all six profiles)

### 2.1 Run record

Every run records, separately, before any result is used:

- Audit label and ID: OAI-LOCAL, OAI-WORK, OAI-DOTS, META-AI, MUSE-AGENT or MUSE-SPARK.
- Vendor: the corporation supplying the Shopping Agent (open text; e.g. Meta, OpenAI, Anthropic, Google, Perplexity, xAI, AI Sharc).
- Product: the actual tool or agent used (open text; e.g. MUSE-SPARK, Meta AI, ChatGPT Work, ChatGPT Dots, Claude, Gemini, harness). For the harness's own scored audits, Vendor is "AI Sharc" and Product is "harness".
- Signed-in account: which account the auditor was signed in as for the run.
- Fresh session (yes/no): whether the run started a fresh session/conversation.
- Mode used: the mode the experience was run in (e.g. Shopping, standard, regular chat).
- Firm (business name as on its website and listings), Primary Business Category.
- Query (the service searched, in the user's words).
- Town + ZIP searched, and the date of the run.
- Model the experience reports using, and the tools it reports using.
- The auditor (who ran it) and a reference to the full run transcript.

Each of these three fields carries a confirmed flag — signed-in account confirmed (yes/no), fresh session confirmed (yes/no), mode used confirmed (yes/no). The fields are added empty; no values are filled in for the Houston restart runs here — Tim confirms the three runs' metadata separately.

No run is usable without the vendor, product, model, tools, date, query, and location (Spec §8.1).

### 2.2 The standard shopping tasks

The auditor gives the experience a **standard shopping task**, in the user's words, in the same form for every profile so the observations are comparable. There are three standard tasks (decided by Tim, 12 Nov 2026 — three for now; more are added only by a further decision, not by an auditor on a run):

| # | Task | Form |
|---|---|---|
| 1 | Combined | "Find a [service] firm in [town], TX [ZIP] for [service need] installation and repair and compare the firms you find." |
| 2 | Repair only | "Find a [service] firm in [town], TX [ZIP] for [service need] repair and compare the firms you find." |
| 3 | Installation / replacement only | "Find a [service] firm in [town], TX [ZIP] for [service need] installation and replacement and compare the firms you find." |

Example forms (pilot parameters, not a firm choice): Task 1 — "Find an HVAC firm in Coppell, TX 75019 for AC installation and repair and compare the firms you find." Task 2 — "Find an HVAC firm in Coppell, TX 75019 for AC repair and compare the firms you find." Task 3 — "Find an HVAC firm in Coppell, TX 75019 for AC installation and replacement and compare the firms you find." Each task names the service, the town, and the ZIP, and asks for a comparison — it does not name a firm, a website, or a listing. The auditor records the exact task text used, and which of the three tasks it was. A run uses one task; a profile's observation set is the three tasks run as separate fresh sessions (see section 3 for OAI-LOCAL).

**Neutral observation.** The experience receives only this shopping request. It is **not** shown the rubric — the 36-row Item/Category/Ranking Suggestion criteria — and the auditor does not give it directed checks (for example, "check the firm's licence" or "read the firm's warranty page"). Directed checks belong in the separate core AI Sharc audit, not in the agent task. What the experience does with the plain shopping request is the observation.

### 2.3 What the auditor does

1. Gives the standard task to the experience (a fresh ChatGPT conversation for OAI-LOCAL; Work or a dot for the other OpenAI profiles; the Meta AI assistant in Shopping mode for META-AI; a signed-in Muse session for MUSE-AGENT; the Model API call for MUSE-SPARK).
2. Captures the **full response verbatim** (the complete transcript), including every firm the experience named, every figure it quoted, and every source it cited.
3. Records the date and time of the run, the model, and the tools the experience used.
4. Records, for each Item, what the experience actually checked — from what it returned, not from what the auditor assumes it read.
5. Records any delegation (see 2.7) and any tool the experience needed but could not use.

The auditor does **not** prompt the experience toward a firm, a website, or a listing, and does not re-ask a question to get a different answer. **Follow-ups are allowed** when they do not steer toward a firm, a website, or a listing; the exact follow-up prompt must be recorded, and firms named in a follow-up are labelled as follow-up. If the experience's answer is unclear on an Item, the Item is recorded as Not observed (see 2.5), not re-tested in the same run.

### 2.4 Scoring — the same 36 rows

Each run is scored against the same 36 rows as an AI Sharc audit (Spec §13): 7 Category reference summaries, 21 Items, 8 Ranking Suggestions. There are no Gate rows. The per-Item result for the agent is one of:

| Result | Meaning |
|---|---|
| **Pass** | The agent checked the Item and found the fact present and correct. |
| **Fail** | The agent checked the Item and found the fact absent or wrong. |
| **Not observed** | The agent's answer does not mention the fact, or states the fact without demonstrating it (reason code (b), §2.5). The agent did not show it checked the Item. This is **not** a Fail. |
| **Not completed** | The check was interrupted, or a tool the agent needed was unavailable, so the agent did not complete the check for that Item. |
| **Not tested** | The audit has not been run. |

The Website Access minimum condition (Spec §5) is recorded per firm in the run as Pass / Fail (field 10, §9.1; column website_access on agent_run_firms): if the firm's website is unreachable on the firm's side, or the firm is not in business, the firm is F and no Items are scored. A confirmed block of the agent — it could not access the site at all — is recorded as that agent's observation only. It does **not** change the AI Sharc grade, except through the AI crawler access Item (C7.1 AI crawler access (M1), Category 7) (Spec §4.1.1, §8.1).

**Review status per row.** Each observation row carries a review status of **proposed / confirmed / changed**, and who confirmed it (**confirmed-by**). Rows start as **proposed**; Tim's confirmation (or a change he directs) is what moves them to confirmed or changed.

Category results are points subtotals (Spec §8), not Pass/Fail, and the grade is **not** re-derived from one agent's observation. The **official** Category results and the grade are determined only by the AI Sharc audit; per-agent observations never change the grade (Spec §8.1). (A per-agent observation record carries its own Category summary for reference only — see §9.1, field 12. That summary is not the official Category result and is never presented as the grade.)

### 2.5 Evidence — the hard rules apply

The hard rules (Spec §4.3) apply to OAI observations exactly as they apply to an AI Sharc audit:

- Every Pass or Fail cites the agent's **exact wording** and the **sources it cited**, with the date. A Pass or Fail claimed without recordable evidence — the agent's exact wording with a cited source, in the response body, the sources panel, or a follow-up turn — is **not** recorded as a Pass or Fail: it is recorded as **Not observed** with reason code (b) (Spec §7.1), and the Reason field states what was missing. "Not confirmed" is **not** an observation status (the statuses are in §2.4); it describes the treatment — the result is not confirmed and counts as neither a Pass nor a Fail.
- No partial credit. No provisional Pass. No auditor discretion on Pass/Fail.
- A firm's own confirmation does not change a score (Spec §4.3). The agent's word alone is not evidence for a live-test Ranking Suggestion either (see 2.6).
- An issue is counted once, in the one section it belongs to.
- **Sources-panel rule.** Sources-panel content is part of the response and can support a Pass. Record where the evidence came from — response body, sources panel, or follow-up turn — for every Pass or Fail.
- **Reason codes for Not observed (Spec §7.1).** **(a) Not mentioned** — the agent's answer, including its sources panel and any follow-up turns, does not state the fact and does not show that the agent checked the Item. **(b) Mentioned, not demonstrated** — the answer states the fact, but either (1) there is no recordable evidence in the response body, sources panel, or follow-up turn (no exact agent wording with a cited source to record), or (2) what it states does not meet the Item's pass criteria in full (for example, hours given as one daily range rather than day by day, or one firm's figure where the Item requires consistency across sources). Neither code is a Fail; both are excluded from the cross-agent majority (§9.2). Reason codes apply to observation rows only, never to audit rows. **Not completed takes no code** — its definition already states why (the check was interrupted, or a tool was unavailable).

**Consequence:** the Task 2 C4.4 free-estimate status for repair Pass STANDS — it rests on a sources-panel snippet, and sources-panel content is part of the response and can support a Pass. The Task 2 workbook record is NOT changed here — it is already Pass.

### 2.6 Ranking Suggestions (not scored)

The eight Ranking Suggestions (S1 Booking and quote route; S2 Availability; S3 Price for this user; S4 Brand and system coverage; S5 Service-area dispatch; S6 Machine discovery (llms.txt); C3.2 BBB accreditation and rating consistent with bbb.org; C4.1 six-line warranty card) are recorded per run as Observed, Recommendation, or Not checked for the six Section 6 factors (S1–S6), and as Complete, Suggested, or Not checked for C3.2 BBB accreditation and rating consistent with bbb.org and C4.1 six-line warranty card (Section 4), decided only by the hard rules (Spec §4.3, rule 8). Observed and Complete require **public evidence directly proving the Ranking Suggestion, with URL and date**; a firm's statement alone is never Observed or Complete for a Ranking Suggestion that needs a live test — and the agent's claim alone is not Observed or Complete either. The auditor verifies a Ranking Suggestion against the public source before recording Observed or Complete. Ranking Suggestions never affect the grade.

### 2.7 Delegation

**Delegation matters only when it is visible (decided by Tim, 11 Nov 2026).** If a run visibly delegates to another agent — the transcript shows the delegation, or the experience reports that it used another agent — the per-agent observations record it: which agent delegated, which agent received it, and what was delegated. A delegated result **adds no independent vote** — only the originator's result counts in that Item's majority (Spec §8.1). Example: if a Dots run visibly delegates a check to ChatGPT Work, the Work result counts once; the Dots observation records that it came via Work. The cross-agent summary must not imply independent corroboration where delegation was visible.

If the delegation happens invisibly in the background — the experience does not show that it called another agent — the auditor does **not** go hunting for it. The observation stands as that experience's own, and no delegation is recorded. What matters is what the experience showed the user, not what it called in the background.

### 2.8 What the auditor must not do

- Do not average recommendation positions across agents. No average, no combined rank, without a defined method (Spec §8.1).
- Do not treat an untested agent as a failure. Untested stays Not tested (Spec §8.1).
- Do not treat an omission as a Fail. A Fail requires the agent to have checked and found the fact absent or wrong (Spec §8.1).
- Do not use a firm's confirmation, or the agent's bare assertion, as evidence for a scored Item or an Observed Ranking Suggestion.

### 2.9 Status mapping for directed AI Sharc Audits

In a directed AI Sharc Audit, agents use the official Spec §7 statuses (Pass, Pass with warning, Missing, Conflict, Not accessible) plus Not completed when a tool was unavailable. Not observed and reason codes (a)/(b) stay for shopping-query observations only. For the majority: Pass and Pass with warning count as pass, Missing and Conflict count as fail, Not accessible and Not completed are left out. An unreadable site is recorded as Not accessible under the Spec, not Not observed. (The decided rule for shopping-query observations remains §2.4/§2.5.)

## 3. Execution profile: OAI-LOCAL — AI Sharc — ChatGPT Local-Service Discovery Audit

**What it is.** ChatGPT local-business discovery/search — a fresh ordinary ChatGPT conversation with web search available, outside the AI Sharc project and its instructions. **The primary OpenAI test** for a local-service firm (see 1.4). It is not claimed to be a dedicated shopping product, and this audit does not claim it is one.

**How to run it.** Start a fresh ordinary ChatGPT conversation with web search available, outside the AI Sharc project and its instructions. Give it one of the three standard shopping tasks (2.2), with "Do not contact any business or submit a request." added. Do not include firm names, websites or the rubric. Run the three tasks as **separate fresh sessions** — Task 1 (combined), Task 2 (repair only), Task 3 (installation/replacement only) — using the fixed wording in 2.2, so results are comparable across experiences. Record whether web search actually ran, and preserve the complete response — text, cards, links and citations — with the exact prompt, date/time, account/settings, explicit location, model and visible tools.

**What to record.** Everything in 2.1, plus: discovery, comparison and next-step capability, recorded separately — discovery: the response identifies the correct business/location as an option for the requested service area (preserve text, cards, links and citations); comparison: it supplies attributable facts or reasons that help distinguish firms (verify those facts independently); next step: a website/contact link, quote route or in-chat action is displayed (record which one; do not require payment). Get Quote / checkout availability, recorded separately — which one, if either, was displayed — and never a prerequisite for passing (see 1.4). And, for the firms with recorded evidence for that query and town, each firm's presence scored against the **same returned candidate set** — a firm omitted from one answer is Not observed in that run, not proof ChatGPT cannot find it. A later company-name search, if run to diagnose findability, is labelled separately from neutral discovery. (For the pilot, the firms with recorded evidence are the original 19 HVAC companies from the 25 Oct 2026 work, and the firm under test is Airtron — see section 10.)

**Known limits — to be confirmed at the pilot.** The exact model and tools shown in an ordinary ChatGPT conversation, and how web-search activity and citations are displayed, have **not** been verified by Muse for this profile. The auditor records the exact steps used at the first documented run, so the profile becomes reproducible. Repeat fixed prompts in fresh sessions to measure variation.

**Status.** Not tested.

## 4. Execution profile: OAI-WORK — AI Sharc — OpenAI ChatGPT Work Audit

**What it is.** ChatGPT Work — ChatGPT's agent mode, announced 9 July 2026; the old ChatGPT Agent mode is retired. A general-purpose agent that carries out a task delegated to it. Verified against OpenAI's own pages, 2026-11-09. It is **not** a dedicated shopping product, and this audit does not claim it is one.

**How to run it.** The auditor delegates the standard shopping task (2.2) to ChatGPT Work in ChatGPT, and records the model and tools Work reports using, the date, the query, and the location. The full response is captured verbatim.

**What to record.** Everything in 2.1, plus: the tools Work actually used on this run, any source Work cited for each Pass or Fail, and whether Work completed each check (2.4).

**Known limits — to be confirmed at the pilot.** The exact invocation steps in the ChatGPT interface (where the auditor starts Work, and how Work's model and tools are shown) have **not** been verified by Muse. The auditor records the exact steps used at the first documented run, so the profile becomes reproducible. Work's tool use may vary by task; the profile records what it actually used on each run, and does not assume a fixed tool set.

**Status.** Not tested.

## 5. Execution profile: OAI-DOTS — AI Sharc — OpenAI Dots Audit

**What it is.** Dots — OpenAI's always-on agents. A dot can delegate tasks to ChatGPT Work or Codex, and can create Work or Codex tasks. Verified against OpenAI's own Dots documentation (`https://learn.chatgpt.com/docs/dots`), 2026-11-11. It is **not** a dedicated shopping product, and this audit does not claim it is one.

**How to run it.** The auditor gives the standard shopping task (2.2) to a dot, and records the model and tools the dot reports using, the date, the query, and the location. The full response is captured verbatim.

**Delegation.** If the dot **visibly** delegates any part of the task to Work (or Codex) — the transcript shows it, or the dot reports it — the run records the delegation (2.7): what was delegated, and to which agent. The Dots observation records that the result came via Work; the Work result counts once in any majority; the two observations are **not** independent corroboration of each other. If the dot calls Work invisibly in the background, the observation stands as the dot's own (2.7); the auditor does not go hunting for background delegation.

**What to record.** Everything in 2.1, plus: the tools the dot actually used, any source the dot cited for each Pass or Fail, whether the dot completed each check, and the delegation record.

**Known limits — to be confirmed at the pilot.** The exact dot setup and invocation steps (how the auditor creates or selects a dot, and how the dot's model and tools are shown) have **not** been verified by Muse. The auditor records the exact steps used at the first documented run, so the profile becomes reproducible.

**Status.** Not tested.

## 6. Execution profile: META-AI — AI Sharc — Meta AI Assistant Audit (Shopping mode)

**What it is.** The Meta AI assistant (meta.ai web and the Meta AI app) in Shopping mode — a mode in the mode picker (Instant / Thinking / Shopping) in the Meta AI app. A general assistant that carries out a shopping task in Shopping mode. It is **not** a dedicated shopping product, and this audit does not claim it is one.

**How to run it.** Give the standard shopping task (2.2) to the Meta AI assistant with Shopping mode on, in the Meta AI app (tap Ask Meta AI, tap the mode shown bottom right, pick Shopping). Record the model and tools the assistant reports using, the date, the query, and the location. The full response is captured verbatim, including Sources / See details.

**What to record.** Everything in 2.1, plus: the mode actually used — Shopping or standard — recorded explicitly (a run in standard mode is a standard-mode observation, not a Shopping-mode observation); the tools and sources the assistant showed; and whether the assistant completed each check (2.4).

**Known limits — to be confirmed at the pilot.** Shopping mode was **not** available on the auditor's devices at the last check (not in the meta.ai web mode dropdown; not in the Meta AI app on the auditor's iPad Pro) — it is a server-side rollout, not something installation unlocks. The exact Shopping-mode invocation steps on a device where it is available have **not** been verified by Muse. The auditor records the exact steps used at the first documented Shopping-mode run, so the profile becomes reproducible. There is no native Windows Meta AI app (Mac app in beta only).

**Status.** One documented observation (run 1, standard mode, meta.ai web, 11 Nov 2026). Shopping mode Not tested.

## 7. Execution profile: MUSE-AGENT — AI Sharc — Muse Personal Agent Audit

**What it is.** The Muse personal agent (muse.ai / WhatsApp) — Meta's personal agent, powered by the Muse Spark model family. A general personal agent that carries out a shopping task delegated to it. It is **not** a dedicated shopping product, and this audit does not claim it is one.

**How to run it.** Give the standard shopping task (2.2) to the Muse personal agent in a signed-in session (muse.ai or WhatsApp), and record the model and tools the agent reports using, the date, the query, and the location. The full response is captured verbatim, including Sources / See details.

**What to record.** Everything in 2.1, plus: the tools the agent actually used on this run, any source the agent cited for each Pass or Fail, and whether the agent completed each check (2.4).

**Known limits — to be confirmed at the pilot.** No run has been made yet. The exact invocation steps in a signed-in session (how the auditor starts the task, and how the agent's model and tools are shown) have **not** been verified by Muse. The auditor records the exact steps used at the first documented run, so the profile becomes reproducible.

**Status.** Not tested.

## 8. Execution profile: MUSE-SPARK — AI Sharc — Muse Spark Model Observation

**What it is.** The Muse Spark model (muse-spark-1.3) called through the Meta Model API with web search — a **model observation, not an experience audit**. It tests what the model does with the shopping task when called through the API, not what a user-facing experience does. It is labelled separately from the experience audits and is never presented as one.

**How to run it.** Call `POST https://api.meta.ai/v1/responses` with model muse-spark-1.3, web_search grounding, url_citations, and user_location (Coppell, TX) inside the web_search tool object. The harness agent layer (`aisharc_harness/agent/muse_api.py`) implements this call; the API key comes from the connector, never from this design. Give it the standard shopping task (2.2). Record the response ID, the model, the web_search calls made, the date, the query, and the location. The full response is captured verbatim (raw JSON retained).

**What to record.** Everything in 2.1, plus: the response ID; the number of web_search calls and results; the number of url_citation annotations and the distinct URLs cited; the cost; and whether the model completed each check (2.4).

**Known limits.** The Model API is a model surface, not a user-facing experience — this observation does not stand in for an experience audit. Web search is grounding through the API's web_search tool; the model does not browse interactively.

**Status.** One documented observation (run 1, 11 Nov 2026, ~20:51 CST, response `resp_6af4d52c3d277297d741445c`: 6 web_search calls, 23 results, 99 url_citation annotations from 4 distinct URLs, cost ~$0.06; named 2 of 19 firms).

## 9. Results format (for aggregation)

### 9.1 Per-agent observation record

One record per run, per agent. Fields, in order:

| # | Field | Notes |
|---|---|---|
| 1 | Audit ID | OAI-LOCAL, OAI-WORK, OAI-DOTS, META-AI, MUSE-AGENT or MUSE-SPARK |
| 2 | Firm | Business name as on website and listings |
| 3 | Primary Business Category | Standard places-listing category |
| 4 | Query | Service searched, in the user's words |
| 5 | Town + ZIP searched | |
| 6 | Date of run | |
| 7 | Model | As reported by the experience |
| 8 | Tools | As reported/used by the experience |
| 9 | Run transcript reference | Where the full verbatim response is kept |
| 10 | Website Access minimum condition (F) | Pass / Fail per Spec v2.8 §5 (website readable on the firm's side and firm in business); if F, no Items are scored |
| 11 | Item results (21) | Pass / Fail / Not observed / Not completed, per Item, with the agent's exact wording and its cited source for each Pass or Fail; a reason code (a) or (b) (Spec §7.1, defined in §2.5) and a reason field for any Item recorded as Not observed, stating why (including "no agent wording / cited source recorded" where that is the reason, per §2.5); and a reason field for any Item recorded as Not completed, stating why — Not completed takes no code |
| 12 | Category results (7) | Reference summary only — derived from this agent's Item results as points earned out of points available (Spec v2.8 §8); not the official Category results and not the grade. Must be labelled as a per-agent reference summary wherever shown |
| 13 | Ranking Suggestion results (8) | Observed / Recommendation / Not checked (Section 6 factors S1–S6); Complete / Suggested / Not checked (Section 4: C3.2 BBB accreditation and rating consistent with bbb.org, C4.1 six-line warranty card), per Spec §4.3 rule 8 |
| 14 | Delegation record | From → to, what was delegated; empty if none |
| 15 | Auditor | Who ran it |
| 16 | Vendor | The corporation supplying the Shopping Agent (open text; e.g. Meta, OpenAI, Anthropic, Google, Perplexity, xAI, AI Sharc) |
| 17 | Product | The actual tool or agent used (open text; e.g. MUSE-SPARK, Meta AI, ChatGPT Work, ChatGPT Dots, Claude, Gemini, harness). For the harness's own scored audits, Vendor is "AI Sharc" and Product is "harness" |
| 18 | Review status | proposed / confirmed / changed (see §2.4); rows start as proposed |
| 19 | Confirmed by | Who confirmed the row (or directed a change); empty while the row is proposed |

For OAI-LOCAL, the observation record also carries the separate discovery / comparison / next-step measurements and the Get Quote / checkout availability recorded under section 3.

Agent Observation Record — one record per run, per agent (Database tables: `agent_runs` / `agent_run_firms` / `agent_observation_rows`, §9.4). One record per run, per agent — not per firm: firms named in the run are recorded in `agent_run_firms` (§9.4), and the 36 observation rows attach to the run. Field 2 (Firm) applies to a single-firm observation; for a run naming several firms, the firms are listed in `agent_run_firms`. Records are stored in the observation tables in the audit DB (Spec §13; §9.4); the Agent Validation record (files) and transcripts stay as the human-readable audit trail. They are **not** AI Sharc audit rows and do **not** enter the scored audit tables (Spec §13, 36 rows per AI Sharc audit). The 36-row field set is defined in the Database fields sheet. The database tables are the system of record the aggregation layer queries.

### 9.2 Cross-agent summary

Built from the per-agent observation records, per Spec §8.1. For each Item:

- **Pass** if more than half of the tested agents that completed the check for that Item pass it; **Fail** if half or fewer pass.
- **Only completed checks count.** An agent that did not complete the check for an Item — interrupted, or a tool it needed was unavailable — is excluded from that Item's majority. It is not counted as a Pass or a Fail. The summary states how many agents completed the check for each Item.
- **A delegated result adds no independent vote — when the delegation is visible.** Only the originator's result counts in that Item's majority (2.7). Delegation that happens invisibly in the background is not recorded and does not change the observation.
- **The majority rule is strict.** With two tested agents that both completed the check, one Pass and one Fail is a Fail, because half or fewer passed.
- **No averaging of recommendation positions.** No average, no combined rank, without a defined method.
- The summary always states **how many agents were tested**.

**Adopted rule (decided by Tim, 11 Nov 2026):** an Item recorded as **Not observed** for an agent is **excluded from that Item's majority**, the same as Not completed. Reason: a Not observed agent demonstrated neither a Pass nor a Fail, and counting it in the denominator as a non-pass would treat an omission as a Fail, which the Spec forbids ("a Fail requires the agent to have checked and found the fact absent or wrong").

**Worked examples (two tested agents, both completed the check unless stated; with three tested agents the same strict-majority rule applies — Pass only if more than half of the agents that completed the check pass it):**

| OAI-WORK | OAI-DOTS | Cross-agent result | Why |
|---|---|---|---|
| Pass | Fail | **Fail** | 1 of 2 passed — half or fewer (strict majority) |
| Pass | Pass | **Pass** | 2 of 2 passed — more than half |
| Fail | Fail | **Fail** | 0 of 2 passed |
| Pass | Not observed | **Pass** | Only one agent completed the check; 1 of 1 passed (adopted rule, §9.2) |
| Pass (via Work) | Pass (visibly delegated to Work) | **Pass, counted once** | Dots visibly delegated to Work; the Work result counts once, not twice |

**Common deficiency** — an Item that fails the majority rule. **Agent-specific problem** — an Item that fails for one agent but passes the majority rule. Fixes are prioritized by how many tested agents found the issue, then by AI Sharc grade impact (Spec §8.1).

### 9.3 The three outputs stay distinct

1. **AI Sharc grade** — compliance with the fixed audit criteria (the 21 scored Items, Category subtotals, and grade bands). Determined only by the AI Sharc audit; per-agent observations never change the grade.
2. **Per-agent observations** — what each tested agent actually found, read, verified, or could not access (9.1).
3. **Cross-agent summary** — common deficiencies, agent-specific problems, and prioritized fixes, with how many agents were tested (9.2).

### 9.4 Storage — observation records get database tables (decided 13 Nov 2026)

Observation records are stored in tables in the same audit database defined in Spec §13 (Supabase Postgres — AI Sharc Orchestrator East is the live database), alongside the audit tables — not as a separate store, and not as files alone. Changes are tried first in the test database (Test AI Sharc Orchestrator, Supabase, us-west-2) and applied to East only after the test checks out. The full column list is the Database fields sheet of Licensed Home Trade Field Mapping Rev 10; the summary below must match it. Three tables, plus the reference table `observation_reason_codes` (code, label, definition — the Spec §7.1 codes (a) and (b)):

| Table | Contents |
|---|---|
| `agent_runs` | One row per task run. Columns: run_id; vendor; product; agent_label; query (task text, full sentence as sent); query_id; service_query; town_zip; checked_at; model; tools_used; signed_in_account; signed_in_account_confirmed (yes/no); fresh_session (yes/no); fresh_session_confirmed (yes/no); mode_used; mode_used_confirmed (yes/no); repeat_number; session_state; location_setting; auditor; transcript_reference; delegation (from → to, what was delegated; empty if none — §2.7); task_number (1, 2 or 3); service; checked_at_text (checked_at exactly as written in the workbook); source_file (the workbook filename); file_hash (sha256 of the workbook bytes); loaded_at. session_state is logged in / logged out / incognito only — a fresh session is recorded in fresh_session. UNIQUE (vendor, product, agent_label, query_id, checked_at). run_id is the human key: the workbook filename without its suffix. |
| `agent_run_firms` | One row per firm named. Columns: run_id (FK to agent_runs); position (order in the agent's answer); name_as_given (exactly as the agent gave it); figure_quoted, source_cited and notes (as recorded on the Firms and figures sheet of the Shopping Query Return workbook); matched_firm (canonical firm name); firm_id (if matched); match_status (matched / unmatched / ambiguous); aliases (other name forms seen for this firm, semicolon-separated); section (main / social / price context / follow-up); turn (0 = first answer, 1+ = follow-up turn); mention_type (place card / named in text / cited link only / social post); cited_url (the URL the agent cited for this firm, empty if none); cited_own_domain (yes / no / none cited); total_firms_shown (firms shown in the answer, same value on every firm row of the run); website_access (Pass / Fail per Spec v2.8 §5 — §9.1 field 10). UNIQUE (run_id, position); also (run_id, name_as_given) unique. |
| `agent_observation_rows` | The 36 rows, attached to the run. Columns: run_id (FK to agent_runs); row_type (Category reference / Item / Ranking Suggestion); check_id; description; result (Items: Pass / Fail / Not observed / Not completed / Not tested; S1–S6: Observed / Recommendation / Not checked; C3.2/C4.1: Complete / Suggested / Not checked); agent_exact_wording; cited_source; reason (for Not observed, including reason code (a) or (b) per §2.5; for Not completed, a reason field only — Not completed takes no code); review_status (proposed / confirmed / changed); confirmed_by. UNIQUE (run_id, check_id). |

**This REPLACES the `agent_observations` table and its 2026-11-18 uniqueness key: firm_id moves to `agent_run_firms`, and the run key is now (vendor, product, agent_label, query_id, checked_at). `agent_observations` was never built. The three tables above are built in the test database (2026-11-20, on Tim's instruction) and recorded in Field Mapping Rev 10; they are not yet built in AI Sharc Orchestrator East.**

**Firm aliases and match status.** Aliases and match status live on `agent_run_firms`: `name_as_given` records the name exactly as the agent gave it, `matched_firm` / `firm_id` record the canonical firm it was matched to, `match_status` records matched / unmatched / ambiguous, and `aliases` records other name forms seen for the firm, semicolon-separated. Match status is a join, not part of the observation (Tim, 2026-11-20): when a firm is added to the firms table after a run was recorded, an unmatched mention whose name_as_given matches it exactly is updated to matched and linked to its firm_id, so the observation links to that firm's audits. What the agent said is never changed. On 2026-11-20, 19 Meta AI Houston mentions were updated this way. Worked examples from the Houston runs — each counted once: "Air Tech of Houston" vs "Air Tech of Houston AC & Plumbing"; "Safe Air LLC" vs "Safe Air Conditioning and Heating"; "Ace Comfort" vs "Ace Comfort Air Conditioning & Heating".

Rules:

- **One database for all agents.** Agents are distinguished by the agent_label on each record, not by a store (Aggregation pipeline design §7, decided 12 Nov 2026).
- **A re-run is a new run.** Uniqueness is (vendor, product, agent_label, query_id, checked_at) on `agent_runs`; (run_id, position) and (run_id, name_as_given) on `agent_run_firms`; (run_id, check_id) on `agent_observation_rows`. A re-run inserts new rows and never overwrites the old ones — the same rule as audits (Spec §13). Loading the same run twice is a no-op, never a second run — whether it comes back under the same run key or as the same workbook under another name (same file hash).
- **Observation tables never enter the scored tables.** They do not enter `audit_rows`, and the `audit_summary` view is unchanged (it derives from `audit_rows` only). Per-agent observations never change the AI Sharc grade (§9.3).
- **The cross-agent summary is computed, not stored.** The aggregation layer computes it from these tables per §9.2; the website displays it as computed and never computes it itself (Aggregation pipeline design §4–§5).
- **Files stay as the audit trail.** The Agent Validation record (Field Mapping) remains the human-readable record, and the observation files and transcripts stay as the evidence a reviewer can re-open; the database tables are the system of record the aggregation layer queries. The storage question is decided, not undecided: Field Mapping Rev 1 (2026-11-19) records these tables (the old §6.1 reference and the "undecided" note are superseded, 2026-11-18).

**Observation file naming.** Observation files are per-run (one workbook and one .md per shopping query, covering all firms in that run), not per-firm. For new runs they use the double-underscore pattern in Spec §13 ('File naming and folder layout', Specification v2.8): `<agent>__<query_id>__r<repeat>__<YYYYMMDDTHHMMSS±hhmm>__shopping-query-return.xlsx` and the matching `__observation.md`, where `<agent>` is the vendor-product pair (for example meta-metaai); existing files keep their existing human-readable names.

## 10. Pilot plan

10.1. **First documented runs.** Run the three OpenAI profiles on the **same firm, query, town + ZIP, and date** (or as close as the three experiences allow), so the observations are comparable and the cross-agent summary can be computed with three agents. **OAI-LOCAL runs first**, as the primary profile, in separate fresh sessions for AC repair and for AC installation/replacement (see 2.2 and section 3).

10.2. **Pilot firm — Airtron (decided by Tim, 12 Nov 2026).** Readable website, verifiable listing, in Coppell, TX 75019, and the only firm with row-level evidence in the audit DB, so an OAI observation can be compared against known facts. Its licence (TACLB00097767E) is verified active to 2027-06-05. Neither Meta surface named Airtron in its run, so the pilot tests whether the OpenAI surfaces surface the top-ranked 2026 firm at all. The pilot is a **new audit** (a new agent observation), not a re-score of any existing card. (One caveat, carried from the 11 Nov harness run: Airtron graded F on missing evidence there — no Meta listing found by the runner. That does not change the pilot; the pilot is a new agent observation, not a re-score.)

10.3. **Record the invocation steps.** At the first run of each profile, the auditor records the exact steps used to start the experience and to see its model and tools (see the "Known limits" in sections 3–8). Those recorded steps become the reproducible procedure; this draft does not invent interface steps it has not verified.

10.4. **After the pilot.** The Field Mapping Agent Validation rows for ChatGPT local-service discovery (OAI-LOCAL), ChatGPT Work (OAI-WORK) and Dots (OAI-DOTS) move from Not tested to the observed status, with the run date, query, and location recorded, and the rows for the Meta AI assistant (META-AI), the Muse personal agent (MUSE-AGENT) and the Muse Spark model (MUSE-SPARK) move the same way after their runs. The OAI-LOCAL row was added in Field Mapping Rev 4 (it did not exist in Rev 3); the Muse row in Rev 4 is the MUSE-AGENT row. The META-AI and MUSE-SPARK rows are in Field Mapping Rev 5. The rows move from Not tested to the observed status when their runs are recorded there, with MUSE-SPARK's run 1 (11 Nov 2026) recorded then. The pilot results are reported to Tim before any further runs are scheduled.

10.5. **Meta profiles.** The Meta profiles are piloted after the OAI pilot, on the same firm, query, town + ZIP and date where feasible, so the cross-agent summary can include them. META-AI Shopping mode is piloted when the mode is available on the auditor's device; until then only the standard-mode observation stands. MUSE-SPARK's run 1 is already documented; further MUSE-SPARK runs use the same Model API call so they are comparable.

## 11. What this draft does not decide

- Whether a fourth (or further) standard shopping task is added. Three are defined in §2.2 (decided 12 Nov 2026); more are added only by a further decision.

## 12. Traceability to Specification v2.8

| This draft | Spec v2.8 |
|---|---|
| Experience audits OAI-LOCAL (primary) / OAI-WORK / OAI-DOTS, Not tested | §8.1 (classification, answered 11 Nov 2026; OAI-LOCAL primary, answered 12 Nov 2026) |
| OAI-LOCAL method: fresh ordinary ChatGPT conversation, web search, separate fresh sessions for repair / installation | section 3; ChatGPT product-discovery answer, 12 Nov 2026 |
| Get Quote recorded separately, never a prerequisite; Instant Checkout no documented HVAC-service support | §1.4, section 3; ChatGPT product-discovery answer, 12 Nov 2026 |
| Three distinct outputs | §8.1 |
| Majority rule, strict (1 Pass + 1 Fail = Fail) | §8.1 |
| Only completed checks count | §8.1 |
| Delegated result adds no independent vote (when delegation is visible; decided 11 Nov 2026) | §8.1 |
| Omission = Not observed, not a Fail | §8.1 |
| No averaging of recommendation positions | §8.1 |
| Per-agent block affects only that agent's observation, and the grade only through the AI crawler access Item (C7.1 AI crawler access (M1), Category 7) | §4.1.1, §8.1 |
| Hard evidence rules (source, date, exact wording) | §4.3 |
| Ranking Suggestion Observed rules | §4.3 rule 8; §9 |
| 36 rows (7 Category reference summaries / 21 Items / 8 Ranking Suggestions, no Gates), spec_version '2.8' | §13; §6.10 Label reference table |
| Six Stage 1 Gates merged into the 21 scored Items; F is the Website Access minimum condition only | §5, §6 |
| AI crawler access (former M1) is the scored Item C7.1 AI crawler access (M1), Category 7 | §6.9; §6.10 |
| Per-agent observation record: Website Access minimum condition (field 10) replaces Gate results; 36 rows (Template Rev 1 (2026-11-19)) | §9.1; Shopping Query Return Template Rev 1 (2026-11-19) |
| Generalized title and scope — one shared design, per-surface profiles | Title; purpose and scope; §1 (decided 12 Nov 2026) |
| Three standard shopping tasks, used by every profile | §2.2 (decided 12 Nov 2026) |
| Candidate set generalized — firms with recorded evidence for that query and town | section 3 (decided 12 Nov 2026) |
| 'Experience' defined | Definition Rev 8 (decided 12 Nov 2026) |
| Agent Validation: META-AI and MUSE-SPARK rows; OAI-LOCAL row | Field Mapping Rev 1 (2026-11-19) |
| Shopping-agent classification (purchase ability not required) | §8.1; Definition Rev 8 |
| Meta profiles META-AI / MUSE-AGENT / MUSE-SPARK added, in that order; MUSE-SPARK a model observation, not an experience audit | Sections 6–8 (decided 13 Nov 2026) |
| Observation records stored in audit DB tables (`agent_runs`, `agent_run_firms`, `agent_observation_rows`); cross-agent summary computed, not stored | §9.4 (decided 13 Nov 2026); Aggregation pipeline design §7 item 2 |
| Vendor and Product recorded on every observation record (run record §2.1; per-agent record §9.1 fields 16–17; `agent_runs` table §9.4) | Spec v2.1 §3/§13 (Tim's decision 18 Nov 2026) |
| Placement decided — new governing document in the Latest folder | Status line; §11 (decided 13 Nov 2026) — SUPERSEDED 2026-11-18, path (a): kept as a working procedure document, not a governing document |
| Contradiction fix — observation records stored in audit DB tables (`agent_observations` / `agent_observation_rows`); "undecided" language removed; stale §6.1 reference corrected to §9.1; kept as working procedure document | §9.1, §9.4; amendment note 2026-11-18 (decided 18 Nov 2026, path (a)) |
| Sections renumbered: results §6→§9, pilot §7→§10, undecided §8→§11, traceability §9→§12 | Rev 8 (13 Nov 2026) |

*Draft Rev 17 prepared 2026-11-20 (change approved by Tim 2026-11-20): §9.4 aligned with Field Mapping Rev 10 and the database as built — tables built in the test database, not yet in East; added agent_runs and agent_run_firms columns; session_state values; match status is a join; duplicate workbooks skipped by file hash. Baseline Specification v2.9. Rev 16 stays untouched.*

*Draft Rev 16 prepared 2026-11-19: §9.4 agent_run_firms columns aligned with Field Mapping Rev 9 and Template Rev 7; baseline Specification v2.9.*

*Draft Rev 15 prepared 2026-11-19: applies Specification v2.8 — §9.4 agent_runs re-based to checked_at/query_id (date_checked, time_checked and timezone dropped; query_id, checked_at, repeat_number, session_state and location_setting added); cross-references Field Mapping Rev 9 and Shopping Query Return Template Rev 7 (2026-11-19). Baseline: Specification v2.8. Working procedure document, not a governing document (kept per Tim's decision 2026-11-18, path (a)). Rev 14, Rev 3, Rev 2, Rev 1, Rev 11, Rev 10, Rev 9 (approved 13 Nov 2026), Rev 8, Rev 7, Rev 6, Rev 5 and Rev 4 stay untouched.*
