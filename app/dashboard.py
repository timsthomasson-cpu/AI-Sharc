# AI Sharc — dashboard: magic-link sessions (same pattern as Stage 2's card
# session), report card history, PDF download, subscription status, self-serve
# cancel with confirmation email, billing history. Final cards and PDFs are
# visible ONLY to the purchasing firm — sessions are per-email, and every
# route re-checks ownership.
import datetime as dt

from fastapi import Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import billing, mailer, security
from app.config import settings
from app.db import get_db
from app.models import (AuditRequest, DashboardSession, FinalCard, PreliminaryCard,
                        MonitorScan, new_token, utcnow)


def _dashboard_url(token):
    return f"{settings.base_url}/dashboard/login/{token}"


def send_dashboard_login(db, email):
    """Create a single-use magic link and email it. Always returns True; the
    page copy never reveals whether the email exists (no account enumeration)."""
    email = email.strip().lower()
    if not security.is_valid_email(email):
        return False
    sess = DashboardSession(token=new_token(), email=email,
                            expires_at=utcnow() + dt.timedelta(minutes=30))
    db.add(sess)
    db.commit()
    mailer.send_dashboard_login_email(email, _dashboard_url(sess.token))
    return True


def session_email(request, db):
    """The signed-in email, or None. Token is a random secret, not derivable.
    The login LINK is single-use (used_at marks the link consumed); the
    resulting dashboard session stays valid until it expires."""
    raw = request.cookies.get("dash_session")
    if not raw:
        return None
    sess = db.scalar(select(DashboardSession).where(DashboardSession.token == raw))
    if sess is None:
        return None
    exp = sess.expires_at
    if exp.tzinfo is None:
        import datetime as dt
        exp = exp.replace(tzinfo=dt.timezone.utc)
    if utcnow() >= exp:
        return None
    # Only the owner of this token may use it: the token was issued to an
    # email and consumed by whoever clicked the link — the cookie holder.
    # Sessions carry no email binding beyond their own row; the row's email
    # is the identity.
    return sess.email


def dash_shell(title, desc, body, email=None, status_code=200):
    from app import pages
    html = pages.shell("dashboard.html", title, desc, body)
    return HTMLResponse(html, status_code=status_code)


def history_html(db, email):
    """Report card history: Preliminary + Final per firm/query, monitor scans,
    with subscription status per Final card."""
    rows = firm_rows(db, email)
    if not rows:
        return ('<section class="hero"><div class="wrap"><h1>Your dashboard</h1>'
                "<p class=\"lead\">Nothing here yet. Submit your site on the "
                '<a href="/get-audited">Get Audited</a> page to get your free '
                "Preliminary Report Card.</p></div></section>")
    parts = ['<section class="hero"><div class="wrap"><h1>Your dashboard</h1>'
             "<p class=\"lead\">Your Report Cards, subscription and billing — "
             "all in one place.</p></div></section><section><div class=\"wrap\">"]
    for req in rows:
        prelim = db.scalar(select(PreliminaryCard).where(
            PreliminaryCard.request_id == req.id))
        final = db.scalar(select(FinalCard).where(FinalCard.request_id == req.id))
        card_html = '<div class="card" style="max-width:640px;margin-bottom:24px">'
        card_html += (f"<h3 style=\"margin-top:0\">{security.escape_html(req.normalized_domain)}"
                      f"</h3><p class=\"note\">Requested {req.created_at:%b %d, %Y}</p>")
        if prelim is not None:
            card_html += (f"<p><strong>Preliminary Report Card</strong> — grade "
                          f"{security.escape_html(prelim.grade)} &middot; "
                          f'<a href="/card/{prelim.card_id}">view card</a></p>')
        if final is not None:
            status = billing.subscription_status(final)
            card_html += (f"<p><strong>Final Report Card</strong> — grade "
                          f"{security.escape_html(final.grade)} &middot; "
                          f'<a href="/final/{final.card_id}">view card</a> &middot; '
                          f'<a href="/final/{final.card_id}/pdf">download PDF</a></p>')
            if status["monitoring_active"]:
                card_html += (f"<p>Monitoring: <strong>active</strong> — "
                              f"{status['included_months_remaining']} included month(s) "
                              f"remaining, through {status['included_ends_at']:%b %d, %Y}.</p>")
            else:
                card_html += ("<p>Monitoring: <strong>not active</strong> — included "
                              "months have ended or monitoring was canceled.</p>")
            if status["recheck_active"]:
                card_html += (f"<p>Re-check window: open through "
                              f"{status['recheck_ends_at']:%b %d, %Y} "
                              "(unlimited re-checks of your site).</p>")
            scans = db.scalars(select(MonitorScan).where(
                MonitorScan.final_card_id == final.card_id)
                .order_by(MonitorScan.id.desc())).all()
            if scans:
                card_html += "<p class=\"note\">Recent re-scans: " + ", ".join(
                    f"{s.scanned_at:%b %d} ({security.escape_html(s.grade)})"
                    + (" — grade changed" if s.grade_changed else "")
                    for s in scans[:3]) + "</p>"
            card_html += cancel_button_html(final)
        else:
            card_html += ('<p><a class="btn btn-teal" href="/final-card">Upgrade to the '
                          "Final Report Card</a></p>")
        card_html += "</div>"
        parts.append(card_html)
    parts.append(billing_history_html(db, email))
    parts.append("</div></section>")
    return "".join(parts)


def cancel_button_html(final):
    if final.canceled_at is not None or not final.subscription_active:
        return ""
    return ('''<form action="/dashboard/cancel" method="post" style="margin-top:8px">
<input type="hidden" name="final_card_id" value="''' + final.card_id + '''">
<p><button class="btn btn-ghost" type="submit">Cancel monitoring</button></p>
<p class="note">Cancels the paid monitoring subscription. Your Final Report Card stays yours.</p>
</form>''')


def billing_history_html(db, email):
    rows = firm_rows(db, email)
    events = []
    for req in rows:
        from app.models import BillingEvent
        events += db.scalars(select(BillingEvent).where(
            BillingEvent.request_id == req.id).order_by(BillingEvent.id.desc())).all()
    if not events:
        return ('<div class="card" style="max-width:640px"><h3>Billing history</h3>'
                "<p class=\"note\">No payments yet.</p></div>")
    items = "".join(
        f"<li>{e.created_at:%b %d, %Y} — {security.escape_html(e.description or e.stripe_type)}"
        + (f" — ${e.amount_cents / 100:.2f}" if e.amount_cents else "")
        + "</li>" for e in events[:20])
    return (f'<div class="card" style="max-width:640px"><h3>Billing history</h3>'
            f"<ul>{items}</ul>"
            '<p class="note">Receipts come from Stripe; this list mirrors them.</p></div>')


def owned_final(db, email, final_card_id):
    """Final card owned by this email only — the cross-firm access guard."""
    finals = db.scalars(select(FinalCard).where(FinalCard.card_id == final_card_id)).all()
    for final in finals:
        req_row = db.get(AuditRequest, final.request_id)
        if req_row is not None and req_row.email == email:
            return final
    return None


def firm_rows(db, email):
    """All verified requests for this email, oldest first — one row per
    firm/query/town. A firm = a request; cards hang off requests."""
    return db.scalars(select(AuditRequest).where(
        AuditRequest.email == email, AuditRequest.verified == True)  # noqa: E712
        .order_by(AuditRequest.id)).all()
