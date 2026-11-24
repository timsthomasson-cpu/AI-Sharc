# Handoff — Digest email subscription (repo: AI-Sharc, branch stage-3-monetize)

Commit 149d990 (local only, NOT pushed — orchestrator pushes). Full suite: 72 passed
(53 pre-existing + 19 new in tests/test_digest.py). Site rebuilt, byte-identical to
committed site/.

## Files changed

- `app/models.py` — `DigestSubscriber` (unique email, confirmed_at/unsubscribed_at
  nullable, single-use confirmation_token + 30-day confirmation_expires_at,
  long-lived per-subscriber unsubscribe_token, source) and `DigestSend` ledger
  (unique per subscriber_id+article_slug). NOTE: these two models plus the mailer
  and config additions landed inside commit 77b9d85 (another agent's
  texas-hvac-contractor commit swept up in-progress files with its `git add -A`);
  my commit 149d990 carries the rest. No duplicate definitions — verified.
- `app/routes_digest.py` (new, mounted in `app/main.py`) — POST /digest/subscribe
  (honeypot silent-200, email validation 422, per-IP/per-email hourly rate limits
  reusing submit_rate_* settings, counted via `digest_subscribe` funnel events),
  GET /digest/confirm/<token> (404 unknown / 410 used-or-expired / 200 confirms),
  GET /digest/unsubscribe/<token> (idempotent), GET+POST /admin/digest/send
  (ADMIN_TOKEN auth, ?slug=..., 404 unknown article).
- `app/mailer.py` — `send_digest_confirmation(to, confirm_url, unsubscribe_url="")`
  and `send_digest_weekly(to, article_title, article_url, unsubscribe_url)`, plus
  `_digest_footer`: PO Box 1622, Coppell, TX 75019 + unsubscribe link +
  "You're receiving this because you subscribed at aisharc.com/digest". Article
  links only, no scoring detail (§12).
- `app/digest_sender.py` (new) — `send_digest_batch(db, slug)`: emails one article
  to confirmed, non-unsubscribed subscribers; idempotent per (subscriber, article)
  via DigestSend; slug defaults to DIGEST_LATEST env, else newest ARTICLES entry.
- `app/config.py` — `DIGEST_LATEST` env → `settings.digest_latest_slug`.
- `build/content_digest.py` — subscribe form (email + honeypot, plain POST to
  {FLOW_ORIGIN}/digest/subscribe, no JS, anchor id="subscribe") on the digest
  index; one-line subscribe link in every article footer. Also FIXED a pre-existing
  bug: all six digest pages shipped with a literal unresolved `{FLOW_ORIGIN}`
  placeholder in their CTA links; a resolver now runs (site/ rebuilt).
- `tests/test_digest.py` (new, 19 tests) + helpers in `tests/helpers.py`
  (last_digest_subscriber, digest_subscriber_by_email, digest_send_count,
  expire_digest_confirmation).

## Behaviour notes

- Duplicate subscribe is idempotent: unconfirmed → token refreshed + resent;
  already confirmed → nothing sent, row untouched; unsubscribed → row reset
  (unsubscribed_at/confirmed_at cleared, fresh tokens) and re-confirmation
  required before any weekly email (suppression honoured until then).
- Confirmation tokens are single-use: 404 unknown, 410 used or expired
  (same shape as the verify magic link).
- Weekly send returns {"sent", "skipped", "slug"}; retried runs skip already-sent
  pairs via the unique constraint.

## Risks / open questions

- The SSR shell's header/footer nav uses relative links, so on /digest/* app
  routes they resolve under /digest/ (pre-existing pattern on /card/* and
  /final/* too). Body links are root-absolute. Harmless but worth a look if
  the shell is ever made path-aware.
- The other agent's commit 77b9d85 was made while this task was in flight; if
  it gets rebased/reverted, app/models.py, app/mailer.py and app/config.py
  digest changes ride along with it, not with 149d990.
- Unsubscribe links are per-subscriber and long-lived; rotation on resubscribe
  was deliberately not done (old link keeps working, which is CAN-SPAM-safe).
