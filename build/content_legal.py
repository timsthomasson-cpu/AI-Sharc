# AI Sharc — legal + contact pages.
from build.content_pages import _sec, _hero

def legal_shell(title_h1, intro, sections):
    rows = "".join(f"<h2>{h}</h2>{b}" for h, b in sections)
    body = _hero(title_h1, intro, "")
    body += _sec("", rows)
    return body

CONTACT_ADDR = "AI Sharc, PO Box 1622, Coppell, TX 75019"

privacy_body = legal_shell(
    "Privacy Policy",
    "Last updated: 11 November 2026. Plain-English summary first, then the details.",
    [
      ("The short version",
       "<p>We collect the minimum we need to deliver your Report Card: the website address you submit and "
       "your business email. We use your email to verify you, deliver your cards, and (only if you opt in) "
       "send occasional marketing. We don't sell your data. You can ask us to delete it any time.</p>"),
      ("What we collect",
       "<ul>"
       "<li><strong>Website address</strong> you submit for audit, and the public content of that website, which we analyse to produce your Report Card.</li>"
       "<li><strong>Business email address</strong>, used for verification (double opt-in) and delivery of your cards.</li>"
       "<li><strong>Account activity</strong> if you purchase a Final Report Card: card history, billing receipts and subscription status, so you can manage everything from your dashboard.</li>"
       "<li><strong>Server logs</strong> (standard web logs) for security and rate limiting.</li></ul>"),
      ("What we don't do",
       "<ul>"
       "<li>We don't sell or rent your personal information.</li>"
       "<li>We don't use passwords — accounts work by email magic link, so we store no passwords at all.</li>"
       "<li>We don't audit or publish any firm's detailed results without that firm's involvement. Your card is yours.</li></ul>"),
      ("Email and marketing",
       "<p>Transactional email (verification links, your cards, subscription confirmations) is part of the "
       "service. Any marketing email we send identifies itself as an advertisement and includes our postal "
       "address (" + CONTACT_ADDR + ") and a working unsubscribe. Unsubscribe requests are honoured within "
       "10 days and added to a suppression list.</p>"),
      ("Cookies and analytics",
       "<p>We use privacy-friendly, cookieless analytics to count page visits — no advertising trackers, no "
       "cross-site profiling. If cookies are ever needed, we'll ask first.</p>"),
      ("Payments",
       "<p>Payments for the Final Report Card and monitoring subscriptions are handled by Stripe. We never "
       "see or store your card number.</p>"),
      ("Data retention and deletion",
       "<p>We keep your card data while your account is active so your history works. Email us to delete "
       "your data, and we'll remove it within 30 days, minus anything we must keep for tax or legal reasons.</p>"),
      ("Contact",
       "<p>Privacy questions: write to us at " + CONTACT_ADDR + ", or use the <a href='contact.html'>contact page</a>.</p>"),
    ])

terms_body = legal_shell(
    "Terms of Service",
    "Last updated: 11 November 2026. These terms govern your use of aisharc.com and the AI Sharc audit service.",
    [
      ("The service",
       "<p>AI Sharc audits business websites for AI-agent readiness and issues graded Report Cards "
       "(A&ndash;F). The Preliminary Report Card is free. The Final Report Card is a paid, one-time "
       "purchase. Monitoring is a month-to-month subscription you may cancel at any time.</p>"),
      ("What the audit is — and isn't",
       "<p>The audit assesses how easily automated AI shopping agents can find, read and trust information "
       "on your website, based on the publicly visible content of that site on the date audited. It is not "
       "a guarantee of traffic, rankings, revenue or AI-assistant recommendations. Grades describe your "
       "site as checked; sites change, and grades reflect the date of the audit.</p>"),
      ("Every finding is sourced",
       "<p>Findings cite the checked page, its exact wording and the check date so you can verify them. If "
       "you believe a finding is wrong (for example, the page changed after we checked), contact us and "
       "we'll re-check.</p>"),
      ("Your responsibilities",
       "<p>Submit only websites you own or are authorised to represent. Provide a valid business email for "
       "verification. Don't submit sites to probe, stress or abuse the service.</p>"),
      ("Payments and cancellation",
       "<p>The Final Report Card is a one-time payment ($99 introductory price for the first 500 firms; "
       "regular price $149). Your first months of monitoring are included with the Final Report Card; "
       "after the included months, monitoring continues at $25/month introductory (regular $30/month), "
       "billed monthly, cancellable by you at any time from your dashboard. Cancellation stops future "
       "billing; the current month is not refunded.</p>"),
      ("No professional advice",
       "<p>Report Cards and fixes are marketing and technical guidance for your website. They are not "
       "legal, insurance, licensing or tax advice.</p>"),
      ("Limitation of liability",
       "<p>To the maximum extent permitted by law, AI Sharc's liability arising from the service is limited "
       "to the amounts you paid us in the 12 months before the claim.</p>"),
      ("Governing law",
       "<p>These terms are governed by the laws of the State of Texas.</p>"),
      ("Contact",
       "<p>Questions about these terms: " + CONTACT_ADDR + ", or the <a href='contact.html'>contact page</a>.</p>"),
    ])

contact_body = _hero(
    'Contact &amp; About',
    "AI Sharc is the AI Shopping Health Audit Report Card — a graded audit of how easily AI shopping "
    "agents can find, read and trust a home-services business. Audit-only: we grade, you fix.", '')
contact_body += _sec("", '''<div class="grid g2">
<div class="card"><h3>About AI Sharc</h3>
<p>We started AI Sharc because the way homeowners find a plumber, an HVAC tech or a roofer is changing:
they ask AI assistants, not search engines. A business that the machines can't find, read and trust is
invisible to those customers &mdash; no matter how good the work is.</p>
<p>So we built the audit we wished existed: honest, sourced, graded A&ndash;F, with bite-sized fixes.
We're based in Coppell, Texas, and we launched with Texas licensed home trades &mdash; the businesses
where trust decides the hire.</p>
<p class="tag">Bite-sized fixes. Shark-sized results.</p></div>
<div class="card"><h3>Get in touch</h3>
<p><strong>Mail:</strong><br>AI Sharc<br>PO Box 1622<br>Coppell, TX 75019</p>
<p><strong>Questions about the audit or your card?</strong><br>
Check the <a href="faq.html">FAQ</a> first &mdash; it covers most things, fast.</p>
<p><strong>Ready to see your grade?</strong><br>
<a href="get-audited.html">Get your free Preliminary Report Card</a> &mdash; it takes minutes.</p></div>
</div>''')
