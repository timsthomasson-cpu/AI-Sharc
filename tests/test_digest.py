# AI Sharc — Digest subscription tests. No real external calls: mailer
# functions are monkeypatched; the console backend never sends.
import datetime as dt

import pytest

SUBSCRIBE = "/digest/subscribe"


def subscribe(client, email="reader@acme.example.com", hp=None):
    data = {"email": email}
    if hp is not None:
        data["hp"] = hp
    return client.post(SUBSCRIBE, data=data, follow_redirects=False)


def capture_confirmation(monkeypatch):
    import app.mailer as m
    sent = []
    monkeypatch.setattr(m, "send_digest_confirmation",
                        lambda to, url, unsub="": sent.append((to, url, unsub)))
    return sent


def capture_weekly(monkeypatch):
    import app.mailer as m
    sent = []
    monkeypatch.setattr(m, "send_digest_weekly",
                        lambda to, title, url, unsub: sent.append((to, title, url, unsub)))
    return sent


def confirm(client, token):
    return client.get(f"/digest/confirm/{token}", follow_redirects=False)


def unsubscribe(client, token):
    return client.get(f"/digest/unsubscribe/{token}", follow_redirects=False)


def db_session():
    """A session on the same in-memory DB the app under test uses."""
    from tests.helpers import _STATE
    return _STATE["session_factory"]()


def confirmed_subscriber(client, email="reader@acme.example.com", monkeypatch=None):
    """Subscribe + confirm; returns the subscriber row."""
    if monkeypatch is not None:
        capture_confirmation(monkeypatch)
    r = subscribe(client, email)
    assert r.status_code == 200
    from tests.helpers import digest_subscriber_by_email
    sub = digest_subscriber_by_email(email)
    r2 = confirm(client, sub.confirmation_token)
    assert r2.status_code == 200
    return digest_subscriber_by_email(email)


# ---------------------------------------------------------------- subscribe

def test_subscribe_happy_path_creates_unconfirmed_row(client, monkeypatch):
    sent = capture_confirmation(monkeypatch)
    r = subscribe(client)
    assert r.status_code == 200
    assert "Check your email" in r.text
    from tests.helpers import digest_subscriber_by_email
    sub = digest_subscriber_by_email("reader@acme.example.com")
    assert sub is not None
    assert sub.confirmed_at is None
    assert sub.unsubscribed_at is None
    assert sub.confirmation_token
    assert sub.unsubscribe_token
    assert sub.source
    # Confirmation email carries the magic link and a per-subscriber opt-out.
    assert len(sent) == 1
    to, url, unsub = sent[0]
    assert to == "reader@acme.example.com"
    assert sub.confirmation_token in url
    assert sub.unsubscribe_token in unsub


def test_subscribe_invalid_email_rejected(client, monkeypatch):
    sent = capture_confirmation(monkeypatch)
    r = subscribe(client, email="not-an-email")
    assert r.status_code == 422
    assert sent == []
    from tests.helpers import digest_subscriber_by_email
    assert digest_subscriber_by_email("not-an-email") is None


def test_honeypot_silently_ignored(client, monkeypatch):
    sent = capture_confirmation(monkeypatch)
    r = subscribe(client, hp="on")
    assert r.status_code == 200
    assert "Check your email" in r.text
    assert sent == []  # no email for bots
    from tests.helpers import digest_subscriber_by_email
    assert digest_subscriber_by_email("reader@acme.example.com") is None


def test_rate_limit_per_email(client, monkeypatch):
    capture_confirmation(monkeypatch)
    for _ in range(3):
        assert subscribe(client, email="busy@acme.example.com").status_code == 200
    r = subscribe(client, email="busy@acme.example.com")
    assert r.status_code == 429


def test_rate_limit_per_ip(client, monkeypatch):
    capture_confirmation(monkeypatch)
    for i in range(5):
        assert subscribe(client, email=f"user{i}@acme.example.com").status_code == 200
    r = subscribe(client, email="user6@acme.example.com")
    assert r.status_code == 429


