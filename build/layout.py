# AI Sharc site layout — shared HTML shell (header/footer), no JS.
import os
BASE = "https://aisharc.com"
# Flow host (Railway): the dynamic Get-Audited flow lives here; Pages serves the shell.
FLOW_ORIGIN = os.environ.get("FLOW_ORIGIN", "https://aisharc.com")

FIN = ('<svg class="fin" width="26" height="20" viewBox="-14 -48 132 102" aria-hidden="true">'
       '<path d="M 6 44 Q 50 -20 105 -34 Q 80 16 96 44 Z" fill="#00D4C8"/></svg>')

NAV = [
    ("how-it-works.html", "How it works"),
    ("pricing.html", "Pricing"),
    ("sample-cards.html", "Sample"),
    ("faq.html", "FAQ"),
    ("contact.html", "Contact"),
]

def header(active):
    parts = []
    for href, label in NAV:
        cur = ' aria-current="page"' if href == active else ""
        parts.append(f'<a href="{href}"{cur}>{label}</a>')
    links = "".join(parts)
    return f'''<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="index.html" aria-label="AI Sharc home">{FIN}<strong>AI&nbsp;Sharc</strong></a>
    <nav class="nav" aria-label="Main">{links}
      <a class="btn btn-teal" style="padding:8px 16px" href="{FLOW_ORIGIN}/get-audited">Get audited</a>
    </nav>
  </div>
</header>'''

def footer():
    trade_links = "".join(
        f'<li><a href="{h}">{t}</a></li>'
        for h, t in [("hvac-contractor.html", "HVAC Contractor"),
                     ("plumber.html", "Plumber"),
                     ("electrician.html", "Electrician"),
                     ("roofing-contractor.html", "Roofing Contractor")])
    return f'''<footer class="site-footer">
  <div class="wrap">
    <div class="cols">
      <div style="max-width:300px">
        <h4>AI Sharc</h4>
        <p>The AI Shopping Health Audit Report Card. We grade how easily AI shopping agents can find, read and trust your business &mdash; and show you the fixes.</p>
        <p class="tag">Bite-sized fixes. Shark-sized results.</p>
      </div>
      <div>
        <h4>Site</h4>
        <ul>
          <li><a href="how-it-works.html">How the audit works</a></li>
          <li><a href="pricing.html">Pricing</a></li>
          <li><a href="sample-cards.html">Sample report cards</a></li>
          <li><a href="{FLOW_ORIGIN}/get-audited">Get audited</a></li>
          <li><a href="faq.html">FAQ</a></li>
        </ul>
      </div>
      <div>
        <h4>Built for home trades &mdash; Texas first</h4>
        <ul>{trade_links}</ul>
      </div>
      <div>
        <h4>Legal</h4>
        <ul>
          <li><a href="privacy.html">Privacy</a></li>
          <li><a href="terms.html">Terms</a></li>
          <li><a href="contact.html">Contact &amp; About</a></li>
        </ul>
      </div>
    </div>
    <div class="legal">
      <address>AI Sharc &middot; PO&nbsp;Box&nbsp;1622, Coppell, TX&nbsp;75019</address>
      <span>&copy; 2026 AI Sharc. All rights reserved.</span>
    </div>
  </div>
</footer>'''

def page(slug, title, desc, body, og_type="website", canon=None):
    canon = canon or (f"{BASE}/{slug}" if slug != "index.html" else BASE + "/")
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32.png">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="AI Sharc">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{BASE}/assets/social-share-1200x630.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{BASE}/assets/social-share-1200x630.png">
<link rel="stylesheet" href="assets/css/main.css">
</head>
<body>
{header(slug)}
<main id="main">
{body}
</main>
{footer()}
</body>
</html>'''
