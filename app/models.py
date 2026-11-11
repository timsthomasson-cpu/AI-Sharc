# AI Sharc — database models. No item-level scoring data is ever stored in a
# Preliminary card: only grade + summary-level findings with source and date.
import datetime as dt
import secrets
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def new_token():
    return secrets.token_urlsafe(32)


class AuditRequest(Base):
    """A submission on /get-audited (pre- and post-verification)."""
    __tablename__ = "audit_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(2048))
    normalized_domain: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    card_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remote_ip: Mapped[str] = mapped_column(String(64), default="")

    tokens: Mapped[list["VerifyToken"]] = relationship(back_populates="request")


class VerifyToken(Base):
    """Single-use magic link. Double opt-in: the card only unlocks via this."""
    __tablename__ = "verify_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("audit_requests.id"), index=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    request: Mapped["AuditRequest"] = relationship(back_populates="tokens")

    def is_valid(self):
        exp = self.expires_at
        if exp.tzinfo is None:  # SQLite returns naive UTC
            exp = exp.replace(tzinfo=dt.timezone.utc)
        return self.used_at is None and utcnow() < exp


class CardView(Base):
    """10-per-firm-per-query ledger: one row per card render (view or refresh)."""
    __tablename__ = "card_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("audit_requests.id"), index=True)
    card_id: Mapped[str] = mapped_column(String(64), index=True)
    viewed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FunnelEvent(Base):
    """Server-emitted funnel: submit -> verified -> preliminary_viewed."""
    __tablename__ = "funnel_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    event: Mapped[str] = mapped_column(String(32), index=True)
    card_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    meta: Mapped[str] = mapped_column(Text, default="")


class PreliminaryCard(Base):
    """Result of the Preliminary scan. Summary-level findings only — each
    finding carries a source URL and check date; no item rows, weights,
    thresholds or gate names are stored or rendered."""
    __tablename__ = "preliminary_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("audit_requests.id"), index=True)
    grade: Mapped[str] = mapped_column(String(2))
    headline: Mapped[str] = mapped_column(String(300))
    findings_json: Mapped[str] = mapped_column(Text)  # [{title, detail, source, checked}]
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
