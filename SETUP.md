# AI Sharc — aisharc.com: setup, DNS and run guide

Last updated: 2026-11-11 (Stage 3 built on `stage-3-monetize`). Owner: Tim (with Devin).

## What is live right now

- **Stage 1 marketing shell (13 static pages)** is deployed and serving at:
  **https://timsthomasson-cpu.github.io/AI-Sharc/**
  Branch `gh-pages` (built from `site/` on `stage-1-marketing-shell`). HTTPS on, custom domain `aisharc.com` is registered on the Pages site via the repo CNAME file — it goes live the moment DNS points here.

## DNS batch for Tim (ONE ask — site + email together)

At the registrar for aisharc.com, add/point:

### Site (GitHub Pages)
| Type | Name | Value |
|---|---|---|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| AAAA | @ | 2606:50c0:8000::153 |
| AAAA | @ | 2606:50c0:8001::153 |
| AAAA | @ | 2606:50c0:8002::153 |
| AAAA | @ | 2606:50c0:8003::153 |
| CNAME | www | timsthomasson-cpu.github.io. |

(If the registrar uses "ALIAS/ANAME" for the apex instead of A records, ALIAS @ → timsthomasson-cpu.github.io is equally fine.)

### Email (SendGrid domain authentication — Stage 2 deliverability)
SendGrid must be told to expect these BEFORE the records are added (Devin/Tim create the sender domain in SendGrid; SendGrid then shows the exact CNAME values — the table below is the standard shape):

| Type | Name | Value |
|---|---|---|
| CNAME | url<key>.aisharc.com | sendgrid.net. |
| CNAME | <key1>.domainkey.aisharc.com | <DKIM1 host>.domainkey.u<id>.wl<id>.sendgrid.net. |
| CNAME | <key2>.domainkey.aisharc.com | <DKIM2 host>.domainkey.u<id>.wl<id>.sendgrid.net. |
| TXT | aisharc.com | v=spf1 include:sendgrid.net -all (merge with existing SPF if one exists — Google mail is on this domain today) |
| TXT | _dmarc.aisharc.com | v=DMARC1; p=quarantine; rua=mailto:<dmarc-reports@aisharc.com> |

⚠️ The exact `<key>` / `<id>` values come from the SendGrid sender-domain page once it's created. ⚠️ The SPF note matters: aisharc.com currently routes mail through Google (smtp.google.com) — if any mailbox on the domain must keep receiving mail, the SPF record must include BOTH `include:sendgrid.net` and Google's mechanism (`include:_spf.google.com`), not replace one with the other.

**Order of operations:** create the SendGrid sender domain → collect exact CNAME/TXT values → add ALL records in one registrar batch (site + email) → verify in SendGrid → only then enable live email sends. No test or real emails from the domain before verification.

## Tim's two pending picks (not build blockers)
1. **Monitoring months included with the Final card: 3 or 4.** DECIDED 2026-11-12: **3** (`MONITORING_INCLUDED_MONTHS = 3` in `build/content_pages.py`; pricing copy everywhere follows the constant).
2. **GitHub push token** — provided 2026-11-11; used for pushes and Pages deploy.

## Repo / branches
- `main` — docs + requirements (Website Requirements v1.1 canonical).
- `stage-1-marketing-shell` — 13 static no-JS pages + brand assets + build system. QA: `qa/qa_check.py` (ALL CHECKS PASSED), screenshots in `qa/screenshots/`, report in `qa/stage-1-report.md`.
- `gh-pages` — deploy branch (flat copy of `site/` + CNAME).
- Stage 2 (`stage-2-get-audited`, FastAPI Get-Audited flow) in progress.

## Stage 2 — Get Audited flow: configuration and running

The FastAPI app lives in `app/` on branch `stage-2-get-audited`. It serves the
same 13 marketing pages (byte-identical to the `site/` build) plus the dynamic
flow: `POST /get-audited` → verification email → `GET /verify/<token>` (single-use
magic link, double opt-in, runs the Preliminary scan) → `GET /card/<id>`
(server-rendered Preliminary card, 10 views per firm per query, magic-link-gated).

### Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | prod: yes | `sqlite:///./aisharc.db` | Postgres in prod, e.g. `postgresql+psycopg://user:pass@host/aisharc`. SQLite for dev/tests. |
| `SECRET_KEY` | **prod: yes** | random (ephemeral) | Signs the `card_session` cookie. Without it sessions reset on restart. Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `BASE_URL` | prod: yes | `https://aisharc.com` | Absolute base for verification links + canonical URLs. |
| `MAILER` | no | `console` | `console` (logs the link — dev), `smtp`, or `sendgrid`. |
| `MAIL_FROM` | prod: yes | `cards@aisharc.com` | From address on verification email. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | if `MAILER=smtp` | — | SMTP relay credentials. **Env only, never committed.** |
| `SENDGRID_API_KEY` | if `MAILER=sendgrid` | — | SendGrid HTTP API key. **Env only, never committed.** |
| `VERIFY_TOKEN_TTL_MINUTES` | no | `30` | Magic-link expiry. |
| `CARD_SESSION_TTL_SECONDS` | no | `604800` (7 days) | How long a verified visitor stays unlocked. |
| `CARD_VIEW_LIMIT` | no | `10` | Preliminary card views per firm per query. |
| `SUBMIT_RATE_PER_IP_HOUR` / `SUBMIT_RATE_PER_EMAIL_HOUR` | no | `5` / `3` | Submission rate limits (honeypot is separate). |
| `SCAN_TIMEOUT_SECONDS` | no | `10` | Per-request timeout of the Preliminary scan. |

### Run

```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg://..."
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export BASE_URL="https://aisharc.com"
export MAILER=sendgrid SENDGRID_API_KEY=... MAIL_FROM=cards@aisharc.com
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`GET /healthz` for checks. Tests: `python3 -m pytest tests/ -q` (no real
network calls — scanner stubbed, mailer is the console backend).

### Email sending — what's implemented vs. DNS

The app implements only the **sending adapter** (console / SMTP / SendGrid HTTP).
SPF, DKIM, DMARC and the return-path are **DNS records — see the Email section
above**; they are added by Tim at the registrar after the SendGrid sender domain
is created. Nothing credential-related is committed; until `MAILER` is switched
from `console`, no real email is sent anywhere.

### Not in Stage 2 scope

Stripe checkout, Final Report Card (Rev 6), dashboard, PDF export, monitoring
subscription (Stage 3).


## Run the static build
```
python3 build/build.py     # regenerates site/ (13 pages + sitemap + robots)
python3 qa/qa_check.py     # link/metadata/leak checks
```

## Stage 2 app quick reference
Dynamic routes: `GET/POST /get-audited`, `GET /verify/<token>`, `GET /card/<id>`.
See the "Stage 2 — Get Audited flow" section above for env vars, run
instructions and the email-adapter/DNS split. Tests: `python3 -m pytest tests/ -q`.

### Stage 3 — Monetization + Account (branch `stage-3-monetize`)

Adds: `/final-card` landing · Stripe checkout (`POST /final/checkout`) ·
webhook grant (`POST /stripe/webhook`) · Final card view + PDF
(`/final/<id>`, `/final/<id>/pdf`) · dashboard with magic-link sign-in
(`/dashboard`) · self-serve cancel (`POST /dashboard/cancel`) · monthly
monitoring re-scans with grade-change emails · admin reconciliation for
missed webhooks (`GET /admin/reconcile?token=...`, cron:
`GET /admin/run-monitoring?token=...`).

**Monitoring model (charge-at-purchase, the simpler faithful reading of the
spec):** the one-time Final payment covers the audit + the 3 included months
of monitoring. No Stripe subscription exists during the included months
(`monthly_price_cents = 0`). When the included months end, the monthly job
sees the card as due-renewal and the first `invoice.paid` webhook past expiry
extends monitoring by a month at the then-current price. Cancel from the
dashboard is self-serve and stops everything immediately (the Final card and
the 60-day re-check window are unaffected). A Stripe subscription can be
added later without a schema change (`stripe_subscription_id` is already on
the FinalCard row).

**Webhook-missed recovery:** Stripe retries failed deliveries; beyond that an
admin can replay a purchase by checkout session id at
`GET /admin/reconcile?token=<ADMIN_TOKEN>` → post the session id. The grant is
idempotent, so replays never double-issue.

### Additional environment variables (Stage 3)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `STRIPE_API_KEY` | prod: yes | — (empty = checkout off, honest 503 page) | Stripe secret key. **Env only, never committed.** |
| `STRIPE_WEBHOOK_SECRET` | prod: yes | — | Webhook signature verification (`whsec_...`). |
| `STRIPE_TEST_MODE` | no | — | Set `1` when using Stripe test keys. |
| `PRICE_FINAL_INTRO_CENTS` / `PRICE_FINAL_REGULAR_CENTS` | no | `9900` / `14900` | Final card price ($99 intro / $149 regular). |
| `PRICE_MONITORING_INTRO_CENTS` / `PRICE_MONITORING_REGULAR_CENTS` | no | `2500` / `3000` | Monitoring after included months ($25 / $30 per month). |
| `INTRO_FIRM_LIMIT` | no | `500` | Introductory price applies to the first 500 firms (tracked in `purchase_counter`). |
| `RECHECK_WINDOW_DAYS` | no | `60` | Unlimited re-checks window from the original card (spec v1.22). |
| `MONITORING_SCAN_INTERVAL_DAYS` | no | `30` | Monthly re-scan cadence. |
| `MONITORING_POLL_SECONDS` | no | `3600` | How often the in-app scheduler looks for due scans. |
| `ADMIN_TOKEN` | prod: yes | — (empty = admin endpoints closed) | Token for `/admin/reconcile` and `/admin/run-monitoring`. **Env only.** |

### Stripe setup checklist (Tim / Devin, when going live)

1. Create the product/price in Stripe (or let Checkout inline price it — the
   app sends `price_data`, so no Stripe price objects are needed).
2. Add a webhook endpoint at `https://aisharc.com/stripe/webhook` for:
   `checkout.session.completed`, `invoice.paid`,
   `customer.subscription.*`.
