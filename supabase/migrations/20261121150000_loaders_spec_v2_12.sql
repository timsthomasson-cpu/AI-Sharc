-- 2026-11-21: loaders follow Specification v2.12 §13 and Licensed Home Trade Field Mapping Rev 13.
-- * load_audit_bundle: a firm it adds gets verification_status (now required) and discovery_source.
-- * load_observation_bundle: agent mentions are linked by a person's match or by the ladder, never by an automatic
--   name match; name-only matches go to firm_review_queue; unmatched mentions enter the list as agent-named.
-- Applied to the test database (Test AI Sharc Orchestrator) on 2026-11-21. Not yet applied to East.

-- Spec v2.12 §13 helpers.
-- website_host: the normalised website for rung 3 — host name, lower case, no leading www; a shared host that is
-- not a firm's own site (social networks, directories, map links, manufacturers, Google Sites) gives null. A firm's own
-- subdomain on a website builder (name.wixsite.com) is its own site and counts.
create or replace function public.website_host(url text) returns text
language sql immutable set search_path = public, pg_temp as $$
  select case when h is null or h = '' or h ~ '(^|\.)(facebook\.com|fb\.com|instagram\.com|linkedin\.com|x\.com|twitter\.com|youtube\.com|tiktok\.com|yelp\.com|google\.com|goo\.gl|g\.page|bbb\.org|angi\.com|homeadvisor\.com|thumbtack\.com|nextdoor\.com|carrier\.com|trane\.com|lennox\.com|rheem\.com|goodmanmfg\.com|texas\.gov)$'
              then null else h end
  from (select regexp_replace(lower(split_part(split_part(regexp_replace(coalesce(url, ''), '^[a-zA-Z]+://', ''), '/', 1), '?', 1)), '^www\.', '') as h) q
$$;

