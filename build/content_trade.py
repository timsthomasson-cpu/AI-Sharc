# AI Sharc — trade-group pages, one shared template, per-trade copy.
from build.layout import page

SHARED_CTA = ('<a class="btn btn-teal" href="get-audited.html">Get your free Report Card</a> '
              '<a class="btn btn-ghost" href="how-it-works.html">How the audit works</a>')

def trade_page(slug, trade, hero_h1, hero_lead, why, what_looks, extra_html="", note=""):
    body = f'''<section class="hero"><div class="wrap">
<p style="text-transform:uppercase;letter-spacing:0.08em;font-size:0.85rem;color:var(--teal);font-weight:500;margin:0 0 10px">Texas {trade}</p>
<h1>{hero_h1}</h1>
<p class="lead">{hero_lead}</p>
<p>{SHARED_CTA}</p>
</div></section>'''
    body += f'''<section><div class="wrap"><h2>Why AI agents matter for a {trade.lower()}</h2>
<p style="max-width:70ch">{why}</p></div></section>'''
    cards = "".join(f'<div class="card"><h3>{t}</h3><p>{p}</p></div>' for t, p in what_looks)
    body += f'''<section class="alt"><div class="wrap"><h2>What the audit looks at for {trade.lower()}s</h2>
<p style="max-width:70ch">Every trade gets the same honest, sourced audit. What counts as "findable,
readable and trustworthy" differs by trade, so the audit pays attention to what your customers and
the machines both check first.</p>
<div class="grid g3">{cards}</div>{extra_html}
<p style="margin-top:16px"><a class="btn btn-teal" href="get-audited.html">See where you stand &mdash; free</a></p>
{f'<p class="note">{note}</p>' if note else ''}</div></section>'''
    return body

