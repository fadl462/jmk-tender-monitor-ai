from pydantic import BaseModel
from typing import Optional
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

    class Config:
        from_attributes = True


class AssistantQuery(BaseModel):
    question: str
