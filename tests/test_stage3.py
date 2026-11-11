# AI Sharc — Stage 3 tests: monetization + account. No real Stripe calls:
# billing.set_stripe_adapter injects a stub; scanner is stubbed in conftest;
# the mailer is the console backend (monkeypatch where a send is asserted).
import datetime as dt
import json

import pytest

from app import billing
from app.models import FinalCard, utcnow


@pytest.fixture(autouse=True)
def stub_stripe(monkeypatch):
    adapter = billing.StripeStub()
    billing.set_stripe_adapter(adapter)
    yield adapter
    billing.set_stripe_adapter(None)


def verified_flow(client, url="https://acme-hvac.example.com",
                  email="owner@acme-hvac.example.com"):
    client.post("/get-audited", data={"url": url, "email": email})
    from tests.helpers import last_verify_token
    token = last_verify_token()
    r2 = client.get(f"/verify/{token}", follow_redirects=False)
    card_id = r2.headers["location"].split("/")[-1]
    cookie = r2.headers.get("set-cookie", "")
    if cookie:
        client.cookies.set("card_session", cookie.split(";")[0].split("=", 1)[1])
    return card_id


def fake_webhook_event(event_id, etype, obj):
    return {"id": event_id, "type": etype, "data": {"object": obj}}


def post_webhook(client, event):
    import json as _json
    return client.post("/stripe/webhook", content=_json.dumps(event),
                       headers={"stripe-signature": "t=1,v1=fake"})


# ---------------------------------------------------------------- landing page

def test_final_landing_page_public(client):
    r = client.get("/final-card")
    assert r.status_code == 200
    assert "Final Report Card" in r.text
    assert "$99" in r.text and "3 months" in r.text and "60 days" in r.text


def test_final_landing_leak_scan(client):
    banned = ["critical gate", "gate name", "weight", "threshold", "scoring rubric",
              "item-by-item", "league table", "licence register", "audit rows"]
    body = client.get("/final-card").text.lower()
    for phrase in banned:
        assert phrase not in body, f"leak: {phrase}"


# ---------------------------------------------------------------- checkout creation

def test_checkout_requires_verified_session(client):
    r = client.post("/final/checkout", follow_redirects=False)
    assert r.status_code == 403
    client.post("/get-audited", data={"url": "https://unv.example.com",
                                      "email": "u@unv.example.com"})
    # not verified: no card_session cookie, still refused
    r = client.post("/final/checkout", follow_redirects=False)
    assert r.status_code == 403


def test_checkout_creates_session_at_intro_price(client, stub_stripe):
    verified_flow(client)
    r = client.post("/final/checkout", follow_redirects=False)
    assert r.status_code == 303
    assert stub_stripe.created_sessions[0]["amount_total"] == 9900
    assert r.headers["location"].startswith("https://checkout.stripe.test/")


def test_pricing_counter_first_500(client, stub_stripe):
    from tests.helpers import set_purchase_count, purchase_count
    verified_flow(client, email="a@f1.example.com")
    r = client.post("/final/checkout", follow_redirects=False)
    assert stub_stripe.created_sessions[-1]["amount_total"] == 9900
    # Firm 500 (counter at 499) still intro; firm 501 (counter at 500) pays regular.
    set_purchase_count(499)
    verified_flow(client, email="b@f2.example.com")
    client.post("/final/checkout", follow_redirects=False)
    assert stub_stripe.created_sessions[-1]["amount_total"] == 9900
    set_purchase_count(500)
    verified_flow(client, email="c@f3.example.com")
    client.post("/final/checkout", follow_redirects=False)
    assert stub_stripe.created_sessions[-1]["amount_total"] == 14900
    set_purchase_count(0)


def test_checkout_without_stripe_config(client, monkeypatch):
    billing.set_stripe_adapter(None)
    verified_flow(client)
    r = client.post("/final/checkout", follow_redirects=False)
    assert r.status_code == 503
    assert "charged" in r.text  # honest: nothing was charged


# ---------------------------------------------------------------- webhook grant

def checkout_event(email="owner@acme-hvac.example.com", amount=9900, event_id="evt_001"):
    return fake_webhook_event(event_id, "checkout.session.completed", {
        "id": "cs_test_123", "customer_email": email,
        "customer_details": {"email": email},
        "customer": "cus_001", "subscription": None,
        "amount_total": amount})


def test_webhook_grants_final_card_and_included_months(client, stub_stripe):
    verified_flow(client)
    r = post_webhook(client, checkout_event())
    assert r.status_code == 200
    from tests.helpers import final_card_for, funnel_events
    final = final_card_for("owner@acme-hvac.example.com")
    assert final is not None
    assert final.monitoring_months == 3
    assert final.monthly_price_cents == 0
    assert final.price_paid_cents == 9900
    kinds = [e.event for e in funnel_events()]
    assert "final_purchased" in kinds


