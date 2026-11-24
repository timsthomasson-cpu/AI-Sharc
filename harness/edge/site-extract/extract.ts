// Pure extraction logic for site-extract (no I/O), so it can be tested on its own.
// Rule-based: every fact keeps the wording and the page URL it came from.

export type Page = { url: string; why: string; role: string; html: string };
export type Kinds = Record<string, string[]>; // name_norm -> ["city","common","alias","county"]

export const VERSION = "rules-2026-11-24a";

const SA_URL = /service[-_]?areas?|areas?[-_]?(we[-_]?)?serv|where[-_]?we[-_]?serve|locations?|cities|communities|coverage/i;
const TRIGGER = /\b(serv(?:e|es|ed|ing)|service areas?|areas? (?:we )?serv\w*|proudly|communities|nearby|surrounding|throughout|in and around|locations?)\b/gi;
const UNNAMED = /\b(?:and (?:many )?more|surrounding (?:areas|communities|cities|towns)|nearby (?:areas|communities|cities|towns)|and beyond|neighboring (?:areas|communities|cities)|greater [A-Z][a-z]+(?: [A-Z][a-z]+)? area|metro(?:politan)? area|\+\s?\d+ more)\b/;

// Place names that are also everyday words or HVAC words: only counted when written as "<name>, TX" / "<name>, Texas".
const STOP_ALWAYS = new Set(["comfort", "center", "mission", "commerce", "west", "early", "earth", "van", "sunset", "cool", "energy",
  "frost", "post", "rule", "hart", "wells", "troy", "nash", "paris", "miami", "garden", "industry", "price", "quail", "wink", "normal",
  "venus", "lone star", "texas", "tx", "star", "lake", "bend", "point", "como", "nevada", "detroit", "loop", "carbon", "buffalo",
  "ace", "royal", "meadow", "china", "blue", "berry", "concord", "smiley", "alamo", "reno", "tioga", "progreso"]);
// Person-like or ambiguous names: counted on service-area pages, and in phrase windows only inside a list ("..., Kyle, ...").
const STOP_PERSON = new Set(["allen", "tyler", "bryan", "kyle", "marion", "morgan", "lucas", "gary", "nolan", "wilson", "hunt", "hughes",
  "travis", "hamilton", "lamar", "crockett", "bowie", "joshua", "franklin", "madison", "lincoln", "jackson", "washington", "jefferson",
  "henderson", "lancaster", "hawkins", "goodrich", "liberty", "orange", "temple", "cleveland", "atlanta", "trinity", "converse",
  "sanger", "elgin", "hereford", "sweeny", "kingsland", "ivanhoe", "carthage", "mabank", "victoria"]);

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const clip = (s: string, n = 240) => s.replace(/\s+/g, " ").trim().slice(0, n);
// The wording around a match, kept inside its own line (paragraph / list item).
function around(text: string, idx: number, len: number) {
  const ls = text.lastIndexOf("\n", idx) + 1; let le = text.indexOf("\n", idx + len); if (le < 0) le = text.length;
  return clip(text.slice(Math.max(ls, idx - 110), Math.min(le, idx + len + 110)));
}

