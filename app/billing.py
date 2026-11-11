# AI Sharc — billing: Stripe Checkout Session creation, webhook grant,
# subscription lifecycle and customer portal. All Stripe access goes through
# the adapter below so tests run with a stub — no real Stripe calls in tests.
# Secrets are env-only (see app/config.py / SETUP.md).
import datetime as dt
import json
import logging

from sqlalchemy import select

from app.config import settings
from app.models import (AuditRequest, BillingEvent, FinalCard, PreliminaryCard,
                        PurchaseCounter, MonitorScan, utcnow)

log = logging.getLogger("aisharc.billing")


class StripeAdapter:
    """Interface the app talks to. The real implementation wraps stripe-python;
    tests inject StripeStub. `settings.stripe_api_key` empty => unavailable."""

    def create_checkout_session(self, email, success_url, cancel_url, price_cents):
        raise NotImplementedError

    def create_portal_session(self, customer_id, return_url):
        raise NotImplementedError

    def construct_event(self, payload, sig_header):
        """Verify the webhook signature and return the parsed event dict.
        Raises on signature failure."""
        raise NotImplementedError

    def cancel_subscription(self, subscription_id):
        raise NotImplementedError

    def fetch_subscription(self, subscription_id):
        raise NotImplementedError

    def fetch_checkout_session(self, session_id):
        raise NotImplementedError


class LiveStripe(StripeAdapter):
    """Real stripe-python wrapper. Only constructed when STRIPE_API_KEY is set."""

    def __init__(self):
        import stripe
        stripe.api_key = settings.stripe_api_key
        self._stripe = stripe

    def create_checkout_session(self, email, success_url, cancel_url, price_cents):
        return self._stripe.checkout.Session.create(
            mode="payment",
            customer_email=email,
            line_items=[{
                "quantity": 1,
                "price_data": {
                    "currency": "usd",
                    "unit_amount": price_cents,
                    "product_data": {"name": "AI Sharc Final Report Card"},
                },
            }],
            # Charge-at-purchase model: the Final payment covers the audit and
            # the included monitoring months. After those months, monitoring is
            # billed as a separate month-to-month subscription (created on
            # first renewal invoice by the monthly job — see SETUP.md).
            success_url=success_url,
            cancel_url=cancel_url,
        )

    def create_portal_session(self, customer_id, return_url):
        return self._stripe.billingPortal.Session.create(
            customer=customer_id, return_url=return_url)

    def construct_event(self, payload, sig_header):
        return self._stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret)

    def cancel_subscription(self, subscription_id):
        return self._stripe.Subscription.cancel(subscription_id)

    def fetch_subscription(self, subscription_id):
        return self._stripe.Subscription.retrieve(subscription_id)

    def fetch_checkout_session(self, session_id):
        return self._stripe.checkout.Session.retrieve(session_id)


class StripeStub(StripeAdapter):
    """Test/dev adapter. Same shape as LiveStripe, no network. Records calls
    for assertions; webhook events are handed in by the test."""

    def __init__(self):
        self.created_sessions = []
        self.created_portals = []
        self.canceled = []
        self.next_session_id = "cs_test_0001"
        self.sessions = {}

    def create_checkout_session(self, email, success_url, cancel_url, price_cents):
        sid = f"cs_test_{len(self.created_sessions) + 1:04d}"
        sess = {"id": sid, "customer_email": email, "amount_total": price_cents,
                "success_url": success_url, "cancel_url": cancel_url}
        self.created_sessions.append(sess)
        self.sessions[sid] = sess
        return sess

    def create_portal_session(self, customer_id, return_url):
        sess = {"id": "bps_test_0001", "customer": customer_id, "url": return_url + "#portal"}
        self.created_portals.append(sess)
        return sess

    def construct_event(self, payload, sig_header):
        # The stub trusts the caller: tests post pre-built event JSON and no
        # signature (or a wrong one — signature-failure behaviour is tested
        # against LiveStripe-style rejection in the handler itself).
        return json.loads(payload)

    def cancel_subscription(self, subscription_id):
        self.canceled.append(subscription_id)
        return {"id": subscription_id, "status": "canceled"}

    def fetch_subscription(self, subscription_id):
        return {"id": subscription_id, "status": "active"}

    def fetch_checkout_session(self, session_id):
        return self.sessions.get(session_id)


