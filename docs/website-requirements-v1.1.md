# Website Requirements — AI Sharc (aisharc.com)
**Version:** 1.1 | **Date:** 2026-11-11 | **Status:** Build spec (living doc — the Website Specification). Basis: Tim's requirements sheet (updated 11 Nov 2026) + decisions 9 Nov 2026 + Audit Spec v1.21. Changelog at bottom.

## Decisions locked (Tim, 9 Nov 2026)
1. **Audit form:** anyone can submit any site URL. Business email required, validated (double opt-in verification email before the Preliminary card is viewable). Preliminary is always free.
2. **Pricing (direction locked, final numbers pending):**
   - Preliminary Report Card: **free**, always.
   - Final Report Card: **$149, introductory $99** (intro applies to first 500 firms per business plan).
   - Final includes a **monitoring subscription for the first 3–4 months** (Tim to pick 3 or 4 — recommendation below).
   - After the included months: **$30/month, introductory $25/month**, **month-to-month, cancel anytime** self-serve.
3. **Accounts:** magic-link (email = identity, no passwords). Open to suggestions — this is my recommendation and the default.
4. **Additions agreed:** Privacy/Terms, pricing page, contact/about, FAQ, spam protection, analytics.
5. **Trade-group pages (added 11 Nov):** a separate web page per trade group with trade-specific marketing. Launch list (Licences Home Trade): HVAC Contractor, Plumber, Electrician, Roofing Contractor. List grows over time — pages built from a shared template with per-trade copy, not hand-built per trade.
6. **Customer reviews (added 11 Nov):** capture and display customer reviews, with a path to add them to Google (e.g. direct link to the firm's Google review flow). Display respects spec honesty rules — no averaging across platforms, platform + count + date always cited.
7. **High-level audit overview page (added 11 Nov):** public page showing a high-level overview of how the audit works — deliberately does NOT expose scoring details, item lists, weights, or thresholds to competitors. The detailed audit description is internal (spec section 12 exposure rules apply).

### Pricing recommendation — pick 4 months, not 3
$99 / 4 months = $24.75/mo embedded — almost exactly the $25 intro rate, so the story is clean: *"$99 gets the full audit plus your first 4 months. Then $25/mo (intro)."* With 3 months, the embedded rate is $33/mo, which quietly overpromises the intro. Final numbers ($149/$99, $30/$25) are yours to set; structure is locked.

## Pages (final list)
Must: Home · Get audited (form + validation) · Preliminary card viewer · Final Report Card landing + Stripe checkout · Account dashboard · Pricing · How the audit works (high-level only — see decision 7) · Sample cards · Privacy + Terms · Contact/About · Trade-group pages ×4 (HVAC, Plumbing, Electrical, Roofing — template-driven) · Review capture/display
Should: Articles/Digest (launch shell + 2–3 seeded posts) · FAQ
Later: additional trade groups beyond the four LHT trades · other states

## Conversion path (final)
1. Visitor submits site URL + business email on Get Audited.
2. Verification email (magic link). Verified → Preliminary Report Card viewable on site (counts toward spec's 10-per-firm-per-query limit; ledger recorded).
3. Card shows fixes + grade → CTA: Final Report Card landing page.
4. Stripe checkout: $99 intro / $149. Purchase → Final card in dashboard + PDF download.
5. Subscription active for included 3–4 months → re-scan updates emailed + dashboard.
6. After included months: $25/mo intro → $30/mo. Month-to-month. Self-serve cancel in dashboard + confirmation email.
7. Marketing emails (opt-in aware, CAN-SPAM mechanics: postal address, ad identification, 10-day opt-out honouring, suppression list).

## Account system (magic-link)
- Email + magic link = login. Sessions via signed cookie (30-day).
- Dashboard: report card history (Preliminary + Final, per firm/query/town per spec card identity), PDF/download per card, subscription status, cancel button, billing receipt history.
- No passwords stored anywhere. Email change requires re-verification.

## Technical plan
- FastAPI + Postgres (SQLite audit data ingestible later). Server-side card rendering (HTML + PDF via Playwright). Stripe (checkout + webhooks + cancel). SendGrid (transactional + marketing, SPF/DKIM/DMARC). Honeypot + rate limiting. Plausible-style analytics with funnel: submit → verified → preliminary viewed → final purchased → subscribed.
- Site itself must demo the product: fast, clean HTML, no JS-dependence.

## Launch checklist (trade/review additions)
- [ ] Trade-group pages render from one template; per-trade copy approved by Tim
- [ ] Review capture flow tested end-to-end; Google review link verified for a test firm
- [ ] High-level audit page reviewed to confirm no scoring detail leaks

## Launch checklist
- [ ] Email validation + magic-link flow tested on real inbox
- [ ] 10-per-firm/query Preliminary limit enforced in ledger
- [ ] Stripe: purchase, receipt, included-months tracking, upgrade to $25→$30, cancel, webhook failure handling
- [ ] PDF export both card types; download in dashboard
- [ ] Subscription cancel flow + confirmation email
- [x] CAN-SPAM: postal address live (PO Box 1622, Coppell, TX 75019), suppression list, opt-out honoured
- [ ] Privacy/Terms published before any marketing send
- [ ] Mobile verified on real phone (card viewer + checkout)
- [ ] Favicon (fin-only icon) + social share image
- [ ] Backups + restore tested; daily smoke tests live

## Changelog
- **v1.1 (2026-11-11):** Added trade-group pages (decision 5, per Requirements sheet Trades tab), customer review capture/display with Google add path (decision 6), high-level audit overview page with no competitor-exposed detail (decision 7). Converted from "v1.0 LOCKED" to living Website Specification.
- **v1.0 (2026-11-09):** Initial locked spec.
