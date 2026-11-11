# AI Sharc — per-page content. Every page returns (slug, title, meta_description, body_html).
import textwrap

# TIM TO CONFIRM: number of monitoring months included with the Final Report Card
# (spec allows 3 or 4; 4 recommended because $99 / 4 = $24.75/mo embedded, matching the
# $25 intro rate). This constant is the ONLY place the figure lives in the copy.
MONITORING_INCLUDED_MONTHS = 4

def _sec(cls, inner):
    return f'<section class="{cls}"><div class="wrap">{inner}</div></section>'

def _hero(h1, lead, ctas):
    return f'''<section class="hero"><div class="wrap">
<h1>{h1}</h1>
<p class="lead">{lead}</p>
<p>{ctas}</p>
</div></section>'''

CTA_GET = '<a class="btn btn-teal" href="get-audited.html">Get your free Report Card</a>'

# ---------------------------------------------------------------- home
home_body = _hero(
    'Is your store ready for the <span class="accent">machines that shop?</span>',
    "More of your customers now ask AI — ChatGPT, Gemini, voice assistants — who to hire. "
    "AI Sharc audits your website the way those AI agents see it, grades it A&ndash;F, and hands "
    "you a plain-English list of fixes.",
    CTA_GET + ' <a class="btn btn-ghost" href="sample-cards.html">See a sample Report Card</a>')
home_body += _sec("", '''
<h2 style="margin-bottom:8px">Your next customer may never open Google</h2>
<p style="max-width:70ch">When a homeowner's AC dies, more and more of them ask an AI assistant instead of
searching. The assistant can only recommend businesses whose websites it can <strong>find</strong>,
<strong>read</strong> and <strong>trust</strong>. If your site hides its services in images, buries your
service area, or never states your licence, the machines skip you &mdash; and the homeowner never knows
you existed.</p>''')
home_body += _sec("alt", '''
<h2>What a Report Card gives you</h2>
<div class="grid g3">
  <div class="card"><h3>A grade you can act on</h3><p>One overall letter grade, A through F, plus the
  specific things holding your site back &mdash; each one written in plain English, not tech talk.</p></div>
  <div class="card"><h3>Every finding has a source</h3><p>We don't guess. Every point on your card cites
  the exact page, the exact wording and the date we checked it. You can verify every line yourself.</p></div>
  <div class="card"><h3>Bite-sized fixes</h3><p>Each finding comes with the fix, sized so you or your web
  person can do it &mdash; or hand it over as-is. No 40-page consulting deck.</p></div>
</div>''')
home_body += _sec("", '''
<h2>How you get graded</h2>
<div class="grid g3">
  <div class="card"><span class="badge">Free, always</span><h3>1. Preliminary Report Card</h3>
  <p>Submit your website and business email. Verify it's you with one click, and your Preliminary
  Report Card is ready to view. No card, no charge.</p></div>
  <div class="card"><span class="badge">$99 introductory</span><h3>2. Final Report Card</h3>
  <p>The full deep audit: your complete graded card, every finding with its source, and your fix list.
  Includes monitoring so you can watch the grade move.</p></div>
  <div class="card"><span class="badge">Built for Texas home trades</span><h3>3. Fix and watch it climb</h3>
  <p>Work the fixes. Your monitoring subscription keeps checking, so you see the grade respond as your
  site becomes easier for AI agents to read and trust.</p></div>
</div>
<p style="margin-top:24px"><a class="btn btn-outline" href="how-it-works.html">How the audit works</a></p>''')
home_body += _sec("alt", '''
<h2>Made for licensed home trades in Texas</h2>
<p style="max-width:70ch">We built the audit around what your customers actually check: licence,
service area, response time and trust. Pick your trade to see what matters for your kind of business.</p>
<div class="grid g2">
  <div class="card"><h3><a href="hvac-contractor.html">HVAC Contractor</a></h3><p>Stay-ahead maintenance
  plans, emergency calls and Texas TDLR licence rules.</p></div>
  <div class="card"><h3><a href="plumber.html">Plumber</a></h3><p>Emergency jobs, water-heater replacements
  and the licence checks homeowners run before they call.</p></div>
  <div class="card"><h3><a href="electrician.html">Electrician</a></h3><p>Panel upgrades, EV chargers and
  standing out in a trade where trust is everything.</p></div>
  <div class="card"><h3><a href="roofing-contractor.html">Roofing Contractor</a></h3><p>Storm season, insurance
  claims and a market with no state licence &mdash; where proof matters twice as much.</p></div>
</div>''')
home_body += _sec("", '''
<h2>Bite-sized fixes. Shark-sized results.</h2>
<p style="max-width:70ch">You don't need a new website. You need the machines that shop to find, read and
trust the one you have. Find out in minutes where you stand.</p>
<p><a class="btn btn-teal" href="get-audited.html">Get audited &mdash; Preliminary is free</a></p>''')

