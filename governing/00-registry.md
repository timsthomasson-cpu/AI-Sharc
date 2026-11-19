# AI Sharc — Governing Document Registry

**Source of truth.** This Project holds the live AI Sharc documentation, maintained by Claude at Tim's instruction (2026-11-19). The live revision of each document is the one listed here. Earlier revisions are superseded and are not kept in this Project.

**Change process.** All changes go through Claude: Tim approves a change, Claude edits the document, raises its revision number, logs the change in the document's own change log, updates this registry, and hands out files (Word, Excel, PDF) to anyone who needs them. Other agents, including Muse, read these documents and propose changes; they do not edit copies of their own.

**Formats.** Markdown documents here are the masters. Spreadsheets are stored here as text copies for reading and search; the .xlsx file is the controlling original. Word and PDF versions are produced from the masters when needed. Original files (.xlsx, .docx, .pdf) are kept in the AI-Sharc GitHub repository (timsthomasson-cpu/ai-sharc) under governing/originals/, alongside these Markdown masters under governing/. Supabase Storage will hold copies once the database is built.

## Live revisions (as of 2026-11-19)

| Document | Live revision | Role | Audience | File in this Project |
|---|---|---|---|---|
| AI Sharc Audit Specification | v2.9 (2026-11-19) | Canonical governing document; wins every conflict | Internal only | audit-specification-v2.9.md |
| Definition of Terms | Rev 8.3 (2026-11-19) | Governing (words only) | Internal | definition-of-terms-rev8.3.md (text copy of .xlsx) |
| Licensed Home Trade Field Mapping (internal) | Rev 9 (2026-11-19) | Governing; holds the Database fields sheet | Internal | licensed-home-trade-field-mapping-rev9.md (text copy of .xlsx) |
| Overview for Shopping Agents | Rev 7 (2026-11-19) | Governing | Agent-facing | overview-for-shopping-agents-rev7.md |
| Field Mapping for Shopping Agents | Rev 4 (2026-11-19) | Governing (the audit rubric) | Agent-facing | field-mapping-for-shopping-agents-rev4.md (text copy of .xlsx) |
| Shopping Query Return Template | Rev 7 (2026-11-19) | Governing (return format) | Agent-facing | shopping-query-return-template-rev7.md (text copy of .xlsx) |
| Template 1 Crosswalk | Rev 1 (adopted 2026-10-30) | Governing (trade categories and licences) | Internal | template-1-crosswalk-rev1.md |
| Buying Pattern Trade Groups | Rev 1 (2026-11-05) | Reference | Internal | buying-pattern-trade-groups-rev1.md (text copy of .xlsx) |
| Shopping Agent Observation Design | Rev 16 (2026-11-19, draft) | Working procedure, not governing | Internal only | observation-design-rev16.md |
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

## Open items

None.
