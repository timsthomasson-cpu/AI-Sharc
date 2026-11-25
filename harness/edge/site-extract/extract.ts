// Pure extraction logic for site-extract (no I/O), so it can be tested on its own.
// Rule-based: every fact keeps the wording and the page URL it came from.

export type Page = { url: string; why: string; role: string; html: string };
export type Kinds = Record<string, string[]>; // name_norm -> ["city","common","alias","county"]

export const VERSION = "rules-2026-11-24d";

const SA_URL = /service[-_]?areas?|areas?[-_]?(we[-_]?)?serv|where[-_]?we[-_]?serve|locations?|cities|communities|coverage/i;
const TRIGGER = /\b(serv(?:e|es|ed|ing)|service areas?|areas? (?:we )?serv\w*|proudly|communities|nearby|surrounding|throughout|in and around|locations?)\b/gi;
const UNNAMED = /\b(?:and (?:many )?more|surrounding (?:areas|communities|cities|towns)|nearby (?:areas|communities|cities|towns)|and beyond|neighboring (?:areas|communities|cities)|greater [A-Z][a-z]+(?: [A-Z][a-z]+)? area|metro(?:politan)? area|\+\s?\d+ more)\b/;

// Place names that are also everyday words or HVAC words: only counted when written as "<name>, TX" / "<name>, Texas".
const STOP_ALWAYS = new Set(["comfort", "center", "mission", "commerce", "west", "early", "earth", "van", "sunset", "cool", "energy",
  "frost", "post", "rule", "hart", "wells", "troy", "nash", "paris", "miami", "garden", "industry", "price", "quail", "wink", "normal",
  "venus", "lone star", "texas", "tx", "star", "lake", "bend", "point", "como", "nevada", "detroit", "loop", "carbon", "buffalo",
  "ace", "royal", "meadow", "china", "blue", "berry", "concord", "smiley", "alamo", "reno", "tioga", "progreso", "call", "best",
  "tell", "happy", "cost", "may", "era", "panhandle", "guy", "art", "black", "silver", "tool"]);
// Small towns (2010 population under 50,000) whose names are also common English words or first/last names
// (word frequency from the wordfreq package, zipf >= 3.0). Counted only when written as a list item or "<name>, TX".
const AMBIGUOUS = new Set(`
  abbott addison adrian alamo alba albany albert alice allison alpine alto alton alvin ames amherst anderson andrews anna anthony
  anton arcadia art athens atlanta aubrey aurora avalon avery bailey baird bangs barry bartlett beasley bedford bellevue bells
  benjamin best bigfoot bishop black blackwell blanco blanket blessing bloomington blossom booker booth boston bowie boyd brady
  brandon bridgeport briggs brock bronson bryson buffalo burke burlington burton cactus caldwell call calvert cameron campbell
  canadian canton canyon carbon carlton carthage celeste center chandler channing charlotte cherokee chester chico china christine
  cisco clarendon claude cleveland clifton clint clyde coleman columbus combine comfort commerce como cone converse cool cooper cost
  cove covington crane crawford crockett crosby crossroads crowley dale damon dawson dayton dean decatur deport detroit devine diana
  dickens dickinson donna dorchester douglass driscoll dublin early earth easton eddy eden edna elgin elsa emory ennis era fairfield
  fate fayetteville ferris fife fischer flint florence forest franklin fred fresno frost fulton gail gainesville galveston garrison
  gary geneva goldsmith gonzales gordon gorman graham granger greenville gregory groom groves guthrie guy hamilton happy harper hart
  hartley haskell hawkins hays heartland heath henderson henrietta hereford hewitt higgins highlands hitchcock holland hooks howe
  hubbard hull hunt huntington hurst imperial industry ingram ira irene italy jacksonville jasper jefferson joaquin josephine joshua
  junction justin kaufman kemp kent kermit kirby klein kyle lakeside lancaster lawn leonard leroy lexington liberty lincoln linden
  lindsay linn liverpool livingston lockhart lolita london loop lorenzo louise loving lucas malone manor maple marathon marble
  marietta marion markham marlin marquez marshall mart mason maud maxwell may mccoy mclean meadow medina melissa melvin memphis
  mercedes meridian merkel miami midfield midway milano miles milford mineral montague montgomery moody moore moran morgan morse
  morton moscow mumford murphy mustang myra nada naples nash natalia nazareth nemo nevada newark newcastle newton nixon nolan norton
  novice nursery omaha orange orchard otto paige palestine palmer pandora paradise paris parker penelope perry petersburg petty
  phillips plains point ponder porter portland post powell princeton prosper putnam quail rainbow raisin randolph ranger rankin
  reagan recycle reno rice richards ridge riverside riviera roanoke robinson rochelle rochester rogers roma roscoe rosenberg rule
  rye sanctuary sanderson sanford santo saratoga sargent savoy scotland sebastian selma seymour sheffield shepherd sheridan sherman
  sidney silver simms singleton smiley snyder somerset somerville speaks spur stafford stamford stanton staples stratford sudan
  sumner sunset sur sylvester taft tarzan tatum taylor telephone tell thornton tool tow trent trenton trinidad trinity troy turkey
  utopia valentine van vega venus vera vernon voss waller wallis warren washington webster welch wellington wells west westbrook
  westfield wharton wheeler whitehouse whitney willis wilson winchester wink winnie winters
`.trim().split(/\s+/));
// Larger towns that are also first names or words: in phrase windows (not service-area pages) they need list context too.
const STOP_PERSON = new Set(["allen", "tyler", "bryan", "victoria", "temple", "mission", "kyle"]);

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