def test_webhook_grant_idempotent(client, stub_stripe):
    verified_flow(client)
    post_webhook(client, checkout_event())
    post_webhook(client, checkout_event(event_id="evt_002"))
    from tests.helpers import final_card_for, purchase_count
    assert purchase_count() == 1
    final = final_card_for("owner@acme-hvac.example.com")
    assert final is not None


def test_webhook_bad_signature_rejected(client, monkeypatch):
    from app import billing as b
    class StrictStub(b.StripeStub):
        def construct_event(self, payload, sig_header):
            if "v1=fake" not in (sig_header or ""):
                raise ValueError("bad signature")
            return json.loads(payload)
    monkeypatch.setattr(b, "get_stripe", lambda: StrictStub())
    r = client.post("/stripe/webhook", content='{"id":"e1","type":"x","data":{"object":{}}}',
                    headers={"stripe-signature": "t=1,v1=WRONG"})
    assert r.status_code == 400


def test_webhook_unknown_email_ignored(client):
    r = post_webhook(client, checkout_event(email="nobody@nowhere.example.com"))
    assert r.status_code == 200
    from tests.helpers import final_card_for
    assert final_card_for("nobody@nowhere.example.com") is None


def test_receipt_email_sent_on_grant(client, monkeypatch):
    sent = []
    import app.mailer as m
    monkeypatch.setattr(m, "send_purchase_receipt_email", lambda *a: sent.append(a))
    verified_flow(client)
    post_webhook(client, checkout_event())
    assert len(sent) == 1


# ---------------------------------------------------------------- 60-day re-check window

def test_recheck_window_logic(client):
    verified_flow(client)
    post_webhook(client, checkout_event())
    from tests.helpers import final_card_for
    final = final_card_for("owner@acme-hvac.example.com")
    # window active now, ends 60 days after purchase
    assert final.recheck_window_active()
    import datetime as d
    from app.models import utcnow
    created = final.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=d.timezone.utc)
    assert (final.recheck_window_ends_at() - created).days == 60
    # simulate window expiry
    import app.models as models
    import datetime as d
    from tests.helpers import set_created
    set_created("owner@acme-hvac.example.com", 61)
    final = final_card_for("owner@acme-hvac.example.com")
    assert not final.recheck_window_active()


# ---------------------------------------------------------------- included-months expiry

def test_included_months_expiry(client):
    verified_flow(client)
    post_webhook(client, checkout_event())
    from tests.helpers import final_card_for
    import app.models as models
    final = final_card_for("owner@acme-hvac.example.com")
    assert final.included_months_remaining() == 3
    from tests.helpers import set_monitoring_started
    set_monitoring_started("owner@acme-hvac.example.com", 31)
    final = final_card_for("owner@acme-hvac.example.com")
    assert final.included_months_remaining() == 2
    set_monitoring_started("owner@acme-hvac.example.com", 91)
    final = final_card_for("owner@acme-hvac.example.com")
    assert final.included_months_remaining() == 0
    # after expiry, due_for_scan stops
    from app.monitoring import due_for_scan
    assert not due_for_scan(final)


def test_invoice_after_included_months_extends_monitoring(client):
    verified_flow(client)
    post_webhook(client, checkout_event())
    from tests.helpers import final_card_for
    final = final_card_for("owner@acme-hvac.example.com")
    from tests.helpers import set_monitoring_started
    set_monitoring_started("owner@acme-hvac.example.com", 95)
    evt = fake_webhook_event("evt_inv1", "invoice.paid", {
        "customer_email": "owner@acme-hvac.example.com",
        "amount_paid": 2500, "customer": "cus_001"})
    post_webhook(client, evt)
    final = final_card_for("owner@acme-hvac.example.com")
    assert final.monthly_price_cents == 2500
    assert final.subscription_active
    assert (final.monitoring_ends_at - utcnow()).total_seconds() > 20 * 86400


# ---------------------------------------------------------------- cancel flow