TRADES = [
  dict(
    slug="hvac-contractor.html",
    title="AI Audit for HVAC Contractors in Texas — AI Sharc Report Card",
    desc="Free AI-readiness Report Card for Texas HVAC contractors. See if AI shopping agents can find, read and trust your site — graded A–F, every finding sourced.",
    trade="HVAC Contractor",
    hero_h1="When an AC dies at 9pm, will the machines recommend <span class=\"accent\">you?</span>",
    hero_lead="Texas homeowners increasingly ask AI assistants who to call. AI Sharc grades how easily AI agents can find, read and trust your HVAC website — and hands you the fixes.",
    why="HVAC is the highest-stakes emergency hire in the home. A homeowner with a dead compressor asks their AI assistant who to call — and the assistant can only name firms whose sites it can find, read and trust. If your maintenance plans, emergency service and licence are buried in images or PDFs, the machines skip you.",
    what_looks=[
      ("Emergency and service clarity in text",
       "Can a machine tell, in plain text, that you answer emergency calls and what your hours are?"),
      ("Maintenance plans as offerings",
       "Agents recommend firms with recurring-revenue plans. If your plan isn't described in text, it doesn't exist to them."),
      ("Texas TDLR licence signals",
       "Your TACLIC/contractor licence details stated clearly, where homeowners and machines both look."),
      ("Service area in words",
       "The towns and counties you serve, written out — not just a map graphic."),
    ]),
  dict(
    slug="plumber.html",
    title="AI Audit for Plumbers in Texas — AI Sharc Report Card",
    desc="Free AI-readiness Report Card for Texas plumbers. Find out if AI assistants can find, read and trust your website — graded A–F, every finding cited with its source.",
    trade="Plumber",
    hero_h1="The burst pipe won't wait. Neither will the homeowner asking AI <span class=\"accent\">who to call.</span>",
    hero_lead="Water emergencies are the fastest decisions a homeowner makes. AI Sharc grades whether AI agents can find, read and trust your plumbing website fast enough to recommend you.",
    why="Plumbing searches are urgent and local, which makes them exactly the kind of question people now hand to an AI assistant. The agent builds its shortlist from what it can read about you: your emergency availability, your licence, your service area. If those live only in photos or a phone number in a footer image, you're not on the list.",
    what_looks=[
      ("24/7 and emergency language in text",
       "Is 'we answer 24/7' actually written on your site, in words a machine can read?"),
      ("Licence and master-plumber proof",
       "Your Texas licence stated in text where trust decisions happen."),
      ("Water heater, repipe and drain services named",
       "Each service named in its own words, so agents can match the job to you."),
      ("Service area in words",
       "Towns and ZIP-level areas listed as text, not locked in a map image."),
    ]),
  dict(
    slug="electrician.html",
    title="AI Audit for Electricians in Texas — AI Sharc Report Card",
    desc="Free AI-readiness Report Card for Texas electricians. See whether AI shopping agents can find, read and trust your site — graded A–F, every finding sourced.",
    trade="Electrician",
    hero_h1="Panel upgrades, EV chargers, whole-home rewires — do the machines know <span class=\"accent\">you do that?</span>",
    hero_lead="Electrical work runs on trust. AI Sharc grades how easily AI agents can find, read and trust your electrician website when a homeowner asks who to hire.",
    why="Homeowners hiring an electrician are buying safety, and they ask AI assistants for trustworthy names. An agent can only vouch for what it can read: your specialities (EV chargers, panel upgrades, generators), your licence, your proof of good work. High-ticket jobs go to the firms the machine can describe confidently.",
    what_looks=[
      ("High-ticket services in text",
       "EV charger installs, panel upgrades and generators named clearly — these are the jobs worth winning."),
      ("Texas licence signals",
       "Your licence details in text where agents and homeowners check for trust."),
      ("Permit and safety signals",
       "Whether your site shows the careful, permitted way you work — the trust an agent needs to recommend you."),
      ("Service area in words",
       "The towns you serve, written in text a machine can quote."),
    ]),
  dict(
    slug="roofing-contractor.html",
    title="AI Audit for Roofing Contractors in Texas — AI Sharc Report Card",
    desc="Free AI-readiness Report Card for Texas roofing contractors. See if AI agents can find, read and trust your roofing website — graded A–F, every finding cited.",
    trade="Roofing Contractor",
    hero_h1="Storm season sends homeowners to AI with one question: <span class=\"accent\">which roofer can I trust?</span>",
    hero_lead="Roofing has no Texas state licence, so trust has to come from somewhere else. AI Sharc grades whether AI agents can find, read and trust the proof on your roofing website.",
    why="Roofing is the biggest single hire a homeowner makes, and Texas doesn't license roofers at the state level — so an AI agent has no licence to lean on. It recommends the firm whose site proves, in readable text, that it's real: insurance, manufacturer certifications, local track record. If that proof is missing or locked in images, the machines can't tell you apart from a storm-chaser.",
    what_looks=[
      ("Proof instead of licence",
       "Insurance, manufacturer certifications (GAF, Owens Corning and similar) and warranties stated in text — the signals that stand in for a state licence."),
      ("Storm and insurance-claim clarity",
       "Can a machine tell that you handle insurance claims, and how the process works for the homeowner?"),
      ("Local track record in words",
       "Towns served and years in the area written as text an agent can cite."),
      ("Material and service specifics",
       "Replacement, repair, inspection and materials named so agents match the job to you."),
    ],
    note="Note: Texas does not licence roofing contractors at the state level, so our audit never claims licence-based checks for roofers. Your grade rests on the proof signals above — the honest stand-ins.",
  ),
]

def build_trade_pages():
    out = []
    for t in TRADES:
        body = trade_page(t["slug"], t["trade"], t["hero_h1"], t["hero_lead"], t["why"],
                          t["what_looks"], t.get("extra_html", ""), t.get("note", ""))
        out.append(page(t["slug"], t["title"], t["desc"], body))
    return out
