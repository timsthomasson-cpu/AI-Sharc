# AI Sharc — Stage 3 smoke test: runs the real app with the Stripe stub and a
# real browser (Playwright, system Chromium). Walks purchase -> dashboard ->
# Final card -> PDF -> cancel; screenshots land in qa/stage3/.
import json
import os
import re
import sys
import time

sys.path.insert(0, "/root/projects/AI-Sharc")
os.environ["DATABASE_URL"] = "sqlite:////tmp/aisharc-smoke.db"
os.environ["SECRET_KEY"] = "smoke-secret-key-not-for-production"
os.environ["BASE_URL"] = "http://127.0.0.1:8000"
os.environ["MAILER"] = "console"
os.environ["ADMIN_TOKEN"] = "smoke-admin-token"
if os.path.exists("/tmp/aisharc-smoke.db"):
    os.remove("/tmp/aisharc-smoke.db")

from app import billing  # noqa: E402
billing.set_stripe_adapter(billing.StripeStub())

import uvicorn  # noqa: E402
from app.main import app  # noqa: E402

config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
server = uvicorn.Server(config)
import threading
t = threading.Thread(target=server.run, daemon=True)
t.start()
for _ in range(50):
    if server.started:
        break
    time.sleep(0.2)

import httpx  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from app.models import VerifyToken, DashboardSession, FinalCard  # noqa: E402

eng = create_engine("sqlite:////tmp/aisharc-smoke.db",
                    connect_args={"check_same_thread": False})
SF = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)

EMAIL = "owner@acme-hvac.example.com"
BASE = "http://127.0.0.1:8000"
SHOTS = "/root/projects/AI-Sharc/qa/stage3"
os.makedirs(SHOTS, exist_ok=True)
c = httpx.Client(base_url=BASE, timeout=30)

# 1. submit + verify
r = c.post("/get-audited", data={"url": "https://acme-hvac.example.com", "email": EMAIL})
assert r.status_code == 200
tok = SF().query(VerifyToken).order_by(VerifyToken.id.desc()).first().token
r = c.get(f"/verify/{tok}", follow_redirects=False)
assert r.status_code == 303
print("SMOKE 1/7 preliminary verified")

# 2. webhook grant
event = {"id": "evt_smoke_1", "type": "checkout.session.completed",
         "data": {"object": {"id": "cs_smoke_1", "customer_email": EMAIL,
                             "customer_details": {"email": EMAIL},
                             "customer": "cus_smoke", "subscription": None,
                             "amount_total": 9900}}}
r = c.post("/stripe/webhook", content=json.dumps(event),
           headers={"stripe-signature": "t=1,v1=stub"})
assert r.status_code == 200
final = SF().query(FinalCard).order_by(FinalCard.id.desc()).first()
assert final is not None
FINAL_ID = final.card_id
print("SMOKE 2/7 webhook granted Final card", FINAL_ID)

# 3. dashboard magic-link sign-in (exercise the real login route: create the
# session the way send_dashboard_login would, then consume the link)
import datetime as dt
from app.models import new_token, utcnow
sess_token = new_token()
_db = SF()
_db.add(DashboardSession(token=sess_token, email=EMAIL,
                         expires_at=utcnow() + dt.timedelta(minutes=30)))
_db.commit()
_db.close()
r = c.get(f"/dashboard/login/{sess_token}", follow_redirects=False)
assert r.status_code == 303
c.headers["cookie"] = r.headers["set-cookie"].split(";")[0]
r = c.get("/dashboard")
assert "Final Report Card" in r.text and "acme-hvac.example.com" in r.text
print("SMOKE 3/7 dashboard shows Final card")

# 4. browser: dashboard + Final card screenshots at 1440 and 390
from playwright.sync_api import sync_playwright  # noqa: E402

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/local/bin/chromium",
                                args=["--no-sandbox"])
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                              base_url=BASE)
    ctx.add_cookies([{"name": "dash_session",
                      "value": c.headers["cookie"].split("=", 1)[1],
                      "url": BASE}])
    page = ctx.new_page()
    page.goto(f"{BASE}/dashboard", wait_until="networkidle")
    assert "Final Report Card" in page.content()
    page.screenshot(path=f"{SHOTS}/dashboard-1440.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=f"{SHOTS}/dashboard-390.png", full_page=True)
    print("SMOKE 4/7 dashboard screenshots 1440/390")

    # Final card page at both sizes
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{BASE}/final/{FINAL_ID}", wait_until="networkidle")
    assert "fix list" in page.content().lower()
    page.screenshot(path=f"{SHOTS}/final-card-1440.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=f"{SHOTS}/final-card-390.png", full_page=True)
    print("SMOKE 5/7 Final card screenshots 1440/390")

    # 6. PDF download through the browser
    resp = page.request.get(f"{BASE}/final/{FINAL_ID}/pdf")
    assert resp.status == 200
    body = resp.body()
    assert body[:4] == b"%PDF"
    with open(f"{SHOTS}/final-card.pdf", "wb") as f:
        f.write(body)
    print("SMOKE 6/7 PDF downloaded,", len(body), "bytes")

    # 7. self-serve cancel through the real form
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{BASE}/dashboard", wait_until="networkidle")
    page.click("form[action='/dashboard/cancel'] button")
    page.wait_for_load_state("networkidle")
    assert "not active" in page.content().lower()
    page.screenshot(path=f"{SHOTS}/dashboard-after-cancel-1440.png", full_page=True)
    final = SF().query(FinalCard).order_by(FinalCard.id.desc()).first()
    assert final.canceled_at is not None
    print("SMOKE 7/7 self-serve cancel works, state flipped")

    browser.close()

print("SMOKE COMPLETE — all 7 steps passed")