// Is text[start..end) set off like a list item: separators (or a line holding only the name) on both sides?
function inList(text: string, start: number, end: number) {
  const b = text.slice(Math.max(0, start - 8), start), a = text.slice(end, end + 8);
  const sepB = start === 0 || /(?:^|[,|•·;/\n(]|\band|&)\s*$/.test(b);
  const sepA = end >= text.length || /^\s*(?:[,|•·;/\n.)]|and\b|&|$)/.test(a);
  return sepB && sepA;
}

// Find place names in a piece of text: runs of Capitalised (or ALL CAPS) words, longest match first.
// strict = phrase window (not a service-area page): person-like and ambiguous names need list context.
function findPlaces(text: string, kinds: Kinds, url: string, how: string, strict: boolean, places: Hit[], counties: Hit[]) {
  const RUN = /[A-Z][A-Za-z'.]*(?:[ -](?:[A-Z][A-Za-z'.]*|of|de|la|del))*/g;
  let m: RegExpExecArray | null;
  while ((m = RUN.exec(text))) {
    const pos: number[] = []; const words: string[] = [];
    for (const w of m[0].matchAll(/[^ -]+/g)) { words.push(w[0]); pos.push(m.index + (w.index ?? 0)); }
    let i = 0;
    while (i < words.length) {
      let took = 0;
      for (let L = Math.min(4, words.length - i); L >= 1; L--) {
        const raw = words.slice(i, i + L).join(" ").replace(/[.']+$/, "");
        const n = norm(raw);
        const k = Object.prototype.hasOwnProperty.call(kinds, n) ? kinds[n] : undefined;   // not "constructor" etc.
        if (!Array.isArray(k) || n.length < 3) continue;
        const s0 = pos[i], s1 = pos[i + L - 1] + words[i + L - 1].replace(/[.']+$/, "").length;
        const nextWord = words[i + L];
        if (nextWord && /^county$/i.test(nextWord) && k.includes("county")) {   // "<X> County"
          counties.push({ name: raw + " County", norm: n, url, how }); took = L + 1; break;
        }
        if (!k.some((x) => x !== "county")) {                                   // county name without "County"
          if (L >= 2) { counties.push({ name: raw, norm: n, url, how }); took = L; break; }
          continue;
        }
        const txAfter = /^\s*,?\s*(?:TX|Texas)\b/.test(text.slice(s1, s1 + 10));
        if (!txAfter) {
          if (STOP_ALWAYS.has(n)) continue;
          if (L === 1 && AMBIGUOUS.has(n) && !inList(text, s0, s1)) continue;
          if (strict && L === 1 && STOP_PERSON.has(n) && !inList(text, s0, s1)) continue;
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
      const kk = Object.prototype.hasOwnProperty.call(kinds, n) ? kinds[n] : undefined;
      if (Array.isArray(kk) && kk.some((k) => k !== "county") && !STOP_ALWAYS.has(n)) {
        places.push({ name: n.replace(/\b\w/g, (c) => c.toUpperCase()), norm: n, url: u, how: "url slug" }); break;
      }
    }
  }
}

const ADDR = /(?<![\d\-().])(\d{1,6}[A-Za-z]?\s+(?:[NSEW]\.?\s+)?[A-Za-z][A-Za-z0-9.'\- ]{1,50}?\b(?:St|Street|Rd|Road|Dr|Drive|Ave|Avenue|Blvd|Boulevard|Ln|Lane|Pkwy|Parkway|Fwy|Freeway|Hwy|Highway|Way|Ct|Court|Cir|Circle|Trl|Trail|Loop|Pl|Place|Expy|Expressway|Plaza|Tollway|Pike|Pass|Row|Bend|Crossing|Xing|Sq|Square)\.?(?:\s+(?:N|S|E|W|North|South|East|West)\b)?(?:,?\s*(?:Suite|Ste\.?|Unit|Bldg|Building|#)\s*[\w-]+)?)\s*,?\s+([A-Z][A-Za-z .'-]{2,30}?),?\s+(?:TX|Texas)\.?,?\s+(7[5-9]\d{3})(?:-\d{4})?\b/g;

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

// Wording that advises the reader (buyer's guides, blog posts) rather than stating the firm's own position.
const ADVICE = /\b(?:should|make sure|be sure to|ask (?:if|whether|for|about)|check (?:if|whether|that)|verify|look for|beware|when (?:choosing|hiring)|a (?:good|reputable) (?:contractor|company))\b/i;

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
      const g = new RegExp(rx.source, "gi"); let m: RegExpExecArray | null; let n = 0;
      while ((m = g.exec(text)) && n++ < 20) {
        const w = around(text, m.index, m[0].length);
        if (k !== "freeEstimate" && ADVICE.test(w)) continue;   // "a contractor should carry insurance", "ask about financing options"
        first[k] = { wording: w, url: p.url }; break;
      }
    }
    for (const m of text.matchAll(/\bTACL\s*-?\s*([AB])?\s*[-#:]?\s*(0*\d{3,8})\s*([CE])?\b/gi))
      lic.add(`TACL${(m[1] || "").toUpperCase()}${m[2]}${(m[3] || "").toUpperCase()}`);
    // what an installation estimate includes: sentences on install / estimate / home pages that say "includes" or "covers"
    if (/install|estimate|replac|financ/.test(p.why) || p.role === "home" || /install|replac|estimate|quote/i.test(p.url)) {
      for (const s of text.split(/(?<=[.!?])\s+|\n/)) {
        if (s.length > 600 || !/\b(?:includes|included|comes? with|covers|covered|we (?:handle|take care of))\b/i.test(s)) continue;
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