# ---------------------------------------------------------------- get audited (teaser)
get_body = _hero(
    'Get your free Report Card',
    "Submit your website address and business email. We email you a one-click verification link, and "
    "your Preliminary Report Card is ready to view &mdash; free, always.",
    '')
get_body += _sec("", '''<div class="card form" style="max-width:560px">
<h2 style="font-size:1.3rem">Submit your site</h2>
<form action="/get-audited" method="post">
  <label for="url">Your website address</label>
  <input type="url" id="url" name="url" placeholder="https://yourbusiness.com" required>
  <label for="email">Business email</label>
  <input type="email" id="email" name="email" placeholder="you@yourbusiness.com" required>
  <p style="margin:8px 0"><label style="font-weight:400"><input type="checkbox" name="hp" class="hp" tabindex="-1" autocomplete="off"> Leave this box unchecked</label></p>
  <p><button class="btn btn-teal" type="submit">Request my free Report Card</button></p>
</form>
<p class="note">Double-check the email: we send a verification link there, and your card unlocks after you
click it. Your Preliminary Report Card is always free. Questions? See the <a href="faq.html">FAQ</a>.</p>
</div>''')
get_body += _sec("alt", '''<h2>What happens after you submit</h2>
<div class="grid g3">
<div class="card"><h3>1. Verify it's you</h3><p>We email a one-click link to your business email.
Click it and your Preliminary Report Card unlocks. No passwords, no account set-up.</p></div>
<div class="card"><h3>2. Read your card</h3><p>Your grade, and the specific things AI agents can't find,
read or trust on your site today &mdash; each with its source.</p></div>
<div class="card"><h3>3. Decide</h3><p>Fix it yourself, or get the full Final Report Card with monitoring
to watch the grade move. You're never on the hook.</p></div>
</div>''')

# ---------------------------------------------------------------- pricing
pricing_body = _hero(
    'Simple pricing. The Report Card is the product.',
    "The Preliminary Report Card is free, always. The Final Report Card is one payment. Monitoring after "
    "that is month-to-month and you can cancel any time, yourself, in your dashboard.",
    '<a class="btn btn-teal" href="get-audited.html">Start free</a>')
