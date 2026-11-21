# AI Sharc audit database

Migrations for the Supabase Postgres audit database (Spec v2.9 §13; Licensed Home Trade Field Mapping Rev 13).

Note (2026-11-21): the migration files here cover the 2026-11-20 build. The test database has since had two more migrations (central_firm_list_rev11, firms_verification_status), a firm_review_queue table and the reference schema (Field Mapping Rev 11–13). They are not in this folder yet.

| Project | Role | Status |
|---|---|---|
| Test AI Sharc Orchestrator (us-west-2) | Test | Migrations applied 2026-11-20; Houston 2026-11-19 harness run (44 audits) and the 3 Meta AI Shopping Query Return runs loaded |
| AI Sharc Orchestrator East (us-east-1) | Live | Empty — apply these migrations only after the test checks out |

## What is built

- `firms`, `audits`, `audit_rows`, `audit_measurements` (empty), `delivery_checks`
- `audit_summary` view — total points, passed Items, High issues, grade and eligible rank are derived here, never loaded
- `load_audit_bundle(jsonb)` — loader entry point (service role only). Skips a file whose sha256 is already loaded, rejects a file whose checked_at does not match the filename timestamp or whose rows do not reconcile to 36 (7/21/8); one bad audit does not stop the rest.

- `agent_runs`, `agent_run_firms`, `agent_observation_rows`, `observation_reason_codes` and `load_observation_bundle(jsonb)`: built in the test project on Tim's instruction, 2026-11-20. Field Mapping Rev 10 recorded them as built in the test project.

## Not built

`queries` (still documentation only in Field Mapping Rev 13).

## Loading a run

```
python3 loader/build_bundle.py <run_folder> bundle.json   # validates and writes the bundle
-- then, as the service role:
select public.load_audit_bundle('<bundle.json contents>'::jsonb);
```

`<run_folder>` must hold each audit's `__audit-data.json`, `__summary.json` and `__delivery-check.json`.

Shopping Query Return workbooks: `python3 loader/build_observation_bundle.py <run_folder> obs.json`, then `select public.load_observation_bundle('<obs.json contents>'::jsonb);`.
