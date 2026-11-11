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


class FinalCard(Base):
    """The purchased, deeper Report Card: every finding with source, plus the
    full prioritised fix list. Same exposure rule as Preliminary — no item
    rows, weights, thresholds or gate names are stored or rendered.
    TODO(audit-spec Rev 6): the Final card layout is Rev 6; the Rev 6 file has
    NOT arrived. This renders from the current card renderer extended with the
    spec's deeper fields; swapping in Rev 6 should be one renderer change in
    app/pages.py (render_final_card) plus this model's stored fields."""
    __tablename__ = "final_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("audit_requests.id"), index=True)
    grade: Mapped[str] = mapped_column(String(2))
    headline: Mapped[str] = mapped_column(String(300))
    findings_json: Mapped[str] = mapped_column(Text)  # [{title, detail, source, ok}]
    fixes_json: Mapped[str] = mapped_column(Text)  # [{title, detail, priority}]
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Purchase bookkeeping
    stripe_session_id: Mapped[str] = mapped_column(String(255), default="")
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), default="")
    stripe_customer_id: Mapped[str] = mapped_column(String(255), default="")
    price_paid_cents: Mapped[int] = mapped_column(Integer, default=0)
    monitoring_months: Mapped[int] = mapped_column(Integer, default=3)
    monitoring_started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow)
    # Includes $0 months while covered by purchase; after that $25/$30 per scan.
    monthly_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    subscription_active: Mapped[bool] = mapped_column(Boolean, default=True)
    canceled_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    last_scan_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    @property
    def monitoring_ends_at(self):
        import datetime as _dt
        start = self.monitoring_started_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=_dt.timezone.utc)
        return start + _dt.timedelta(days=30 * self.monitoring_months)

    def included_months_remaining(self):
        """Whole months of included monitoring left (0 after expiry)."""
        import datetime as _dt
        now = utcnow()
        if now >= self.monitoring_ends_at:
            return 0
        elapsed_days = (now - self.monitoring_started_at.replace(
            tzinfo=dt.timezone.utc) if self.monitoring_started_at.tzinfo is None
            else now - self.monitoring_started_at).days
        # Month 1 is the purchase month itself: days 0-29 are month 1, so at
        # day 0 all included months are still ahead.
        used = min(self.monitoring_months, elapsed_days // 30)
        return max(0, self.monitoring_months - used)

    def recheck_window_ends_at(self):
        import datetime as _dt
        start = self.created_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=_dt.timezone.utc)
        return start + _dt.timedelta(days=60)

    def recheck_window_active(self):
        return utcnow() <= self.recheck_window_ends_at()


class BillingEvent(Base):
    """Stripe event log: receipts, subscription lifecycle, cancellations.
    Powers the dashboard billing history and the webhook-missed reconciliation."""
    __tablename__ = "billing_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    final_card_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stripe_event_id: Mapped[str] = mapped_column(String(255), unique=True)
    stripe_type: Mapped[str] = mapped_column(String(64), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="usd")
    description: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    raw_json: Mapped[str] = mapped_column(Text, default="")


class PurchaseCounter(Base):
    """Simple counter for the first-500 introductory price rule: one row."""
    __tablename__ = "purchase_counter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchases: Mapped[int] = mapped_column(Integer, default=0)


class MonitorScan(Base):
    """One monthly monitoring re-scan of a Final card's site."""
    __tablename__ = "monitor_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    final_card_id: Mapped[str] = mapped_column(String(64), index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("audit_requests.id"), index=True)
    grade: Mapped[str] = mapped_column(String(2))
    headline: Mapped[str] = mapped_column(String(300))
    findings_json: Mapped[str] = mapped_column(Text)
    fixes_json: Mapped[str] = mapped_column(Text)
    previous_grade: Mapped[str | None] = mapped_column(String(2), nullable=True)
    grade_changed: Mapped[bool] = mapped_column(Boolean, default=False)
    scanned_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DashboardSession(Base):
    """Magic-link dashboard sessions. Email = identity, no passwords."""
    __tablename__ = "dashboard_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def is_valid(self):
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=dt.timezone.utc)
        return self.used_at is None and utcnow() < exp