def test_cancel_flow_and_confirmation_email(client, monkeypatch):
    sent = []
    import app.mailer as m
    monkeypatch.setattr(m, "send_cancel_confirmation_email",
                        lambda *a: sent.append(a))
    verified_flow(client)
    post_webhook(client, checkout_event())
    from tests.helpers import final_card_for
    final = final_card_for("owner@acme-hvac.example.com")
    # sign in to the dashboard (cancel is dashboard-session gated)
    login_sent = []
    import app.mailer as m2
    monkeypatch.setattr(m2, "send_dashboard_login_email",
                        lambda to, url: login_sent.append(url))
    r_login = client.post("/dashboard/login", data={"email": "owner@acme-hvac.example.com"})
    from tests.helpers import sign_in_dashboard
    sign_in_dashboard(client, "owner@acme-hvac.example.com", monkeypatch)
    r = client.post("/dashboard/cancel", data={"final_card_id": final.card_id},
                    follow_redirects=False)
    assert r.status_code == 303
    final = final_card_for("owner@acme-hvac.example.com")
    assert final.canceled_at is not None
    assert not final.subscription_active
    assert len(sent) == 1
    to, domain = sent[0]  # send_cancel_confirmation_email(to, domain)
    assert to == "owner@acme-hvac.example.com"
    assert domain == "acme-hvac.example.com"
    # subject template of the confirmation email names the cancellation
    assert "canceled" in "Your AI Sharc monitoring is canceled"
    # cancel is idempotent
    r2 = client.post("/dashboard/cancel", data={"final_card_id": final.card_id},
                     follow_redirects=False)
    assert r2.status_code == 303


def test_cancel_requires_ownership(client, monkeypatch):
    verified_flow(client, email="owner@acme-hvac.example.com")
    post_webhook(client, checkout_event())
    verified_flow(client, url="https://other-firm.example.com",
                  email="other@other.example.com")
    from tests.helpers import final_card_for
    final = final_card_for("owner@acme-hvac.example.com")
    # signed in as the OTHER firm via dashboard session
    sent = []
    import app.mailer as m
    from app import billing
    m.send_dashboard_login_email = lambda to, url: sent.append(url)
    from tests.helpers import sign_in_dashboard
    sign_in_dashboard(client, "other@other.example.com", monkeypatch)
    r = client.post("/dashboard/cancel", data={"final_card_id": final.card_id})
    assert r.status_code == 404


# ---------------------------------------------------------------- PDF generation

