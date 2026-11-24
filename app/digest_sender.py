# AI Sharc — weekly Digest send. Emails one article to every confirmed,
# non-unsubscribed subscriber. Idempotent per (subscriber, article) via the
# digest_sends ledger, so a retried cron run never double-sends. Digest emails
# carry article links only — no scoring detail anywhere (§12).
from sqlalchemy import select

from app import mailer
from app.config import settings
from app.models import DigestSend, DigestSubscriber


def latest_slug():
    """The article to send when none is given: DIGEST_LATEST env, else the
    newest article in the Digest content module."""
    if settings.digest_latest_slug:
        return settings.digest_latest_slug
    from build.content_digest import ARTICLES
    return ARTICLES[0]["slug"]


def send_digest_batch(db, slug=""):
    """Email one article to all confirmed, non-unsubscribed subscribers.
    Returns {"sent": n, "skipped": m, "slug": slug}; raises ValueError for an
    unknown slug. Idempotent per (subscriber, article)."""
    from build.content_digest import ARTICLES
    slug = slug or latest_slug()
    article = next((a for a in ARTICLES if a["slug"] == slug), None)
    if article is None:
        raise ValueError(f"unknown article: {slug}")
    article_url = f"{settings.base_url}/digest/{slug}"
    subs = db.scalars(select(DigestSubscriber).where(
        DigestSubscriber.confirmed_at.is_not(None),
        DigestSubscriber.unsubscribed_at.is_(None)
    ).order_by(DigestSubscriber.id)).all()
    sent = skipped = 0
    for sub in subs:
        already = db.scalar(select(DigestSend).where(
            DigestSend.subscriber_id == sub.id,
            DigestSend.article_slug == slug))
        if already is not None:
            skipped += 1
            continue
        unsub_url = f"{settings.base_url}/digest/unsubscribe/{sub.unsubscribe_token}"
        mailer.send_digest_weekly(sub.email, article["title"], article_url, unsub_url)
        db.add(DigestSend(subscriber_id=sub.id, article_slug=slug))
        sent += 1
    db.commit()
    return {"sent": sent, "skipped": skipped, "slug": slug}
