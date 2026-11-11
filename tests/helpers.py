# AI Sharc — test helpers: reach into the DB used by the app under test.
"""Helpers read the latest rows created by the client's requests.

The app under test uses a dependency-overridden session factory bound to one
in-memory SQLite engine (created per fixture in conftest); tests reach the
same data through app.db.SessionLocal-style access via the override target.
"""
import datetime as dt

from app.models import AuditRequest, FunnelEvent, PreliminaryCard, VerifyToken, utcnow

_STATE = {"session_factory": None}


def set_session_factory(factory):
    _STATE["session_factory"] = factory


def last_verify_token():
    db = _STATE["session_factory"]()
    try:
        rows = db.query(VerifyToken).order_by(VerifyToken.id.desc()).all()
        return rows[0].token
    finally:
        db.close()


def expire_last_token():
    db = _STATE["session_factory"]()
    try:
        row = db.query(VerifyToken).order_by(VerifyToken.id.desc()).first()
        row.expires_at = utcnow() - dt.timedelta(minutes=1)
        db.commit()
    finally:
        db.close()


def last_card_id_if_any():
    db = _STATE["session_factory"]()
    try:
        row = db.query(PreliminaryCard).order_by(PreliminaryCard.id.desc()).first()
        return row.card_id if row else None
    finally:
        db.close()


def funnel_events():
    db = _STATE["session_factory"]()
    try:
        return db.query(FunnelEvent).order_by(FunnelEvent.id).all()
    finally:
        db.close()


def last_dashboard_token():
    db = _STATE["session_factory"]()
    try:
        rows = db.query(__import__("app.models", fromlist=["DashboardSession"]).DashboardSession).order_by(
            __import__("app.models", fromlist=["DashboardSession"]).DashboardSession.id.desc()).all()
        return rows[0].token if rows else None
    finally:
        db.close()


def set_purchase_count(n):
    from app.models import PurchaseCounter
    db = _STATE["session_factory"]()
    try:
        row = db.query(PurchaseCounter).first()
        if row is None:
            row = PurchaseCounter(purchases=n)
            db.add(row)
        else:
            row.purchases = n
        db.commit()
    finally:
        db.close()


def purchase_count():
    from app.models import PurchaseCounter
    db = _STATE["session_factory"]()
    try:
        row = db.query(PurchaseCounter).first()
        return row.purchases if row else 0
    finally:
        db.close()


def final_card_for(email):
    from app.models import AuditRequest, FinalCard
    db = _STATE["session_factory"]()
    try:
        req = db.query(AuditRequest).filter(AuditRequest.email == email).order_by(
            AuditRequest.id.desc()).first()
        if req is None:
            return None
        return db.query(FinalCard).filter(FinalCard.request_id == req.id).first()
    finally:
        db.close()


def set_monitoring_started(email, days_ago):
    import datetime as dt
    from app.models import AuditRequest, FinalCard
    db = _STATE["session_factory"]()
    try:
        req = db.query(AuditRequest).filter(AuditRequest.email == email).order_by(
            AuditRequest.id.desc()).first()
        final = db.query(FinalCard).filter(FinalCard.request_id == req.id).first()
        final.monitoring_started_at = utcnow() - dt.timedelta(days=days_ago)
        db.commit()
    finally:
        db.close()


def set_created(email, days_ago):
    import datetime as dt
    from app.models import AuditRequest, FinalCard
    db = _STATE["session_factory"]()
    try:
        req = db.query(AuditRequest).filter(AuditRequest.email == email).order_by(
            AuditRequest.id.desc()).first()
        final = db.query(FinalCard).filter(FinalCard.request_id == req.id).first()
        final.created_at = utcnow() - dt.timedelta(days=days_ago)
        db.commit()
    finally:
        db.close()


def cancel_in_db(email):
    from app.models import AuditRequest, FinalCard
    db = _STATE["session_factory"]()
    try:
        req = db.query(AuditRequest).filter(AuditRequest.email == email).order_by(
            AuditRequest.id.desc()).first()
        final = db.query(FinalCard).filter(FinalCard.request_id == req.id).first()
        final.canceled_at = utcnow()
        final.subscription_active = False
        db.commit()
    finally:
        db.close()


def sign_in_dashboard(client, email, monkeypatch):
    """Full dashboard sign-in via magic link. BASE_URL is https so the session
    cookie is marked Secure — a plain-http test client drops it, so set it
    manually the way a real https browser would."""
    sent = []
    import app.mailer as m
    monkeypatch.setattr(m, "send_dashboard_login_email",
                        lambda to, url: sent.append(url))
    r = client.post("/dashboard/login", data={"email": email})
    assert r.status_code == 200, r.text
    r_tok = client.get(sent[0], follow_redirects=False)
    assert r_tok.status_code == 303
    cookie = r_tok.headers.get("set-cookie", "").split(";")[0]
    name, _, value = cookie.partition("=")
    client.cookies.set(name, value)
    return value
