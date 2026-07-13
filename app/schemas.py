from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime


class OpportunityOut(BaseModel):
    id: str
    kind: str
    title: str
    org: str
    location: str
    sector: str
    deadline: str
    employment_type: str
    match_score: int
    match_reason: str
    source: str
    source_url: str
    source_tier: str
    first_seen: Optional[datetime] = None

    class Config:
        from_attributes = True


class BoardItemIn(BaseModel):
    title: str
    funder: Optional[str] = ""
    sector: Optional[str] = ""
    status: Optional[str] = "New"
    deadline: Optional[str] = ""
    value: Optional[str] = ""
    ref: Optional[str] = ""
    link: Optional[str] = ""
    notes: Optional[str] = ""


class BoardItemUpdate(BaseModel):
    title: Optional[str] = None
    funder: Optional[str] = None
    sector: Optional[str] = None
    status: Optional[str] = None
    deadline: Optional[str] = None
    value: Optional[str] = None
    ref: Optional[str] = None
    link: Optional[str] = None
    notes: Optional[str] = None


class BoardItemOut(BaseModel):
    id: str
    title: str
    funder: str
    sector: str
    status: str
    deadline: str
    value: str
    ref: str
    link: str
    notes: str
    added_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CrawlStatusOut(BaseModel):
    state: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    tenders_in_feed: int = 0
    jobs_in_feed: int = 0
    new_items_last_run: int = 0
    email_sent: int = 0
    email_note: str = ""
    error: str = ""
    source_stats: str = "{}"

    class Config:
        from_attributes = True


class AssistantQuery(BaseModel):
    question: str


class AppSettingsOut(BaseModel):
    match_threshold: int
    min_ghana_job_results: int
    feed_window_days: int

    digest_from: str
    digest_recipients: str
    brevo_api_key_set: bool  # never send the real key back, just whether one is stored

    crawl_schedule_time: str
    crawl_timezone: str

    ai_provider: str

    notify_high_priority: bool
    notify_deadline_3_days: bool
    notify_donor_watch: bool
    donor_watch_keywords: str  # comma-separated
    notify_scan_complete: bool

    theme_default: str

    extra_sector_keywords: Dict[str, str]   # sector -> comma-separated extra keywords
    extra_role_keywords: str                 # comma-separated
    extra_negative_keywords: str              # comma-separated


class AppSettingsIn(BaseModel):
    match_threshold: Optional[int] = None
    min_ghana_job_results: Optional[int] = None
    feed_window_days: Optional[int] = None

    digest_from: Optional[str] = None
    digest_recipients: Optional[str] = None
    brevo_api_key: Optional[str] = None  # only written if non-empty

    crawl_schedule_time: Optional[str] = None
    crawl_timezone: Optional[str] = None

    ai_provider: Optional[str] = None

    notify_high_priority: Optional[bool] = None
    notify_deadline_3_days: Optional[bool] = None
    notify_donor_watch: Optional[bool] = None
    donor_watch_keywords: Optional[str] = None
    notify_scan_complete: Optional[bool] = None

    theme_default: Optional[str] = None

    extra_sector_keywords: Optional[Dict[str, str]] = None
    extra_role_keywords: Optional[str] = None
    extra_negative_keywords: Optional[str] = None


class NotificationOut(BaseModel):
    id: str
    type: str
    title: str
    message: str
    opportunity_id: str
    is_read: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
