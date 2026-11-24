# AI Sharc — The Digest: double opt-in subscribe / confirm / unsubscribe, and
# the admin weekly-send endpoint. No JavaScript: plain POST forms, SSR pages
# through the same shell as the rest of the app.
import datetime as dt

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import mailer, pages, security
from app.config import settings
from app.db import get_db
from app.models import DigestSubscriber, FunnelEvent, new_token, utcnow

router = APIRouter()

CONFIRM_TTL_DAYS = 30

_USED_OR_EXPIRED_BODY = (
    '<section class="hero"><div class="wrap"><h1>This link has been used or expired</h1>'
    "<p class=\"lead\">Each confirmation link works once. Subscribe again on "
    '<a href="/digest/index.html">The Digest</a> page and we\'ll email a fresh '
    "link.</p></div></section>")


def _page(slug, title, desc, body, status_code=200):
    return HTMLResponse(pages.shell(slug, title, desc, body), status_code=status_code)


def _check_email_page(email=""):
    who = (f'<strong>{security.escape_html(email)}</strong>' if email
           else "your email")
    return _page(
        "digest/index.html", "Check your email — AI Sharc",
        "One click in your email confirms your subscription to The Digest.",
        f'''<section class="hero"><div class="wrap"><h1>Check your email</h1>
<p class="lead">We sent a one-click confirmation link to {who}. You're subscribed
to The Digest only after you click it. The link works once and expires in
{CONFIRM_TTL_DAYS} days.</p>
<p><a class="btn btn-ghost" href="/digest/index.html">Back to The Digest</a></p></div></section>''')


def _subscribe_form_page(message):
    import html as _h
    return f'''<section class="hero"><div class="wrap"><h1>One thing to fix</h1></div></section>
<section><div class="wrap"><div class="card form" style="max-width:560px">
<h2 style="font-size:1.3rem">Subscribe to The Digest</h2>
<p class="note" style="color:#b3362c;font-weight:600">{message}</p>
<form action="/digest/subscribe" method="post">
  <label for="email">Your email</label>
  <input type="email" id="email" name="email" required>
  <p style="margin:8px 0"><label style="font-weight:400"><input type="checkbox" name="hp" class="hp" tabindex="-1" autocomplete="off"> Leave this box unchecked</label></p>
  <p><button class="btn btn-teal" type="submit">Subscribe to The Digest</button></p>
</form>
<p class="note">One article a week, every one sourced. Unsubscribe any time with one click.</p>
</div></div></section>'''


def _digest_rate_limit_ok(db, ip, email):
    """Per-IP and per-email hourly caps on subscribe attempts. Same shape as
    the get-audited limiter; attempts are logged as funnel events."""
    cutoff = utcnow() - dt.timedelta(hours=1)
    ip_count = len(db.scalars(select(FunnelEvent.id).where(
        FunnelEvent.event == "digest_subscribe", FunnelEvent.meta == f"ip={ip}",
        FunnelEvent.created_at > cutoff)).all())
    if ip_count >= settings.submit_rate_per_ip_hour:
        return False
    em_count = len(db.scalars(select(FunnelEvent.id).where(
        FunnelEvent.event == "digest_subscribe", FunnelEvent.meta == f"email={email}",
        FunnelEvent.created_at > cutoff)).all())
    return em_count < settings.submit_rate_per_email_hour


# ------------------------------------------------------------- subscribe
@router.post("/digest/subscribe")
def digest_subscribe(request: Request, email: str = Form(""), hp: str = Form(""),
                     db: Session = Depends(get_db)):
    # Honeypot: any interaction with the hidden field is a bot. Silent 200,
    # no row, no email — same shape as the get-audited honeypot.
    if hp.strip():
        return _check_email_page()

    email = email.strip().lower()
    if not security.is_valid_email(email):
        return _page(
            "digest/index.html", "Check your email — AI Sharc",
            "The email address you entered needs a small fix.",
            _subscribe_form_page("Please enter your email, like you@yourbusiness.com."),
            status_code=422)

    ip = security.client_ip(request)
    if not _digest_rate_limit_ok(db, ip, email):
        return _page(
            "digest/index.html", "Too many requests — AI Sharc",
            "Too many requests. Please wait a while and try again.",
            '<section class="hero"><div class="wrap"><h1>Too many requests</h1>'
            "<p class=\"lead\">Too many subscribe attempts from you recently. Please "
            "wait an hour and try again.</p></div></section>", status_code=429)

    sub = db.scalar(select(DigestSubscriber).where(DigestSubscriber.email == email))
    if sub is None:
        sub = DigestSubscriber(
            email=email, confirmation_token=new_token(),
            confirmation_expires_at=utcnow() + dt.timedelta(days=CONFIRM_TTL_DAYS),
            unsubscribe_token=new_token(), source="digest form")
        db.add(sub)
        db.flush()
        send = True
    elif sub.unsubscribed_at is not None:
        # Resubscribe after unsubscribing: a fresh confirmation is required.
        # The row is reset — they only get email again after confirming.
        sub.unsubscribed_at = None
        sub.confirmed_at = None
        sub.confirmation_token = new_token()
        sub.confirmation_expires_at = utcnow() + dt.timedelta(days=CONFIRM_TTL_DAYS)
        send = True
    elif sub.confirmed_at is None:
        # Still unconfirmed: refresh the token and resend the link.
        sub.confirmation_token = new_token()
        sub.confirmation_expires_at = utcnow() + dt.timedelta(days=CONFIRM_TTL_DAYS)
        send = True
    else:
        # Already confirmed and active: idempotent — no duplicate row, no email.
        send = False

    security.emit(db, "digest_subscribe", meta=f"ip={ip}")
    security.emit(db, "digest_subscribe", meta=f"email={email}")
    if send:
        confirm_url = f"{settings.base_url}/digest/confirm/{sub.confirmation_token}"
        unsub_url = f"{settings.base_url}/digest/unsubscribe/{sub.unsubscribe_token}"
        mailer.send_digest_confirmation(email, confirm_url, unsub_url)
    db.commit()
    return _check_email_page(email)


