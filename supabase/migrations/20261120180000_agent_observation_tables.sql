-- Agent observation tables (Observation Design Rev 16 §9.4; Field Mapping Rev 9, Database fields sheet;
-- Shopping Query Return Template Rev 7; Spec v2.9 §7.1).
-- Field Mapping Rev 9 marks agent_runs as "DESIGNED table — documentation only; do not build".
-- Built in the TEST project on Tim's explicit instruction, 2026-11-20 (Spec §15 override, test DB only).
-- Not built here: queries (still documentation only). agent_runs.query_id is plain text, no foreign key.
--
-- Columns beyond the Field Mapping design, flagged for Tim:
--   agent_runs: task_number, service, source_file, file_hash, loaded_at (traceability, as on audits)
--   agent_run_firms: figure_quoted, source_cited, notes (Template Rev 7 "Firms and figures" columns)
-- Observation rows never enter audit_rows or audit_summary and never change a grade (§9.3).

create table public.observation_reason_codes (
  code        text primary key,
  label       text not null,
  definition  text not null
);

insert into public.observation_reason_codes (code, label, definition) values
('a', 'Not mentioned',
 'The agent''s answer, including its sources panel and any follow-up turns, does not state the fact and does not show that the agent checked the Item.'),
('b', 'Mentioned, not demonstrated',
 'The answer states the fact, but either (1) there is no recordable evidence for it in the response body, sources panel, or follow-up turn — no exact agent wording with a cited source to record — or (2) what it states does not meet the Item''s pass criteria in full (for example, hours given as one daily range rather than day by day, or one firm''s figure where the Item requires consistency across sources).');

