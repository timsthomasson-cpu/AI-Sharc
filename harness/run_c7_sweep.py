"""Evidence-only sweep: Category 7 (Machine Readability) + TDLR licence
check for the 19-firm registry — 2026-11-11.

NOT a full audit and NOT a grade. It runs only the fetchers already built
and live-tested (website initial HTML, robots.txt, JSON-LD, sitemap,
llms.txt, TDLR register) and scores only C7.1-C7.4 (M1, M2, M4, M5) and,
where a licence number is recorded, C3.1 — using the rules engine's own
check functions. Everything else is left unscored: no Pass is assumed,
no firm is graded, no firm is contacted, no card is produced.

Output: runs/2026-11-11/c7_sweep.json (full evidence + per-item results)
and a summary printed to stdout.
"""
import json, os, sys
sys.path.insert(0, '/home/hatch/workspace/goals/score-card-audit-product/files/aisharc-harness')
from datetime import date
from aisharc_harness.evidence import fetchers as F
from aisharc_harness.rules.engine import (load_definitions, ITEM_CHECKS,
                                          check_lever_llms_txt, norm_licence)

BASE = '/home/hatch/workspace/goals/score-card-audit-product/files/aisharc-harness'
TODAY = date.today().isoformat()
defs = load_definitions()

with open(os.path.join(BASE, 'firms.json')) as fh:
    reg = json.load(fh)

results = []
for firm in reg['firms']:
    fid, name, site = firm['firm_id'], firm['name'], firm.get('website')
    rec = {'firm_id': fid, 'name': name, 'website': site, 'date': TODAY}
    if not site:
        rec['note'] = 'No website recorded in 25 Oct 2026 research; not fetched.'
        rec['c7'] = {}
        results.append(rec)
        continue
    base = site.rstrip('/')
    # Machine-readability files live at the SITE ROOT, not at the recorded
    # page URL (which for Airtron / Eric's is a service-area page). Using
    # the page URL here gave false 404s for robots.txt / sitemap / llms.txt
    # on the first run; corrected 2026-11-11.
    from urllib.parse import urlparse as _up
    _p = _up(site)
    root = f"{_p.scheme}://{_p.netloc}"
    # Website (initial HTML; rendered not attempted — no renderer installed)
    web = F.fetch_website(site)
    html = (web['initial_html'].exact or '') if web['initial_html'].accessible else ''
    text = web.get('text') or ''
    rec['website_readable'] = not web['unreadable']
    rec['initial_html_accessible'] = bool(web['initial_html'].accessible)
    if not web['initial_html'].accessible:
        rec['website_reason'] = web['initial_html'].reason
    robots = F.fetch_robots_txt(root)
    rec['robots'] = {k: v for k, v in robots.items() if k != 'body'}
    rec['robots_body_present'] = bool(robots.get('body'))
    ld = F.parse_json_ld(html)
    rec['json_ld'] = {k: v for k, v in ld.items() if k != 'node'}
    if ld.get('node'):
        rec['json_ld']['node_type'] = ld['node'].get('@type')
        rec['json_ld']['node_name'] = ld['node'].get('name')
    sm = F.fetch_sitemap(root, robots)
    rec['sitemap'] = sm
    llms = F.fetch_llms_txt(root)
    rec['llms_txt'] = {k: v for k, v in llms.items() if k != 'body'}
    # Score C7.1-C7.4 with the engine's own checks.
    ev7 = {
        'C7.1': {'robots_txt': robots},
        'C7.2': {'initial_html': {'accessible': web['initial_html'].accessible,
                                   'reason': getattr(web['initial_html'], 'reason', ''),
                                   'missing_facts': F.key_facts_in_html(html)['missing_facts'] if html else []}},
        'C7.3': {'json_ld': ld},
        'C7.4': {'sitemap': sm},
    }
    # M2: if HTML unreadable, key_facts check is Not accessible, not Missing.
    if not html:
        ev7['C7.2'] = {'initial_html': {'accessible': False,
                                         'reason': rec.get('website_reason', '')}}
    c7 = {}
    for iid in ('C7.1', 'C7.2', 'C7.3', 'C7.4'):
        row = ITEM_CHECKS[iid](ev7[iid], defs)
        c7[iid] = {'result': row.result, 'evidence': row.evidence}
    c7['points'] = sum(1 for v in c7.values() if isinstance(v, dict) and v['result'] == 'Pass')
    rec['c7'] = c7
    # llms.txt lever (M3, not scored)
    lv = check_lever_llms_txt({'llms_txt': llms}, defs)
    rec['llms_lever'] = {'result': lv.result, 'evidence': lv.evidence}
    # TDLR, only where a licence number is recorded in the registry.
    lic = firm.get('licence_recorded')
    if lic:
        digits = norm_licence(lic)
        published = digits in (text.replace('-', '').replace(' ', '') or '') or digits in (html or '')
        # Simpler, robust check: digits appear anywhere in the plain text.
        published = digits in ''.join(text.split()) or digits in html
        reg_lookup = F.tdlr_lookup(lic, 'A/C Contractor', TODAY)
        row = ITEM_CHECKS['C3.1']({'licence': {'published': published, 'number': lic,
                                                'register': reg_lookup}, 'trade': 'HVAC'}, defs)
        rec['c31_licence'] = {'recorded': lic, 'published_on_site': published,
                              'register': {k: v for k, v in reg_lookup.items() if k != 'row'},
                              'register_expiry': reg_lookup.get('expiry'),
                              'register_active': reg_lookup.get('active'),
                              'result': row.result, 'evidence': row.evidence}
    results.append(rec)
    print(f"{fid}: readable={rec['website_readable']} C7={c7['points']}/4 "
          f"({', '.join(v['result'] for k, v in c7.items() if isinstance(v, dict))})"
          + (f" C3.1={rec['c31_licence']['result']}" if 'c31_licence' in rec else ''), flush=True)
    F.polite_sleep()

outdir = os.path.join(BASE, 'runs', TODAY)
os.makedirs(outdir, exist_ok=True)
with open(os.path.join(outdir, 'c7_sweep.json'), 'w') as fh:
    json.dump({'date': TODAY, 'spec_version': '1.22', 'scope': 'Category 7 + TDLR only; not a full audit, no grade',
               'query': reg['query'], 'town_zip': reg['town_zip'], 'results': results}, fh, indent=2)
n = len(results)
readable = sum(1 for r in results if r.get('website_readable'))
print(f"\nSUMMARY {TODAY}: {n} firms, {readable} websites readable (initial HTML), "
      f"{n - readable} without a recorded website or unreadable.")
for iid in ('C7.1', 'C7.2', 'C7.3', 'C7.4'):
    counts = {}
    for r in results:
        v = (r.get('c7') or {}).get(iid)
        if v: counts[v['result']] = counts.get(v['result'], 0) + 1
    print(f"  {iid}: {counts}")
print(f"  llms.txt present: {sum(1 for r in results if (r.get('llms_txt') or {}).get('exists'))}/{n}")
print("  C7 points distribution: " + str(sorted(sum(1 for v in (r.get('c7') or {}).values() if isinstance(v, dict) and v['result'] == 'Pass') for r in results)))
