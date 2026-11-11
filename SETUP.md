# AI Sharc — aisharc.com: setup, DNS and run guide

Last updated: 2026-11-11 (Stage 1 live). Owner: Tim (with Devin).

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
1. **Monitoring months included with the Final card: 3 or 4.** Build assumption: **4** (Devin's recommendation: $99 ÷ 4 = $24.75/mo embedded ≈ the $25 intro rate). One-line change: `MONITORING_INCLUDED_MONTHS = 4` in `build/content_pages.py`, then rebuild. If flipped to 3, pricing copy updates everywhere from the constant.
2. **GitHub push token** — provided 2026-11-11; used for pushes and Pages deploy.

## Repo / branches
- `main` — docs + requirements (Website Requirements v1.1 canonical).
- `stage-1-marketing-shell` — 13 static no-JS pages + brand assets + build system. QA: `qa/qa_check.py` (ALL CHECKS PASSED), screenshots in `qa/screenshots/`, report in `qa/stage-1-report.md`.
- `gh-pages` — deploy branch (flat copy of `site/` + CNAME).
- Stage 2 (`stage-2-get-audited`, FastAPI Get-Audited flow) in progress.

## Run the static build
```
python3 build/build.py     # regenerates site/ (13 pages + sitemap + robots)
python3 qa/qa_check.py     # link/metadata/leak checks
```

## Later stages (so DNS can be planned once)
- Stage 2 adds the FastAPI app (Get Audited flow). GitHub Pages can serve only static pages — when Stage 2 ships, the dynamic app needs a host (a small VPS/Fly/Railway etc.). Decision deferred; the marketing shell stays on Pages regardless.
- Stage 3 adds Stripe checkout + dashboard; needs `STRIPE_API_KEY` env + webhook endpoint URL (same host decision as Stage 2).