export function htmlToText(htmlIn: string) {
  const html = htmlIn.length > 900000 ? htmlIn.slice(0, 900000) : htmlIn;
  const ld = [...html.matchAll(/<script[^>]*application\/ld\+json[^>]*>([\s\S]*?)<\/script>/gi)].map((m) => m[1]);
  let t = html.replace(/<(script|style|noscript|svg|template|iframe)\b[\s\S]*?<\/\1>/gi, " ")
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<br\s*\/?>|<\/(p|div|li|h[1-6]|tr|td|th|section|ul|ol|header|footer|nav|article|option)>/gi, "\n")
    .replace(/<[^>]+>/g, " ");
  t = t.replace(/&nbsp;|&#160;/g, " ").replace(/&amp;/g, "&").replace(/&#0?39;|&rsquo;|&lsquo;|&#8217;|&#x27;/g, "'")
    .replace(/&quot;|&ldquo;|&rdquo;|&#8220;|&#8221;/g, '"').replace(/&ndash;|&mdash;|&#8211;|&#8212;/g, "-")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&#\d+;|&[a-z]+;/gi, " ");
  t = t.replace(/[ \t\r\f\v]+/g, " ").replace(/\n\s*/g, "\n").replace(/\u0000/g, "");
  return { text: t, ld };
}

function* ldNodes(x: unknown): Generator<Record<string, unknown>> {
  if (Array.isArray(x)) { for (const y of x) yield* ldNodes(y); return; }
  if (x && typeof x === "object") {
    const o = x as Record<string, unknown>;
    yield o;
    for (const v of Object.values(o)) if (v && typeof v === "object") yield* ldNodes(v);
  }
}
function parseLd(blocks: string[]) {
  const out: Record<string, unknown>[] = [];
  for (const b of blocks) { try { for (const n of ldNodes(JSON.parse(b.trim()))) out.push(n); } catch { /* bad JSON-LD */ } }
  return out;
}

type Hit = { name: string; norm: string; url: string; how: string };

// Find place names in a piece of text: runs of Capitalised (or ALL CAPS) words, longest match first.
function findPlaces(text: string, kinds: Kinds, url: string, how: string, strict: boolean, places: Hit[], counties: Hit[]) {
  const RUN = /[A-Z][A-Za-z'.]*(?:[ -](?:[A-Z][A-Za-z'.]*|of|de|la|del))*/g;
  let m: RegExpExecArray | null;
  while ((m = RUN.exec(text))) {
    const words = m[0].split(/[ -]+/).filter(Boolean);
    const after = text.slice(m.index + m[0].length, m.index + m[0].length + 12);
    const before = text.slice(Math.max(0, m.index - 3), m.index);
    let i = 0;
    while (i < words.length) {
      let took = 0;
      for (let L = Math.min(4, words.length - i); L >= 1; L--) {
        const raw = words.slice(i, i + L).join(" ").replace(/[.']+$/, "");
        const n = norm(raw);
        const k = kinds[n];
        if (!k || n.length < 3) continue;
        const isLast = i + L === words.length;
        const nextWord = words[i + L];
        // "<X> County"
        if (nextWord && /^county$/i.test(nextWord) && k.includes("county")) {
          counties.push({ name: raw + " County", norm: n, url, how }); took = L + 1; break;
        }
        const placeKinds = k.filter((x) => x !== "county");
        if (!placeKinds.length) {
          if (L >= 2) { counties.push({ name: raw, norm: n, url, how }); took = L; break; }
          continue;
        }
        const txAfter = isLast && /^\s*,?\s*(TX|Texas)\b/.test(after);
        if (!txAfter && STOP_ALWAYS.has(n)) continue;
        if (!txAfter && STOP_PERSON.has(n) && strict) {
          // in phrase windows a person-like name counts only inside a list ("..., Kyle, ...")
          const listy = (i > 0 ? false : /[,|•\n]\s*$/.test(before)) || (isLast && /^\s*[,|•\n]/.test(after));
          if (!listy) continue;
        }
        places.push({ name: raw, norm: n, url, how }); took = L; break;
      }
      i += took || 1;
    }
  }
}

function slugPlaces(u: string, kinds: Kinds, places: Hit[]) {
  let path: string; try { path = new URL(u).pathname.toLowerCase(); } catch { return; }
  const segs = path.split("/").filter(Boolean);
  for (let s = 0; s < segs.length; s++) {
    const seg = segs[s];
    const parentSA = s > 0 && SA_URL.test(segs[s - 1]);
    const tx = seg.match(/^(?:.*?-)?([a-z]+(?:-[a-z]+){0,2})-(?:tx|texas)$/);
    const words = (tx ? tx[1] : parentSA ? seg : "").split("-").filter(Boolean);
    if (!words.length) continue;
    for (let L = Math.min(3, words.length); L >= 1; L--) {
      const n = words.slice(words.length - L).join(" ");
      if (kinds[n] && kinds[n].some((k) => k !== "county") && !STOP_ALWAYS.has(n)) {
        places.push({ name: n.replace(/\b\w/g, (c) => c.toUpperCase()), norm: n, url: u, how: "url slug" }); break;
      }
    }
  }
}

const ADDR = /(\d{1,6}[A-Za-z]?\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.'\- ]{2,50}?\b(?:St|Street|Rd|Road|Dr|Drive|Ave|Avenue|Blvd|Boulevard|Ln|Lane|Pkwy|Parkway|Fwy|Freeway|Hwy|Highway|Way|Ct|Court|Cir|Circle|Trl|Trail|Loop|Pl|Place|Expy|Expressway|Plaza|Tollway|Pike|Pass|Row|Bend|Crossing|Xing|Sq|Square)\.?(?:\s+(?:N|S|E|W|North|South|East|West)\b)?(?:,?\s*(?:Suite|Ste\.?|Unit|Bldg|Building|#)\s*[\w-]+)?)\s*,?\s+([A-Z][A-Za-z .'-]{2,30}?),?\s+(?:TX|Texas)\.?,?\s+(7[5-9]\d{3})(?:-\d{4})?\b/g;

