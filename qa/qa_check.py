# QA pass: screenshot every page at 1440px and 390px, check links, titles, overlap, JS.
import os, re, json, sys
from playwright.sync_api import sync_playwright

SITE = "file:///root/projects/AI-Sharc/site/"
OUT = "/root/projects/AI-Sharc/qa/screenshots/"
os.makedirs(OUT, exist_ok=True)
PAGES = ["index.html","get-audited.html","how-it-works.html","pricing.html","faq.html",
         "sample-cards.html","privacy.html","terms.html","contact.html",
         "hvac-contractor.html","plumber.html","electrician.html","roofing-contractor.html"]
issues = []
titles, descs, h1s = {}, {}, {}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/local/bin/chromium", args=["--no-sandbox"])
    for slug in PAGES:
        url = SITE + slug
        pg = b.new_page(viewport={"width":1440,"height":900})
        pg.goto(url, wait_until="networkidle")
        # console errors / page errors
        pg.screenshot(path=OUT + slug.replace(".html","") + "-desktop.jpg", quality=80,
                      full_page=True, type="jpeg")
        titles[slug] = pg.title()
        descs[slug] = pg.eval_on_selector("meta[name=description]", "m => m && m.content")
        h1s[slug] = pg.eval_on_selector_all("h1", "els => els.length")
        # link integrity: collect hrefs, check internal file targets + hash targets
        hrefs = pg.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
        pg.close()
        pgm = b.new_page(viewport={"width":390,"height":844})
        pgm.goto(url, wait_until="networkidle")
        # horizontal overflow check on mobile
        overflow = pgm.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        if overflow > 1:
            issues.append(f"{slug}: horizontal overflow {overflow}px at 390px")
        pgm.screenshot(path=OUT + slug.replace(".html","") + "-mobile.jpg", quality=80,
                       full_page=True, type="jpeg")
        pgm.close()
        # link target check
        for h in hrefs:
            if not h: continue
            if h.startswith("http"):
                if "aisharc.com" not in h and "fonts.gstatic" not in h:
                    issues.append(f"{slug}: external link {h}")
                continue
            if h.startswith("#"):
                continue
            target = h.split("#")[0]
            if target and not os.path.exists("/root/projects/AI-Sharc/site/" + target):
                issues.append(f"{slug}: broken link -> {h}")
        # anchor targets within page
        pg2 = b.new_page(viewport={"width":1440,"height":900})
        pg2.goto(url)
        anchors = set()
        for h in hrefs:
            if h and h.startswith("#") and len(h) > 1:
                anchors.add(h[1:])
        ids = pg2.eval_on_selector_all("[id]", "els => els.map(e => e.id)")
        for a in anchors:
            if a not in ids:
                issues.append(f"{slug}: anchor #{a} has no target")
        pg2.close()
    b.close()

# uniqueness checks
if len(set(titles.values())) != len(titles): issues.append("titles not unique")
if len(set(descs.values())) != len(descs): issues.append("descriptions not unique")
for s, n in h1s.items():
    if n != 1: issues.append(f"{s}: {n} H1 tags")
for s, t in titles.items():
    if not t or len(t) > 70: issues.append(f"{s}: title len {len(t)}")
for s, d in descs.items():
    if not d or len(d) > 165: issues.append(f"{s}: desc len {len(d)}")

# no <script> tags anywhere
for slug in PAGES:
    html = open("/root/projects/AI-Sharc/site/" + slug).read()
    if "<script" in html.lower(): issues.append(f"{slug}: contains <script>")
    for bad in ["gate", "threshold", "weight", "critical gate", "40 audit", "20 items", "7 categories", "6 critical"]:
        body = re.sub(r"<[^>]+>", " ", html).lower()
        if bad in body: issues.append(f"{slug}: possible scoring-detail leak: '{bad}'")

print(json.dumps(issues, indent=1) if issues else "ALL CHECKS PASSED")
print(f"{len(PAGES)} pages checked")
