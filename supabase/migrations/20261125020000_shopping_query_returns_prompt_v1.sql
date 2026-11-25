-- Shopping Query Returns from Prompt v1 (Tim, 2026-11-24).
-- Agents now return the verbatim answer as an observation .md file. Claude reads each answer and writes an
-- extract (run details, the firms named, the agent's rank and what the ranking is based on). This loader takes
-- the run and the firms. The 36 observation rows are added later as a separate step, so a run loaded here is
-- marked observation_rows_status = 'pending'.

alter table public.agent_runs
  add column if not exists prompt_version          text,
  add column if not exists web_search_ran          text check (web_search_ran in ('yes','no','not stated')),
  add column if not exists sources_cited           jsonb,
  add column if not exists ranked                  text check (ranked in ('yes','no')),
  add column if not exists ranking_basis           text,
  add column if not exists ranking_origin          text check (ranking_origin in ('own','copied from another site','mixed','not stated')),
  add column if not exists follow_up               text,
  add column if not exists business_contacted      text check (business_contacted in ('no','yes','not stated')),
  add column if not exists response_text           text,
  add column if not exists drive_file_id           text,
  add column if not exists extracted_by            text,
  add column if not exists observation_rows_status text not null default 'loaded'
                                                   check (observation_rows_status in ('loaded','pending'));

alter table public.agent_run_firms
  add column if not exists agent_rank           int check (agent_rank >= 1),
  add column if not exists phone_as_given       text,
  add column if not exists address_as_given     text,
  add column if not exists website_as_given     text,
  add column if not exists rating_as_given      numeric(3,2),
  add column if not exists review_count_as_given int,
  add column if not exists match_rung           text check (match_rung in ('google place id','website','phone','name only','new firm'));

comment on column public.agent_run_firms.position is
  'Order in which the firm appears in the answer (1, 2, 3 …). Not the agent''s rank: see agent_rank.';
comment on column public.agent_run_firms.agent_rank is
  'The rank the agent gave the firm when asked to rank (Prompt v1). Null when the agent did not rank it.';

-- Ten digits, US numbers only; anything else gives null.
create or replace function public.phone_digits(p text) returns text
language sql immutable as $$
  select case when length(d) = 10 then d when length(d) = 11 and left(d,1) = '1' then substr(d,2) end
  from (select regexp_replace(coalesce(p,''), '\D', '', 'g') d) x
$$;

-- Loader for Prompt v1 returns. Input: {"runs": [{file, file_hash, run{}, firms[]}]}, built by
-- loader/build_return_bundle.py from the .md file and Claude's extract.
-- Matching ladder (Spec v2.13 §13): Google place ID, then website host, then phone. A rung counts only when
-- exactly one firm matches. A name-only match is left ambiguous and queued for review. A firm that matches
-- nothing enters the firm list as agent-named: verified when it came with a website, unverified otherwise.
create or replace function public.load_shopping_query_return(bundle jsonb)
returns jsonb
language plpgsql
set search_path = public, pg_temp
as $fn$
declare
  x jsonb; r jsonb; f jsonb; fname text; ts text; rid text; fid text; cand text; status text; rung text;
  host text; ph text; pid text; n int;
  loaded jsonb := '[]'::jsonb; skipped jsonb := '[]'::jsonb; rejected jsonb := '[]'::jsonb;
begin
  for x in select * from jsonb_array_elements(bundle -> 'runs') loop
    fname := x ->> 'file'; r := x -> 'run'; ts := r ->> 'checked_at'; rid := r ->> 'run_id';
    if exists (select 1 from agent_runs where file_hash = x ->> 'file_hash')
       or exists (select 1 from agent_runs where run_id = rid) then
      skipped := skipped || jsonb_build_object('file', fname, 'reason', 'already loaded');
      continue;
    end if;
    begin
      if split_part(fname, '__', 4) <> replace(substr(ts,1,10),'-','') || 'T' || replace(substr(ts,12,8),':','') || replace(substr(ts,20),':','') then
        raise exception 'checked_at % does not match filename timestamp %', ts, split_part(fname, '__', 4);
      end if;
      if coalesce(r ->> 'prompt_version', '') = '' then
        raise exception 'prompt version missing';
      end if;

      insert into agent_runs (run_id, vendor, product, agent_label, query, query_id, task_number, service, service_query, town_zip,
        checked_at, checked_at_text, model, tools_used, signed_in_account, fresh_session, repeat_number, session_state,
        auditor, source_file, file_hash, prompt_version, web_search_ran, sources_cited, ranked, ranking_basis, ranking_origin,
        follow_up, business_contacted, response_text, drive_file_id, extracted_by, observation_rows_status)
      values (rid, r ->> 'vendor', r ->> 'product', r ->> 'agent_label', r ->> 'query', r ->> 'query_id',
        (r ->> 'task_number')::int, r ->> 'service', r ->> 'service_query', r ->> 'town_zip', ts::timestamptz, ts,
        r ->> 'model', r ->> 'tools_used', r ->> 'signed_in_account', r ->> 'fresh_session', (r ->> 'repeat_number')::int,
        r ->> 'session_state', r ->> 'auditor', fname, x ->> 'file_hash', r ->> 'prompt_version', r ->> 'web_search_ran',
        r -> 'sources_cited', r ->> 'ranked', r ->> 'ranking_basis', r ->> 'ranking_origin', r ->> 'follow_up',
        r ->> 'business_contacted', r ->> 'response_text', r ->> 'drive_file_id', r ->> 'extracted_by', 'pending');

      for f in select * from jsonb_array_elements(x -> 'firms') loop
        fid := null; cand := null; status := null; rung := null;
        pid := nullif(f ->> 'google_place_id', '');
        host := public.website_host(nullif(f ->> 'website_as_given', ''));
        ph := public.phone_digits(f ->> 'phone_as_given');

        if pid is not null and (select count(*) from firms where google_place_id = pid) = 1 then
          select firm_id into fid from firms where google_place_id = pid; rung := 'google place id';
        elsif host is not null and (select count(*) from firms where public.website_host(website_url) = host) = 1 then
          select firm_id into fid from firms where public.website_host(website_url) = host; rung := 'website';
        elsif ph is not null and (select count(*) from firms where public.phone_digits(unique_primary_phone) = ph) = 1 then
          select firm_id into fid from firms where public.phone_digits(unique_primary_phone) = ph; rung := 'phone';
        end if;

        if fid is not null then
          status := 'matched';
        else
          select firm_id into cand from firms
           where public.normalise_firm_name(name) = public.normalise_firm_name(f ->> 'name_as_given')
           order by firm_id limit 1;
          if cand is not null then
            status := 'ambiguous'; rung := 'name only';
          else
            fid := public.firm_slug(f ->> 'name_as_given');
            select count(*) into n from firms where firm_id = fid;
            if n > 0 then fid := fid || '-' || substr(md5(rid || (f ->> 'name_as_given')), 1, 6); end if;
            insert into firms (firm_id, name, trade, website_url, unique_primary_phone, address, verification_status,
                               discovery_source, query, first_seen_date)
            values (fid, f ->> 'name_as_given',
                    case split_part(r ->> 'query_id', '-', 1) when 'hvac' then 'HVAC' when 'plumbing' then 'Plumbing'
                      when 'electrical' then 'Electrical' when 'roofing' then 'Roofing' end,
                    case when host is not null then f ->> 'website_as_given' end,
                    f ->> 'phone_as_given', f ->> 'address_as_given',
                    case when host is not null then 'verified' else 'unverified' end,
                    (r ->> 'vendor') || ' ' || (r ->> 'product') || ' shopping query ' || substr(ts, 1, 10),
                    r ->> 'service_query', substr(ts, 1, 10)::date);
            status := 'matched'; rung := 'new firm';
          end if;
        end if;

        insert into agent_run_firms (run_id, position, name_as_given, figure_quoted, source_cited, notes, matched_firm, firm_id,
          match_status, section, cited_url, cited_own_domain, mention_type, total_firms_shown, turn,
          agent_rank, phone_as_given, address_as_given, website_as_given, rating_as_given, review_count_as_given, match_rung)
        values (rid, f ->> 'position', f ->> 'name_as_given', f ->> 'figure_quoted', f ->> 'source_cited', f ->> 'notes',
          (select name from firms where firm_id = fid), fid, status, coalesce(f ->> 'section', 'main'), f ->> 'cited_url',
          f ->> 'cited_own_domain', f ->> 'mention_type', jsonb_array_length(x -> 'firms'), coalesce((f ->> 'turn')::int, 0),
          (f ->> 'agent_rank')::int, f ->> 'phone_as_given', f ->> 'address_as_given', f ->> 'website_as_given',
          (f ->> 'rating_as_given')::numeric, (f ->> 'review_count_as_given')::int, rung);

        if status = 'ambiguous' then
          insert into firm_review_queue (firm_id, candidate_firm_id, source, reason, rung_tried, values_seen, note)
          values (null, cand, 'agent_run_firms ' || rid || ' position ' || (f ->> 'position'), 'name-only match',
                  'google place id, website, phone',
                  jsonb_build_object('name_as_given', f ->> 'name_as_given', 'candidate_name', (select name from firms where firm_id = cand),
                                     'phone_as_given', f ->> 'phone_as_given', 'website_as_given', f ->> 'website_as_given'),
                  'Agent mention matches a firm by name only; left ambiguous until a person links it.');
        end if;
      end loop;

      loaded := loaded || jsonb_build_object('file', fname, 'run_id', rid, 'firms', jsonb_array_length(x -> 'firms'));
    exception when others then
      rejected := rejected || jsonb_build_object('file', fname, 'reason', sqlerrm);
    end;
  end loop;
  return jsonb_build_object('loaded', jsonb_array_length(loaded), 'skipped', skipped, 'rejected', rejected, 'runs', loaded);
end;
$fn$;

revoke all on function public.load_shopping_query_return(jsonb) from public, anon, authenticated;
grant execute on function public.load_shopping_query_return(jsonb) to service_role;