def test_duplicate_subscribe_is_idempotent(client, monkeypatch):
    sent = capture_confirmation(monkeypatch)
    assert subscribe(client).status_code == 200
    assert subscribe(client).status_code == 200  # unconfirmed: token refreshed, resent
    from tests.helpers import digest_subscriber_by_email
    subs = [digest_subscriber_by_email("reader@acme.example.com")]
    assert len(sent) == 2
    # Still exactly one row.
    from tests.helpers import _STATE
    db = _STATE["session_factory"]()
    try:
        from app.models import DigestSubscriber
        rows = db.query(DigestSubscriber).filter(
            DigestSubscriber.email == "reader@acme.example.com").all()
        assert len(rows) == 1
    finally:
        db.close()
    # Already confirmed: subscribing again sends nothing, changes nothing.
    sub = confirmed_subscriber(client, "settled@acme.example.com", monkeypatch)
    confirmed_at = sub.confirmed_at
    sent.clear()
    assert subscribe(client, email="settled@acme.example.com").status_code == 200
    assert sent == []
    sub2 = digest_subscriber_by_email("settled@acme.example.com")
    assert sub2.confirmed_at == confirmed_at


# ---------------------------------------------------------------- confirm

def test_confirm_happy_path(client, monkeypatch):
    capture_confirmation(monkeypatch)
    subscribe(client)
    from tests.helpers import digest_subscriber_by_email
    token = digest_subscriber_by_email("reader@acme.example.com").confirmation_token
    r = confirm(client, token)
    assert r.status_code == 200
    assert "subscribed" in r.text.lower()
    assert "/digest/index.html" in r.text
    sub = digest_subscriber_by_email("reader@acme.example.com")
    assert sub.confirmed_at is not None


def test_confirm_single_use(client, monkeypatch):
    capture_confirmation(monkeypatch)
    subscribe(client)
    from tests.helpers import digest_subscriber_by_email
    token = digest_subscriber_by_email("reader@acme.example.com").confirmation_token
    assert confirm(client, token).status_code == 200
    assert confirm(client, token).status_code == 410  # second use: gone


def test_confirm_unknown_token_404(client):
    assert confirm(client, "deadbeef").status_code == 404


def test_confirm_expired_410(client, monkeypatch):
    capture_confirmation(monkeypatch)
    subscribe(client)
    from tests.helpers import digest_subscriber_by_email, expire_digest_confirmation
    expire_digest_confirmation("reader@acme.example.com")
    token = digest_subscriber_by_email("reader@acme.example.com").confirmation_token
    assert confirm(client, token).status_code == 410


# ---------------------------------------------------------------- unsubscribe

def test_unsubscribe_flow_and_suppression(client, monkeypatch):
    weekly = capture_weekly(monkeypatch)
    sub = confirmed_subscriber(client, monkeypatch=monkeypatch)
    r = unsubscribe(client, sub.unsubscribe_token)
    assert r.status_code == 200
    assert "unsubscribed" in r.text.lower()
    from tests.helpers import digest_subscriber_by_email
    sub = digest_subscriber_by_email("reader@acme.example.com")
    assert sub.unsubscribed_at is not None
    # Suppressed: the weekly send never emails an unsubscribed address.
    from app import digest_sender
    digest_sender.send_digest_batch(db_session())
    assert weekly == []
    # Unsubscribe link is idempotent.
    assert unsubscribe(client, sub.unsubscribe_token).status_code == 200


def test_unsubscribe_unknown_token_404(client):
    assert unsubscribe(client, "deadbeef").status_code == 404


def test_resubscribe_after_unsubscribe_requires_confirmation(client, monkeypatch):
    weekly = capture_weekly(monkeypatch)
    sub = confirmed_subscriber(client, monkeypatch=monkeypatch)
    unsubscribe(client, sub.unsubscribe_token)
    # Resubscribe: fresh confirmation, old state wiped.
    sent = capture_confirmation(monkeypatch)
    assert subscribe(client).status_code == 200
    from tests.helpers import digest_subscriber_by_email
    sub2 = digest_subscriber_by_email("reader@acme.example.com")
    assert sub2.unsubscribed_at is None
    assert sub2.confirmed_at is None
    assert sub2.confirmation_token != sub.confirmation_token
    assert len(sent) == 1
    # Still suppressed until the fresh confirmation is clicked.
    from app import digest_sender
    db = db_session()
    digest_sender.send_digest_batch(db)
    assert weekly == []
    assert confirm(client, sub2.confirmation_token).status_code == 200
    digest_sender.send_digest_batch(db)
    assert len(weekly) == 1