pricing_body += _sec("", f'''
<div class="grid g3">
  <div class="card"><span class="badge">Free, always</span>
    <div class="price">$0</div><p style="margin-bottom:12px"><small>Preliminary Report Card</small></p>
    <ul class="tick">
      <li>One Preliminary Report Card for your site</li>
      <li>Overall A&ndash;F grade</li>
      <li>Summary-level findings, each with its source</li>
      <li>Plain-English fixes to start on</li>
    </ul>
    <p><a class="btn btn-outline" href="get-audited.html">Get it free</a></p></div>
  <div class="card" style="border-color:var(--teal);border-width:2px"><span class="badge">One payment</span>
    <div class="price">$99 <small>introductory</small></div>
    <p style="margin-bottom:12px"><small>Final Report Card &mdash; regular price $149. Introductory price applies to the first 500 firms.</small></p>
    <ul class="tick">
      <li>The full, deep audit of your site</li>
      <li>Complete graded card, every finding with its source</li>
      <li>Your full prioritised fix list</li>
      <li>Unlimited re-checks for 60 days after your Final card</li>
      <li>Monitoring included for your first <strong>{MONITORING_INCLUDED_MONTHS}</strong> months</li>
      <li>Re-scan updates while monitoring is active</li>
    </ul>
    <p><a class="btn btn-teal" href="get-audited.html">Start with the free card</a></p></div>
  <div class="card"><span class="badge">Month-to-month</span>
    <div class="price">$25<small>/mo introductory</small></div>
    <p style="margin-bottom:12px"><small>Monitoring after your included months &mdash; regular price $30/mo.</small></p>
    <ul class="tick">
      <li>Keep watching your grade</li>
      <li>Re-scan updates when your site changes</li>
      <li>Cancel any time, yourself, in your dashboard</li>
      <li>No contract, no phone call to quit</li>
    </ul></div>
</div>
<p class="note" style="margin-top:16px">Monitoring included with the Final Report Card runs for the first
<strong>{MONITORING_INCLUDED_MONTHS}</strong> months after purchase. After that it's $25/month introductory (regular $30/month),
month-to-month. The Final price also covers the original Report Card and unlimited re-checks of your site
within 60 days of the original card &mdash; that window is separate from monitoring and doesn't count against it.</p>''')
pricing_body += _sec("alt", '''<h2>What you're paying for &mdash; and what you're not</h2>
<div class="grid g2">
<div class="card"><h3>You are paying for</h3><ul class="tick"><li>An honest, sourced, graded read on how AI
agents see your site.</li><li>A fix list you can act on without hiring anyone.</li><li>Optional monitoring
so you know the fixes worked.</li></ul></div>
<div class="card"><h3>You are not paying for</h3><ul class="tick"><li>Implementation. AI Sharc audits; it
doesn't touch your site.</li><li>A plugin or software to install.</li><li>A contract. Everything after the
Final card is month-to-month, cancelled by you in your dashboard.</li></ul></div>
</div>''')

# ---------------------------------------------------------------- how it works (HIGH-LEVEL ONLY)
hiw_body = _hero(
    'How the audit works',
    "AI Sharc checks your website the way AI shopping agents do: can they find you, read you, and trust "
    "you enough to recommend you? Then you get a graded Report Card with the fixes.",
    '')
hiw_body += _sec("", '''<h2>Three questions, one grade</h2>
<p style="max-width:70ch">An AI shopping agent &mdash; ChatGPT, Gemini, a voice assistant &mdash; only
recommends businesses it can deal with. Our audit asks the same three questions it asks, in the same order:</p>
<div class="grid g3">
<div class="card"><h3>Can they find you?</h3><p>When someone asks an AI for your service in your area, can
the agent even tell that you exist and serve that area?</p></div>
<div class="card"><h3>Can they read you?</h3><p>Once it lands on your site, can the machine actually read
what you do, where you do it, and how to reach you? Or is that information locked in images and forms?</p></div>
<div class="card"><h3>Can they trust you?</h3><p>Does your site give an agent reasons to recommend you over
the next firm &mdash; the proof, the specifics and the signals that separate real businesses from thin ones?</p></div>
</div>''')
hiw_body += _sec("alt", '''<h2>A graded report card, not a wall of tech talk</h2>
<div class="grid g2">
<div class="card"><h3>The grade</h3><p>Your site gets one overall letter grade from A to F, the way a
report card works. No partial credit and no averaging: what fails, fails, and you see exactly what it is.</p></div>
<div class="card"><h3>The findings</h3><p>Every finding is a specific, plain-English statement about your
site &mdash; and each one cites its source: the page we checked, the exact wording, and the date. Nothing
on your card is our opinion of your industry. It's what's on your site.</p></div>
</div>''')
hiw_body += _sec("", '''<h2>Two versions of your card</h2>
<div class="grid g2">
<div class="card"><span class="badge">Free, always</span><h3>Preliminary Report Card</h3>
<p>Submit your site, verify your email, and see your grade with summary-level findings. It tells you where
you stand and gives you the first fixes &mdash; enough to start today.</p></div>
<div class="card"><span class="badge">$99 introductory</span><h3>Final Report Card</h3>
<p>The deep audit. The complete card, every finding with its source, and your full fix list &mdash; plus
monitoring for your first few months so you can watch the grade move as you work.</p></div>
</div>
<p style="margin-top:8px"><a class="btn btn-teal" href="get-audited.html">Start with the free Preliminary</a>
 <a class="btn btn-outline" href="sample-cards.html">See a sample card</a></p>''')
