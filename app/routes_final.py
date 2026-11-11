# AI Sharc — Stage 3 routes: Final card landing, Stripe checkout + webhooks,
# Final card view + PDF, dashboard, cancel, admin reconciliation.
# No JavaScript: every form is a plain POST, every page SSR.
import json
import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import billing, dashboard as dash, mailer, monitoring, pages, pdf, security
from app.config import settings
from app.db import get_db
from app.models import (AuditRequest, DashboardSession, FinalCard, MonitorScan,
                        new_token, utcnow)

router = APIRouter()

log = logging.getLogger("aisharc.routes")


def _request_for_email(db, email):
    return db.scalar(select(AuditRequest).where(
        AuditRequest.email == email, AuditRequest.verified == True)  # noqa: E712
        .order_by(AuditRequest.id.desc()))


def _buyer_email(request, db):
    """The signed-in buyer: dashboard session first, then card session."""
    email = dash.session_email(request, db)
    if email:
        return email
    card_session = request.cookies.get("card_session")
    if card_session:
        card_id = security.unsign_card_id(card_session)
        if card_id:
            req = db.scalar(select(AuditRequest).where(AuditRequest.card_id == card_id))
            if req is not None and req.verified:
                return req.email
    return None


# ------------------------------------------------------------- Final landing page
FINAL_LANDING_BODY = '''
<section class="hero"><div class="wrap"><h1>The Final Report Card</h1>
<p class="lead">The full deep audit of how AI shopping agents see your site &mdash; your complete
graded card, every finding with its source, and your full prioritised fix list.</p>
<p><form action="/final/checkout" method="post">
<button class="btn btn-teal" type="submit">Get my Final Report Card &mdash; $99 introductory</button>
</form></p></div></section>
<section><div class="wrap"><h2>What the Final adds over the free Preliminary</h2>
<div class="grid g3">
<div class="card"><h3>Free Preliminary</h3><ul class="tick">
<li>One overall A&ndash;F grade</li><li>Summary-level findings, each with its source</li>
<li>A starting fix list</li></ul></div>
<div class="card" style="border-color:var(--teal);border-width:2px"><h3>Final Report Card</h3>
<ul class="tick"><li>The complete graded card</li><li>Every finding, each citing the exact page,
wording and date checked</li><li>Your full prioritised fix list</li>
<li>Monitoring for your first 3 months: a monthly re-scan, emailed when your grade changes</li>
<li>Unlimited re-checks within 60 days of your original card</li></ul></div>
<div class="card"><h3>After the included months</h3><ul class="tick">
<li>Optional monitoring at $25/month introductory (regular $30)</li>
<li>Month-to-month, cancel any time yourself in your dashboard</li>
<li>No contract, no phone call to quit</li></ul></div>
</div>
<p class="note" style="margin-top:16px">AI Sharc makes no guarantee of business results. Cards report
what we checked and when; they are not a prediction of traffic, leads or sales. Introductory pricing
applies to the first 500 firms.</p>
<p><a class="btn btn-ghost" href="/sample-cards">See a sample card</a>
<a class="btn btn-teal" href="/get-audited">Start with the free card</a></p>
</div></section>'''


@router.get("/final-card", response_class=HTMLResponse)
def final_landing():
    return HTMLResponse(pages.shell(
        "final-card.html", "The Final Report Card — $99 introductory | AI Sharc",
        "The full deep audit: complete graded card, every finding with its source, full prioritised "
        "fix list, 3 months monitoring and unlimited 60-day re-checks.",
        FINAL_LANDING_BODY))


# ------------------------------------------------------------- checkout
@router.post("/final/checkout")
def start_checkout(request: Request, db: Session = Depends(get_db)):
    email = _buyer_email(request, db)
    if email is None:
        return dash.dash_shell(
            "Sign in first — AI Sharc", "Sign in to buy your Final Report Card.",
            '<section class="hero"><div class="wrap"><h1>Verify first</h1>'
            "<p class=\"lead\">The Final Report Card is bought from your own verified "
            "dashboard. Open the verification link from your email, or "
            '<a href="/get-audited">start with the free card</a>.</p></div></section>',
            status_code=403)
    req_row = _request_for_email(db, email)
    if req_row is None:
        return dash.dash_shell(
            "No card yet — AI Sharc", "Get your free Preliminary card first.",
            '<section class="hero"><div class="wrap"><h1>Get your free card first</h1>'
            "<p class=\"lead\">Buy the Final Report Card after your free Preliminary card: "
            '<a href="/get-audited">Get Audited</a>.</p></div></section>', status_code=404)
    final = db.scalar(select(FinalCard).where(FinalCard.request_id == req_row.id))
    if final is not None:
        return RedirectResponse(f"/final/{final.card_id}", status_code=303)
    base = settings.base_url
    session, price_cents = billing.create_checkout(db, req_row, base)
    db.commit()
    if session is None:
        # Stripe not configured (no STRIPE_API_KEY): show the terms page, never
        # a half-working checkout. Dev-safe and honest.
        return dash.dash_shell(
            "Checkout not configured — AI Sharc",
            "Online checkout isn't switched on for this site yet.",
            '<section class="hero"><div class="wrap"><h1>Checkout isn\'t switched on yet</h1>'
            f"<p class=\"lead\">Your Final Report Card is ${price_cents // 100}. Online "
            "checkout isn't connected on this site yet &mdash; contact us and we'll sort "
            "it out. Nothing has been charged.</p>"
            '<p><a class="btn btn-ghost" href="/contact">Contact us</a></p></div></section>',
            status_code=503)
    return RedirectResponse(session["url"], status_code=303)