-- normalise_firm_name: Spec §6.6 normalisation — case, curly quotes, '&' vs 'and', commas and periods, 'A/C' = 'AC',
-- and a trailing legal suffix are ignored.
create or replace function public.normalise_firm_name(t text) returns text
language sql immutable set search_path = public, pg_temp as $$
  select btrim(regexp_replace(btrim(regexp_replace(regexp_replace(regexp_replace(
           lower(replace(replace(replace(coalesce(t, ''), '’', ''''), 'A/C', 'AC'), 'a/c', 'ac')),
           '&|\mand\M', ' ', 'g'), '[^a-z0-9 ]', ' ', 'g'), '\s+', ' ', 'g')),
           '\s+(llc|inc|corp|co|ltd|lp|llp|pllc)$', ''))
$$;

-- firm_slug: a new firm_id from a name; the slug rule of Field Mapping Rev 13 (name, then a numeric suffix when taken).
create or replace function public.firm_slug(t text) returns text
language plpgsql stable set search_path = public, pg_temp as $$
declare base text; s text; n int := 2;
begin
  base := btrim(regexp_replace(regexp_replace(lower(replace(replace(coalesce(t, ''), '&', ' and '), '''', '')), '[^a-z0-9]+', '-', 'g'), '-+', '-', 'g'), '-');
  if base = '' then base := 'firm'; end if;
  s := base;
  while exists (select 1 from firms where firm_id = s) loop s := base || '-' || n; n := n + 1; end loop;
  return s;
end $$;

-- Loader entry point for harness audits (Spec v2.12 §13; first built 2026-11-20).
create or replace function public.load_audit_bundle(bundle jsonb)
returns jsonb
language plpgsql
set search_path = public, pg_temp
as $fn$
declare
  x         jsonb;
  a         jsonb;
  new_id    bigint;
  fname     text;
  ts        text;
  n_rows    int;
  loaded    jsonb := '[]'::jsonb;
  skipped   jsonb := '[]'::jsonb;
  rejected  jsonb := '[]'::jsonb;
begin
  for x in select * from jsonb_array_elements(bundle -> 'audits') loop
    fname := x ->> 'file';
    a     := x -> 'audit';
    if exists (select 1 from audits where file_hash = x ->> 'file_hash') then
      skipped := skipped || jsonb_build_object('file', fname, 'reason', 'already loaded (same file hash)');
      continue;
    end if;
    begin
      ts := a ->> 'checked_at';
      if ts !~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$' then
        raise exception 'checked_at % is not ISO 8601 with seconds and offset', ts;
      end if;
      if split_part(fname, '__', 4) <> replace(substr(ts,1,10),'-','') || 'T' || replace(substr(ts,12,8),':','') || replace(substr(ts,20),':','') then
        raise exception 'checked_at % does not match filename timestamp %', ts, split_part(fname, '__', 4);
      end if;
      n_rows := jsonb_array_length(x -> 'rows');
      if n_rows <> 36
         or (select count(*) from jsonb_array_elements(x -> 'rows') r where r ->> 'row_type' = 'Category result') <> 7
         or (select count(*) from jsonb_array_elements(x -> 'rows') r where r ->> 'row_type' = 'Item') <> 21
         or (select count(*) from jsonb_array_elements(x -> 'rows') r where r ->> 'row_type' = 'Ranking Suggestion') <> 8 then
        raise exception 'row counts do not reconcile to 36 (7/21/8)';
      end if;

      -- The harness audits firms from the central firm list, so the firm normally exists already.
      -- A firm it does not know is added with its verification status (Spec v2.12 §13: verified =
      -- a Meta place ID or a website, either one is enough) and where it came from. An existing firm
      -- is never changed here (enrich, don't overwrite).
      insert into firms (firm_id, name, primary_business_category, website_url, trade, meta_place_id,
                         verification_status, discovery_source)
      select x #>> '{firm,firm_id}', x #>> '{firm,name}', x #>> '{firm,primary_business_category}',
             x #>> '{firm,website_url}', x #>> '{firm,trade}', x #>> '{firm,meta_place_id}',
             case when coalesce(x #>> '{firm,website_url}', x #>> '{firm,meta_place_id}') is not null
                  then 'verified' else 'unverified' end,
             'harness audit ' || coalesce(a ->> 'run_id', '')
      on conflict (firm_id) do nothing;

      insert into audits (firm_id, run_id, query, town_zip, query_id, checked_at, checked_at_text, spec_version, vendor, product,
                          evidence_source, file_hash, primary_email, primary_email_source, website_home, service_page, harness,
                          website_unreadable, unverified, unverified_reason, f_reason)
      values (x #>> '{firm,firm_id}', a ->> 'run_id', a ->> 'query', a ->> 'town_zip', a ->> 'query_id', ts::timestamptz, ts,
              a ->> 'spec_version', a ->> 'vendor', a ->> 'product', a ->> 'evidence_source', x ->> 'file_hash',
              nullif(nullif(a ->> 'primary_email', 'None'), ''), nullif(a ->> 'primary_email_source', ''),
              a ->> 'website_home', a ->> 'service_page', a ->> 'harness',
              coalesce((a ->> 'website_unreadable')::boolean, false), coalesce((a ->> 'unverified')::boolean, false),
              nullif(a ->> 'unverified_reason', ''), nullif(a ->> 'f_reason', ''))
      returning audit_id into new_id;

      insert into audit_rows (audit_id, seq_no, stage, row_type, category_or_gate, item, result, source_url, evidence_note,
                              why_it_matters, website_change, listing_change, operational_change, fix_priority, counts_toward, populates)
      select new_id, (r ->> 'seq_no')::int, r ->> 'stage', r ->> 'row_type', r ->> 'category_or_gate', r ->> 'item', r ->> 'result',
             r ->> 'source_url', r ->> 'evidence_note', r ->> 'why_it_matters', r ->> 'website_change', r ->> 'listing_change',
             r ->> 'operational_change', r ->> 'fix_priority', r ->> 'counts_toward', r ->> 'populates'
      from jsonb_array_elements(x -> 'rows') r;

      if jsonb_typeof(x -> 'delivery_check') = 'object' then
        insert into delivery_checks (audit_id, date_checked, published_business_email, emails_found, primary_email, primary_email_source,
                                     primary_email_rule, collection_method, do_not_harvest_notice_present, notice_wording,
                                     notice_wording_page, notice_type, can_spam_requirements_met, can_spam_note, delivery_route,
                                     delivery_route_reason, note)
        select new_id, (d ->> 'date_checked')::date, d ->> 'published_business_email',
               case jsonb_typeof(d -> 'emails_found') when 'array' then d -> 'emails_found'
                                                       when 'string' then (d ->> 'emails_found')::jsonb
                                                       else '[]'::jsonb end,
               d ->> 'primary_email', nullif(d ->> 'primary_email_source', ''), d ->> 'primary_email_rule', d ->> 'collection_method',
               d ->> 'do_not_harvest_notice_present', d ->> 'notice_wording', d ->> 'notice_wording_page', d ->> 'notice_type',
               d ->> 'can_spam_requirements_met', d ->> 'can_spam_note', d ->> 'delivery_route', d ->> 'delivery_route_reason', d ->> 'note'
        from (select x -> 'delivery_check' as d) q;
      end if;

      loaded := loaded || jsonb_build_object('file', fname, 'audit_id', new_id);
    exception when others then
      rejected := rejected || jsonb_build_object('file', fname, 'reason', sqlerrm);
    end;
  end loop;
  return jsonb_build_object('loaded', jsonb_array_length(loaded), 'skipped', skipped, 'rejected', rejected, 'audits', loaded);
end;
$fn$;

revoke all on function public.load_audit_bundle(jsonb) from public, anon, authenticated;
grant execute on function public.load_audit_bundle(jsonb) to service_role;

-- Loader: input is the bundle from loader/build_observation_bundle.py: {"runs": [{file, file_hash, run{}, firms[], rows[]}]}.
-- Same file hash, or same (vendor, product, agent_label, query_id, checked_at): skipped as already loaded.
-- Each run loads in its own sub-transaction; a bad run is reported as rejected and the rest still load.
create or replace function public.load_observation_bundle(bundle jsonb)
returns jsonb
language plpgsql
set search_path = public, pg_temp
as $fn$
declare
  x jsonb; r jsonb; f jsonb; fname text; ts text; rid text; fid text; cand text; status text; host text;
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

      -- Spec v2.12 §13 / Field Mapping Rev 13: an agent mention is linked to a firm only
      --   (1) when the workbook's "Matched firm" (a person's match) names exactly one firm, or
      --   (2) by the matching ladder: the same normalised website host as a firm, when the agent cited
      --       the firm's own domain and exactly one firm has that host (agent answers carry no town and ZIP,
      --       so rung 3 is read here as host only and never across shared hosts).
      -- A mention whose name matches a firm only by name is left ambiguous and queued for review.
      -- A mention that matches nothing enters the firm list as agent-named (unverified unless it cited
      -- its own website) and is linked to that new firm.
      for f in select * from jsonb_array_elements(x -> 'firms') loop
        fid := null; status := null; cand := null;
        host := public.website_host(case when f ->> 'cited_own_domain' = 'yes' then f ->> 'cited_url' end);
        if nullif(f ->> 'matched_firm', '') is not null
           and (select count(*) from firms where name = f ->> 'matched_firm') = 1 then
          select firm_id into fid from firms where name = f ->> 'matched_firm';
          status := 'matched';
        elsif host is not null and (select count(*) from firms where public.website_host(website_url) = host) = 1 then
          select firm_id into fid from firms where public.website_host(website_url) = host;
          status := 'matched';
        else
          select firm_id into cand from firms
           where public.normalise_firm_name(name) = public.normalise_firm_name(f ->> 'name_as_given')
           order by firm_id limit 1;
          if cand is not null then
            status := 'ambiguous';
          else
            fid := public.firm_slug(f ->> 'name_as_given');
            insert into firms (firm_id, name, trade, website_url, verification_status, discovery_source, query)
            values (fid, f ->> 'name_as_given', case split_part(r ->> 'query_id', '-', 1) when 'hvac' then 'HVAC' when 'plumbing' then 'Plumbing'
                    when 'electrical' then 'Electrical' when 'roofing' then 'Roofing' end,
                    case when host is not null then f ->> 'cited_url' end,
                    case when host is not null then 'verified' else 'unverified' end,
                    (r ->> 'vendor') || ' ' || (r ->> 'product') || ' shopping query ' || substr(ts, 1, 10),
                    r ->> 'service_query');
            status := 'matched';
          end if;
        end if;

        insert into agent_run_firms (run_id, position, name_as_given, figure_quoted, source_cited, notes, matched_firm, firm_id,
          match_status, aliases, section, cited_url, cited_own_domain, mention_type, total_firms_shown, turn)
        values (rid, f ->> 'position', f ->> 'name_as_given', f ->> 'figure_quoted', f ->> 'source_cited', f ->> 'notes',
          (select name from firms where firm_id = fid), fid, status, f ->> 'aliases', f ->> 'section', f ->> 'cited_url',
          f ->> 'cited_own_domain', f ->> 'mention_type', (f ->> 'total_firms_shown')::int, coalesce((f ->> 'turn')::int, 0));

        if status = 'ambiguous' then
          insert into firm_review_queue (firm_id, candidate_firm_id, source, reason, rung_tried, values_seen, note)
          values (null, cand, 'agent_run_firms ' || rid || ' position ' || (f ->> 'position'), 'name-only match', 'name',
                  jsonb_build_object('name_as_given', f ->> 'name_as_given', 'candidate_name', (select name from firms where firm_id = cand),
                                     'cited_url', f ->> 'cited_url'),
                  'Agent mention matches a firm by name only; left ambiguous until a person links it.');
        end if;
      end loop;

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
