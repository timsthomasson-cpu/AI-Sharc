# AI Sharc — SSR page shell. Reuses build/layout so the FastAPI-served pages are
# byte-identical to the Stage 1 static build; adds dynamic page fragments.
from build.layout import page as _page, header, footer, BASE


def shell(slug, title, desc, body, canon=None):
    return _page(slug, title, desc, body, canon=canon)


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
