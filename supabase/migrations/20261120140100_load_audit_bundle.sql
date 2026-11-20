-- Loader entry point for harness audits (Spec v2.9 §13, File naming and folder layout).
-- Input: the bundle written by loader/build_bundle.py: {"audits": [{file, file_hash, firm{}, audit{}, rows[], delivery_check{}}]}.
-- Rules enforced here as well as in build_bundle.py:
--   * a file whose sha256 is already loaded is skipped as already loaded (a renamed copy is recognised);
--   * a re-check is a new audit, never an overwrite (identity unique key on audits);
--   * checked_at must be ISO 8601 with seconds and offset and must match the filename timestamp;
--   * 36 rows: 7 Category result, 21 Item, 8 Ranking Suggestion; vocabulary enforced by table checks.
-- Each audit loads in its own sub-transaction: one bad audit is reported as rejected and the rest still load.
-- Only the service role (and the database owner) may call it.

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

      insert into firms (firm_id, name, primary_business_category, website_url, trade, meta_place_id)
      select x #>> '{firm,firm_id}', x #>> '{firm,name}', x #>> '{firm,primary_business_category}',
             x #>> '{firm,website_url}', x #>> '{firm,trade}', x #>> '{firm,meta_place_id}'
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
