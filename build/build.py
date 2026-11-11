# AI Sharc — build script: assembles all static pages from layout + content modules.
# Usage: python3 -m build.build  (from repo root)  → writes site/*.html
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build.layout import page
from build import content_pages as cp
from build import content_trade as ct
from build import content_legal as cl

PAGES = [
    ("index.html", "AI Sharc — Is your store ready for the machines that shop?",
     "Free AI-readiness Report Card for Texas home trades. AI Sharc grades how easily AI shopping agents can find, read and trust your website — and shows you the fixes.",
     cp.home_body),
    ("get-audited.html", "Get Your Free AI Readiness Report Card — AI Sharc",
     "Submit your website and business email. Verify with one click and view your free Preliminary Report Card: your A–F grade, with sourced findings.",
     cp.get_body),
    ("how-it-works.html", "How the AI Sharc Audit Works — Find, Read, Trust",
     "AI Sharc checks your site the way AI shopping agents do: can they find you, read you, trust you? You get a graded A–F Report Card with sourced findings.",
     cp.hiw_body),
    ("pricing.html", "Pricing — Free Preliminary, $99 Final Report Card | AI Sharc",
     "Preliminary Report Card: free, always. Final Report Card: $99 introductory ($149 regular). Monitoring included for months, then $25/mo intro, cancel any time.",
     cp.pricing_body),
    ("faq.html", "FAQ — AI Sharc Report Cards",
     "Answers about the AI Sharc audit: what's checked, Preliminary vs Final Report Cards, pricing, cancellation and privacy — in plain English.",
     cp.faq_body),
    ("sample-cards.html", "Sample Report Cards — AI Sharc",
     "Sample Preliminary Report Cards with dummy data: see the A–F grade and sourced, summary-level findings your AI Sharc card contains.",
     cp.sample_body),
    ("privacy.html", "Privacy Policy — AI Sharc",
     "How AI Sharc handles your data: what we collect, what we never do, email and cookie practices, retention and deletion.",
     cl.privacy_body),
    ("terms.html", "Terms of Service — AI Sharc",
     "Terms for the AI Sharc audit service: what the audit is and isn't, payments, cancellation, sourced findings and our no-guarantee rule.",
     cl.terms_body),
    ("contact.html", "Contact & About — AI Sharc, Coppell TX",
     "About AI Sharc and how to reach us: PO Box 1622, Coppell, TX 75019. The AI Shopping Health Audit Report Card for home trades.",
     cl.contact_body),
]

def main():
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for slug, title, desc, body in PAGES:
        html = page(slug, title, desc, body)
        path = os.path.join(out_dir, slug)
        with open(path, "w") as f:
            f.write(html)
        written.append(slug)
    for html in ct.build_trade_pages():
        slug = html.split('href="')[0]  # not used; slug resolved below
    # trade pages need their slug; rebuild explicitly
    for t in ct.TRADES:
        body = ct.trade_page(t["slug"], t["trade"], t["hero_h1"], t["hero_lead"], t["why"],
                             t["what_looks"], t.get("extra_html", ""), t.get("note", ""))
        with open(os.path.join(out_dir, t["slug"]), "w") as f:
            f.write(page(t["slug"], t["title"], t["desc"], body))
        written.append(t["slug"])
    # sitemap
    urls = []
    for slug, title, desc, body in PAGES:
        loc = "https://aisharc.com/" if slug == "index.html" else f"https://aisharc.com/{slug}"
        urls.append(loc)
    for t in ct.TRADES:
        urls.append(f"https://aisharc.com/{t['slug']}")
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc in urls:
        sm.append(f"  <url><loc>{loc}</loc></url>")
    sm.append("</urlset>")
    with open(os.path.join(out_dir, "sitemap.xml"), "w") as f:
        f.write("\n".join(sm) + "\n")
    with open(os.path.join(out_dir, "robots.txt"), "w") as f:
        f.write("User-agent: *\nAllow: /\nSitemap: https://aisharc.com/sitemap.xml\n")
    print(f"Wrote {len(written)} pages + sitemap.xml + robots.txt to site/:")
    print("  " + ", ".join(sorted(written)))

if __name__ == "__main__":
    main()
