# AI Sharc — helpers: validation, rate limiting, funnel events, card sessions.
import datetime as dt
import hashlib
import hmac
import json
import logging
import re
import secrets
from urllib.parse import urlparse

from fastapi import Request
from sqlalchemy import select

from app.config import settings
from app.models import AuditRequest, CardView, FunnelEvent, utcnow

log = logging.getLogger("aisharc.funnel")

BANNED_PHRASES = [
    "critical gate", "gate name", "weight", "threshold", "scoring rubric",
    "licence register", "item-by-item", "league table", "audit rows",
]


def normalize_domain(url):
    """Return a lowercase host (no scheme, no path) or raise ValueError."""
    u = url.strip()
    if not u:
        raise ValueError("empty url")
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    p = urlparse(u)
    host = (p.hostname or "").lower()
    if not host or "." not in host:
        raise ValueError("not a valid website address")
    if host in ("localhost", "example.com", "example.org", "example.net"):
        raise ValueError("blocked domain")
    return host


def is_valid_email(email):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", (email or "").strip()))


def client_ip(request):
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else request.client.host) if request.client else ""


def rate_limit_ok(db, ip, email):
    """Per-IP and per-email hourly caps on new submissions."""
    cutoff = utcnow() - dt.timedelta(hours=1)
    ip_count = len(db.scalars(select(AuditRequest.id).where(
        AuditRequest.remote_ip == ip, AuditRequest.created_at > cutoff)).all())
    if ip_count >= settings.submit_rate_per_ip_hour:
        return False
    em_count = len(db.scalars(select(AuditRequest.id).where(
        AuditRequest.email == email, AuditRequest.created_at > cutoff)).all())
    return em_count < settings.submit_rate_per_email_hour


def emit(db, event, request_id=None, card_id=None, meta=""):
    """Funnel event: structured log line + events table (Plausible-style)."""
    row = FunnelEvent(request_id=request_id, event=event, card_id=card_id, meta=meta)
    db.add(row)
    db.flush()
    log.info(json.dumps({
        "funnel_event": event, "request_id": request_id, "card_id": card_id,
        "at": row.created_at.isoformat(), "meta": meta}))
    return row


def card_sessions_enabled():
    return bool(settings.secret_key)


def sign_card_id(card_id):
    key = settings.secret_key.encode()
    sig = hmac.new(key, card_id.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{card_id}.{sig}"


def unsign_card_id(value):
    if not card_sessions_enabled() or not value or "." not in value:
        return None
    card_id, sig = value.rsplit(".", 1)
    if hmac.compare_digest(sign_card_id(card_id).rsplit(".", 1)[1], sig):
        return card_id
    return None


def escape_html(s):
    import html as _h
    return _h.escape(s or "")


def new_card_id():
    return uuid_short()


def uuid_short():
    return secrets.token_hex(8)


def views_used(db, request_id):
    return len(db.scalars(select(CardView.id).where(
        CardView.request_id == request_id)).all())


def views_remaining(db, request_id):
    return max(0, settings.card_view_limit - views_used(db, request_id))


def record_view(db, request_id, card_id):
    db.add(CardView(request_id=request_id, card_id=card_id))