const RX = {
  insurance: /\b(?:licensed|bonded)[ ,]*(?:and|&)?[ ,]*(?:bonded[ ,]*(?:and|&)?[ ,]*)?insured\b|\bfully insured\b|\binsured\b[ ,]*(?:and|&)[ ,]*(?:licensed|bonded)\b|\bliability insurance\b|\bworkers'? comp(?:ensation)?\b/i,
  epa: /\bEPA\b[^.\n]{0,60}\b(?:certif\w*|608|licensed)\b|\b(?:certif\w*|608)\b[^.\n]{0,40}\bEPA\b|\bSection 608\b/i,
  financing: /\bfinanc(?:e|ing)(?! (?:company|charge|department))\b|\bpayment plans?\b|\bmonthly payments?\b|\b(?:Synchrony|GreenSky|Service Finance|FTL Finance|Wells Fargo Home Projects|Hearth|EnerBank|Foundation Finance|Acima|Affirm)\b/i,
  rebates: /\brebates?\b|\btax credits?\b|\b25C\b|Inflation Reduction Act|\butility incentives?\b|\bincentive programs?\b/i,
  freeEstimate: /\bfree\b[^.\n]{0,25}\b(?:estimates?|quotes?|consultations?|in-home (?:estimates?|assessments?)|second opinions?)\b|\bno[- ]cost (?:estimates?|quotes?)\b/i,
};
const INCL = {
  permits: /\bpermits?\b/i,
  old_unit_removal: /\b(?:remov\w*|haul\w*(?: away)?|dispos\w*)\b[^.\n]{0,40}\b(?:old|existing)\b[^.\n]{0,15}\b(?:unit|system|equipment)s?\b|\b(?:old|existing) (?:unit|system|equipment)s?\b[^.\n]{0,30}\b(?:remov\w*|haul\w*|dispos\w*)\b/i,
  thermostat: /\bthermostats?\b/i,
  ductwork: /\bduct(?:work|s)?\b/i,
};

const PAGE_ORDER = (p: Page) => /about/.test(p.why) ? 0 : p.role === "home" ? 1 : /contact/.test(p.why) ? 2 : 3;

