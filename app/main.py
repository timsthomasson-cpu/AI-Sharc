# AI Sharc — FastAPI app. Serves the Stage 1 marketing shell (same build/ output,
# pages byte-identical) plus the dynamic Get Audited flow. No JavaScript: forms
# submit as normal POST, pages are server-rendered HTML.
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import billing, mailer, monitoring, pages, scanner, security
from app.config import settings
from app.db import SessionLocal, get_db, init_db
from app.models import AuditRequest, PreliminaryCard, VerifyToken, new_token, utcnow
from app.routes_final import router as stage3_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_app):
    if not settings.secret_key:
        # Dev-only fallback so sessions work without config; production must
        # set SECRET_KEY (see SETUP.md).
        import secrets
        settings.secret_key = secrets.token_hex(32)
    if settings.stripe_api_key:
        # Monitoring scheduler only in a live-configured app; tests set a stub
        # adapter or no key and call the scan functions directly.
        monitoring.start()
    yield
    monitoring.stop()


app = FastAPI(title="AI Sharc", docs_url=None, redoc_url=None, openapi_url=None,
              lifespan=lifespan)
init_db()
app.include_router(stage3_router)

SITE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
STATIC_PAGES = ["index.html", "how-it-works.html", "pricing.html", "faq.html",
                "sample-cards.html", "privacy.html", "terms.html", "contact.html",
                "hvac-contractor.html", "plumber.html", "electrician.html",
                "roofing-contractor.html"]

BLOCKED_DOMAINS = {"aisharc.com", "www.aisharc.com", "google.com", "www.google.com",
                   "facebook.com", "instagram.com", "x.com", "twitter.com", "youtube.com",
                   "yahoo.com", "gmail.com", "hotmail.com", "outlook.com"}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/")
def home():
    return FileResponse(os.path.join(SITE_DIR, "index.html"))


@app.get("/robots.txt")
def robots():
    return FileResponse(os.path.join(SITE_DIR, "robots.txt"))


@app.get("/sitemap.xml")
def sitemap():
    return FileResponse(os.path.join(SITE_DIR, "sitemap.xml"))


# ------------------------------------------------------------- get audited
@app.get("/get-audited", response_class=HTMLResponse)
def get_audited():
    return FileResponse(os.path.join(SITE_DIR, "get-audited.html"))


@app.post("/get-audited")
def submit_audited(request: Request, url: str = Form(""), email: str = Form(""),
                   hp: str = Form(""), db: Session = Depends(get_db)):
    # Honeypot: any interaction with the hidden field is a bot. Silent 200.
    if hp.strip():
        return HTMLResponse(pages.shell(
            "get-audited.html", "Check your email — AI Sharc",
            "Check your email for your AI Sharc verification link.",
            '<section class="hero"><div class="wrap"><h1>Check your email</h1>'
            "<p class=lead>If your request looks right, a verification link is on its way."
            "</p></div></section>"), status_code=200)

    try:
        domain = security.normalize_domain(url)
    except ValueError as e:
        return HTMLResponse(pages.shell(
            "get-audited.html", "Check your website address — AI Sharc",
            "The website address you entered needs a small fix.",
            _form_page_error("Please enter your website address, like https://yourbusiness.com.",
                             url, email)), status_code=422)

    if domain in BLOCKED_DOMAINS:
        return HTMLResponse(pages.shell(
            "get-audited.html", "Check your website address — AI Sharc",
            "That address can't be audited.",
            _form_page_error("That address can't be audited. Enter your own business website.",
                             url, email)), status_code=422)

    email = email.strip().lower()
    if not security.is_valid_email(email):
        return HTMLResponse(pages.shell(
            "get-audited.html", "Check your email — AI Sharc",
            "The email address you entered needs a small fix.",
            _form_page_error("Please enter your business email, like you@yourbusiness.com.",
                             url, email)), status_code=422)

    ip = security.client_ip(request)
    if not security.rate_limit_ok(db, ip, email):
        security.emit(db, "rate_limited", meta=f"ip={ip}")
        db.commit()
        return HTMLResponse(pages.shell(
            "get-audited.html", "Too many requests — AI Sharc",
            "Too many requests. Please wait a while and try again.",
            _form_page_error("Too many requests from you recently. Please wait an hour and "
                             "try again.")), status_code=429)

    req_row = AuditRequest(url=url.strip(), normalized_domain=domain, email=email,
                           remote_ip=ip)
    db.add(req_row)
    db.flush()

    token = new_token()
    from app.models import VerifyToken as VT
    db.add(VT(request_id=req_row.id, token=token,
              expires_at=utcnow() + __import__("datetime").timedelta(
                  minutes=settings.verify_token_ttl_minutes)))
    db.flush()

    verify_url = f"{settings.base_url}/verify/{token}"
    mailer.send_verification_email(email, verify_url)
    security.emit(db, "submit", request_id=req_row.id)
    db.commit()

    return HTMLResponse(pages.shell(
        "get-audited.html", "Check your email — AI Sharc",
        "One click in your email unlocks your free Preliminary Report Card.",
        '<section class="hero"><div class="wrap">'
        "<h1>Check your email</h1>"
        f'<p class="lead">We sent a one-click verification link to <strong>'
        f'{email}</strong>. Click it and your Preliminary Report Card unlocks — '
        "free, always. The link works once and expires soon, so open it soon.</p>"
        '<p><a class="btn btn-ghost" href="/how-it-works">How the audit works</a></p>'
        "</div></section>"))