# ------------------------------------------------------------- confirm (double opt-in)
@router.get("/digest/confirm/{token}")
def digest_confirm(token: str, db: Session = Depends(get_db)):
    sub = db.scalar(select(DigestSubscriber).where(
        DigestSubscriber.confirmation_token == token))
    if sub is None:
        return _page(
            "digest/index.html", "Confirmation link — AI Sharc",
            "This confirmation link has been used or has expired.",
            _USED_OR_EXPIRED_BODY, status_code=404)
    if not sub.confirmation_valid():
        # Used or expired: single-use, same as the verify magic link.
        return _page(
            "digest/index.html", "Confirmation link — AI Sharc",
            "This confirmation link has been used or has expired.",
            _USED_OR_EXPIRED_BODY, status_code=410)

    sub.confirmed_at = utcnow()
    security.emit(db, "digest_confirmed")
    db.commit()
    return _page(
        "digest/index.html", "You're subscribed — AI Sharc",
        "Your subscription to The Digest is confirmed.",
        '<section class="hero"><div class="wrap"><h1>You\'re subscribed</h1>'
        "<p class=\"lead\">Thanks — your subscription to The Digest is confirmed. "
        "One article a week, every one sourced, unsubscribe any time with one "
        "click.</p>"
        '<p><a class="btn btn-teal" href="/digest/index.html">Read The Digest</a></p>'
        "</div></section>")


# ------------------------------------------------------------- unsubscribe
@router.get("/digest/unsubscribe/{token}")
def digest_unsubscribe(token: str, db: Session = Depends(get_db)):
    sub = db.scalar(select(DigestSubscriber).where(
        DigestSubscriber.unsubscribe_token == token))
    if sub is None:
        return _page(
            "digest/index.html", "Unsubscribe link — AI Sharc",
            "This unsubscribe link doesn't exist.",
            '<section class="hero"><div class="wrap"><h1>Link not found</h1>'
            "<p class=\"lead\">This unsubscribe link doesn't exist. Use the link in "
            "the footer of your Digest email.</p></div></section>", status_code=404)

    if sub.unsubscribed_at is None:
        sub.unsubscribed_at = utcnow()
        security.emit(db, "digest_unsubscribed")
        db.commit()
    # Idempotent: an already-unsubscribed token shows the same confirmation.
    return _page(
        "digest/index.html", "You're unsubscribed — AI Sharc",
        "Your subscription to The Digest is cancelled.",
        '<section class="hero"><div class="wrap"><h1>You\'re unsubscribed</h1>'
        "<p class=\"lead\">You won't receive The Digest any more. Changed your "
        "mind? Subscribe again any time on "
        '<a href="/digest/index.html">The Digest</a> page.</p></div></section>')


# ------------------------------------------------------------- admin: weekly send
@router.post("/admin/digest/send")
@router.get("/admin/digest/send")
def admin_digest_send(token: str = "", slug: str = "", db: Session = Depends(get_db)):
    """Cron entry point: email one article to all confirmed, non-unsubscribed
    subscribers. Idempotent per (subscriber, article). Auth: ADMIN_TOKEN env."""
    if not settings.admin_token or token != settings.admin_token:
        return HTMLResponse("forbidden", status_code=403)
    from app import digest_sender
    try:
        result = digest_sender.send_digest_batch(db, slug)
    except ValueError:
        return HTMLResponse("unknown article", status_code=404)
    return result
