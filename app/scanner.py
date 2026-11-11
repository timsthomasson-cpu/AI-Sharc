# AI Sharc — Preliminary scan. Plain-HTTP checks an AI shopping agent would do:
# can it FIND contact info, READ services and service area as text, TRUST the
# site (clickable phone, consistent details). Findings are summary-level only:
# each carries a source URL and the date checked. No scoring internals here.
import datetime as dt

import httpx
from bs4 import BeautifulSoup

UA = "AISharcPreliminary/1.0 (+https://aisharc.com)"
CHECK_DATE = dt.date.today().isoformat()


def _get(client, base, path):
    try:
        r = client.get(base + path, follow_redirects=True, timeout=8)
        if r.status_code == 200 and "text/html" in (r.headers.get("content-type", "")):
            return r.text, r.url
    except httpx.HTTPError:
        pass
    return None, None


def _text_or_none(html):
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup


def _find_phone(text):
    import re
    m = re.search(r"\(?\b\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}\b", text or "")
    return m.group(0) if m else None


def scan_site(url):
    """Returns (grade, headline, findings list of dicts)."""
    findings = []
    base = url.rstrip("/")

    def add(ok, title, detail, source):
        findings.append({
            "title": title,
            "detail": detail,
            "source": f"Source: {source} · checked {CHECK_DATE}",
            "ok": ok,
        })

    try:
        with httpx.Client(headers={"User-Agent": UA}) as client:
            home_html, _ = _get(client, base, "/")
            contact_html, contact_url = _get(client, base, "/contact")
    except httpx.HTTPError:
        return "F", "We couldn't reach your site to check it.", [
            {"title": "Site unreachable",
             "detail": "We tried to open your homepage over plain HTTP and couldn't. "
                       "AI agents hit the same wall.",
             "source": f"Source: {base} · checked {CHECK_DATE}", "ok": False}]

    if home_html is None:
        return "F", "We couldn't read your homepage.", [
            {"title": "Homepage not readable",
             "detail": "Your homepage didn't return a readable page. AI agents can't "
                       "read what they can't open.",
             "source": f"Source: {base} · checked {CHECK_DATE}", "ok": False}]

    soup = _text_or_none(home_html)
    text = soup.get_text(" ", strip=True)

    # 1. Services readable as text
    words = [w for w in ("air conditioning", "heating", "hvac", "repair", "installation",
                         "plumbing", "electric", "roofing", "maintenance") if w in text.lower()]
    add(bool(words), "Services described in text" if words else "Services are not readable text",
        (f"Your pages name what you sell in text, so an AI agent can quote it."
         if words else
         "We couldn't find what you sell written as plain text on your homepage. "
         "Machines can't read services that live only in images or menus."),
        base + "/")

    # 2. Service area in text
    area = any(k in text.lower() for k in ("serving", "service area", "areas we serve",
                                           "texas", "tx,", " tx "))
    add(area, "Service area stated in text" if area else "Service area not stated in text",
        ("Where you work is written on the page, so agents can match you to nearby customers."
         if area else
         "We couldn't find the towns or region you serve written as text. Agents can't tell "
         "if you cover the customer's address."),
        base + "/")

    # 3. Clickable phone
    tel_link = soup.find("a", href=True) and any(
        a["href"].startswith("tel:") for a in soup.find_all("a", href=True))
    phone = _find_phone(text)
    add(bool(tel_link and phone), "Phone number is tappable" if tel_link and phone
        else "Phone number isn't tappable",
        ("Your phone number is a tap-to-call link with the number in text."
         if tel_link and phone else
         "We couldn't find your phone number as both text and a tap-to-call link. "
         "Mobile visitors and agents both lose it."),
        base + "/")

    # 4. Contact info findable
    contact_ok = contact_html is not None and (_find_phone(_text_or_none(contact_html).get_text(" ", strip=True)) or "email" in contact_html.lower() or "@" in contact_html)
    add(contact_ok, "Contact info easy to find" if contact_ok else "Contact info hard to find",
        ("A contact page exists and carries a phone number or email."
         if contact_ok else
         "We couldn't confirm a contact page with a phone number or email at /contact."),
        (contact_url or base + "/contact"))

    # 5. Consistency across pages
    home_phone = phone
    contact_phone = _find_phone(_text_or_none(contact_html).get_text(" ", strip=True)) if contact_html else None
    consistent = bool(home_phone and contact_phone and home_phone == contact_phone)
    add(consistent, "Contact details consistent" if consistent else "Contact details don't match up",
        ("The same phone number appears on your homepage and contact page."
         if consistent else
         "Your homepage and contact page don't show the same phone number. Agents treat "
         "mismatched details as a trust problem."),
        base + "/")

    passes = sum(1 for f in findings if f["ok"])
    grades = {5: "A", 4: "B", 3: "C", 2: "D"}
    grade = grades.get(passes, "F")
    headline = {
        "A": "Strong. AI agents can find, read and trust this site.",
        "B": "Good overall, with a few trust signals to tighten.",
        "C": "The basics are there, but agents can't fully read or trust the site.",
        "D": "Agents can't read what you sell — most of the card is fixes.",
        "F": "Agents will struggle to use this site at all.",
    }[grade]
    return grade, headline, findings