hiw_body += _sec("alt", '''<h2>What we check</h2>
<p style="max-width:70ch">In plain terms, we check everything that decides whether an AI agent can find,
read and trust your business: how your site describes your services and your service area, whether the
essentials (contact, hours, licence, proof) are stated in text a machine can read, how your site holds up
against the basics agents rely on, and whether the signals that build trust are present and consistent.</p>
<p class="note">We don't publish the detailed scoring behind the grade &mdash; it's what keeps the audit
honest and hard to game. Your own card tells you everything about <em>your</em> site.</p>''')

# ---------------------------------------------------------------- FAQ
FAQ = [
 ("What is AI Sharc?",
  "AI Sharc issues the AI Shopping Health Audit Report Card: a graded A&ndash;F audit of how easily AI "
  "shopping agents &mdash; ChatGPT, Gemini, voice assistants &mdash; can find, read and trust your business "
  "website. You get the grade and a plain-English fix list. We audit; we don't touch your site."),
 ("Who is it for?",
  "Home-services firms, starting with licensed home trades in Texas: HVAC contractors, plumbers, "
  "electricians and roofing contractors. If homeowners hire you after finding you online, this is for you."),
 ("What do AI shopping agents have to do with my business?",
  "More customers ask AI assistants for recommendations instead of searching. The assistant can only "
  "recommend businesses whose websites it can find, read and trust. If yours hides that information, the "
  "machines recommend someone else &mdash; and the homeowner never hears about you."),
 ("What's the difference between the Preliminary and Final Report Card?",
  "The Preliminary is free, always: your overall grade and summary-level findings. The Final is the deep "
  "audit &mdash; the complete card, every finding with its cited source, and your full fix list &mdash; plus "
  "monitoring for your first few months."),
 ("Why is every finding sourced?",
  "So you can check our work. Each finding cites the page we looked at, the exact wording, and the date we "
  "checked. Nothing on your card is a guess or an opinion about your industry."),
 ("What does 'no partial credit' mean?",
  "Your grade reflects what's actually true on your site. A half-done fix doesn't earn half the points: if "
  "something fails, it fails, and your card says exactly what to finish."),
 ("Do I need a new website?",
  "Almost never. Most grades move with small, specific changes to the site you already have. That's the "
  "point of bite-sized fixes: each one is small enough to actually get done."),
 ("Does AI Sharc fix my site for me?",
  "No. AI Sharc is audit-only: we grade and we show you the fixes. Your card is written so you or your web "
  "person can act on it directly."),
 ("How do I get started?",
  "Submit your website address and business email on the Get Audited page. We email you a one-click "
  "verification link; click it and your free Preliminary Report Card is ready to view."),
 ("How does billing work?",
  "The Preliminary Report Card is free. The Final Report Card is a one-time payment ($99 introductory, "
  "regular $149). Monitoring is included for your first few months, then it's $25/month introductory "
  "(regular $30/month), month-to-month, cancelled any time by you in your dashboard."),
 ("Can I cancel monitoring?",
  "Yes, any time, yourself, from your dashboard. No contract, no phone call, no email chain."),
 ("What about my privacy?",
  "We ask for your website address and business email, and use them to deliver and verify your Report Card. "
  "Details are in our <a href=\"privacy.html\">Privacy Policy</a>."),
]
faq_rows = "".join(f"<details><summary>{q}</summary><div class='a'>{a}</div></details>" for q, a in FAQ)
faq_body = _hero('Frequently asked questions',
                 "Short answers about the audit, the Report Cards, pricing and what AI Sharc does and doesn't do.", '')
