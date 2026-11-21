-- AI Sharc audit database — live audit tables (Spec v2.9 §13; Licensed Home Trade Field Mapping Rev 9, Database fields sheet).
-- Applied first to the TEST project (AI Sharc Orchestrator, us-west-2). Apply the same file to AI Sharc Orchestrator East only after the test load checks out.
--
-- Built here: firms, audits, audit_rows, audit_measurements (empty), delivery_checks, audit_summary (view).
-- NOT built here: queries, agent_runs, agent_run_firms, agent_observation_rows, observation_reason_codes.
--   Field Mapping Rev 9 marks queries and agent_runs as "DESIGNED table — documentation only; do not build".
--   They wait for Tim's explicit go-ahead (Spec §15).
--
-- Grade, points and counts are never loaded: audit_summary derives them from audit_rows (Field Mapping Rev 9).

create table public.firms (
  firm_id                    text primary key check (firm_id ~ '^[a-z0-9-]+$'),
  name                       text not null unique,
  primary_business_category  text,
  website_url                text,
  trade                      text check (trade in ('HVAC','Plumbing','Electrical','Roofing')),
  meta_place_id              text,
  created_at                 timestamptz not null default now()
);

create table public.audits (
  audit_id              bigint generated always as identity primary key,
  firm_id               text not null references public.firms(firm_id),
  run_id                text not null,
  query                 text not null,
  town_zip              text not null,
  query_id              text not null check (query_id ~ '^[a-z]+-[a-z0-9]+-[0-9]{5}-t[123]$'),
  checked_at            timestamptz not null,
  checked_at_text       text not null check (checked_at_text ~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$'),
  spec_version          text not null,
  vendor                text not null check (btrim(vendor) <> ''),
  product               text not null check (btrim(product) <> ''),
  evidence_source       text not null,
  file_hash             text not null unique check (file_hash ~ '^[0-9a-f]{64}$'),
  audit_role            text not null default 'raw' check (audit_role in ('raw','official')),
  consolidated_from     jsonb not null default '[]'::jsonb,
  primary_email         text,
  primary_email_source  text,
  website_home          text,
  service_page          text,
  harness               text,
  -- Website-access determination (Spec §4.1.1, §5). Inputs to the grade, not the grade.
  -- Source: the audit's __summary.json (website_unreadable / unverified / unverified_reason / f_reason).
  -- Not listed in Field Mapping Rev 9 — flagged for Tim; without them the view cannot tell F or unverified from a scored audit.
  website_unreadable    boolean not null default false,
  unverified            boolean not null default false,
  unverified_reason     text,
  f_reason              text,
  loaded_at             timestamptz not null default now(),
  -- A re-check is a new audit, never an overwrite (Spec §13 identity: firm, query, town/ZIP, checked_at, vendor, product).
  unique (firm_id, query, town_zip, checked_at, vendor, product),
  check (audit_role = 'official' or consolidated_from = '[]'::jsonb)
);

create table public.audit_rows (
  audit_id            bigint not null references public.audits(audit_id) on delete cascade,
  seq_no              int not null check (seq_no between 1 and 36),
  stage               text,
  row_type            text not null check (row_type in ('Category result','Item','Ranking Suggestion')),
  category_or_gate    text,
  item                text not null,
  result              text not null,
  source_url          text,
  evidence_note       text,
  why_it_matters      text,
  website_change      text,
  listing_change      text,
  operational_change  text,
  fix_priority        text,
  counts_toward       text,
  populates           text,
  primary key (audit_id, seq_no),
  -- Controlled vocabulary (Spec §7). 'Not completed' is allowed for agent audits only.
  check (
       (row_type = 'Item' and result in ('Pass','Pass with warning','Missing','Conflict','Not accessible','Not completed'))
    or (row_type = 'Ranking Suggestion' and result in ('Observed','Recommendation','Not checked','Complete','Suggested'))
    or (row_type = 'Category result' and result ~ '^\d+ of \d+ points$')
  )
);

-- Built empty (Spec v2.9 version note); populated by future harness/measurement writes.
create table public.audit_measurements (
  measurement_id  bigint generated always as identity primary key,
  audit_id        bigint not null references public.audits(audit_id) on delete cascade,
  metric          text not null check (metric in (
                    'robots_txt_status_per_crawler','llms_txt','sitemap','json_ld_types',
                    'rating_and_review_count_per_platform','core_web_vitals',
                    'google_business_profile_and_meta_place_presence','service_and_town_page_counts')),
  value           text,
  unit            text,
  platform        text,
  source_url      text,
  method          text,
  checked_at      timestamptz not null
);

-- One record per audit; delivery only, never a scored row (Spec §4.2).
create table public.delivery_checks (
  audit_id                       bigint primary key references public.audits(audit_id) on delete cascade,
  date_checked                   date,
  published_business_email       text,
  emails_found                   jsonb not null default '[]'::jsonb,
  primary_email                  text,
  primary_email_source           text,
  primary_email_rule             text,
  collection_method              text,
  do_not_harvest_notice_present  text,
  notice_wording                 text,
  notice_wording_page            text,
  notice_type                    text,
  can_spam_requirements_met      text,
  can_spam_note                  text,
  delivery_route                 text,
  delivery_route_reason          text,
  note                           text
);

create index audits_query_idx on public.audits (query_id, town_zip, checked_at);
create index audits_firm_idx on public.audits (firm_id);
create index audit_measurements_audit_idx on public.audit_measurements (audit_id);

-- RLS on, no policies: only the service role / database owner can read or write. The website gets read policies later.
alter table public.firms              enable row level security;
alter table public.audits             enable row level security;
alter table public.audit_rows         enable row level security;
alter table public.audit_measurements enable row level security;
alter table public.delivery_checks    enable row level security;

-- Derived figures (Spec §8). Never stored.
create view public.audit_summary with (security_invoker = true) as
with r as (
  select
    audit_id,
    count(*)                                                        as rows_total,
    count(*) filter (where row_type = 'Category result')            as category_rows,
    count(*) filter (where row_type = 'Item')                       as item_rows,
    count(*) filter (where row_type = 'Ranking Suggestion')         as ranking_rows,
    count(*) filter (where row_type = 'Item' and result in ('Pass','Pass with warning')) as passed_items_raw,
    count(*) filter (where row_type = 'Item' and result not in ('Pass','Pass with warning')) as failed_items_raw,
    coalesce(sum((regexp_match(result, '^(\d+) of'))[1]::int) filter (where row_type = 'Category result'), 0) as points_raw,
    coalesce(sum((regexp_match(result, 'of (\d+) points'))[1]::int) filter (where row_type = 'Category result'), 0) as points_available
  from public.audit_rows
  group by audit_id
), s as (
  select
    a.audit_id, a.firm_id, f.name as firm, a.query_id, a.query, a.town_zip, a.checked_at, a.checked_at_text,
    a.vendor, a.product, a.audit_role, a.spec_version,
    r.rows_total, r.category_rows, r.item_rows, r.ranking_rows, r.points_available,
    (r.rows_total = 36 and r.category_rows = 7 and r.item_rows = 21 and r.ranking_rows = 8) as reconciles,
    case
      when coalesce(a.f_reason, '') <> '' then 'F'
      when a.unverified or a.website_unreadable then 'unverified'
      else 'eligible'
    end as access_status,
    a.f_reason, a.unverified_reason,
    r.points_raw, r.passed_items_raw, r.failed_items_raw
  from public.audits a
  join public.firms f using (firm_id)
  join r using (audit_id)
)
select
  audit_id, firm_id, firm, query_id, query, town_zip, checked_at, checked_at_text, vendor, product, audit_role, spec_version,
  access_status, f_reason, unverified_reason,
  case when access_status = 'eligible' then points_raw else 0 end        as total_points,
  case when access_status = 'eligible' then passed_items_raw else 0 end  as passed_items,
  case when access_status = 'eligible' then failed_items_raw else 0 end  as high_issues,
  case
    when access_status = 'F' then 'F'
    when access_status = 'unverified' then null
    when points_raw >= 65 then 'A'
    when points_raw >= 50 then 'B'
    when points_raw >= 30 then 'C'
    else 'D'
  end as grade,
  -- Eligible rank within the same query, town/ZIP and audit role: total points, then fewest High issues.
  -- Spec §8 tie-break 3 (original ranking in the reviewed set) is not stored yet, so ties share a rank.
  case when access_status = 'eligible' then
    rank() over (partition by query_id, town_zip, audit_role, (access_status = 'eligible')
                 order by points_raw desc, failed_items_raw asc)
  end as eligible_rank,
  case when access_status = 'eligible' then
    count(*) over (partition by query_id, town_zip, audit_role, (access_status = 'eligible'))
  end as eligible_count,
  points_available, rows_total, category_rows, item_rows, ranking_rows, reconciles
from s;
