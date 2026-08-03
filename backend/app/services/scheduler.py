"""
Periodic Re-verification Scheduler
====================================
Uses APScheduler to run two background jobs:

  1. reverify_all_regulations — monthly: re-fetches source_url for every
     regulation and updates verification scores. Flags CONTENT_DRIFT_DETECTED
     and POSSIBLE_AMENDMENT when the live page diverges from stored content.

  2. check_amendment_headers — same schedule: separately checks HTTP
     Last-Modified headers against stored publication_date without full
     text fetch (fast, low-bandwidth).

Configuration:
  SOURCE_REVERIFY_INTERVAL_DAYS — env var, default 30
  Set to 1 for daily, 7 for weekly, 30 for monthly.
"""

import os
import logging
import datetime
from typing import Optional

logger = logging.getLogger("compliance_platform.scheduler")

_scheduler: Optional[object] = None


def _reverify_job():
    """Periodic job: re-verify source URLs for all regulations due a re-check."""
    from app.core.database import SessionLocal
    from app.models.domain import Regulation
    from app.services.source_url_verifier import verify_regulation_source_url

    interval_days = int(os.getenv("SOURCE_REVERIFY_INTERVAL_DAYS", "30"))
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=interval_days)

    db = SessionLocal()
    try:
        # Regulations that have never been verified OR are overdue OR previously flagged
        regs = db.query(Regulation).filter(
            (Regulation.source_url.isnot(None)) &
            (
                (Regulation.source_url_last_verified_at.is_(None)) |
                (Regulation.source_url_last_verified_at < cutoff) |
                (Regulation.source_url_verified == -1)
            )
        ).all()

        logger.info("Periodic re-verification: %d regulations queued", len(regs))

        for reg in regs:
            try:
                result = verify_regulation_source_url(reg, db)
                if result.get("source_url_verified") == -1:
                    logger.warning(
                        "Re-verification MISMATCH: %s — %s (score=%.3f)",
                        reg.id, result.get("source_url_verification_note"),
                        result.get("source_url_verification_score") or 0.0
                    )
            except Exception as e:
                logger.error("Re-verification failed for %s: %s", reg.id, e)
    finally:
        db.close()


def _check_amendment_headers_job():
    """
    Fast job: check Last-Modified HTTP headers against stored publication_date.
    Does not fetch the full page body — just a HEAD request.
    Flags possible_amendment_detected = 1 if server reports the page was
    modified more recently than when we ingested the regulation.
    """
    import urllib.request
    from app.core.database import SessionLocal
    from app.models.domain import Regulation
    from email.utils import parsedate_to_datetime

    db = SessionLocal()
    try:
        regs = db.query(Regulation).filter(Regulation.source_url.isnot(None)).all()
        for reg in regs:
            try:
                req = urllib.request.Request(reg.source_url, method="HEAD")
                req.add_header("User-Agent", "CompliancePlatformVerifier/1.0")
                with urllib.request.urlopen(req, timeout=8) as resp:
                    last_modified_str = resp.headers.get("Last-Modified")
                    if last_modified_str:
                        last_modified = parsedate_to_datetime(last_modified_str)
                        last_modified_naive = last_modified.replace(tzinfo=None)
                        reg_pub_dt = datetime.datetime.combine(reg.publication_date, datetime.time.min)
                        if last_modified_naive > reg_pub_dt:
                            reg.possible_amendment_detected = 1
                            reg.needs_human_review = 1
                            logger.warning(
                                "AMENDMENT HEADER DETECTED: %s — Last-Modified %s > publication_date %s",
                                reg.id, last_modified_str, reg.publication_date
                            )
            except Exception:
                pass  # Silent: HEAD requests often blocked; full verify_job will catch real issues
        db.commit()
    finally:
        db.close()


def start_scheduler():
    """Start the APScheduler background scheduler. Call from app lifespan."""
    global _scheduler

    interval_days = int(os.getenv("SOURCE_REVERIFY_INTERVAL_DAYS", "30"))

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.warning(
            "APScheduler not installed — periodic re-verification disabled. "
            "Run: pip install apscheduler"
        )
        return None

    _scheduler = BackgroundScheduler(daemon=True)

    _scheduler.add_job(
        _reverify_job,
        trigger=IntervalTrigger(days=interval_days),
        id="reverify_all_regulations",
        name=f"Source URL Re-verification (every {interval_days} days)",
        replace_existing=True,
        next_run_time=datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
    )

    _scheduler.add_job(
        _check_amendment_headers_job,
        trigger=IntervalTrigger(days=interval_days),
        id="check_amendment_headers",
        name=f"Amendment Header Check (every {interval_days} days)",
        replace_existing=True,
        next_run_time=datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
    )

    _scheduler.start()
    logger.info(
        "Periodic re-verification scheduler started — interval: %d days, "
        "first run in 5 min",
        interval_days
    )
    return _scheduler


def stop_scheduler():
    """Shut down scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Periodic re-verification scheduler stopped")


def run_reverify_now() -> dict:
    """
    Trigger an immediate full re-verification sweep.
    Called by POST /api/v1/regulations/re-verify-all.
    Runs synchronously (blocking) for the admin endpoint.
    """
    from app.core.database import SessionLocal
    from app.models.domain import Regulation
    from app.services.source_url_verifier import verify_regulation_source_url

    db = SessionLocal()
    results = {"verified": 0, "mismatch": 0, "failed": 0, "skipped": 0}
    try:
        regs = db.query(Regulation).filter(Regulation.source_url.isnot(None)).all()
        for reg in regs:
            try:
                result = verify_regulation_source_url(reg, db)
                v = result.get("source_url_verified", 0)
                if v == 1:
                    results["verified"] += 1
                elif v == -1:
                    results["mismatch"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                logger.error("Re-verification failed for %s: %s", reg.id, e)
                results["failed"] += 1

        skipped = db.query(Regulation).filter(Regulation.source_url.is_(None)).count()
        results["skipped"] = skipped
        results["total_regulations"] = len(regs) + skipped
        return results
    finally:
        db.close()
