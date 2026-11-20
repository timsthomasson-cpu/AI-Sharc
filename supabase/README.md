# AI Sharc audit database

Migrations for the Supabase Postgres audit database (Spec v2.9 §13; Licensed Home Trade Field Mapping Rev 9).

| Project | Role | Status |
|---|---|---|
| AI Sharc Orchestrator (us-west-2) — to be renamed "Test AI Sharc Orchestrator" | Test | Migrations applied 2026-11-20; Houston 2026-11-19 harness run loaded (44 audits) |
| AI Sharc Orchestrator East (us-east-1) | Live | Empty — apply these migrations only after the test checks out |

## What is built

- `firms`, `audits`, `audit_rows`, `audit_measurements` (empty), `delivery_checks`
- `audit_summary` view — total points, passed Items, High issues, grade and eligible rank are derived here, never loaded
- `load_audit_bundle(jsonb)` — loader entry point (service role only). Skips a file whose sha256 is already loaded, rejects a file whose checked_at does not match the filename timestamp or whose rows do not reconcile to 36 (7/21/8); one bad audit does not stop the rest.

## Not built (waiting on Tim)

`queries`, `agent_runs`, `agent_run_firms`, `agent_observation_rows`, `observation_reason_codes`. Field Mapping Rev 9 marks `queries` and `agent_runs` as designed tables, "documentation only; do not build" (Spec §15 deviation rule). The Meta AI Shopping Query Return workbooks are not loaded for that reason.

## Loading a run

```
python3 loader/build_bundle.py <run_folder> bundle.json   # validates and writes the bundle
-- then, as the service role:
select public.load_audit_bundle('<bundle.json contents>'::jsonb);
```

`<run_folder>` must hold each audit's `__audit-data.json`, `__summary.json` and `__delivery-check.json`.