@router.get("/billing/complete")
def billing_complete(request: Request, session_id: str = "", db: Session = Depends(get_db)):
    """Landed back from Stripe. If the webhook already granted the card, show
    it; otherwise show a short 'confirming' page (webhook is the source of truth)."""
    email = _buyer_email(request, db)
    req_row = _request_for_email(db, email) if email else None
    final = db.scalar(select(FinalCard).where(
        FinalCard.request_id == req_row.id)) if req_row is not None else None
    if final is not None:
        return RedirectResponse(f"/final/{final.card_id}", status_code=303)
    return dash.dash_shell(
        "Confirming your purchase — AI Sharc", "Your payment is confirming.",
        '<section class="hero"><div class="wrap"><h1>Confirming your purchase</h1>'
        "<p class=\"lead\">Thanks — payment received. Your Final Report Card unlocks "
        "in your dashboard within a minute. If it doesn't appear, contact us.</p>"
        '<p><a class="btn btn-teal" href="/dashboard">Open your dashboard</a></p>'
        "</div></section>")

# ------------------------------------------------------------- webhook
@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    adapter = billing.get_stripe()
    if adapter is None:
        return HTMLResponse("billing not configured", status_code=503)
    try:
        event = adapter.construct_event(payload, sig)
    except Exception:
        # Bad signature: reject loudly, never process.
        return HTMLResponse("invalid signature", status_code=400)
    etype = event.get("type", "")
    eid = event.get("id", "")
    try:
        if etype == "checkout.session.completed":
            final = billing.handle_checkout_completed(db, event)
            if final is not None:
                req_row = db.get(AuditRequest, final.request_id)
                mailer.send_purchase_receipt_email(req_row.email, settings.base_url)
        elif etype.startswith(("invoice.", "customer.subscription.")):
            billing.handle_subscription_event(db, event)
        db.commit()
    except Exception:
        log.warning("webhook handling failed for %s (%s)", eid, etype)
        db.rollback()
        # 500 tells Stripe to retry — the missed-webhook path.
        return HTMLResponse("webhook error", status_code=500)
    return {"received": True}


@router.get("/admin/reconcile")
def admin_reconcile(request: Request, token: str = "", db: Session = Depends(get_db)):
    """Webhook-missed recovery: an admin fetches this form (token query param)
    and posts a Stripe checkout session id; we fetch it from Stripe and replay
    the grant. Auth: ADMIN_TOKEN env."""
    if not settings.admin_token or token != settings.admin_token:
        return HTMLResponse("forbidden", status_code=403)
    return HTMLResponse(f'''<section class="hero"><div class="wrap"><h1>Reconcile a purchase</h1>
<form method="post" action="/admin/reconcile-session">
<input type="hidden" name="token" value="{token}">
<label for="sid">Stripe checkout session id</label>
<input type="text" id="sid" name="session_id" required>
<p><button class="btn btn-teal" type="submit">Replay grant</button></p>
</form></div></section>''')


@router.post("/admin/reconcile-session")
def admin_reconcile_session(request: Request, token: str = Form(""),
                            session_id: str = Form(""), db: Session = Depends(get_db)):
    if not settings.admin_token or token != settings.admin_token:
        return HTMLResponse("forbidden", status_code=403)
    adapter = billing.get_stripe()
    if adapter is None:
        return HTMLResponse("billing not configured", status_code=503)
    try:
        session = adapter.fetch_checkout_session(session_id)
    except Exception:
        return HTMLResponse("session not found", status_code=404)
    event = {"id": f"reconcile_{session_id}", "type": "checkout.session.completed",
             "data": {"object": session}}
    final = billing.handle_checkout_completed(db, event)
    db.commit()
    if final is None:
        return HTMLResponse("could not grant", status_code=422)
    return RedirectResponse(f"/final/{final.card_id}", status_code=303)


