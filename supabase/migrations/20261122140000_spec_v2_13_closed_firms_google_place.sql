-- Spec v2.13 / Field Mapping Rev 14 (approved by Tim 2026-11-22). Test database first.
-- 1. firms.google_place_id: rung 1 of the matching ladder with meta_place_id; makes a firm verified.
alter table public.firms add column if not exists google_place_id text;
create unique index if not exists firms_google_place_id_key on public.firms (google_place_id) where google_place_id is not null;

-- 2. firm_status: in business / temporarily closed / permanently closed (was in business / not in business).
update public.firms set firm_status = 'permanently closed' where firm_status = 'not in business';
alter table public.firms drop constraint if exists firms_firm_status_check;
alter table public.firms add constraint firms_firm_status_check
  check (firm_status in ('in business', 'temporarily closed', 'permanently closed'));

-- 3. Review-queue reasons for Google place matching and closure conflicts.
alter table public.firm_review_queue drop constraint if exists firm_review_queue_reason_check;
alter table public.firm_review_queue add constraint firm_review_queue_reason_check
  check (reason in ('name-only match', 'conflict on phone', 'conflict on website', 'conflict on licence',
                    'conflict on place ID', 'no location', 'rung 3 match, name and phone differ',
                    'several Google place matches', 'conflict on closed status'));

-- 4. Verification follows the rule whatever writes the row: verified as soon as a Meta place ID,
--    Google place ID or own website is recorded (Spec v2.13 §13). An own website excludes shared hosts,
--    which the loaders already leave out of website_url for agent-named firms.
create or replace function public.firms_set_verification() returns trigger
language plpgsql set search_path = public as $$
begin
  if new.meta_place_id is not null or new.google_place_id is not null or new.website_url is not null then
    new.verification_status := 'verified';
  elsif new.verification_status is null then
    new.verification_status := 'unverified';
  end if;
  return new;
end $$;
drop trigger if exists firms_set_verification on public.firms;
create trigger firms_set_verification before insert or update of meta_place_id, google_place_id, website_url, verification_status
  on public.firms for each row execute function public.firms_set_verification();
