# AI Sharc — Get Audited flow tests. No real external calls: scanner stubbed,
# mailer is console. Leak-scan patterns reused from qa/qa_check.py.
import re

GET_AUDITED = "/get-audited"


def submit(client, url="https://acme-hvac.example.com", email="owner@acme-hvac.example.com", **kw):
    data = {"url": url, "email": email, "hp": kw.get("hp", "")}
    data.update({k: v for k, v in kw.items() if k in ("url", "email")})
    if "hp" not in kw:
        data.pop("hp")
    return client.post(GET_AUDITED, data=data, follow_redirects=False)


def verified_card_id(client, url="https://acme-hvac.example.com",
                     email="owner@acme-hvac.example.com"):
    """Run the full double opt-in flow; return (card_id, token, verify_response).

    A real browser stores the card_session cookie the verify response sets and
    follows the redirect — emulate that here, because the test client does not
    persist cookies from a non-followed redirect."""
    r = submit(client, url, email)
    assert r.status_code == 200
    from tests.helpers import last_verify_token
    token = last_verify_token()
    r2 = client.get(f"/verify/{token}", follow_redirects=False)
    card_id = r2.headers["location"].split("/")[-1]
    cookie = r2.headers.get("set-cookie", "")
    if cookie:
        client.cookies.set("card_session", cookie.split(";")[0].split("=", 1)[1])
    return card_id, token, r2


# ---------------------------------------------------------------- form validation

def test_submit_valid_returns_check_email(client):
    r = submit(client)
    assert r.status_code == 200
    assert "Check your email" in r.text


def test_submit_bad_url_rejected(client):
    r = submit(client, url="not a url")
    assert r.status_code == 422
    assert "website address" in r.text.lower()


def test_submit_bad_url_value_error(client):
    for bad in ["", "https://", "http://localhost", "https://example.com", "justtext"]:
        r = submit(client, url=bad)
        assert r.status_code == 422, bad


def test_submit_bad_email_rejected(client):
    r = submit(client, email="not-an-email")
    assert r.status_code == 422


def test_submit_blocked_domain_rejected(client):
    r = submit(client, url="https://google.com")
    assert r.status_code == 422


# ---------------------------------------------------------------- honeypot

def test_honeypot_filled_is_silently_accepted_no_email(client, monkeypatch):
    sent = []
    import app.mailer as m
    monkeypatch.setattr(m, "send_verification_email", lambda *a: sent.append(a))
    r = submit(client, hp="on")
    assert r.status_code == 200
    assert "Check your email" in r.text
    assert sent == []  # no verification email for bots


def test_honeypot_empty_proceeds(client):
    r = submit(client, hp="")
    assert r.status_code == 200


# ---------------------------------------------------------------- rate limiting

def test_rate_limit_per_email(client):
    for _ in range(3):
        assert submit(client, email="busy@acme.example.com").status_code == 200
    r = submit(client, email="busy@acme.example.com")
    assert r.status_code == 429


def test_rate_limit_per_ip(client):
    for i in range(5):
        assert submit(client, email=f"user{i}@acme.example.com").status_code == 200
    r = submit(client, email="user6@acme.example.com")
    assert r.status_code == 429


# ---------------------------------------------------------------- magic link

def test_magic_link_single_use(client):
    card_id, token, _ = verified_card_id(client)
    r1 = client.get(f"/verify/{token}", follow_redirects=False)
    assert r1.status_code in (303, 410)
    assert r1.status_code == 410  # second use: gone


def test_magic_link_unknown_token_404(client):
    r = client.get("/verify/deadbeef", follow_redirects=False)
    assert r.status_code == 404


def test_magic_link_expiry(client):
    submit(client)
    from tests.helpers import last_verify_token, expire_last_token
    token = last_verify_token()
    expire_last_token()
    r = client.get(f"/verify/{token}", follow_redirects=False)
    assert r.status_code == 410


def test_double_optin_not_bypassable(client):
    # Card id only exists after verification; direct /card/<id> without the
    # verification cookie is refused even if the id were guessable.
    submit(client, url="https://unverified.example.com",
           email="owner@unverified.example.com")
    from tests.helpers import last_card_id_if_any
    assert last_card_id_if_any() is None  # nothing scanned before verify
    r = client.get("/card/aaaaaaaaaaaaaaaa", follow_redirects=False)
    assert r.status_code == 404


def test_verify_sets_session_and_card_accessible(client):
    card_id, token, r2 = verified_card_id(client)
    assert r2.status_code == 303
    assert "card_session" in r2.headers.get("set-cookie", "")
    r = client.get(f"/card/{card_id}")
    assert r.status_code == 200
    assert "Preliminary Report Card" in r.text


# ---------------------------------------------------------------- ledger limit

def test_ten_view_limit(client):
    card_id, _, _ = verified_card_id(client)
    for i in range(10):
        r = client.get(f"/card/{card_id}")
        assert r.status_code == 200, i
    r = client.get(f"/card/{card_id}")
    assert r.status_code == 429
    assert "10 times" in r.text


# ---------------------------------------------------------------- card rendering + leak scan

BANNED = ["critical gate", "gate ", "weight", "threshold", "scoring rubric",
          "item-by-item", "league table", "licence register", "audit rows",
          "points", "passes ", "score"]


def test_card_contains_no_scoring_detail(client):
    card_id, _, _ = verified_card_id(client)
    html = client.get(f"/card/{card_id}").text
    body = re.sub(r"<[^>]+>", " ", html).lower()
    for phrase in BANNED:
        assert phrase not in body, f"leak: {phrase}"


def test_card_has_source_and_date_per_finding(client):
    card_id, _, _ = verified_card_id(client)
    html = client.get(f"/card/{card_id}").text
    assert "Source:" in html
    assert "checked 2026-11-11" in html


def test_card_grade_and_no_guarantee_disclaimer(client):
    card_id, _, _ = verified_card_id(client)
    html = client.get(f"/card/{card_id}").text
    assert "no guarantee" in html.lower()


# ---------------------------------------------------------------- funnel events

def test_funnel_events_submit_verified_viewed(client):
    card_id, _, _ = verified_card_id(client)
    client.get(f"/card/{card_id}")
    from tests.helpers import funnel_events
    events = funnel_events()
    kinds = [e.event for e in events]
    assert kinds == ["submit", "verified", "preliminary_viewed"]


# ---------------------------------------------------------------- marketing shell intact

def test_static_pages_served(client):
    for slug in ["", "how-it-works", "pricing", "faq", "sample-cards", "privacy",
                 "terms", "contact", "hvac-contractor"]:
        r = client.get("/" + slug)
        assert r.status_code == 200, slug
        assert "<!doctype html>" in r.text.lower()


def test_get_audited_page_has_form_and_honeypot(client):
    r = client.get(GET_AUDITED)
    assert r.status_code == 200
    assert 'method="post"' in r.text
    assert 'name="hp"' in r.text


def test_no_javascript_anywhere(client):
    for slug in ["", "get-audited", "how-it-works", "pricing"]:
        html = client.get("/" + slug).text
        assert "<script" not in html.lower()
