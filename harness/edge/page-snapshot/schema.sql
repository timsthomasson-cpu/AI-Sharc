-- Database objects used by the page-snapshot edge function.
-- Applied to the test project (Test - AI Sharc Orchestrator) on 2026-11-23 as migrations
-- page_snapshots_storage, snapshot_queue_and_dispatcher and snapshot_dispatch_priority_fix.
-- Not yet applied to AI Sharc Orchestrator East. Replace the function URL below when you do.

create extension if not exists pg_net;
create extension if not exists pg_cron;

insert into storage.buckets (id, name, public) values ('page-snapshots', 'page-snapshots', false)
on conflict (id) do nothing;

create table if not exists public.page_snapshots (
  snapshot_id bigserial primary key,
  firm_id text not null references public.firms(firm_id),
  run_label text not null,
  requested_url text not null,
  final_url text,
  page_role text not null,            -- home | selected | robots | sitemap | llms
  selected_because text,              -- must-have category / keyword / menu link / fixed file
  fetched_at timestamptz not null default now(),
  method text not null default 'direct fetch',
  http_status integer,
  content_type text,
  bytes integer,
  sha256 text,
  storage_path text,                  -- gzip file in bucket page-snapshots
  deduplicated boolean not null default false,
  access_reason text                  -- Spec 4.1.1 code when not readable, e.g. [BLOCKED]
);
create index if not exists page_snapshots_firm_idx on public.page_snapshots (firm_id, fetched_at);
create index if not exists page_snapshots_url_hash_idx on public.page_snapshots (requested_url, sha256);
alter table public.page_snapshots enable row level security;

create table if not exists public.site_inventories (
  inventory_id bigserial primary key,
  firm_id text not null references public.firms(firm_id),
  run_label text not null,
  fetched_at timestamptz not null default now(),
  start_url text,
  robots_disallow jsonb,
  sitemap_url_count integer,
  sitemap_urls jsonb,                 -- URL list only; pages not fetched
  home_links jsonb,
  pages_selected integer,
  truncated boolean default false,
  note text
);
alter table public.site_inventories enable row level security;

-- Shared token so only our own database calls can run the function.
select vault.create_secret(encode(extensions.gen_random_bytes(32), 'hex'), 'snapshot_token', 'Token for the page-snapshot edge function')
where not exists (select 1 from vault.secrets where name = 'snapshot_token');

create or replace function public.snapshot_token_ok(t text) returns boolean
language sql security definer set search_path = '' as $$
  select exists (select 1 from vault.decrypted_secrets where name = 'snapshot_token' and decrypted_secret = t);
$$;
revoke all on function public.snapshot_token_ok(text) from public, anon, authenticated;
grant execute on function public.snapshot_token_ok(text) to service_role;

create table if not exists public.snapshot_queue (
  firm_id text not null references public.firms(firm_id),
  run_label text not null,
  host text not null,
  priority integer not null default 100,
  status text not null default 'pending' check (status in ('pending','dispatched','done','failed')),
  attempts integer not null default 0,
  dispatched_at timestamptz,
  done_at timestamptz,
  primary key (firm_id, run_label)
);
create index if not exists snapshot_queue_status_idx on public.snapshot_queue (run_label, status, priority);
alter table public.snapshot_queue enable row level security;

-- Sends up to p_batch firms to the function, never two firms on the same host at once.
create or replace function public.dispatch_snapshots(p_run text, p_batch integer default 15)
returns integer language plpgsql security definer set search_path = public, extensions as $$
declare n integer := 0; r record; tok text;
begin
  update snapshot_queue q set status = 'done', done_at = now()
  where q.run_label = p_run and q.status = 'dispatched'
    and exists (select 1 from site_inventories i where i.firm_id = q.firm_id and i.run_label = p_run and i.fetched_at >= q.dispatched_at);
  update snapshot_queue q set status = case when attempts >= 2 then 'failed' else 'pending' end
  where q.run_label = p_run and q.status = 'dispatched' and q.dispatched_at < now() - interval '12 minutes';

  select decrypted_secret into tok from vault.decrypted_secrets where name = 'snapshot_token';
  for r in
    select x.firm_id from (
      select distinct on (q.host) q.firm_id, q.host, q.priority
      from snapshot_queue q
      where q.run_label = p_run and q.status = 'pending'
        and not exists (select 1 from snapshot_queue b where b.run_label = p_run and b.host = q.host and b.status = 'dispatched')
      order by q.host, q.priority, q.firm_id) x
    order by x.priority, random()
    limit p_batch
  loop
    perform net.http_post(
      url := 'https://tofderewwzhwnxkrhgig.supabase.co/functions/v1/page-snapshot',
      headers := jsonb_build_object('content-type','application/json','x-snapshot-token', tok),
      body := jsonb_build_object('firm_id', r.firm_id, 'run_label', p_run),
      timeout_milliseconds := 20000);
    update snapshot_queue set status = 'dispatched', dispatched_at = now(), attempts = attempts + 1
      where firm_id = r.firm_id and run_label = p_run;
    n := n + 1;
  end loop;
  return n;
end $$;
revoke all on function public.dispatch_snapshots(text, integer) from public, anon, authenticated;

-- Example: queue a run and schedule it (10 firms a minute; the job unschedules itself when done).
-- insert into snapshot_queue (firm_id, run_label, host)
-- select firm_id, 'full-2026-11-23', lower(regexp_replace(regexp_replace(website_url, '^https?://(www\.)?', ''), '[/?#].*$', ''))
-- from firms where website_url is not null and coalesce(firm_status, '') <> 'permanently closed';
-- select cron.schedule('snapshot-full-2026-11-23', '* * * * *', $$
--   select case when exists (select 1 from public.snapshot_queue where run_label = 'full-2026-11-23' and status in ('pending','dispatched'))
--     then public.dispatch_snapshots('full-2026-11-23', 10)
--     else (select 0 from cron.unschedule('snapshot-full-2026-11-23')) end; $$);
