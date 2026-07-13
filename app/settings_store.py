"""
Central place for reading/writing the editable Settings.

Everything here has a sensible default (matching the old env-var-only
behaviour), so if nothing has ever been saved from the Settings page, the
app behaves exactly as it did before. Saved values are stored one row per
key in the app_settings table, each value JSON-encoded.
"""
import json
from sqlalchemy.orm import Session

from . import models
from .config import settings as env_settings

DEFAULTS = {
    "match_threshold": env_settings.MIN_MATCH_SCORE,
    "min_ghana_job_results": env_settings.MIN_GHANA_JOB_RESULTS,
    "feed_window_days": env_settings.FEED_WINDOW_DAYS,

    "smtp_host": env_settings.SMTP_HOST,
    "smtp_port": env_settings.SMTP_PORT,
    "smtp_user": env_settings.SMTP_USER,
    "smtp_password": env_settings.SMTP_PASSWORD,
    "digest_from": env_settings.DIGEST_FROM,
    "digest_recipients": env_settings.DIGEST_RECIPIENTS,

    "crawl_schedule_time": "07:00",
    "crawl_timezone": "Africa/Accra",

    "ai_provider": "rule-based",

    "notify_high_priority": True,
    "notify_deadline_3_days": True,
    "notify_donor_watch": True,
    "donor_watch_keywords": "unicef",
    "notify_scan_complete": True,

    "theme_default": "light",

    "extra_sector_keywords": {},
    "extra_role_keywords": "",
    "extra_negative_keywords": "",
}


def _get_row(db: Session, key: str):
    return db.query(models.AppSetting).filter(models.AppSetting.key == key).first()


def get_setting(db: Session, key: str):
    row = _get_row(db, key)
    if row is None:
        return DEFAULTS.get(key)
    try:
        return json.loads(row.value)
    except Exception:
        return DEFAULTS.get(key)


def get_all_settings(db: Session) -> dict:
    result = dict(DEFAULTS)
    rows = db.query(models.AppSetting).all()
    for row in rows:
        try:
            result[row.key] = json.loads(row.value)
        except Exception:
            pass
    return result


def set_setting(db: Session, key: str, value) -> None:
    row = _get_row(db, key)
    encoded = json.dumps(value)
    if row is None:
        row = models.AppSetting(key=key, value=encoded)
        db.add(row)
    else:
        row.value = encoded
    db.commit()


def set_many(db: Session, updates: dict) -> None:
    for key, value in updates.items():
        if value is None:
            continue
        set_setting(db, key, value)