# ------------------------------------------------------------- Final card view + PDF
@router.get("/final/{card_id}", response_class=HTMLResponse)
def view_final(card_id: str, request: Request, db: Session = Depends(get_db)):
    email = _buyer_email(request, db)
    final = dash.owned_final(db, email, card_id) if email else None
    if final is None:
        # Final cards are private: wrong or missing session never leaks that
        # the card exists. Same gate shape as the Preliminary card.
        return dash.dash_shell(
            "Sign in first — AI Sharc", "Final cards are private to the firm that bought them.",
            '<section class="hero"><div class="wrap"><h1>Private card</h1>'
            "<p class=\"lead\">Final Report Cards are visible only to the firm that "
            "bought them. <a href=\"/dashboard\">Sign in to your dashboard</a> to view "
            "yours.</p></div></section>", status_code=403)
    req_row = db.get(AuditRequest, final.request_id)
    status = billing.subscription_status(final)
    note = ""
    scans = db.scalars(select(MonitorScan).where(MonitorScan.final_card_id == card_id)
                       .order_by(MonitorScan.id.desc())).all()
    if scans:
        s = scans[0]
        note = (f"Latest re-scan: {s.scanned_at:%b %d, %Y}"
                + (f" — grade changed from {s.previous_grade} to {s.grade}." if s.grade_changed else "."))
    body = f'''<section class="hero"><div class="wrap"><h1>Your Final Report Card</h1>
<p class="lead">The full audit: every finding with its source, and your complete prioritised fix list.</p>
<p><a class="btn btn-teal" href="/final/{card_id}/pdf">Download PDF</a>
<a class="btn btn-ghost" href="/dashboard">Back to dashboard</a></p></div></section>
<section><div class="wrap">{pages.render_final_card(final, req_row, scan_note=note)}
<p class="note">Monitoring: {'active' if status['monitoring_active'] else 'not active'}
&middot; {status['included_months_remaining']} included month(s) remaining &middot;
re-check window {'open' if status['recheck_active'] else 'closed'}.</p>
</div></section>'''
    return HTMLResponse(pages.shell(
        "final-card-view.html", "Your Final Report Card — AI Sharc",
        "Your Final Report Card: every finding with source and your full fix list.",
        body))