def _form_page_error(message, url="", email=""):
    import html as _h
    return f'''<section class="hero"><div class="wrap"><h1>One thing to fix</h1></div></section>
<section><div class="wrap"><div class="card form" style="max-width:560px">
<h2 style="font-size:1.3rem">Submit your site</h2>
<p class="note" style="color:#b3362c;font-weight:600">{message}</p>
<form action="/get-audited" method="post">
  <label for="url">Your website address</label>
  <input type="url" id="url" name="url" value="{_h.escape(url or "")}" required>
  <label for="email">Business email</label>
  <input type="email" id="email" name="email" value="{_h.escape(email or "")}" required>
  <p style="margin:8px 0"><label style="font-weight:400"><input type="checkbox" name="hp" class="hp" tabindex="-1" autocomplete="off"> Leave this box unchecked</label></p>
  <p><button class="btn btn-teal" type="submit">Request my free Report Card</button></p>
</form>
<p class="note">Double-check the email: we send a verification link there, and your card unlocks
after you click it.</p>
</div></div></section>'''


# ------------------------------------------------------------- verify (double opt-in)
@app.get("/verify/{token}", response_class=HTMLResponse)
def verify(token: str, request: Request, db: Session = Depends(get_db)):
    row = db.scalar(select(VerifyToken).where(VerifyToken.token == token))
    generic = pages.shell(
        "get-audited.html", "Verification link — AI Sharc",
        "This verification link has been used or has expired.",
        '<section class="hero"><div class="wrap"><h1>This link has been used or expired</h1>'
        '<p class="lead">Each verification link works once. Submit again on the '
        '<a href="/get-audited">Get Audited</a> page and we\'ll email a fresh link.</p>'
        "</div></section>")

    if row is None or not row.is_valid():
        return HTMLResponse(generic, status_code=404 if row is None else 410)

    req_row = db.get(AuditRequest, row.request_id)
    if req_row is None:
        return HTMLResponse(generic, status_code=404)

    row.used_at = utcnow()
    if not req_row.verified:
        req_row.verified = True
        req_row.verified_at = utcnow()

    card = db.scalar(select(PreliminaryCard).where(
        PreliminaryCard.request_id == req_row.id))
    if card is None:
        grade, headline, findings = scanner.scan_site(req_row.url)
        card = PreliminaryCard(
            card_id=security.new_card_id(), request_id=req_row.id,
            grade=grade, headline=headline, findings_json=json.dumps(findings))
        db.add(card)
        req_row.card_id = card.card_id
        db.flush()
        security.emit(db, "verified", request_id=req_row.id, card_id=card.card_id)
    db.commit()

    resp = RedirectResponse(f"/card/{card.card_id}", status_code=303)
    if security.card_sessions_enabled():
        resp.set_cookie("card_session", security.sign_card_id(card.card_id),
                        max_age=settings.card_session_ttl_seconds, httponly=True,
                        samesite="lax", secure=settings.base_url.startswith("https"))
    return resp


