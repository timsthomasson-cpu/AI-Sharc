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
