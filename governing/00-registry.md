# AI Sharc — Governing Document Registry

**Source of truth.** This Project holds the live AI Sharc documentation, maintained by Claude at Tim's instruction (2026-11-19). The live revision of each document is the one listed here. Earlier revisions are superseded and are not kept in this Project.

**Change process.** All changes go through Claude: Tim approves a change, Claude edits the document, raises its revision number, logs the change in the document's own change log, updates this registry, and hands out files (Word, Excel, PDF) to anyone who needs them. Other agents, including Muse, read these documents and propose changes; they do not edit copies of their own.

**Formats.** Markdown documents here are the masters. Spreadsheets are stored here as text copies for reading and search; the .xlsx file is the controlling original. Word and PDF versions are produced from the masters when needed. Original files (.xlsx, .docx, .pdf) are kept in the AI-Sharc GitHub repository (timsthomasson-cpu/ai-sharc) under governing/originals/, alongside these Markdown masters under governing/. Supabase Storage will hold copies once the database is built.

## Live revisions (as of 2026-11-21)

| Document | Live revision | Role | Audience | File in this Project |
|---|---|---|---|---|
| AI Sharc Audit Specification | v2.12 (2026-11-21) | Canonical governing document; wins every conflict | Internal only | audit-specification-v2.12.md |
| Definition of Terms | Rev 8.4 (2026-11-21) | Governing (words only) | Internal | definition-of-terms-rev8.4.md (text copy of .xlsx) |
| Licensed Home Trade Field Mapping (internal) | Rev 13 (2026-11-21) | Governing; holds the Database fields sheet | Internal | licensed-home-trade-field-mapping-rev13.md (text copy of .xlsx) |
| Overview for Shopping Agents | Rev 8 (2026-11-21) | Governing | Agent-facing | overview-for-shopping-agents-rev8.md |
| Field Mapping for Shopping Agents | Rev 4 (2026-11-19) | Governing (the audit rubric) | Agent-facing | field-mapping-for-shopping-agents-rev4.md (text copy of .xlsx) |
| Shopping Query Return Template | Rev 8 (2026-11-21) | Governing (return format) | Agent-facing | shopping-query-return-template-rev8.md (text copy of .xlsx) |
| Template 1 Crosswalk | Rev 1 (adopted 2026-10-30) | Governing (trade categories and licences) | Internal | template-1-crosswalk-rev1.md |
| Buying Pattern Trade Groups | Rev 1 (2026-11-05) | Reference | Internal | buying-pattern-trade-groups-rev1.md (text copy of .xlsx) |
| Shopping Agent Observation Design | Rev 17 (2026-11-20, draft) | Working procedure, not governing | Internal only | observation-design-rev17.md |
| Preliminary Report Card — dummy data | Rev 1 (2026-11-19) | Output example | Firm-facing format | PDF in the repo only |
| Final Report Card — dummy data | Rev 1 (2026-11-19) | Output example | Firm-facing format | PDF in the repo only |
| Preliminary business plan | 2026-11-19 | Business reference | Internal | PDF in the repo only |
| AI Sharc vs agentic storefront | 2026-11-19 | Business reference | Internal | PDF in the repo only |

Superseded and not live: How the AI Sharc audit is performed (Rev 4, 2026-11-11), replaced by Specification v2.x.

## Change history

| Date | Change | Approved |
|---|---|---|
| 2026-11-19 | Registry created; Claude made maintainer of the governing documents. Live set loaded: Spec v2.8, Definition 8.3, internal Field Mapping 9, Overview 6, agent Field Mapping 4, Template 7, Crosswalk 1, Trade Groups 1, Observation Design 15. | Tim |
| 2026-11-19 | Spec v2.9 (checked_at wording in §4 and §4.3 rule 2; audit_measurements note corrected), Overview Rev 7 (§3.2 aligned with Spec §4.3 rule 2: unsourced result is Not accessible, not Missing), Observation Design Rev 16 (§9.4 agent_run_firms columns aligned with Field Mapping 9 and Template 7). | Tim |
| 2026-11-20 | Licensed Home Trade Field Mapping Rev 10: Database fields sheet brought into step with the database built in the test database (Test AI Sharc Orchestrator) — firms.firm_id; audits loader columns and the four website-access columns; delivery_checks gap closed; agent_runs, agent_run_firms, agent_observation_rows and observation_reason_codes built (test database only) with their added columns; match status is a join; session_state values; Read Me A4 to Spec v2.9. No scoring change. | Tim |
| 2026-11-20 | Shopping Agent Observation Design Rev 17: §9.4 aligned with Field Mapping Rev 10 and the database as built (observation tables built in the test database, not yet in East; added columns; session_state values; match status is a join; duplicate workbooks skipped by file hash). | Tim |
| 2026-11-21 | Spec v2.10: §3 shopping-query task text names the service area ("Find an HVAC firm whose service area includes [town], TX [ZIP] for …"), three tasks listed; §13 new subsection "Firm list and firm matching" (central firm list, verified base, matching ladder, review queue, merge and load rules, firm name not unique). Field Mapping Rev 11: firms becomes the central firm list (28 columns added, name no longer unique, slug rule, db_firm_id), firm_review_queue table, ladder replaces the exact-name join for agent mentions. Overview Rev 8 and Return Template Rev 8: new task wording, with the note that no shopping query has been run with it yet. No scoring change. | Tim |
| 2026-11-21 | Verified firm defined: a Meta place ID or an own website, either one is enough (Tim). Spec v2.11 (§13 rule; verification status per firm; an agent-named firm with neither is unverified), Definition of Terms Rev 8.4 (Verified firm, Unverified firm), Field Mapping Rev 12 (firms.verification_status; UNIQUE licence_type + licence_number). No scoring change. | Tim |
| 2026-11-21 | Licence reference list: Spec v2.12 (§13 — current TDLR A/C Contractor licences kept in the test database separately from the central firm list; for finding firms and licences, never for grading; name matches kept as leads) and Field Mapping Rev 13 (reference.tdlr_ac_contractors, reference.tdlr_name_matches). No scoring change. | Tim |

## Open items

1. Shopping Agent Observation Design Rev 17 §2.2 still shows the earlier task wording ("Find a [service] firm in [town], TX [ZIP] for …"). It needs the Spec v2.10 §3 wording in its next revision.
2. The Field Mapping .xlsx original for Rev 10 was never produced; the Rev 11 .xlsx was rebuilt from the Rev 9 .xlsx with the Rev 10 and Rev 11 changes applied.
