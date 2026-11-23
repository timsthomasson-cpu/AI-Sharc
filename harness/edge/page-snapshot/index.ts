// page-snapshot: save a capped set of a firm's website pages to Storage.
// Body: { "firm_id": "...", "run_label": "..." }. The URL comes from firms.website_url,
// so the function can only fetch sites already on the central firm list.
// Auth: header x-snapshot-token must match the vault secret 'snapshot_token'.
// Rules (approved 2026-11-23): home + up to 24 more pages: first up to 2 per must-have category, then keyword and menu links
// (service area, install, repair, about, financing, insurance/warranty, estimate, contact, privacy, terms);
// robots.txt, sitemap(s) and llms.txt saved as files;
// sitemap URL list recorded, pages not fetched. robots.txt "User-agent: *" Disallow rules
// are respected; 401/403/429 are recorded as [BLOCKED] and not worked around.
// Same user agent, timeout and 1 s delay as the audit harness (fetchers.py); stops a site on 429/503.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SB = Deno.env.get("SUPABASE_URL")!;
const KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";
const TIMEOUT_MS = 20000, DELAY_MS = 1000, PAGE_CAP = 25, BUDGET_MS = 330000, SITEMAP_URL_CAP = 5000;
const KEYWORDS = /area|serve|serving|location|cities|city|install|replac|repair|about|financ|rebate|insur|warrant|guarantee|estimate|quote|contact|privacy|terms|policy|maintenance|service/i;
const MUST_HAVE: [string, RegExp][] = [
  ["service-area", /service[-_ ]?area|areas[-_ ]?(we[-_ ]?)?serve|where[-_ ]?we[-_ ]?serve|serving|locations?\b|cities/i],
  ["installation", /install|replac/i],
  ["repair", /repair/i],
  ["about", /about/i],
  ["financing", /financ|rebate|payment[-_ ]?plan/i],
  ["insurance-warranty", /insur|warrant|guarantee|licen[cs]/i],
  ["estimate", /estimate|quote/i],
  ["contact", /contact/i],
  ["privacy", /privacy/i],
  ["terms", /terms|conditions/i],
];
const SKIP_EXT =/\.(jpg|jpeg|png|gif|webp|svg|ico|pdf|zip|mp4|mp3|css|js|xml|json|woff2?|ttf)(\?|$)/i;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const hdr = { apikey: KEY, Authorization: `Bearer ${KEY}` };

async function rest(path: string, init: RequestInit = {}) {
  const r = await fetch(`${SB}/rest/v1/${path}`, { ...init, headers: { ...hdr, "Content-Type": "application/json", ...(init.headers || {}) } });
  if (!r.ok) throw new Error(`REST ${path} ${r.status} ${await r.text()}`);
  const t = await r.text();
  return t ? JSON.parse(t) : null;
}

async function sha256(buf: Uint8Array) {
  const d = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
async function gzip(buf: Uint8Array) {
  const s = new Blob([buf]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Uint8Array(await new Response(s).arrayBuffer());
}

type Got = { status: number | null; finalUrl: string | null; ctype: string | null; body: Uint8Array | null; reason: string | null };
async function get(url: string): Promise<Got> {
  try {
    const r = await fetch(url, { headers: { "User-Agent": UA }, redirect: "follow", signal: AbortSignal.timeout(TIMEOUT_MS) });
    const body = new Uint8Array(await r.arrayBuffer());
    let reason: string | null = null;
    if ([401, 403, 429].includes(r.status)) reason = `[BLOCKED] HTTP ${r.status}; not worked around`;
    else if (r.status !== 200) reason = `HTTP ${r.status}`;
    return { status: r.status, finalUrl: r.url, ctype: r.headers.get("content-type"), body, reason };
  } catch (e) {
    const m = String(e);
    const code = /certificate|tls|ssl/i.test(m) ? "CERT-INVALID" : "DEAD";
    return { status: null, finalUrl: null, ctype: null, body: null, reason: `[${code}] ${m.slice(0, 300)}` };
  }
}

async function save(firm: string, run: string, url: string, role: string, because: string, g: Got) {
  const row: Record<string, unknown> = {
    firm_id: firm, run_label: run, requested_url: url, final_url: g.finalUrl, page_role: role,
    selected_because: because, http_status: g.status, content_type: g.ctype,
    bytes: g.body ? g.body.length : null, access_reason: g.reason,
  };
  if (g.body && g.body.length) {
    const h = await sha256(g.body);
    row.sha256 = h;
    const prior = await rest(`page_snapshots?requested_url=eq.${encodeURIComponent(url)}&sha256=eq.${h}&storage_path=not.is.null&select=storage_path&limit=1`);
    if (prior && prior.length) {
      row.storage_path = prior[0].storage_path; row.deduplicated = true;
    } else {
      const path = `${firm}/${h}.gz`;
      const up = await fetch(`${SB}/storage/v1/object/page-snapshots/${path}`, {
        method: "POST", headers: { ...hdr, "Content-Type": "application/gzip", "x-upsert": "true" }, body: await gzip(g.body),
      });
      if (up.ok) row.storage_path = path; else row.access_reason = `${row.access_reason ?? ""} [STORAGE ${up.status}]`.trim();
    }
  }
  await rest("page_snapshots", { method: "POST", body: JSON.stringify(row) });
}

const dec = new TextDecoder();
const hostOf = (u: string) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return ""; } };

