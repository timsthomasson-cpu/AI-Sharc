# AI Sharc — SSR page shell. Reuses build/layout so the FastAPI-served pages are
# byte-identical to the Stage 1 static build; adds dynamic page fragments.
from build.layout import page as _page, header, footer, BASE

import json


def shell(slug, title, desc, body, canon=None):
    return _page(slug, title, desc, body, canon=canon)


def render_final_card(final, request_row, scan_note=""):
    """Final Report Card: the same card design extended with the deeper fields
    — every finding with its source and the full prioritised fix list. Final
    cards are private to the purchasing firm; the same exposure rule as the
    Preliminary card applies: no item rows, weights, thresholds or gate names.
    TODO(audit-spec Rev 6): the Final card layout spec (Rev 6) has NOT arrived
    yet. This renders against the current card renderer + the spec's card
    content list; swapping in Rev 6 should be a single renderer change here.
    """
    import html as _h
    findings = json.loads(final.findings_json)
    fixes = json.loads(final.fixes_json)
    rows = "".join(
        f'<div class="rc-find"><h4>{_h.escape(f["title"])}</h4>'
        f'<p>{_h.escape(f["detail"])}</p>'
        f'<div class="rc-src">{_h.escape(f["source"])}</div></div>'
        for f in findings)
    fix_rows = "".join(
        f'<div class="rc-find"><h4>{i + 1}. {_h.escape(f["title"])}</h4>'
        f"<p>{_h.escape(f['detail'])}</p></div>"
        for i, f in enumerate(fixes)) or "<p class=note>No fixes needed right now.</p>"
    gcls = "g-" + final.grade.lower()
    scan = f'<p class="note">{_h.escape(scan_note)}</p>' if scan_note else ""
    return f'''<div class="report-card" style="max-width:640px">
<div class="rc-head"><span class="grade {gcls}">{_h.escape(final.grade)}</span>
<div><h3 style="margin:0">{_h.escape(request_row.normalized_domain)}</h3>
<div class="rc-src">Final Report Card &middot; full audit &middot; private to your firm</div></div></div>
<p><strong>{_h.escape(final.headline)}</strong></p>
<h4 style="margin-bottom:4px">Every finding, with its source</h4>
{rows}
<h4 style="margin-bottom:4px;margin-top:20px">Your full fix list, in priority order</h4>
{fix_rows}
{scan}
<p style="font-size:0.9rem;color:#5b7186">AI Sharc makes no guarantee of business results. This
card reports what we checked and when; it is not a prediction of traffic, leads or sales.</p>
</div>'''


def render_card(card, request_row):
    """Preliminary Report Card, same design as the sample-card page.
    Summary-level findings with source + date only — no item rows, weights,
    thresholds or gate names appear on any card."""
    import json
    import html as _h

    findings = json.loads(card.findings_json)
    rows = "".join(
        f'<div class="rc-find"><h4>{_h.escape(f["title"])}</h4>'
        f'<p>{_h.escape(f["detail"])}</p>'
        f'<div class="rc-src">{_h.escape(f["source"])}</div></div>'
        for f in findings)
    gcls = "g-" + card.grade.lower()
    return f'''<div class="report-card">
<div class="rc-head"><span class="grade {gcls}">{_h.escape(card.grade)}</span>
<div><h3 style="margin:0">{_h.escape(request_row.normalized_domain)}</h3>
<div class="rc-src">Preliminary Report Card &middot; free</div></div></div>
<p><strong>{_h.escape(card.headline)}</strong></p>
{rows}
<p style="font-size:0.9rem;color:#5b7186">AI Sharc makes no guarantee of business results. This
card reports what we checked and when; it is not a prediction of traffic, leads or sales.</p>
</div>'''
