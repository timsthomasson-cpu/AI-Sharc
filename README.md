# AI Sharc

AI Shopping Health Audit Report Card — audits how easily AI shopping agents can
find, read, and trust a home-services firm's website, and issues a graded
Report Card with exact fixes.

- Governing spec: AI Sharc Audit Specification v1.17 (internal, not published)
- Website requirements: see docs/ (`website-requirements-v1.1.md`, canonical)
- Launch: Texas HVAC

## Stage 2 — Get Audited flow (branch `stage-2-get-audited`)

FastAPI app in `app/`:

- Serves the Stage 1 marketing shell (13 pages, byte-identical to the
  `site/` build — `python3 -m build.build` still regenerates it) plus
  the dynamic flow. Server-rendered HTML, **no JavaScript dependence**.
- `GET /get-audited`: URL + business email form with a honeypot field and
  per-IP/per-email hourly rate limits.
- `POST /get-audited`: validates and stores the request, sends a
  **single-use magic-link verification email** (double opt-in) via a mailer
  adapter (`console` dev backend logs the link; SMTP/SendGrid backends via env).
- `GET /verify/<token>`: marks the request verified, runs the **Preliminary
  scan** (plain-HTTP find/read/trust checks — text-readable services, service
  area, tappable phone, findable contact info, cross-page consistency; every
  finding carries a source URL and check date), computes the A–F grade
  server-side, stores it, and sets a signed `card_session` cookie.
- `GET /card/<id>`: magic-link-gated, server-rendered Preliminary Report Card
  matching the sample-card design. **Summary-level findings only — no item
  rows, weights, thresholds or gate names on any card.** A ledger table
  enforces the 10-views-per-firm-per-query limit.
- Funnel events (`submit → verified → preliminary_viewed`) emitted server-side
  as structured log lines and a `funnel_events` table.
- Storage: SQLAlchemy, Postgres in production via `DATABASE_URL`, SQLite
  fallback for dev/tests.

Run + configure: see **SETUP.md** (env vars, DNS email records for Tim).

Tests: `python3 -m pytest tests/ -q` — form validation, honeypot, rate
limits, magic-link single-use + expiry, double opt-in not bypassable,
10-view ledger, card leak-scan (no scoring-detail phrases), funnel event
order, marketing shell integrity. No real network calls in tests.