# ------------------------------------------------------------- card viewer
@app.get("/card/{card_id}", response_class=HTMLResponse)
def view_card(card_id: str, request: Request, db: Session = Depends(get_db)):
    req_row = db.scalar(select(AuditRequest).where(AuditRequest.card_id == card_id))
    card = db.scalar(select(PreliminaryCard).where(PreliminaryCard.card_id == card_id))
    if req_row is None or card is None:
        return HTMLResponse(pages.shell(
            "get-audited.html", "Report Card not found — AI Sharc",
            "That Report Card link doesn't exist.",
            '<section class="hero"><div class="wrap"><h1>Card not found</h1>'
            "<p class=lead>Check the link, or submit again on the "
            '<a href="/get-audited">Get Audited</a> page.</p></div></section>'),
            status_code=404)
    # Magic-link gate: only a session cookie issued at verification (a signed
    # card id) unlocks the card. An invalid or missing cookie never falls
    # through — re-verify to get a fresh link.
    session = request.cookies.get("card_session")
    if not session or security.unsign_card_id(session) != card_id:
        return HTMLResponse(pages.shell(
            "get-audited.html", "Verify first — AI Sharc",
            "Open the verification link from your email to view your Report Card.",
            '<section class="hero"><div class="wrap"><h1>Verify first</h1>'
            "<p class=lead>Your card unlocks from the verification link in your email. "
            "It works once &mdash; if you've used it, submit again on the "
            '<a href="/get-audited">Get Audited</a> page.</p></div></section>'),
            status_code=403)

    # 10 views per firm per query — the ledger.
    if security.views_used(db, req_row.id) >= settings.card_view_limit:
        return HTMLResponse(pages.shell(
            "get-audited.html", "View limit reached — AI Sharc",
            "This Preliminary Report Card has been viewed the maximum 10 times per query.",
            '<section class="hero"><div class="wrap"><h1>View limit reached</h1>'
            "<p class=lead>A Preliminary Report Card can be viewed up to 10 times per "
            "query. Need it again? Submit a fresh request on the "
            '<a href="/get-audited">Get Audited</a> page.</p></div></section>'),
            status_code=429)

    security.record_view(db, req_row.id, card_id)
    security.emit(db, "preliminary_viewed", request_id=req_row.id, card_id=card_id)
    db.commit()

    remaining = security.views_remaining(db, req_row.id)
    body = f'''<section class="hero"><div class="wrap"><h1>Your Preliminary Report Card</h1>
<p class="lead">Free, always. Every finding cites its source and the date we checked it.</p></div></section>
<section><div class="wrap">
{pages.render_card(card, req_row)}
<p class="note">Views left for this card: {remaining} of {settings.card_view_limit}.
The full line-by-line detail of an audit is only on a firm's own Final Report Card &mdash;
we don't publish the scoring behind it.</p>
<p><a class="btn btn-teal" href="/pricing">See the Final Report Card</a></p>
</div></section>'''
    html = pages.shell("card-view.html", "Your Preliminary Report Card — AI Sharc",
                       "Your free Preliminary Report Card: your A–F grade, with sourced findings.",
                       body,
                       canon=f"{settings.base_url}/card/{card_id}")
    return HTMLResponse(html)


# ------------------------------------------------------------- static marketing shell
@app.get("/{page_name}", response_class=HTMLResponse)
def static_page(page_name: str):
    if page_name in STATIC_PAGES:
        return FileResponse(os.path.join(SITE_DIR, page_name))
    target = page_name if page_name.endswith(".html") else page_name + ".html"
    if target in STATIC_PAGES:
        return RedirectResponse("/" + target, status_code=301)
    return HTMLResponse(pages.shell(
        "404.html", "Page not found — AI Sharc",
        "That page doesn't exist.",
        '<section class="hero"><div class="wrap"><h1>Page not found</h1>'
        '<p class="lead">Try the <a href="/">home page</a>, or get your free '
        'Report Card on the <a href="/get-audited">Get Audited</a> page.</p>'
        "</div></section>"), status_code=404)