export function extract(pages: Page[], kinds: Kinds, inventory: { sitemap_urls?: string[]; home_links?: string[] } | null) {
  const places: Hit[] = []; const counties: Hit[] = []; const zips = new Set<string>();
  let unnamed: string | null = null; let saUrl: string | null = null;
  const texts = pages.map((p) => ({ p, ...htmlToText(p.html) }));
  const addrCount = new Map<string, { street: string; city: string; zip: string; url: string; src: string; n: number }>();
  const first: Record<string, { wording: string; url: string } | undefined> = {};
  const incl: Record<string, { wording: string; url: string }> = {};
  const lic = new Set<string>();

  for (const { p, text, ld } of texts.sort((a, b) => PAGE_ORDER(a.p) - PAGE_ORDER(b.p))) {
    let path = ""; try { path = new URL(p.url).pathname; } catch { /* keep "" */ }
    const isSA = /service-area/.test(p.why) || SA_URL.test(path);
    // service area
    if (isSA) {
      findPlaces(text, kinds, p.url, "service-area page", false, places, counties);
      for (const z of text.match(/\b7[5-9]\d{3}\b/g) || []) zips.add(z);
      const u = text.match(UNNAMED); if (u && !unnamed) unnamed = around(text, u.index ?? 0, u[0].length);
      if (!saUrl) saUrl = p.url;
    } else {
      TRIGGER.lastIndex = 0; let t: RegExpExecArray | null; let lastEnd = -1;
      while ((t = TRIGGER.exec(text))) {
        if (t.index < lastEnd) continue;
        const win = text.slice(t.index, t.index + 500); lastEnd = t.index + 500;
        findPlaces(win, kinds, p.url, "phrase window", true, places, counties);
        for (const z of win.match(/\b7[5-9]\d{3}\b/g) || []) if (/zip/i.test(win)) zips.add(z);
        const u = win.match(UNNAMED); if (u && !unnamed) unnamed = around(win, u.index ?? 0, u[0].length);
      }
    }
    // JSON-LD: areaServed and address
    for (const n of parseLd(ld)) {
      const as = n["areaServed"];
      for (const a of (Array.isArray(as) ? as : as ? [as] : [])) {
        const nm = typeof a === "string" ? a : (a as Record<string, unknown>)?.name;
        if (typeof nm === "string") findPlaces(nm.replace(/\b\w/g, (c) => c.toUpperCase()), kinds, p.url, "json-ld", false, places, counties);
      }
      const ad = n["address"] as Record<string, unknown> | undefined;
      if (ad && typeof ad === "object" && typeof ad["streetAddress"] === "string" && /^7[5-9]\d{3}/.test(String(ad["postalCode"] ?? ""))) {
        const key = `${ad["streetAddress"]}|${ad["postalCode"]}`;
        const e = addrCount.get(key) || { street: String(ad["streetAddress"]), city: String(ad["addressLocality"] ?? ""), zip: String(ad["postalCode"]).slice(0, 5), url: p.url, src: "json-ld", n: 0 };
        e.n += 3; addrCount.set(key, e);
      }
    }
    // address in text
    ADDR.lastIndex = 0; let a: RegExpExecArray | null;
    while ((a = ADDR.exec(text))) {
      const street = clip(a[1], 120), city = clip(a[2], 40), zip = a[3];
      const key = `${norm(street)}|${zip}`;
      const e = addrCount.get(key) || { street, city, zip, url: p.url, src: "page text", n: 0 };
      e.n += 1; addrCount.set(key, e);
    }
    // advice facts: first page (about > home > contact > others) that states it
    for (const [k, rx] of Object.entries(RX)) {
      if (first[k]) continue;
      const m = text.match(rx);
      if (m) first[k] = { wording: around(text, m.index ?? 0, m[0].length), url: p.url };
    }
    for (const m of text.matchAll(/\bTACL\s*-?\s*([AB])?\s*[-#:]?\s*(0*\d{3,8})\s*([CE])?\b/gi))
      lic.add(`TACL${(m[1] || "").toUpperCase()}${m[2]}${(m[3] || "").toUpperCase()}`);
    // what an installation estimate includes: sentences on install / estimate / home pages that say "includes" or "covers"
    if (/install|estimate|replac|financ/.test(p.why) || p.role === "home" || /install|replac|estimate|quote/i.test(p.url)) {
      for (const s of text.split(/(?<=[.!?])\s+|\n/)) {
        if (s.length > 600 || !/\b(?:includ\w*|cover\w*|comes? with|we (?:handle|take care of))\b/i.test(s)) continue;
        if (!/\b(?:install\w*|estimate|quote|replac\w*|new (?:system|unit))\b/i.test(s)) continue;
        for (const [k, rx] of Object.entries(INCL)) if (!incl[k] && rx.test(s)) incl[k] = { wording: clip(s), url: p.url };
      }
    }
  }
  for (const u of [...(inventory?.home_links || []), ...(inventory?.sitemap_urls || [])].slice(0, 6000)) slugPlaces(u, kinds, places);

  const dedupe = (h: Hit[]) => { const s = new Map<string, Hit>(); for (const x of h) if (!s.has(x.norm)) s.set(x.norm, x); return [...s.values()]; };
  const best = [...addrCount.values()].sort((x, y) => y.n - x.n)[0];
  return {
    sa_places: dedupe(places), sa_counties: dedupe(counties), sa_zips_explicit: [...zips].sort(),
    sa_unnamed_extra: !!unnamed, sa_unnamed_wording: unnamed, sa_source_url: saUrl,
    address_street: best?.street ?? null, address_city: best?.city ?? null, address_zip: best?.zip ?? null,
    address_source: best?.src ?? null, address_url: best?.url ?? null,
    insurance_stated: !!first.insurance, insurance_wording: first.insurance?.wording ?? null, insurance_url: first.insurance?.url ?? null,
    epa_stated: !!first.epa, epa_wording: first.epa?.wording ?? null, epa_url: first.epa?.url ?? null,
    tacl_licences: [...lic],
    financing_stated: !!first.financing, financing_wording: first.financing?.wording ?? null, financing_url: first.financing?.url ?? null,
    rebates_stated: !!first.rebates, rebates_wording: first.rebates?.wording ?? null, rebates_url: first.rebates?.url ?? null,
    free_estimate_stated: !!first.freeEstimate, free_estimate_wording: first.freeEstimate?.wording ?? null, free_estimate_url: first.freeEstimate?.url ?? null,
    estimate_includes: incl,
  };
}