# ---------------------------------------------------------------- weekly send

def test_weekly_send_idempotent_per_subscriber_article(client, monkeypatch):
    weekly = capture_weekly(monkeypatch)
    confirmed_subscriber(client, "a@acme.example.com", monkeypatch)
    confirmed_subscriber(client, "b@acme.example.com", monkeypatch)
    subscribe(client, email="unconfirmed@acme.example.com")  # never confirmed
    from app import digest_sender
    from tests.helpers import digest_send_count
    db = db_session()
    slug = "homeowners-ask-ai-first.html"
    r1 = digest_sender.send_digest_batch(db, slug)
    assert r1 == {"sent": 2, "skipped": 0, "slug": slug}
    assert digest_send_count() == 2
    assert len(weekly) == 2
    assert all(unsub for _, _, _, unsub in weekly)
    # Retried run: nothing sent again.
    r2 = digest_sender.send_digest_batch(db, slug)
    assert r2 == {"sent": 0, "skipped": 2, "slug": slug}
    assert digest_send_count() == 2
    assert len(weekly) == 2


def test_weekly_send_unknown_slug_404(client, monkeypatch):
    from app import digest_sender
    db = db_session()
    with pytest.raises(ValueError):
        digest_sender.send_digest_batch(db, "no-such-article.html")


def test_admin_digest_send_requires_token(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "admin_token", "sekrit", raising=False)
    assert client.get("/admin/digest/send").status_code == 403
    assert client.get("/admin/digest/send?token=wrong").status_code == 403
    assert client.post("/admin/digest/send?token=wrong").status_code == 403


def test_admin_digest_send_get_and_post(client, monkeypatch):
    weekly = capture_weekly(monkeypatch)
    from app.config import settings
    monkeypatch.setattr(settings, "admin_token", "sekrit", raising=False)
    confirmed_subscriber(client, "a@acme.example.com", monkeypatch)
    r = client.get("/admin/digest/send?token=sekrit&slug=homeowners-ask-ai-first.html")
    assert r.status_code == 200
    assert r.json() == {"sent": 1, "skipped": 0, "slug": "homeowners-ask-ai-first.html"}
    # POST form of the same endpoint (cron-style trigger).
    confirmed_subscriber(client, "c@acme.example.com", monkeypatch)
    r = client.post("/admin/digest/send?token=sekrit&slug=homeowners-ask-ai-first.html")
    assert r.status_code == 200
    assert r.json()["sent"] == 1
    assert r.json()["skipped"] == 1  # a@ already got this article
    assert client.get("/admin/digest/send?token=sekrit&slug=nope.html").status_code == 404


# ---------------------------------------------------------------- CAN-SPAM footer

def test_can_spam_footer_in_both_email_types(client, monkeypatch):
    import app.mailer as m

    class Capture:
        def __init__(self):
            self.sent = []

        def send(self, to, subject, text):
            self.sent.append((to, subject, text))

    box = Capture()
    monkeypatch.setattr(m, "get_mailer", lambda: box)
    m.send_digest_confirmation("r@acme.example.com", "https://aisharc.com/digest/confirm/t",
                               "https://aisharc.com/digest/unsubscribe/u")
    m.send_digest_weekly("r@acme.example.com", "Some title",
                         "https://aisharc.com/digest/some-article.html",
                         "https://aisharc.com/digest/unsubscribe/u")
    assert len(box.sent) == 2
    for to, subject, text in box.sent:
        assert "PO Box 1622, Coppell, TX 75019" in text
        assert "Unsubscribe" in text
        assert "You're receiving this because you subscribed at aisharc.com/digest" in text
    # Weekly email carries the article link only — no scoring detail (§12).
    to, subject, text = box.sent[1]
    assert "https://aisharc.com/digest/some-article.html" in text


# ---------------------------------------------------------------- static build

def test_site_digest_pages_carry_subscribe_form():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "site", "digest", "index.html")) as f:
        index = f.read()
    assert 'action="https://aisharc.com/digest/subscribe"' in index
    assert 'name="hp"' in index  # honeypot present
    with open(os.path.join(root, "site", "digest", "homeowners-ask-ai-first.html")) as f:
        article = f.read()
    assert "/digest/index.html#subscribe" in article  # footer subscribe link
    assert "{FLOW_ORIGIN}" not in article  # placeholder resolver ran