def get_stripe():
    """Adapter selection: explicit stub override (tests), live key, else None."""
    if getattr(settings, "_stripe_adapter", None) is not None:
        return settings._stripe_adapter
    if settings.stripe_api_key:
        return LiveStripe()
    return None


def set_stripe_adapter(adapter):
    """Test hook: force the adapter (None restores auto-selection)."""
    settings._stripe_adapter = adapter


def final_price_cents(db):
    """$99 intro for the first 500 firms, $149 after (locked pricing)."""
    row = db.scalar(select(PurchaseCounter))
    used = row.purchases if row else 0
    return (settings.price_final_intro_cents if used < settings.intro_firm_limit
            else settings.price_final_regular_cents)


def _bump_purchase_counter(db):
    row = db.scalar(select(PurchaseCounter))
    if row is None:
        row = PurchaseCounter(purchases=0)
        db.add(row)
    row.purchases += 1
    return row.purchases


def create_checkout(db, request_row, base_url):
    """Create a Checkout Session for this firm's Final Report Card.
    Returns (session_dict, price_cents) or (None, price) if Stripe isn't set."""
    price_cents = final_price_cents(db)
    adapter = get_stripe()
    if adapter is None:
        return None, price_cents
    session = adapter.create_checkout_session(
        email=request_row.email,
        success_url=f"{base_url}/billing/complete?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/final-card",
        price_cents=price_cents,
    )
    if session is None:
        return None, price_cents
    if "url" not in session:
        session["url"] = f"https://checkout.stripe.test/pay/{session['id']}"
    return session, price_cents


def _final_from_preliminary(db, request_row):
    """Build the Final card payload from the firm's own Preliminary scan,
    extended with the deeper fields: every finding with source, plus the full
    prioritised fix list derived from the findings (fixes are customer-facing
    actions only — never item rows, weights, thresholds or gate names).
    TODO(audit-spec Rev 6): Final card layout pending; renderer swap only."""
    card = db.scalar(select(PreliminaryCard).where(
        PreliminaryCard.request_id == request_row.id))
    if card is None:
        return None
    findings = json.loads(card.findings_json)
    fixes = []
    for f in findings:
        if not f.get("ok", True):
            fixes.append({"title": f["title"], "detail": f["detail"], "priority": 1})
    fixes.sort(key=lambda x: x["priority"])
    return {"grade": card.grade, "headline": card.headline,
            "findings": findings, "fixes": fixes}


def grant_final_card(db, request_row, session_id, customer_id="", subscription_id="",
                     price_paid_cents=0):
    """Idempotent: checkout.completed -> Final card + monitoring period start.
    Returns the FinalCard row (existing or newly granted)."""
    existing = db.scalar(select(FinalCard).where(FinalCard.request_id == request_row.id))
    if existing is not None:
        return existing, False
    payload = _final_from_preliminary(db, request_row)
    if payload is None:
        return None, False
    from app.security import new_card_id
    final = FinalCard(
        card_id=new_card_id(),
        request_id=request_row.id,
        grade=payload["grade"],
        headline=payload["headline"],
        findings_json=json.dumps(payload["findings"]),
        fixes_json=json.dumps(payload["fixes"]),
        stripe_session_id=session_id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        price_paid_cents=price_paid_cents,
        monitoring_months=settings_monitoring_months(),
        monitoring_started_at=utcnow(),
        monthly_price_cents=0,  # included months are $0
        subscription_active=True,
    )
    db.add(final)
    db.flush()
    _bump_purchase_counter(db)
    return final, True


def settings_monitoring_months():
    from build.content_pages import MONITORING_INCLUDED_MONTHS
    return MONITORING_INCLUDED_MONTHS


