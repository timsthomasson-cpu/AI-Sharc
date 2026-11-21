> Text copy of the Excel workbook, for reading and search. The .xlsx file is the controlling original; edits are made to the .xlsx and this copy is regenerated.

## Read Me
| What this is | The return template for a shopping query. One workbook per run, per agent. The agent (or the auditor running it) fills in the Run, Transcript, and Firms and figures sheets. AI Sharc completes the Observation record sheet from the transcript — the agent does not score Items in the shopping query run. |
| --- | --- |
| The shopping query | Three standard tasks (combined, repair only, installation/replacement only), run as separate fresh sessions, with no rubric and no AI Sharc context. The agent discovers firms itself; no firm list is sent for the shopping query. Task text names the service area (Spec v2.10 §3): Task 1 — 'Find an HVAC firm whose service area includes Houston, TX 77002 for AC installation and repair and compare the firms you find.' Task 2 — 'Find an HVAC firm whose service area includes Houston, TX 77002 for AC repair and compare the firms you find.' Task 3 — 'Find an HVAC firm whose service area includes Houston, TX 77002 for AC installation and replacement and compare the firms you find.' No shopping query has been run with this wording yet (as of 2026-11-21). |
| Who fills in what | Agent / auditor: Run, Transcript, Firms and figures. AI Sharc only: Observation record. The agent must not fill in the Observation record — it does not see the rubric in the shopping query run, and AI Sharc derives the per-Item record from the transcript. |
| Rules | Return the answer verbatim — complete, with nothing added, removed, or reworded. Do not score Items, do not apply the rubric, do not contact a firm. If the answer does not mention a fact, that Item is Not observed (not a Fail) — AI Sharc records that from the transcript. A Pass or Fail in the Observation record needs the agent's exact wording and the source it cited, with the date. |
| Position in the agent's comparison | Firms and figures, first column: the rank the agent gave the firm in its comparison (1, 2, 3, ...). This is the shopping position for that firm in this run. Use 'Unranked' if the agent presented the firm without an order. If the agent recommended one firm without ranking the rest, give the recommended firm position 1 and the rest 'Unranked'. |
| Field set | The Observation record uses the v2.2 field set: 21 Items, 7 Category reference summaries, 8 ranking suggestions (36 rows). There are no Gates in v2.2 — G1 exact name and G6 verifiable listing are Items. Note: this template follows the live Specification v2.10 and Observation Design Rev 17 (three-table observation design: agent\_runs, agent\_run\_firms, agent\_observation\_rows). |
| Controlled vocabulary | Item result: Pass, Fail, Not observed, Not completed, Not tested (Not tested = the check has not been run). Category reference: points earned out of points available. Ranking Suggestion result: Observed, Recommendation, Not checked for the six Section 6 suggestions (S1–S6); Complete, Suggested, Not checked for C3.2 BBB accreditation and rating consistent with bbb.org and C4.1 six-line warranty card (Section 4). Not observed means the answer does not mention the fact. Not completed means the check was interrupted or a needed tool was unavailable. Reason codes (Spec §7.1): every Not observed row starts with (a) or (b), then a short explanation. (a) = the answer, sources panel and follow-ups never mention the fact. (b) = the answer mentions it, but without exact wording and a cited source, or not in the form the Item requires. Not completed takes no code. See the 'Reason codes' row below. Each observation row also carries a Review status (proposed / confirmed / changed) and Confirmed by, recorded by AI Sharc on review. |
| Rev 3 changes (2026-11-17) | Terminology, at Tim's instruction: 'Ranking Levers' renamed 'Ranking Suggestions' (Observation record check type 'Lever' → 'Ranking Suggestion'; L1–L6 check\_id codes unchanged). Template now follows Specification v2.1. No field, row-count, or result change. |
| Check\_id rename (2026-11-18) | 2026-11-18: Ranking Suggestion check\_id codes renamed L1-L6 to S1-S6 at Tim's instruction ('Change them everywhere'). |
| Rev 4 changes (2026-11-18) | C3.2 BBB accreditation and rating consistent with bbb.org and C4.1 six-line warranty card added as Ranking Suggestion rows in the Observation record (36 rows: 21 Items + 7 Category reference summaries + 8 ranking suggestions), per Tim's decision 2026-11-18. Un-scored; the Observation record does not score Items, so no grade or points change. Rev 3 retained. |
| Rev 5 changes (2026-11-18) | 2026-11-18: Ranking Suggestion results split by section — the six Section 6 suggestions (S1 Booking and quote route, S2 Availability, S3 Price for this user, S4 Brand and system coverage, S5 Service-area dispatch, S6 Machine discovery (llms.txt)) keep Observed / Recommendation / Not checked; C3.2 BBB accreditation and rating consistent with bbb.org and C4.1 six-line warranty card (Section 4) now use Complete / Suggested / Not checked (Spec v2.1 §4.3 rule 8, at Tim's instruction 2026-11-18). Observation record result validation split accordingly (D29:D35 and D36:D37). Rev 4 retained. |
| Rev 6 changes (2026-11-18) | 2026-11-18: Vendor and Product added as Run-sheet fields, immediately after 'Agent (Audit ID)' — Vendor is the corporation supplying the Shopping Agent (for example Meta, OpenAI, Anthropic, Google, Perplexity, xAI, AI Sharc); Product is the actual tool or agent used (for example MUSE-SPARK, Meta AI, ChatGPT Work, ChatGPT Dots, Claude, Gemini, harness). 'Agent (Audit ID)' unchanged. Per Specification v2.1 and Tim's decision 2026-11-18. Rev 5 retained. |
| Rev 1 changes (2026-11-19) | 2026-11-19: Specification v2.2; Observation Design Rev 12. Run sheet: signed-in account, fresh session, and mode used added, each with a confirmed flag (yes/no), after the existing run metadata. Observation record: 'Review status' (proposed / confirmed / changed) and 'Confirmed by' columns added after Reason; Item result vocabulary gains Not tested (validation updated). Reason codes (Spec §7.1): every Not observed row starts with (a) or (b), then a short explanation. (a) = the answer, sources panel and follow-ups never mention the fact. (b) = the answer mentions it, but without exact wording and a cited source, or not in the form the Item requires. Not completed takes no code. Firms and figures: 'Matched firm', 'Match status' (matched / unmatched / ambiguous), 'Aliases' (other name forms, semicolon-separated), and 'Section' (main / social / price context / follow-up) columns added. Category rows in the Observation record now use check type 'Category reference', matching Observation Design Rev 12. Rev 6 retained. |
| Reason codes | Observation record, Reason column: every Not observed row starts with (a) or (b), then a short explanation. (a) = the answer, sources panel and follow-ups never mention the fact. (b) = the answer mentions it, but without exact wording and a cited source, or not in the form the Item requires. Example: "(b) Hours shown for two firms as a single daily range; no cited source." See Spec §7.1. |
| Rev 2 changes (2026-11-19) | 2026-11-19: Specification v2.4; Observation Design Rev 2 (content Rev 13). Reason codes: new 'Reason codes' row added with the Spec §7.1 wording verbatim — every Not observed row starts with (a) or (b), then a short explanation; (a) = the answer, sources panel and follow-ups never mention the fact; (b) = the answer mentions it, but without exact wording and a cited source, or not in the form the Item requires. Not completed takes no code. The v2.2 (a)/(b) definitions in 'Controlled vocabulary' and in the Rev 1 change note are replaced with the Spec §7.1 wording. No column or structure change; the 36 observation rows are unchanged. Rev 1 retained. |
| File naming | For new runs, one workbook per run, per agent, named '<agent>\_\_<query\_id>\_\_r<repeat>\_\_<YYYYMMDDTHHMMSS±hhmm>\_\_shopping-query-return.xlsx' (for example 'meta-metaai\_\_hvac-houston-77002-t2\_\_r1\_\_20261118T155000-0600\_\_shopping-query-return.xlsx'), where <agent> is the vendor-product pair (for example meta-metaai), <query\_id> follows the Spec §13 query\_id rule, <repeat> is the repeat number (1 for the first run of a query on an agent; 2+ for fresh-session repeats), and the timestamp is the run's checked\_at in compact form, with seconds and offset. The matching observation file is named '<agent>\_\_<query\_id>\_\_r<repeat>\_\_<YYYYMMDDTHHMMSS±hhmm>\_\_observation.md'. Existing files keep their current names: 'AI Sharc — Shopping Query Return — <Town> <State> <ZIP> — Task <n> <service> — <YYYY-MM-DD> — Rev <n>.xlsx' (for example 'AI Sharc — Shopping Query Return — Houston TX 77002 — Task 1 combined — 2026-11-18 — Rev 1.xlsx'; <service> is combined, repair or installation). Observation files are per-run, not per-firm — the per-firm '\_\_' audit-file pattern does not apply to them as firm files. For the per-firm audit-file naming, see Spec §13 'File naming and folder layout' (Specification v2.6). |
| Rev 3 changes (2026-11-19) | 2026-11-19: Specification v2.5; Observation Design Rev 3 (content Rev 14). 'File naming' row added: workbook naming pattern (one workbook per run, per agent) and a pointer to Spec §13 'File naming and folder layout' for the per-firm audit-file naming. Observation files stay per-run — the per-firm '\_\_' pattern does not apply to them. No field, row-count, or result change; the 36 observation rows are unchanged. Rev 2 retained. |
| Rev 7 changes (2026-11-19) | 2026-11-19: Specification v2.6. Run sheet: 'Date of run' and 'Time of run' replaced by one 'checked\_at' field (ISO 8601 with seconds and offset, e.g. 2026-11-18T15:50:00-06:00); new fields 'query\_id' (e.g. hvac-houston-77002-t2), 'Repeat number' (1 for the first run of a query on an agent; 2+ for fresh-session repeats), 'Session state' (logged in / logged out / incognito), and 'Location setting' (VPN city or API user\_location, separate from the town in the prompt). Firms and figures: new columns 'Cited URL', 'Cited own domain' (yes / no / none cited), 'Mention type' (place card / named in text / cited link only / social post), 'Total firms shown in the answer', and 'Turn' (0 = first answer; 1+ = follow-up turn). File naming: the double-underscore pattern for new runs (Spec v2.6 §13) is now stated, alongside the current workbook pattern for existing files. No field, row-count, or result change in the Observation record; the 36 observation rows are unchanged. Rev 3 retained. |
| Rev 8 changes (2026-11-21) | 2026-11-21: Specification v2.10. Task text now names the service area instead of the town: 'Find an HVAC firm whose service area includes [town], TX [ZIP] for …' (wording decided by Tim 2026-11-21). Read Me 'The shopping query' row lists the three tasks; Run sheet 'Task text (exact)' example updated. No shopping query has been run with this wording yet (as of 2026-11-21). Runs made with the earlier wording keep it. Read Me 'Field set' row updated to Spec v2.10 and Observation Design Rev 17. No field, column, row-count, or result change. Rev 7 retained. |

## Run
| Field | Value | Notes |
| --- | --- | --- |
| Agent (Audit ID) | NaN | OAI-LOCAL, OAI-WORK, OAI-DOTS, META-AI, MUSE-AGENT, or MUSE-SPARK |
| Vendor | NaN | The corporation supplying the Shopping Agent — for example Meta, OpenAI, Anthropic, Google, Perplexity, xAI, AI Sharc |
| Product | NaN | The actual tool or agent used — for example MUSE-SPARK, Meta AI, ChatGPT Work, ChatGPT Dots, Claude, Gemini, harness |
| checked\_at | NaN | ISO 8601 with seconds and offset, e.g. 2026-11-18T15:50:00-06:00. Single timestamp for the run; replaces Date of run and Time of run. |
| Model | NaN | As reported by the experience |
| Tools used | NaN | As reported/used by the experience |
| Task number | NaN | 1 (combined), 2 (repair only), or 3 (installation/replacement only) |
| Task text (exact) | NaN | The exact task text used, e.g. Find an HVAC firm whose service area includes Houston, TX 77002 for AC installation and repair and compare the firms you find. |
| Service | NaN | e.g. HVAC, AC |
| Town | NaN | e.g. Houston — the town named in the task text |
| ZIP | NaN | e.g. 77002 — the ZIP named in the task text |
| Query | NaN | Service searched, in the user's words |
| Auditor | NaN | Who ran it |
| Delegation | NaN | From -> to, what was delegated; empty if none |
| Transcript reference | NaN | Transcript sheet in this workbook (the full verbatim response) |
| Signed-in account | NaN | Account the agent was signed in as for the run |
| Signed-in account confirmed | NaN | yes/no — whether the signed-in account was confirmed for this run |
| Fresh session | NaN | yes/no — whether the run was a fresh session |
| Fresh session confirmed | NaN | yes/no — whether the fresh session was confirmed for this run |
| Mode used | NaN | Mode used, e.g. regular chat; Shopping mode where offered |
| Mode used confirmed | NaN | yes/no — whether the mode used was confirmed for this run |
| query\_id | NaN | e.g. hvac-houston-77002-t2 — <trade>-<town>-<zip>-t<task>, all lowercase; town with spaces and punctuation removed (Spec v2.6 §13 query\_id rule). |
| Repeat number | NaN | 1 for the first run of a query on an agent; 2+ for fresh-session repeats of the same query on the same agent |
| Session state | NaN | logged in / logged out / incognito |
| Location setting | NaN | The agent’s location setting for this run — VPN city or API user\_location — separate from the town in the prompt (Town row). |

## Transcript
| Full answer verbatim — paste the complete response as returned, with nothing added, removed, or reworded. |
| --- |

## Firms and figures
| Position in the agent's comparison | Firm (as named by the agent) | Figure quoted | Source cited | Notes | Matched firm | Match status | Aliases | Section | Cited URL | Cited own domain | Mention type | Total firms shown in the answer | Turn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Observation record
| Check type | Check ID | Description | Result | Agent's exact wording | Cited source | Reason (for Not observed / Not completed) | Review status | Confirmed by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Item | C1.1 | rating and review count readable | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C1.2 | rating figures consistent across sources | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C1.3 | no recurring unaddressed complaint pattern | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C2.1 | service-area page naming town and ZIP | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C2.2 | install and repair listed separately on that page | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C2.3 | brands and system types served on that page | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C2.4 | unique primary phone and booking route on that page | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C3.1 | single consistent applicable state licence number published | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | G6 | verifiable listing | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C4.2 | diagnostic fee in dollars | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C4.3 | free-estimate status for install, stated separately | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C4.4 | free-estimate status for repair, stated separately | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C5.1 | day-by-day hours readable | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C5.2 | hours consistency | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C6.1 | one unique primary phone number everywhere | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C6.2 | founding year and business lineage consistent across sources | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | G1 | exact name | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C7.1 | AI crawler access | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C7.2 | key facts readable without JavaScript | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C7.3 | LocalBusiness structured data | NaN | NaN | NaN | NaN | NaN | NaN |
| Item | C7.4 | sitemap | NaN | NaN | NaN | NaN | NaN | NaN |
| Category reference | C1 | Reputation — per-agent reference summary only, not the official Category result | NaN | NaN | NaN | NaN | NaN | NaN |
| Category reference | C2 | Area Coverage — per-agent reference summary only, not the official Category result | NaN | NaN | NaN | NaN | NaN | NaN |
| Category reference | C3 | Credentials and Trust — per-agent reference summary only, not the official Category result | NaN | NaN | NaN | NaN | NaN | NaN |
| Category reference | C4 | Pricing and Warranty — per-agent reference summary only, not the official Category result | NaN | NaN | NaN | NaN | NaN | NaN |
| Category reference | C5 | Hours and Active Status — per-agent reference summary only, not the official Category result | NaN | NaN | NaN | NaN | NaN | NaN |
| Category reference | C6 | Identity and Contact — per-agent reference summary only, not the official Category result | NaN | NaN | NaN | NaN | NaN | NaN |
| Category reference | C7 | Machine Readability — per-agent reference summary only, not the official Category result | NaN | NaN | NaN | NaN | NaN | NaN |
| Ranking Suggestion | S1 | Booking and quote route | NaN | NaN | NaN | NaN | NaN | NaN |
| Ranking Suggestion | S2 | Availability | NaN | NaN | NaN | NaN | NaN | NaN |
| Ranking Suggestion | S3 | Price for this user | NaN | NaN | NaN | NaN | NaN | NaN |
| Ranking Suggestion | S4 | Brand and system coverage | NaN | NaN | NaN | NaN | NaN | NaN |
| Ranking Suggestion | S5 | Service-area dispatch | NaN | NaN | NaN | NaN | NaN | NaN |
| Ranking Suggestion | S6 | Machine discovery (llms.txt) | NaN | NaN | NaN | NaN | NaN | NaN |
| Ranking Suggestion | C3.2 | BBB accreditation and rating consistent with bbb.org | NaN | NaN | NaN | NaN | NaN | NaN |
| Ranking Suggestion | C4.1 | six-line warranty card | NaN | NaN | NaN | NaN | NaN | NaN |