@router.get("/final/{card_id}/pdf")
def final_pdf(card_id: str, request: Request, db: Session = Depends(get_db)):
    email = _buyer_email(request, db)
    final = dash.owned_final(db, email, card_id) if email else None
    if final is None:
        return dash.dash_shell(
            "Sign in first — AI Sharc", "PDFs are private to the firm that bought the card.",
            '<section class="hero"><div class="wrap"><h1>Private download</h1>'
            "<p class=\"lead\">PDF downloads are limited to the firm that bought the "
            "card. <a href=\"/dashboard\">Sign in to your dashboard</a>.</p></div></section>",
            status_code=403)
    req_row = db.get(AuditRequest, final.request_id)
    doc = pdf.pdf_pdf_document(pages.render_final_card(final, req_row))
    try:
        data = pdf.card_pdf_bytes(doc)
    except Exception:
        return dash.dash_shell(
            "Download problem — AI Sharc", "The PDF could not be generated.",
            '<section class="hero"><div class="wrap"><h1>Download problem</h1>'
            "<p class=\"lead\">The PDF couldn't be generated right now. Try again in a "
            "few minutes, or contact us.</p></div></section>", status_code=503)
    return Response(data, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="aisharc-final-{card_id}.pdf"'})


# ------------------------------------------------------------- dashboard
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_home(request: Request, db: Session = Depends(get_db)):
    email = dash.session_email(request, db)
    if email is None:
        return dash.dash_shell(
            "Sign in — AI Sharc dashboard",
            "One-click sign-in: we email you a link, no password.",
            '''<section class="hero"><div class="wrap"><h1>Your dashboard</h1>
<p class="lead">Your Report Cards, PDFs, monitoring and billing in one place. Sign in with your
business email — we email you a one-click link, no password.</p></div></section>
<section><div class="wrap"><div class="card form" style="max-width:560px">
<h2 style="font-size:1.3rem">Email me a sign-in link</h2>
<form action="/dashboard/login" method="post">
<label for="email">Business email</label>
<input type="email" id="email" name="email" required>
<p><button class="btn btn-teal" type="submit">Send my link</button></p>
</form>
<p class="note">The email on your original Get Audited request is the one that works.</p>
</div></div></section>''')
    return dash.dash_shell(
        "Dashboard — AI Sharc", "Your Report Cards, subscription status and billing history.",
        dash.history_html(db, email))

@router.post("/dashboard/login")
def dashboard_login(email: str = Form(""), db: Session = Depends(get_db)):
    email = (email or "").strip().lower()
    ok = dash.send_dashboard_login(db, email)
    if not ok:
        return dash.dash_shell(
            "Check your email — AI Sharc", "The email address needs a small fix.",
            '<section class="hero"><div class="wrap"><h1>One thing to fix</h1>'
            "<p class=\"lead\">Please enter a valid email address.</p></div></section>",
            status_code=422)
    return dash.dash_shell(
        "Check your email — AI Sharc", "Your dashboard sign-in link is on its way.",
        '<section class="hero"><div class="wrap"><h1>Check your email</h1>'
        "<p class=\"lead\">If that email has an AI Sharc account, a one-click sign-in "
        "link is on its way. It works once and expires in 30 minutes.</p>"
        "</div></section>")


@router.get("/dashboard/login/{token}")
def dashboard_login_token(token: str, db: Session = Depends(get_db)):
    sess = db.scalar(select(DashboardSession).where(DashboardSession.token == token))
    if sess is None or not sess.is_valid():
        return dash.dash_shell(
            "Link expired — AI Sharc", "This sign-in link has been used or expired.",
            '<section class="hero"><div class="wrap"><h1>This link has been used or expired</h1>'
            "<p class=\"lead\">Request a fresh one from the "
            '<a href="/dashboard">dashboard sign-in page</a>.</p></div></section>',
            status_code=410)
    sess.used_at = utcnow()
    db.commit()
    resp = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie("dash_session", sess.token,
                    max_age=settings.card_session_ttl_seconds, httponly=True,
                    samesite="lax", secure=settings.base_url.startswith("https"))
    return resp


# ------------------------------------------------------------- self-serve cancel
@router.post("/dashboard/cancel")
def dashboard_cancel(request: Request, final_card_id: str = Form(""),
                     db: Session = Depends(get_db)):
    email = dash.session_email(request, db)
    if email is None:
        return dash.dash_shell(
            "Sign in first — AI Sharc", "Sign in to manage your subscription.",
            '<section class="hero"><div class="wrap"><h1>Sign in first</h1>'
            "<p class=\"lead\"><a href=\"/dashboard\">Sign in to your dashboard</a> to "
            "manage your subscription.</p></div></section>", status_code=403)
    final = dash.owned_final(db, email, final_card_id)
    if final is None:
        return dash.dash_shell(
            "Not found — AI Sharc", "That card isn't on your account.",
            '<section class="hero"><div class="wrap"><h1>Not found</h1>'
            "<p class=\"lead\">That Report Card isn't on your account.</p></div></section>",
            status_code=404)
    if final.canceled_at is not None:
        return RedirectResponse("/dashboard", status_code=303)
    # Cancel any live Stripe subscription, then flip local state.
    adapter = billing.get_stripe()
    if adapter is not None and final.stripe_subscription_id:
        try:
            adapter.cancel_subscription(final.stripe_subscription_id)
        except Exception:
            log.exception("stripe cancel failed for %s", final.stripe_subscription_id)
    final.subscription_active = False
    final.canceled_at = utcnow()
    req_row = db.get(AuditRequest, final.request_id)
    db.add(billing.BillingEvent(request_id=final.request_id, final_card_id=final.card_id,
                                stripe_event_id=f"cancel_{final.card_id}_{final.canceled_at.timestamp():.0f}",
                                stripe_type="customer.subscription.canceled",
                                description="Monitoring canceled by customer"))
    db.flush()
    db.commit()
    mailer.send_cancel_confirmation_email(email, req_row.normalized_domain)
    from app import security
    security.emit(db, "monitoring_canceled", request_id=final.request_id, card_id=final.card_id)
    db.commit()
    return RedirectResponse("/dashboard", status_code=303)


# ------------------------------------------------------------- admin: run monitoring now
@router.get("/admin/run-monitoring")
def run_monitoring(request: Request, token: str = "", db: Session = Depends(get_db)):
    """Cron entry point: run all due monitoring scans. Auth: ADMIN_TOKEN env."""
    if not settings.admin_token or token != settings.admin_token:
        return HTMLResponse("forbidden", status_code=403)
    from app import scanner
    n = monitoring.scan_all_due(db, scanner)
    db.commit()
    return {"scanned": n}