3. Copy the signing secret to `STRIPE_WEBHOOK_SECRET`.
4. Set `STRIPE_API_KEY` and `ADMIN_TOKEN` in the app's environment.
5. Send a test purchase through the Stripe test cards and confirm the Final
   card appears in the dashboard.

### Stage 3 tests + smoke

`python3 -m pytest tests/ -q` — 52 tests, no real Stripe/network calls
(`billing.set_stripe_adapter(StripeStub())` in tests). Smoke:
`python3 scripts/smoke_stage3.py` — runs the real app with the Stripe stub and
a real browser: purchase → dashboard Final card → PDF → self-serve cancel;
screenshots in `qa/stage3/`.

### Stage 3 notes

- Final card renders from the same card renderer as Preliminary/Sample,
  extended with every finding + the prioritised fix list.
  **TODO(audit-spec Rev 6):** the Rev 6 Final card layout file has NOT
  arrived; when it does, the swap is one renderer change in
  `app/pages.py::render_final_card` (plus stored fields on `FinalCard`).
  Flag Devin within a week of PDF work (client profile open item).
- The PDF export uses Playwright with the system Chromium
  (`/usr/local/bin/chromium`, `--no-sandbox`).


## Railway deploy (the app host — Stage 3)

The marketing shell stays on GitHub Pages. The dynamic app (Stage 2/3
routes, Stripe checkout, dashboard, PDF export) runs on Railway, deployed
from this repo. Configuration lives in the repo (`Dockerfile` +
`railway.json`, Dockerfile builder), so deploying is a one-sitting job —
nothing below needs a terminal.

### The one sitting (Tim, with Devin on the env vars)

1. **Project**: railway.com → logged in as Tim → **New Project** →
   **Deploy from GitHub repo** → pick `timsthomasson-cpu/AI-Sharc`.
2. **Branch**: when Railway shows the service, open it → **Settings** →
   **Source** → set the branch to `stage-3-monetize`. Railway builds the
   repo `Dockerfile` automatically (builder is set in `railway.json`).
3. **Database**: back on the project canvas → **+ Create** →
   **Database** → **Add PostgreSQL**.