create table public.agent_runs (
  run_id                       text primary key,
  vendor                       text not null check (btrim(vendor) <> ''),
  product                      text not null check (btrim(product) <> ''),
  agent_label                  text not null,
  query                        text not null,
  query_id                     text not null check (query_id ~ '^[a-z]+-[a-z0-9]+-[0-9]{5}-t[123]$'),
  task_number                  int check (task_number between 1 and 3),
  service                      text,
  service_query                text,
  town_zip                     text,
  checked_at                   timestamptz not null,
  checked_at_text              text not null check (checked_at_text ~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$'),
  model                        text,
  tools_used                   text,
  signed_in_account            text,
  signed_in_account_confirmed  text check (signed_in_account_confirmed in ('yes','no')),
  fresh_session                text check (fresh_session in ('yes','no')),
  fresh_session_confirmed      text check (fresh_session_confirmed in ('yes','no')),
  mode_used                    text,
  mode_used_confirmed          text check (mode_used_confirmed in ('yes','no')),
  repeat_number                int not null check (repeat_number >= 1),
  session_state                text check (session_state in ('logged in','logged out','incognito')),
  location_setting             text,
  auditor                      text,
  transcript_reference         text,
  delegation                   text,
  source_file                  text not null,
  file_hash                    text not null unique check (file_hash ~ '^[0-9a-f]{64}$'),
  loaded_at                    timestamptz not null default now(),
  -- A re-run is a new run, never an overwrite.
  unique (vendor, product, agent_label, query_id, checked_at)
);

create table public.agent_run_firms (
  run_id             text not null references public.agent_runs(run_id) on delete cascade,
  position           text not null,          -- 1, 2, 3 … or 'Unranked'
  name_as_given      text not null,
  figure_quoted      text,
  source_cited       text,
  notes              text,
  matched_firm       text,
  firm_id            text references public.firms(firm_id),
  match_status       text not null check (match_status in ('matched','unmatched','ambiguous')),
  aliases            text,
  section            text check (section in ('main','social','price context','follow-up')),
  cited_url          text,
  cited_own_domain   text check (cited_own_domain in ('yes','no','none cited')),
  mention_type       text check (mention_type in ('place card','named in text','cited link only','social post')),
  total_firms_shown  int,
  turn               int not null default 0 check (turn >= 0),
  website_access     text check (website_access in ('Pass','Fail')),
  primary key (run_id, position),
  unique (run_id, name_as_given)
);

create table public.agent_observation_rows (
  run_id               text not null references public.agent_runs(run_id) on delete cascade,
  row_type             text not null check (row_type in ('Item','Category reference','Ranking Suggestion')),
  check_id             text not null,
  description          text,
  result               text not null,
  agent_exact_wording  text,
  cited_source         text,
  reason               text,
  review_status        text not null default 'proposed' check (review_status in ('proposed','confirmed','changed')),
  confirmed_by         text,
  primary key (run_id, check_id),
  check (
       (row_type = 'Item' and result in ('Pass','Fail','Not observed','Not completed','Not tested'))
    or (row_type = 'Ranking Suggestion' and check_id in ('C3.2','C4.1') and result in ('Complete','Suggested','Not checked'))
    or (row_type = 'Ranking Suggestion' and check_id ~ '^S[1-6]$' and result in ('Observed','Recommendation','Not checked'))
    or (row_type = 'Category reference')
  ),
  -- Spec §7.1: every Not observed Item carries reason code (a) or (b); a Pass or Fail needs exact wording and a cited source.
  check (row_type <> 'Item' or result <> 'Not observed' or reason ~ '^\((a|b)\)'),
  check (row_type <> 'Item' or result not in ('Pass','Fail')
         or (coalesce(btrim(agent_exact_wording), '') not in ('', '—') and coalesce(btrim(cited_source), '') not in ('', '—')))
);

create index agent_runs_query_idx on public.agent_runs (query_id, checked_at);
create index agent_run_firms_firm_idx on public.agent_run_firms (firm_id);

alter table public.observation_reason_codes enable row level security;
alter table public.agent_runs               enable row level security;
alter table public.agent_run_firms          enable row level security;
alter table public.agent_observation_rows   enable row level security;

-- Loader: input is the bundle from loader/build_observation_bundle.py: {"runs": [{file, file_hash, run{}, firms[], rows[]}]}.
-- Same file hash, or same (vendor, product, agent_label, query_id, checked_at): skipped as already loaded.
-- Each run loads in its own sub-transaction; a bad run is reported as rejected and the rest still load.
create or replace function public.load_observation_bundle(bundle jsonb)
returns jsonb
language plpgsql
set search_path = public, pg_temp
as $fn$
declare
  x jsonb; r jsonb; fname text; ts text; rid text;
  loaded jsonb := '[]'::jsonb; skipped jsonb := '[]'::jsonb; rejected jsonb := '[]'::jsonb;
begin
  for x in select * from jsonb_array_elements(bundle -> 'runs') loop
    fname := x ->> 'file'; r := x -> 'run'; ts := r ->> 'checked_at'; rid := r ->> 'run_id';
    if exists (select 1 from agent_runs where file_hash = x ->> 'file_hash')
       or exists (select 1 from agent_runs where vendor = r ->> 'vendor' and product = r ->> 'product'
                  and agent_label = r ->> 'agent_label' and query_id = r ->> 'query_id' and checked_at = ts::timestamptz) then
      skipped := skipped || jsonb_build_object('file', fname, 'reason', 'already loaded');
      continue;
    end if;
    begin
      if split_part(fname, '__', 4) <> replace(substr(ts,1,10),'-','') || 'T' || replace(substr(ts,12,8),':','') || replace(substr(ts,20),':','') then
        raise exception 'checked_at % does not match filename timestamp %', ts, split_part(fname, '__', 4);
      end if;
      if jsonb_array_length(x -> 'rows') <> 36
         or (select count(*) from jsonb_array_elements(x -> 'rows') o where o ->> 'row_type' = 'Item') <> 21
         or (select count(*) from jsonb_array_elements(x -> 'rows') o where o ->> 'row_type' = 'Category reference') <> 7
         or (select count(*) from jsonb_array_elements(x -> 'rows') o where o ->> 'row_type' = 'Ranking Suggestion') <> 8 then
        raise exception 'observation rows do not reconcile to 36 (21/7/8)';
      end if;
      if jsonb_array_length(x -> 'firms') = 0 then
        raise exception 'no firm in Firms and figures';
      end if;

      insert into agent_runs (run_id, vendor, product, agent_label, query, query_id, task_number, service, service_query, town_zip,
        checked_at, checked_at_text, model, tools_used, signed_in_account, signed_in_account_confirmed, fresh_session,
        fresh_session_confirmed, mode_used, mode_used_confirmed, repeat_number, session_state, location_setting, auditor,
        transcript_reference, delegation, source_file, file_hash)
      values (rid, r ->> 'vendor', r ->> 'product', r ->> 'agent_label', r ->> 'query', r ->> 'query_id',
        (r ->> 'task_number')::int, r ->> 'service', r ->> 'service_query', r ->> 'town_zip', ts::timestamptz, ts,
        r ->> 'model', r ->> 'tools_used', r ->> 'signed_in_account', r ->> 'signed_in_account_confirmed', r ->> 'fresh_session',
        r ->> 'fresh_session_confirmed', r ->> 'mode_used', r ->> 'mode_used_confirmed', (r ->> 'repeat_number')::int,
        r ->> 'session_state', r ->> 'location_setting', r ->> 'auditor', r ->> 'transcript_reference',
        nullif(r ->> 'delegation', 'none'), fname, x ->> 'file_hash');

      insert into agent_run_firms (run_id, position, name_as_given, figure_quoted, source_cited, notes, matched_firm, firm_id,
        match_status, aliases, section, cited_url, cited_own_domain, mention_type, total_firms_shown, turn)
      select rid, f ->> 'position', f ->> 'name_as_given', f ->> 'figure_quoted', f ->> 'source_cited', f ->> 'notes',
             f ->> 'matched_firm', (select firm_id from firms where name = f ->> 'matched_firm'),
             f ->> 'match_status', f ->> 'aliases', f ->> 'section', f ->> 'cited_url', f ->> 'cited_own_domain',
             f ->> 'mention_type', (f ->> 'total_firms_shown')::int, coalesce((f ->> 'turn')::int, 0)
      from jsonb_array_elements(x -> 'firms') f;

      insert into agent_observation_rows (run_id, row_type, check_id, description, result, agent_exact_wording, cited_source,
        reason, review_status, confirmed_by)
      select rid, o ->> 'row_type', o ->> 'check_id', o ->> 'description', o ->> 'result', o ->> 'agent_exact_wording',
             o ->> 'cited_source', o ->> 'reason', coalesce(o ->> 'review_status', 'proposed'), o ->> 'confirmed_by'
      from jsonb_array_elements(x -> 'rows') o;

      loaded := loaded || jsonb_build_object('file', fname, 'run_id', rid);
    exception when others then
      rejected := rejected || jsonb_build_object('file', fname, 'reason', sqlerrm);
    end;
  end loop;
  return jsonb_build_object('loaded', jsonb_array_length(loaded), 'skipped', skipped, 'rejected', rejected, 'runs', loaded);
end;
$fn$;

revoke all on function public.load_observation_bundle(jsonb) from public, anon, authenticated;
grant execute on function public.load_observation_bundle(jsonb) to service_role;
