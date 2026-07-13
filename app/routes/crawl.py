import threading
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from .. import models
from ..config import settings
from ..crawler import run_crawl
from ..schemas import CrawlStatusOut

router = APIRouter(prefix="/api/crawl", tags=["crawl"])

_lock = threading.Lock()
_running = False


def _get_or_create_status(db: Session) -> models.CrawlStatus:
    status = db.query(models.CrawlStatus).filter(models.CrawlStatus.id == "singleton").first()
    if not status:
        status = models.CrawlStatus(id="singleton", state="idle")
        db.add(status)
        db.commit()
        db.refresh(status)
    return status


def _background_crawl():
    global _running
    db = SessionLocal()
    try:
        status = _get_or_create_status(db)
        status.state = "running"
        status.started_at = datetime.utcnow()
        db.commit()

        result = run_crawl(db)

        status = _get_or_create_status(db)
        status.state = "idle"
        status.finished_at = datetime.utcnow()
        status.tenders_in_feed = result["tendersInFeed"]
        status.jobs_in_feed = result["jobsInFeed"]
        status.new_items_last_run = result["newItemsThisRun"]
        status.email_sent = 1 if result["emailSent"] else 0
        status.email_note = result["emailNote"]
        status.error = ""
        status.source_stats = json.dumps(result.get("sourceStats", {}))
        db.commit()
    except Exception as e:
        status = _get_or_create_status(db)
        status.state = "idle"
        status.finished_at = datetime.utcnow()
        status.error = str(e)
        db.commit()
    finally:
        db.close()
        with _lock:
            _running = False


@router.post("/run")
def trigger_crawl(token: str = Query(default="")):
    global _running
    if settings.CRON_SECRET and token != settings.CRON_SECRET:
        raise HTTPException(401, "unauthorized")

    with _lock:
        if _running:
            return {"status": "already running"}
        _running = True

    threading.Thread(target=_background_crawl, daemon=True).start()
    return {"status": "started", "note": "Checking 17 sources takes a minute or two. Poll /api/crawl/status for progress."}


@router.get("/status", response_model=CrawlStatusOut)
def crawl_status(db: Session = Depends(get_db)):
    return _get_or_create_status(db)
