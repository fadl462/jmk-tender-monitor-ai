from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import AppSettingsOut, AppSettingsIn
from .. import settings_store

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=AppSettingsOut)
def get_settings(db: Session = Depends(get_db)):
    s = settings_store.get_all_settings(db)
    return AppSettingsOut(
        match_threshold=s["match_threshold"],
        min_ghana_job_results=s["min_ghana_job_results"],
        feed_window_days=s["feed_window_days"],
        digest_from=s["digest_from"],
        digest_recipients=s["digest_recipients"],
        brevo_api_key_set=bool(s.get("brevo_api_key")),
        crawl_schedule_time=s["crawl_schedule_time"],
        crawl_timezone=s["crawl_timezone"],
        ai_provider=s["ai_provider"],
        notify_high_priority=s["notify_high_priority"],
        notify_deadline_3_days=s["notify_deadline_3_days"],
        notify_donor_watch=s["notify_donor_watch"],
        donor_watch_keywords=s["donor_watch_keywords"],
        notify_scan_complete=s["notify_scan_complete"],
        theme_default=s["theme_default"],
        extra_sector_keywords=s.get("extra_sector_keywords", {}),
        extra_role_keywords=s.get("extra_role_keywords", ""),
        extra_negative_keywords=s.get("extra_negative_keywords", ""),
    )


@router.put("", response_model=AppSettingsOut)
def update_settings(update: AppSettingsIn, db: Session = Depends(get_db)):
    data = update.dict(exclude_unset=True)

    # brevo_api_key is write-only: only touch it if a real value was sent
    incoming_key = data.pop("brevo_api_key", None)
    if incoming_key:
        settings_store.set_setting(db, "brevo_api_key", incoming_key)

    settings_store.set_many(db, data)

    return get_settings(db)