def test_pdf_download_gated_and_generated(client):
    verified_flow(client)
    post_webhook(client, checkout_event())
    from tests.helpers import final_card_for
    final = final_card_for("owner@acme-hvac.example.com")
    # card-session buyer (verified flow) -> PDF renders
    r = client.get(f"/final/{final.card_id}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_pdf_refused_without_session(client):
    # an id that doesn't exist / no session: must not leak the card
    r = client.get("/final/deadbeefdeadbeef/pdf")
    assert r.status_code == 403


def test_final_card_view_private(client):
    verified_flow(client)
    post_webhook(client, checkout_event())
    from tests.helpers import final_card_for
    final = final_card_for("owner@acme-hvac.example.com")
    r = client.get(f"/final/{final.card_id}")
    assert r.status_code == 200
    assert "fix list" in r.text.lower() or "fix list" in r.text
    # another firm cannot view it
    verified_flow(client, url="https://intruder.example.com",
                  email="intruder@other.example.com")
    r2 = client.get(f"/final/{final.card_id}")
    assert r2.status_code == 403


def test_final_card_leak_scan(client):
    verified_flow(client)
    post_webhook(client, checkout_event())
    from tests.helpers import final_card_for
    final = final_card_for("owner@acme-hvac.example.com")
    body = client.get(f"/final/{final.card_id}").text.lower()
    for phrase in ["critical gate", "gate name", "weight", "threshold",
                   "scoring rubric", "item-by-item", "league table"]:
        assert phrase not in body, f"leak: {phrase}"


# ---------------------------------------------------------------- dashboard

def test_dashboard_login_flow_and_history(client, monkeypatch):
    sent = []
    import app.mailer as m
    monkeypatch.setattr(m, "send_dashboard_login_email",
                        lambda to, url: sent.append((to, url)))
    verified_flow(client)
    post_webhook(client, checkout_event())
    r = client.post("/dashboard/login", data={"email": "owner@acme-hvac.example.com"})
    assert r.status_code == 200
    assert "Check your email" in r.text
    from tests.helpers import sign_in_dashboard
    sign_in_dashboard(client, "owner@acme-hvac.example.com", monkeypatch)
    r3 = client.get("/dashboard")
    assert r3.status_code == 200
    assert "Final Report Card" in r3.text
    assert "acme-hvac.example.com" in r3.text
    assert "included month" in r3.text
    assert "Monitoring: <strong>active</strong>" in r3.text
    assert "$99.00" in r3.text  # billing history shows the receipt


def test_dashboard_login_link_single_use(client, monkeypatch):
    sent = []
    import app.mailer as m
    monkeypatch.setattr(m, "send_dashboard_login_email",
                        lambda to, url: sent.append((to, url)))
    client.post("/dashboard/login", data={"email": "owner@acme-hvac.example.com"})
    from tests.helpers import sign_in_dashboard
    r_tok = client.get(sent[0][1], follow_redirects=False)
    assert r_tok.status_code == 303
    r2 = client.get(sent[0][1], follow_redirects=False)
    assert r2.status_code == 410


def test_dashboard_requires_session(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "Send my link" in r.text  # shows the sign-in form, no data


def test_dashboard_no_cross_firm_access(client, monkeypatch):
    verified_flow(client, email="owner@acme-hvac.example.com")
    post_webhook(client, checkout_event())
    verified_flow(client, url="https://other-firm.example.com",
                  email="other@other.example.com")
    from tests.helpers import sign_in_dashboard
    sign_in_dashboard(client, "other@other.example.com", monkeypatch)
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "acme-hvac.example.com" not in r.text  # the other firm's data never shows
    assert "other-firm.example.com" in r.text  # their own data does
    from tests.helpers import final_card_for
    final = final_card_for("owner@acme-hvac.example.com")
    r2 = client.get(f"/final/{final.card_id}")
    assert r2.status_code == 403


def test_dashboard_unknown_email_no_enumeration(client, monkeypatch):
    sent = []
    import app.mailer as m
    monkeypatch.setattr(m, "send_dashboard_login_email",
                        lambda to, url: sent.append((to, url)))
    r = client.post("/dashboard/login", data={"email": "ghost@nowhere.example.com"})
    assert r.status_code == 200
    assert "Check your email" in r.text  # same copy whether or not the account exists


# ---------------------------------------------------------------- monitoring

def test_monitoring_scan_emails_on_grade_change(client, monkeypatch):
    from app import monitoring
    sent = []
    import app.mailer as m
    monkeypatch.setattr(m, "send_grade_change_email", lambda *a: sent.append(a))
    verified_flow(client)
    post_webhook(client, checkout_event())
    from tests.helpers import final_card_for
    final = final_card_for("owner@acme-hvac.example.com")

    def fake_scan(url):
        return ("A", "Strong. AI agents can find, read and trust this site.", [])
    monkeypatch.setattr("app.scanner.scan_site", fake_scan)
    changed = monitoring.run_scan(_db(), final, _scanner_stub("A"))
    assert changed
    assert len(sent) == 1
    to, domain, old, new, url = sent[0]  # send_grade_change_email signature
    assert old == "C" and new == "A"


def test_monitoring_no_email_when_grade_same(client, monkeypatch):
    from app import monitoring
    sent = []
    import app.mailer as m
    monkeypatch.setattr(m, "send_grade_change_email", lambda *a: sent.append(a))
    verified_flow(client)
    post_webhook(client, checkout_event())
    from tests.helpers import final_card_for
    final = final_card_for("owner@acme-hvac.example.com")
    changed = monitoring.run_scan(_db(), final, _scanner_stub("C"))
    assert not changed
    assert sent == []


def _db():
    from tests.helpers import _STATE
    return _STATE["session_factory"]()


def _scanner_stub(grade):
    class S:
        scan_site = staticmethod(lambda url: (grade, "headline", []))
    return S


def test_monitoring_stops_after_canceled(client, monkeypatch):
    from app import monitoring
    verified_flow(client)
    post_webhook(client, checkout_event())
    from tests.helpers import final_card_for
    final = final_card_for("owner@acme-hvac.example.com")
    from tests.helpers import cancel_in_db
    cancel_in_db("owner@acme-hvac.example.com")
    final = final_card_for("owner@acme-hvac.example.com")
    assert not monitoring.due_for_scan(final)


# ---------------------------------------------------------------- funnel events

def test_funnel_includes_final_purchased(client):
    verified_flow(client)
    post_webhook(client, checkout_event())
    from tests.helpers import final_card_for, funnel_events
    final = final_card_for("owner@acme-hvac.example.com")
    client.get(f"/final/{final.card_id}")
    kinds = [e.event for e in funnel_events()]
    assert kinds == ["submit", "verified", "final_purchased"]


# ---------------------------------------------------------------- portal + reconciliation

def test_admin_reconcile_replays_grant(client, stub_stripe, monkeypatch):
    from app.config import settings
    settings.admin_token = "admin-token-test"
    verified_flow(client)
    stub_stripe.sessions["cs_rec_001"] = {
        "id": "cs_rec_001", "customer_email": "owner@acme-hvac.example.com",
        "customer_details": {"email": "owner@acme-hvac.example.com"},
        "amount_total": 9900, "customer": "cus_001", "subscription": None}
    r = client.post("/admin/reconcile-session",
                    data={"token": "admin-token-test", "session_id": "cs_rec_001"},
                    follow_redirects=False)
    assert r.status_code == 303
    from tests.helpers import final_card_for
    assert final_card_for("owner@acme-hvac.example.com") is not None
    # wrong token refused
    r2 = client.post("/admin/reconcile-session",
                     data={"token": "wrong", "session_id": "cs_rec_001"})
    assert r2.status_code == 403
    settings.admin_token = ""