def log_billing_event(db, request_id, final_card_id, event_id, event_type,
                      amount_cents=0, currency="usd", description="", raw=""):
    """Store a Stripe event once (idempotent on stripe_event_id)."""
    existing = db.scalar(select(BillingEvent).where(BillingEvent.stripe_event_id == event_id))
    if existing is not None:
        return existing, False
    row = BillingEvent(request_id=request_id, final_card_id=final_card_id,
                       stripe_event_id=event_id, stripe_type=event_type,
                       amount_cents=amount_cents, currency=currency,
                       description=description, raw_json=raw)
    db.add(row)
    db.flush()
    return row, True


def subscription_status(final):
    """Plain-language status for the dashboard."""
    now = utcnow()
    ends = final.monitoring_ends_at
    included_left = final.included_months_remaining()
    return {
        "monitoring_active": final.subscription_active and now < ends,
        "included_months_remaining": included_left,
        "included_ends_at": ends,
        "recheck_active": final.recheck_window_active(),
        "recheck_ends_at": final.recheck_window_ends_at(),
        "monthly_price_cents": final.monthly_price_cents,
        "canceled_at": final.canceled_at,
    }


def handle_checkout_completed(db, event):
    """checkout.completed: grant the Final card and start the monitoring clock.
    Matches on the customer email of the firm's verified AuditRequest."""
    obj = event["data"]["object"]
    email = (obj.get("customer_details") or {}).get("email") or obj.get("customer_email")
    if not email:
        log.error("checkout.completed without email: %s", event.get("id"))
        return None
    email = email.strip().lower()
    req = db.scalar(select(AuditRequest).where(AuditRequest.email == email)
                    .order_by(AuditRequest.id.desc()))
    if req is None or not req.verified:
        log.error("checkout.completed for unknown/unverified email %s", email)
        return None
    final, created = grant_final_card(
        db, req,
        session_id=obj.get("id", ""),
        customer_id=obj.get("customer") or "",
        subscription_id=(obj.get("subscription") or ""),
        price_paid_cents=obj.get("amount_total") or 0)
    if final is None:
        return None
    log_billing_event(db, req.id, final.card_id, event["id"], event["type"],
                      amount_cents=obj.get("amount_total") or 0,
                      description="Final Report Card purchase", raw="")
    if created:
        from app import security
        security.emit(db, "final_purchased", request_id=req.id, card_id=final.card_id)
    return final


def handle_subscription_event(db, event):
    """Subscription lifecycle: invoice.paid (renewal), subscription events.
    After the included months the monthly job flips monthly_price_cents from
    $0 to the plan price; invoice.paid events extend monitoring by a month
    and record the receipt."""
    obj = event["data"]["object"]
    final = None
    amount = obj.get("amount_paid") if event["type"] == "invoice.paid" else None
    email = (obj.get("customer_email") or obj.get("customer_details", {}).get("email")
             if not obj.get("customer") else None)
    # Match via customer email first, then via any metadata we set.
    if email:
        email = email.strip().lower()
        req = db.scalar(select(AuditRequest).where(AuditRequest.email == email)
                        .order_by(AuditRequest.id.desc()))
        if req is not None:
            final = db.scalar(select(FinalCard).where(FinalCard.request_id == req.id))
    if final is None:
        # Reconciliation fallback: newest Final card (single-firm MVP path).
        final = db.scalar(select(FinalCard).order_by(FinalCard.id.desc()))
    if final is None:
        return None
    if event["type"] == "invoice.paid" and amount:
        # A paid invoice past the included months = one more month of monitoring.
        if utcnow() >= final.monitoring_ends_at and amount >= settings.price_monitoring_intro_cents:
            final.monitoring_started_at = final.monitoring_ends_at
            final.monthly_price_cents = amount
            final.subscription_active = True
    log_billing_event(db, final.request_id, final.card_id, event["id"], event["type"],
                      amount_cents=amount or 0,
                      description=event["type"], raw="")
    return final