function parseRobots(txt: string) {
  // Rules for "User-agent: *" only (Allow and Disallow), plus Sitemap lines.
  const dis: string[] = []; const allow: string[] = []; const maps: string[] = [];
  let star = false, inGroupAgents = false;
  for (const raw of txt.split(/\r?\n/)) {
    const line = raw.replace(/#.*/, "").trim();
    const m = line.match(/^([A-Za-z-]+)\s*:\s*(.*)$/); if (!m) continue;
    const k = m[1].toLowerCase(), v = m[2].trim();
    if (k === "user-agent") { star = inGroupAgents ? (star || v === "*") : v === "*"; inGroupAgents = true; continue; }
    inGroupAgents = false;
    if (k === "disallow" && star && v) dis.push(v);
    else if (k === "allow" && star && v) allow.push(v);
    else if (k === "sitemap" && v) maps.push(v);
  }
  return { dis, allow, maps };
}
// Google-style matching: * is a wildcard, $ anchors the end; the longest matching rule wins, Allow wins ties.
const rx = (p: string) => {
  const end = p.endsWith("$");
  const body = (end ? p.slice(0, -1) : p).replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*");
  return new RegExp("^" + body + (end ? "$" : ""));
};
const rxCache = new Map<string, RegExp>();
const rxc = (p: string) => { let r = rxCache.get(p); if (!r) { r = rx(p); rxCache.set(p, r); } return r; };
function allowed(u: string, r: { dis: string[]; allow: string[] }) {
  const url = new URL(u); const p = url.pathname + url.search;
  let best = -1, ok = true;
  for (const d of r.dis) if (d.length > best && rxc(d).test(p)) { best = d.length; ok = false; }
  for (const a of r.allow) if (a.length >= best && rxc(a).test(p)) { best = a.length; ok = true; }
  return ok;
}

function links(fullHtml: string, base: string) {
  // Parse at most the first 500 KB: page builders can emit multi-MB pages, and the edge
  // runtime stops a worker that uses too much CPU (seen 2026-11-23: "CPU Time exceeded").
  const html = fullHtml.length > 500000 ? fullHtml.slice(0, 500000) : fullHtml;
  const out: { url: string; text: string; menu: boolean }[] = [];
  const menuHtml = (html.match(/<(nav|header)\b[\s\S]*?<\/\1>/gi) || []).join(" ");
  const re = /<a\b[^>]*href\s*=\s*["']([^"'#]+)["'][^>]*>([\s\S]*?)<\/a>/gi;
  const seen = new Set<string>();
  for (const src of [menuHtml, html]) {
    let m;
    while ((m = re.exec(src))) {
      let u: string; try { u = new URL(m[1], base).href.split("#")[0]; } catch { continue; }
      if (!/^https?:/.test(u) || hostOf(u) !== hostOf(base) || SKIP_EXT.test(u) || seen.has(u)) continue;
      seen.add(u);
      out.push({ url: u, text: m[2].replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().slice(0, 120), menu: src === menuHtml });
    }
  }
  return out;
}

async function run(firm: string, start: string, runLabel: string) {
  const t0 = Date.now(); const over = () => Date.now() - t0 > BUDGET_MS;
  const base = new URL(start).origin;
  let truncated = false, rateLimited = false;
  // robots.txt
  const rob = await get(`${base}/robots.txt`); await save(firm, runLabel, `${base}/robots.txt`, "robots", "fixed file", rob); await sleep(DELAY_MS);
  const robots = rob.status === 200 && rob.body ? parseRobots(dec.decode(rob.body)) : { dis: [] as string[], allow: [] as string[], maps: [] as string[] };
  // sitemap list (URLs only)
  const smUrls: string[] = [];
  const smCands = robots.maps.length ? robots.maps.slice(0, 2) : [`${base}/sitemap.xml`];
  const queue = [...smCands]; let smFetched = 0;
  while (queue.length && smFetched < 6 && !over()) {
    const su = queue.shift()!; const g = await get(su); smFetched++;
    await save(firm, runLabel, su, "sitemap", "fixed file", g); await sleep(DELAY_MS);
    if (g.status !== 200 || !g.body) continue;
    const x = dec.decode(g.body);
    const locs = [...x.matchAll(/<loc>\s*([^<\s]+)\s*<\/loc>/gi)].map((m) => m[1]);
    if (/<sitemapindex/i.test(x)) queue.push(...locs.slice(0, 5)); else for (const l of locs) if (smUrls.length < SITEMAP_URL_CAP) smUrls.push(l);
  }
  // llms.txt
  const ll = await get(`${base}/llms.txt`); await save(firm, runLabel, `${base}/llms.txt`, "llms", "fixed file", ll); await sleep(DELAY_MS);
  // home page
  const home = await get(start); await save(firm, runLabel, start, "home", "start URL", home); await sleep(DELAY_MS);
  let found: { url: string; text: string; menu: boolean }[] = [];
  let selected = 1;
  if (home.status === 200 && home.body) {
    found = links(dec.decode(home.body), home.finalUrl || start);
    const startNorm = (home.finalUrl || start).replace(/\/$/, "");
    const homeHost = hostOf(home.finalUrl || start);
    // Sites that build their menu with JavaScript show few links in the HTML, so sitemap URLs
    // matching the keywords are also candidates (they come after home-page links).
    const foundSet = new Set(found.map((l) => l.url));
    // Only sitemap URLs that match a keyword are candidates; keeps CPU low on sites with thousands of URLs.
    const fromSitemap = smUrls.filter((u) => KEYWORDS.test(u) && hostOf(u) === homeHost && !SKIP_EXT.test(u) && !foundSet.has(u))
      .map((u) => ({ url: u, text: "", menu: false, sm: true }));
    const all = [...found.map((l) => ({ ...l, sm: false })), ...fromSitemap];
    const cand = all.filter((l) => l.url.replace(/\/$/, "") !== startNorm && allowed(l.url, robots));
    // 1) up to 2 pages for each must-have category (home links first, then shortest path);
    // 2) other keyword pages; 3) remaining menu links; 4) other keyword sitemap URLs.
    const order = (a: typeof cand[0], b: typeof cand[0]) => (Number(a.sm) - Number(b.sm)) || (a.url.length - b.url.length);
    const picked: { url: string; why: string }[] = []; const has = (u: string) => picked.some((p) => p.url === u);
    for (const [name, re] of MUST_HAVE) {
      for (const l of cand.filter((l) => re.test(l.url + " " + l.text)).sort(order).slice(0, 2))
        if (!has(l.url)) picked.push({ url: l.url, why: `${name} page` });
    }
    const kw = cand.filter((l) => KEYWORDS.test(l.url + " " + l.text) && !has(l.url));
    for (const l of kw.filter((l) => !l.sm)) if (!has(l.url)) picked.push({ url: l.url, why: "keyword link" });
    for (const l of cand.filter((l) => l.menu)) if (!has(l.url)) picked.push({ url: l.url, why: "menu link" });
    for (const l of kw.filter((l) => l.sm)) if (!has(l.url)) picked.push({ url: l.url, why: "keyword sitemap URL" });
    if (picked.length > PAGE_CAP - 1) truncated = true;
    const pick = picked.slice(0, PAGE_CAP - 1);
    for (const p of pick) {
      if (over()) { truncated = true; break; }
      const g = await get(p.url); await save(firm, runLabel, p.url, "selected", p.why, g); selected++;
      // A site that asks us to slow down (429) or is overloaded (503) is left alone for this run.
      if (g.status === 429 || g.status === 503) { truncated = true; rateLimited = true; break; }
      await sleep(DELAY_MS);
    }
  }
  await rest("site_inventories", { method: "POST", body: JSON.stringify({
    firm_id: firm, run_label: runLabel, start_url: start, robots_disallow: robots.dis,
    sitemap_url_count: smUrls.length, sitemap_urls: smUrls, home_links: found.map((l) => l.url),
    pages_selected: selected, truncated,
    note: [home.reason ? `home page: ${home.reason}` : "", allowed(start, robots) ? "" : "robots.txt disallows the whole site for User-agent: *; only the home page and fixed files were read", rateLimited ? "site returned 429/503; stopped early, re-fetch later" : ""].filter(Boolean).join("; ") || null,
  }) });
}

Deno.serve(async (req) => {
  const token = req.headers.get("x-snapshot-token") || "";
  const ok = await rest("rpc/snapshot_token_ok", { method: "POST", body: JSON.stringify({ t: token }) }).catch(() => false);
  if (ok !== true) return new Response("forbidden", { status: 403 });
  const { firm_id, run_label } = await req.json();
  const f = await rest(`firms?firm_id=eq.${encodeURIComponent(firm_id)}&select=website_url`);
  let start: string | undefined = f?.[0]?.website_url?.trim();
  // Some firm records store the site without a scheme (e.g. "example.com").
  if (start && !/^https?:\/\//i.test(start)) start = "https://" + start.replace(/^\/+/, "");
  if (!start) return new Response(JSON.stringify({ firm_id, error: "no website_url" }), { status: 404 });
  const startUrl: string = start;
  EdgeRuntime.waitUntil(run(firm_id, startUrl, run_label || "unlabelled").catch(async (e) => {
    await rest("site_inventories", { method: "POST", body: JSON.stringify({ firm_id, run_label, start_url: startUrl, note: `run failed: ${String(e).slice(0, 500)}` }) }).catch(() => {});
  }));
  return new Response(JSON.stringify({ firm_id, started: start }), { status: 202, headers: { "Content-Type": "application/json" } });
});
