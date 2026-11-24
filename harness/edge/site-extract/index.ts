// site-extract: pull service area, address, insurance/EPA, financing/rebates and estimate details
// out of a firm's saved website pages (page-snapshot) and write one site_extractions row.
// Body: { "firm_id": "...", "run_label": "..." }. Auth: header x-snapshot-token (vault secret 'snapshot_token').
// Reads only what page-snapshot saved; fetches nothing from the firm's website.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { extract, VERSION, type Kinds, type Page } from "./extract.ts";

const SB = Deno.env.get("SUPABASE_URL")!;
const KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const hdr = { apikey: KEY, Authorization: `Bearer ${KEY}` };

async function rest(path: string, init: RequestInit = {}) {
  const r = await fetch(`${SB}/rest/v1/${path}`, { ...init, headers: { ...hdr, "Content-Type": "application/json", ...(init.headers || {}) } });
  if (!r.ok) throw new Error(`REST ${path.slice(0, 60)} ${r.status} ${(await r.text()).slice(0, 300)}`);
  const t = await r.text();
  return t ? JSON.parse(t) : null;
}

let kindsCache: Kinds | null = null;
async function kinds(): Promise<Kinds> {
  if (!kindsCache) kindsCache = await rest("rpc/place_name_kinds", { method: "POST", body: "{}" });
  return kindsCache!;
}

async function download(path: string): Promise<string | null> {
  const r = await fetch(`${SB}/storage/v1/object/page-snapshots/${path}`, { headers: hdr });
  if (!r.ok || !r.body) return null;
  const raw = await new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
  return new TextDecoder("utf-8", { fatal: false }).decode(raw);
}

async function run(firm: string, runLabel: string) {
  const rows: { requested_url: string; selected_because: string; page_role: string; storage_path: string; fetched_at: string }[] =
    await rest(`page_snapshots?firm_id=eq.${encodeURIComponent(firm)}&page_role=in.(home,selected)&http_status=eq.200&storage_path=not.is.null` +
      `&select=requested_url,selected_because,page_role,storage_path,fetched_at&order=fetched_at.desc&limit=200`);
  const latest = new Map<string, typeof rows[0]>();
  for (const r of rows) if (!latest.has(r.requested_url)) latest.set(r.requested_url, r); // newest copy of each URL
  const inv = (await rest(`site_inventories?firm_id=eq.${encodeURIComponent(firm)}&sitemap_urls=not.is.null&select=sitemap_urls,home_links&order=fetched_at.desc&limit=1`))?.[0] ?? null;

  const pages: Page[] = []; let failed = 0;
  const list = [...latest.values()].slice(0, 40);
  for (let i = 0; i < list.length; i += 6) {
    const got = await Promise.all(list.slice(i, i + 6).map(async (r) => ({ r, html: await download(r.storage_path).catch(() => null) })));
    for (const { r, html } of got) {
      if (html == null) { failed++; continue; }
      pages.push({ url: r.requested_url, why: r.selected_because || "", role: r.page_role, html });
    }
  }
  const out = pages.length ? extract(pages, await kinds(), inv) : null;
  const row = {
    firm_id: firm, run_label: runLabel, extractor_version: VERSION, pages_read: pages.length, pages_failed: failed,
    ...(out || {}), note: pages.length ? null : "no saved pages with HTTP 200",
  };
  await rest("site_extractions", { method: "POST", body: JSON.stringify(row).replace(/\\u0000/g, "") });
}

Deno.serve(async (req) => {
  const token = req.headers.get("x-snapshot-token") || "";
  const ok = await rest("rpc/snapshot_token_ok", { method: "POST", body: JSON.stringify({ t: token }) }).catch(() => false);
  if (ok !== true) return new Response("forbidden", { status: 403 });
  const { firm_id, run_label } = await req.json();
  const label = run_label || "unlabelled";
  EdgeRuntime.waitUntil(run(firm_id, label).catch(async (e) => {
    await rest("site_extractions", { method: "POST", body: JSON.stringify({ firm_id, run_label: label, extractor_version: VERSION, note: `run failed: ${String(e).slice(0, 500)}` }) }).catch(() => {});
  }));
  return new Response(JSON.stringify({ firm_id, started: true }), { status: 202, headers: { "Content-Type": "application/json" } });
});