faq_body += _sec("", faq_rows +
  '<p style="margin-top:16px">Still stuck? <a href="contact.html">Contact us</a>.</p>')

# ---------------------------------------------------------------- sample cards
def _rc(grade, gcls, firm, headline, findings, note):
    rows = "".join(
        f'<div class="rc-find"><h4>{h}</h4><p>{p}</p><div class="rc-src">{s}</div></div>'
        for h, p, s in findings)
    return f'''<div class="report-card">
<div class="rc-head"><span class="grade {gcls}">{grade}</span>
<div><h3 style="margin:0">{firm}</h3><div class="rc-src">Preliminary Report Card &middot; sample with dummy data</div></div></div>
<p><strong>{headline}</strong></p>
{rows}
<p style="font-size:0.9rem;color:#5b7186">{note}</p>
</div>'''

sample_body = _hero(
    'Sample Report Cards',
    "These are samples with dummy data &mdash; not real businesses. They show what a Preliminary Report "
    "Card looks like: a grade and summary-level findings, each one citing its source.",
    '')
sample_body += _sec("", '''<h2>Sample 1 &mdash; a site the machines can't read</h2>''' + _rc(
    "D", "g-d", "Sample Air &amp; Heat Co.",
    "AI agents can find this business, but can't read what it sells.",
    [("Services are images, not text",
      "The homepage shows service photos with no text description a machine can read.",
      "Source: homepage, service image row &middot; checked 2026-11-11 (dummy data)"),
     ("No service area stated in text",
      "The towns served appear only inside a map graphic.",
      "Source: homepage, map section &middot; checked 2026-11-11 (dummy data)"),
     ("Phone number not clickable",
      "The phone number is plain text; phones can't tap it and agents can't extract it reliably.",
      "Source: contact page footer &middot; checked 2026-11-11 (dummy data)")],
    "Fixes are bite-sized: name each service in text, list the towns served, and make the phone number a tap-to-call link."))
sample_body += '<h2>Sample 2 &mdash; a site agents can trust</h2>' + _rc(
    "B", "g-b", "Sample Plumbing Co.",
    "Strong overall. A few trust signals are missing for AI agents.",
    [("Licence stated clearly",
      "The licence type and number appear in the site footer, in text.",
      "Source: site footer &middot; checked 2026-11-11 (dummy data)"),
     ("Service pages name each town served",
      "Each service page lists the towns it covers in plain text.",
      "Source: /services pages &middot; checked 2026-11-11 (dummy data)"),
     ("No customer reviews on site",
      "The site shows no customer reviews anywhere, which weakens the trust picture for an agent.",
      "Source: homepage and about page &middot; checked 2026-11-11 (dummy data)")],
    "One small fix list. The firm is close to an A.")
sample_body += _sec("alt", '''<h2>What you won't see here</h2>
<p style="max-width:70ch">Samples show the grade and summary-level findings, the way a Preliminary card
does. The full line-by-line detail of an audit is only on a firm's own Final Report Card &mdash; it's
specific to their site and we don't publish the scoring behind it.</p>
<p><a class="btn btn-teal" href="get-audited.html">Get your own free card</a></p>''')
