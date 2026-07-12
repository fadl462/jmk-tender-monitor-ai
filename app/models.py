"""
Two tables:

- Opportunity: everything the crawler finds (tenders and jobs), scored
  and deduplicated. This is what feeds the dashboard's "Today's
  Intelligence" and the Opportunities page.
- BoardItem: JMK's own working pipeline — things a person has deliberately
  added to track (usually pulled in from an Opportunity, but can also be
  added by hand), with a status like New / Reviewing / Submitted / Won.
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from sqlalchemy.sql import func
import uuid

from .database import Base


def gen_id():
    return uuid.uuid4().hex[:16]


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(String, primary_key=True, default=gen_id)
    kind = Column(String, nullable=False)          # "tender" or "job"
    title = Column(String, nullable=False)
    org = Column(String, default="")                # funder (tenders) or employer (jobs)
    location = Column(String, default="")
    sector = Column(String, default="")
    deadline = Column(String, default="")            # YYYY-MM-DD, best-effort
    employment_type = Column(String, default="")
    match_score = Column(Integer, default=0)
    match_reason = Column(Text, default="")
    source = Column(String, default="")
    source_url = Column(String, default="")
    source_tier = Column(String, default="")          # "Ghana" or "International" (jobs only)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())


class BoardItem(Base):
    __tablename__ = "board_items"

    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String, nullable=False)
    funder = Column(String, default="")
    sector = Column(String, default="")
    status = Column(String, default="New")
    deadline = Column(String, default="")
    value = Column(String, default="")
    ref = Column(String, default="")
    link = Column(String, default="")
    notes = Column(Text, default="")
    added_at = Column(DateTime(timezone=True), server_default=func.now())


class CrawlStatus(Base):
    __tablename__ = "crawl_status"

    id = Column(String, primary_key=True, default=lambda: "singleton")
    state = Column(String, default="idle")
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    tenders_in_feed = Column(Integer, default=0)
    jobs_in_feed = Column(Integer, default=0)
    new_items_last_run = Column(Integer, default=0)
    email_sent = Column(Integer, default=0)  # 0/1 as int for simplicity
    email_note = Column(Text, default="")
    error = Column(Text, default="")