4. **Env vars**: on the app service → **Variables** → add:
   - `DATABASE_URL` — click **Connect** on the Postgres service and copy
     its `DATABASE_URL` (keep Railway's `postgresql://` value as-is; the
     app's SQLAlchemy config also accepts it).
   - `BASE_URL` = `https://app.aisharc.com`
   - `FLOW_ORIGIN` = `https://app.aisharc.com`
   - `SECRET_KEY` — new random value:
     `python3 -c 'import secrets; print(secrets.token_hex(32))'` (Devin can
     run this anywhere; paste the output). Sessions are signed with it.
   - `MAILER` = `sendgrid`, `SENDGRID_API_KEY` and `MAIL_FROM` =
     `cards@aisharc.com` — per the SendGrid section above.
   - `ADMIN_TOKEN` — new random value, same generator (empty = admin
     endpoints stay closed, so set it).
   - `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` — add now or later; empty
     keeps checkout off (honest 503 page). See the Stripe checklist below.
5. **Custom domain**: app service → **Settings** → **Networking** →
   **Custom Domain** → add `app.aisharc.com`. Railway shows a CNAME target.
6. **DNS (Tim, at the registrar, after step 5)**:

   | Type | Name | Value |
   |---|---|---|
   | CNAME | app | <the Railway-assigned CNAME target> |

   Note: this is a separate subdomain from the Pages site — the existing
   `@` / `www` / email records above stay untouched. The domain goes live
   when the CNAME resolves; Railway provisions the TLS certificate
   automatically.

7. **Redeploy**: Railway redeploys on every push to `stage-3-monetize`.
   First deploy: after the vars are set, click **Deploy** (or push once).

### Stripe webhook URL — configure LAST

Once `https://app.aisharc.com` resolves and the deploy is green
(`https://app.aisharc.com/healthz` returns `{"ok": true}`):

- Stripe Dashboard → Developers → **Webhooks** → **Add endpoint** →
  URL: `https://app.aisharc.com/stripe/webhook` → events:
  `checkout.session.completed`, `invoice.paid`,
  `customer.subscription.*` → copy the signing secret to
  `STRIPE_WEBHOOK_SECRET` (step 4) and redeploy.

(The webhook is last because Stripe verifies the endpoint URL is reachable.
Full checklist: "Stripe setup checklist" above.)

### Health check

Railway's healthcheck hits `GET /healthz` (path set in `railway.json`).
Locally: `docker build -t aisharc . && docker run -p 8000:8000 aisharc` then
`curl localhost:8000/healthz`. PDF export uses the apt Chromium from the
image — no Playwright browser download happens at build time.

## Later stages (so DNS can be planned once)
- Stage 2 adds the FastAPI app (Get Audited flow). GitHub Pages can serve only static pages — when Stage 2 ships, the dynamic app needs a host (a small VPS/Fly/Railway etc.). Decision deferred; the marketing shell stays on Pages regardless.
- Stage 3 (this branch) adds Stripe checkout + dashboard; needs `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET` and `ADMIN_TOKEN` env + the webhook endpoint URL (same host decision as Stage 2) — see the Stage 3 section above.

## PRODUCTION GATE — Supabase cutover BEFORE Stripe goes live (agreed 2026-11-13)

The Railway/Postgres deployment is the SANDBOX. Production database = Supabase (Postgres).

Order of operations (Tim + Devin + Marketing Manager):
1. Create the Supabase project (supabase.com, GitHub login) — region close to customers (US East for Texas).
2. Copy Supabase's connection string (Project Settings → Database → Connection string → use the **connection pooler** / "Transaction" mode URI, port 6543) and replace `DATABASE_URL` in Railway's variables → auto-redeploy.
3. Verify: `https://app.aisharc.com/healthz` + one submit→verify→card flow (tables are auto-created on first boot).
4. If the sandbox accumulated real sign-ups worth keeping: export via `pg_dump` from Railway Postgres, import to Supabase, BEFORE announcing anything. (Sandbox-only test rows: skip migration.)
5. THEN Stripe: keys into Railway, webhook endpoint `https://app.aisharc.com/stripe/webhook` (checkout.session.completed, invoice.paid, customer.subscription.*), signing secret as `STRIPE_WEBHOOK_SECRET`.
6. FLOW_ORIGIN flip + gh-pages redeploy (Marketing Manager) → launch.

Do NOT put live Stripe keys in while DATABASE_URL still points at sandbox Postgres.
