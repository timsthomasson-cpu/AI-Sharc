-- 2026-11-21: central firm list (Field Mapping Rev 11–13; Spec v2.10–v2.12 §13).
-- Record of the changes applied to the test database (Test AI Sharc Orchestrator) on 2026-11-21 as migrations
-- central_firm_list_rev11 and firms_verification_status, plus the reference schema. Not yet applied to East.
-- The data loads (1,337 list firms, 6 enriched, 18,949 TDLR licences) were one-off loads and are not repeated here.

alter table public.firms drop constraint if exists firms_name_key;

alter table public.firms
  add column db_firm_id integer,
  add column address text,
  add column unique_primary_phone text,
  add column notes text,
  add column town text,
  add column county text,
  add column town_zip text,
  add column firm_zip text,
  add column discovery_source text,
  add column discovery_note text,
  add column query text,
  add column service_area_zips jsonb not null default '[]'::jsonb,
  add column service_area_towns jsonb not null default '[]'::jsonb,
  add column service_area_source text default 'not_checked'
    check (service_area_source in ('website service-area page','Google Business Profile','Meta place','social claim','not_checked')),
  add column merged_from jsonb not null default '[]'::jsonb,
  add column licence_number text,
  add column licence_type text,
  add column licence_expiration_date date,
  add column service_area_source_url text,
  add column service_area_checked_at date,
  add column normalised_name text,
  add column first_seen_date date,
  add column last_checked_date date,
  add column google_business_profile_url text,
  add column facebook_page_url text,
  add column yelp_url text,
  add column bbb_url text,
  add column firm_status text check (firm_status in ('in business','not in business'));

create unique index firms_db_firm_id_key on public.firms (db_firm_id) where db_firm_id is not null;
create index firms_meta_place_id_idx on public.firms (meta_place_id);
create index firms_town_zip_idx on public.firms (town_zip);

create table public.firm_review_queue (
  review_id bigint generated always as identity primary key,
  firm_id text references public.firms(firm_id),
  candidate_firm_id text references public.firms(firm_id),
  source text not null,
  source_record jsonb,
  reason text not null check (reason in ('name-only match','conflict on phone','conflict on website','conflict on licence',
                                         'conflict on place ID','no location','rung 3 match, name and phone differ')),
  rung_tried text,
  values_seen jsonb,
  status text not null default 'open' check (status in ('open','resolved')),
  resolution text check (resolution in ('merged','separate firms','linked','not linked','dropped')),
  resolved_by text,
  resolved_at timestamptz,
  note text,
  created_at timestamptz not null default now()
);
alter table public.firm_review_queue enable row level security;

-- Verification status (Spec v2.11 §13): verified = a Meta place ID or a website, either one is enough.
alter table public.firms add column verification_status text check (verification_status in ('verified','unverified'));
update public.firms set verification_status = case when meta_place_id is not null or website_url is not null then 'verified' else 'unverified' end;
alter table public.firms alter column verification_status set not null;
create unique index firms_licence_key on public.firms (licence_type, licence_number) where licence_number is not null;

-- Licence reference list (Spec v2.12 §13): kept separately from the central firm list.
create schema if not exists reference;
comment on schema reference is 'Reference data kept for future use; not part of the central firm list (Tim, 2026-11-21).';
create table reference.tdlr_ac_contractors (
  record_id text primary key,
  name text,
  county text,
  licence_type text,
  licence_number text,
  licence_expiration_date date,
  notes text,
  source text,
  loaded_at timestamptz
);
create unique index on reference.tdlr_ac_contractors (licence_type, licence_number);
create table reference.tdlr_name_matches (
  original_review_id bigint,
  record_id text,
  candidate_id text,
  candidate_kind text,
  values_seen jsonb,
  note text,
  created_at timestamptz
);
alter table reference.tdlr_ac_contractors enable row level security;
alter table reference.tdlr_name_matches enable row level security;
