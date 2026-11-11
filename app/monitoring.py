# AI Sharc — monthly monitoring: re-runs the Preliminary scanner against the
# Final card's site on a simple in-app scheduler (background thread, started
# by the FastAPI lifespan; a cron hitting /admin/run-monitoring works too for
# multi-worker deploys). Emails the firm when the grade changes. Stops after
# the included months unless a paid monitoring subscription is active.
import json
import logging
import threading
import time

from sqlalchemy import select

from app import mailer
from app.config import settings
from app.models import AuditRequest, FinalCard, MonitorScan, utcnow

log = logging.getLogger("aisharc.monitoring")
_stop = threading.Event()
_thread = None


def due_for_scan(final, now=None):
    """A Final card is due when monitoring is active and the last scan is
    older than the interval (never scanned = due immediately after grant)."""
    now = now or utcnow()
    if not final.subscription_active or final.canceled_at is not None:
        return False
    if now >= final.monitoring_ends_at:
        return False
    last = final.last_scan_at
    if last is None:
        return True
    if last.tzinfo is None:
        import datetime as dt
        last = last.replace(tzinfo=dt.timezone.utc)
    return (now - last).total_seconds() >= settings.monitoring_scan_interval_days * 86400


def run_scan(db, final, scanner):
    """One monitoring scan: re-run the scanner, store the result, email on
    grade change. Updates the Final card's current grade/fixes in place so
    the dashboard always shows the latest state (history lives in MonitorScan)."""
    req = db.get(AuditRequest, final.request_id)
    grade, headline, findings = scanner.scan_site("https://" + req.normalized_domain)
    fixes = [{"title": f["title"], "detail": f["detail"], "priority": 1}
             for f in findings if not f.get("ok", True)]
    fixes.sort(key=lambda x: x["priority"])
    changed = grade != final.grade
    prev = final.grade
    db.add(MonitorScan(final_card_id=final.card_id, request_id=req.id,
                       grade=grade, headline=headline,
                       findings_json=json.dumps(findings),
                       fixes_json=json.dumps(fixes),
                       previous_grade=prev, grade_changed=changed))
    final.grade = grade
    final.headline = headline
    final.findings_json = json.dumps(findings)
    final.fixes_json = json.dumps(fixes)
    final.last_scan_at = utcnow()
    db.flush()
    if changed:
        mailer.send_grade_change_email(
            req.email, req.normalized_domain, prev, grade,
            f"{settings.base_url}/final/{final.card_id}")
        from app import security
        security.emit(db, "monitoring_grade_changed", request_id=req.id,
                      card_id=final.card_id, meta=f"{prev}->{grade}")
    db.commit()
    return changed


def scan_all_due(db, scanner):
    """Scan every Final card that is due. Returns the number scanned."""
    finals = db.scalars(select(FinalCard)).all()
    n = 0
    for final in finals:
        if due_for_scan(final):
            try:
                run_scan(db, final, scanner)
                n += 1
            except Exception:
                log.exception("monitoring scan failed for %s", final.card_id)
                db.rollback()
    return n


def _loop():
    from app.db import SessionLocal
    from app import scanner
    while not _stop.is_set():
        try:
            db = SessionLocal()
            try:
                scan_all_due(db, scanner)
            finally:
                db.close()
        except Exception:
            log.exception("monitoring loop error")
        _stop.wait(settings.monitoring_poll_seconds)


def start():
    global _thread
    if _thread is None or not _thread.is_alive():
        _stop.clear()
        _thread = threading.Thread(target=_loop, name="aisharc-monitoring", daemon=True)
        _thread.start()


def stop():
    _stop.set()
