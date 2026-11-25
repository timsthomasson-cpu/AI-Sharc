# Orchestrator

Runs the harness (`harness/`) for one shopping query against the central firm list, and loads the results into the audit database. Written to run on Railway; it also runs locally.

## Steps

1. `firm_registry.py --query-id hvac-houston-77002-t2 --out firms.json` — reads the firms the query's shopping runs named (`agent_run_firms`), or `--firm-ids a,b,c`, and writes the harness registry. The town and ZIP are the query's, not the firm's address.
2. `run_query.py --registry firms.json --out-dir runs/<date>-<query_id> [--resume]` — runs `run_audit.run_all()` with the query's task text (Spec v2.12 §3). Each firm gets the four output files.
3. `load_results.py audits runs/<date>-<query_id> [--dry-run]` — builds the bundle and calls `public.load_audit_bundle()`. `load_results.py observations <folder>` does the same for Shopping Query Return workbooks via `public.load_observation_bundle()`.

## Settings

- `DATABASE_URL` — the Supabase connection string, kept as a Railway secret. Use the test database (Test AI Sharc Orchestrator) until the comparison run checks out.

## Not yet portable (step 2 of the Railway plan)

The harness still calls Muse-only tools: `/opt/hatch/bin/places`, `/opt/hatch/bin/web-search`, `/opt/hatch/bin/browser-service` and `dynamic_credentials`. These need replacing with API calls (search and Places keys) before an audit can run on Railway. The rules engine, direct page fetches and the Playwright renderer already run outside Muse.

## Tests

`python -m pytest orchestrator/tests` — offline, no network or database.

## Loading Prompt v1 Shopping Query Returns (2026-11-24)

Each agent saves its answer as `<agent>__<query_id>__r<n>__<YYYYMMDDTHHMMSS-0600>__observation.md` in the Drive
Inbox date folder (Shopping Query Prompt v1). Agent prefixes: `meta-muse`, `meta-metaai`, `openai-chatgpt`.

1. Claude copies the date folder from the Drive Inbox.
2. Claude reads each answer and writes `<same name>__extract.json` beside it: the run details the file states,
   each firm in the order it appears (`position`), the agent's rank (`agent_rank`), phone, website, address,
   rating and review count as given, what the ranking is based on, and whether it was copied from another site.
   The `.md` file is never changed.
3. `load_results.py returns <folder>` checks the extract against the file (the exact Prompt v1 task and ranking
   wording must appear in it, the file name must follow the pattern) and loads the run and its firms with
   `load_shopping_query_return()`. Firms are matched by Google place ID, then website, then phone; a name-only
   match is queued for review; a firm that matches nothing is added as agent-named.
4. The 36 observation rows are added later; until then the run shows `observation_rows_status = 'pending'`.
