"""
JMK Opportunity Crawler — free, rule-based version.
----------------------------------------------------
No Claude/OpenAI API calls anywhere. Listings are pulled from each source's
HTML and scored with keyword matching against JMK's sectors and the kind of
role/tender language JMK cares about. Ghana job platforms are checked first;
international ones only kick in if Ghana doesn't yield enough matches.

Trade-off, stated plainly: this is noisier than an LLM would be — it can
miss an oddly-worded listing, and deadline detection is a regex guess, not
real understanding. It costs nothing to run, and every result links back to
its source so a person makes the final call.
"""
import re
import time
import socket
import smtplib
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urljoin
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from sqlalchemy.orm import Session

from . import models
from .config import settings

SECTORS = [
    "Agricultural Sector",
    "Business Development & Entrepreneurship",
    "Education",
    "Gender, Child & Social Inclusion",
    "Governance",
    "Socio-Economic Livelihood & Engagement",
    "Land, Natural Resources & Environment",
    "WASH",
]

SECTOR_KEYWORDS = {
    "Agricultural Sector": ["agricultur", "agribusiness", "farm", "cocoa", "crop", "livestock", "agroforestry", "value chain", "cassava", "maize", "smallholder"],
    "Business Development & Entrepreneurship": ["business development", "entrepreneur", "sme", "enterprise", "private sector", "market system", "business plan", "trade polic", "startup", "incubat"],
    "Education": ["education", "teacher", "school", "learning", "curriculum", "vocational", "tvet", "atvet", "literacy", "faculty", "university"],
    "Gender, Child & Social Inclusion": ["gender", "child protection", "child labour", "child labor", "social inclusion", "gbv", "safeguard", "youth", "disabilit", "women empowerment", "gender-based"],
    "Governance": ["governance", "policy", "peacebuilding", "advocacy", "accountab", "public sector", "decentraliz", "local government", "electoral", "anti-corruption", "rule of law"],
    "Socio-Economic Livelihood & Engagement": ["livelihood", "socio-economic", "income generation", "community engagement", "social protection", "resilience", "economic empowerment", "cash transfer"],
    "Land, Natural Resources & Environment": ["land tenure", "natural resource", "environment", "climate", "forestry", "conservation", "biodiversity", "land use", "deforestation"],
    "WASH": ["wash", "water suppl", "sanitation", "hygiene", "borehole", "latrine", "sewage", "waste management"],
}

RESEARCH_CONSULTANCY_KEYWORDS = [
    # study/engagement types — the actual work JMK bids for as a firm
    "baseline", "endline", "midline", "mid-term review", "mid term review", "midterm review",
    "impact assessment", "impact evaluation", "final evaluation", "terminal evaluation",
    "summative evaluation", "formative evaluation", "situational analysis", "needs assessment",
    "feasibility study", "evaluation of", "review of the", "assessment of the", "research study",
    # procurement/consultancy-call language — signals a firm can bid, not an employee post
    "consultant", "consultancy", "consulting firm", "call for consultancy", "expression of interest",
    "request for proposal", "terms of reference", " tor ", "invitation to tender", "rfp",
    "eoi", "procurement", "tender", "invitation for bids", "request for quotation", "rfq",
    "technical assistance", "survey", "data collection", "monitoring and evaluation", "m&e",
]

NEGATIVE_KEYWORDS = [
    "driver", "cook", "cleaner", "security guard", "waiter", "waitress", "receptionist",
    "sales executive", "sales representative", "cashier", "electrician", "plumber",
    "chef", "hospitality", "housekeeping", "barista", "mechanic", "dispatch rider",
    "massage therapist", "class teacher", "shs teacher",
    # individual staff/employment postings — JMK bids as a firm, not as a job applicant
    "officer", "coordinator", "manager", "assistant", "director", "internship", " intern ", "intern,",
    "trainee", "volunteer", "permanent staff", "permanent position", "full-time", "full time",
    "employee", "graduate trainee", "vacancy for staff", "staff member", "line manager",
]

MIN_TITLE_LEN = 12
MAX_TITLE_LEN = 170

TENDER_SOURCES = [
    {"name": "GHANEPS", "url": "https://www.ghaneps.gov.gh/"},
    {"name": "PPA Tender Portal", "url": "https://tenders.ppa.gov.gh/tenders"},
    {"name": "UNGM", "url": "https://www.ungm.org/Public/Notice"},
    {"name": "ReliefWeb", "url": "https://reliefweb.int/jobs"},
    {"name": "Devex", "url": "https://www.devex.com/jobs"},
    {"name": "DevelopmentAid", "url": "https://www.developmentaid.org/tenders/search"},
    {"name": "World Bank Procurement", "url": "https://projects.worldbank.org/en/projects-operations/procurement"},
    {"name": "AfDB Procurement", "url": "https://www.afdb.org/en/projects-and-operations/procurement"},
    {"name": "TED", "url": "https://ted.europa.eu/"},
]

GHANA_JOB_SOURCES = [
    {"name": "Jobsinghana.com — NGO/IGO/INGO", "url": "https://www.jobsinghana.com/jobs/indexnew.php?device=d&indu=130"},
    {"name": "Ghana Current Jobs — NGO/International Agencies", "url": "https://www.ghanacurrentjobs.com/category/ngo-international-agencies/"},
    {"name": "NGO Jobs in Africa — Ghana", "url": "https://ngojobsinafrica.com/job-location/ghana/"},
    {"name": "Jobberman Ghana — Consulting & Strategy", "url": "https://www.jobberman.com.gh/jobs/consulting-strategy"},
    {"name": "Jobberman Ghana — Research, Teaching & Training", "url": "https://www.jobberman.com.gh/jobs/research-teaching-training"},
    {"name": "JobWeb Ghana", "url": "https://jobwebghana.com/jobs/"},
    {"name": "BusinessGhana Jobs", "url": "https://www.businessghana.com/site/jobs"},
    {"name": "Ghanajob.com", "url": "https://www.ghanajob.com/"},
]

INTERNATIONAL_JOB_SOURCES = [
    {"name": "ReliefWeb Jobs", "url": "https://reliefweb.int/jobs"},
    {"name": "Devex Jobs", "url": "https://www.devex.com/jobs"},
    {"name": "UNjobs — Ghana", "url": "https://unjobs.org/duty_stations/ghana"},
    {"name": "Impactpool — Ghana", "url": "https://www.impactpool.org/countries/Ghana"},
    {"name": "DevelopmentAid — Jobs in Ghana", "url": "https://www.developmentaid.org/jobs-in-ghana"},
]

DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\.?,?\s+\d{4}\b"),
    re.compile(r"\b[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"),
]


def fetch_html(url, timeout=12):
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"  [warn] could not fetch {url}: {e}")
        return ""


def find_nearby_deadline(context_text):
    for pattern in DATE_PATTERNS:
        m = pattern.search(context_text)
        if m:
            try:
                dt = dateparser.parse(m.group(0), dayfirst=False, fuzzy=True)
                if dt and 2020 <= dt.year <= 2035:
                    return dt.strftime("%Y-%m-%d")
            except Exception:
                continue
    return ""


ORG_SPLIT_PATTERNS = [" - ", " – ", " — ", " | ", " at "]


def extract_org_from_title(title):
    """Best-effort: many job/tender titles follow 'Role - Organization' or
    'Role at Organization' patterns. Not reliable for every source, but
    catches a meaningful share without needing a per-site scraper."""
    for pat in ORG_SPLIT_PATTERNS:
        if pat in title:
            parts = title.rsplit(pat, 1)
            if len(parts) == 2 and 2 <= len(parts[1].strip()) <= 60:
                candidate = parts[1].strip()
                if any(c.isalpha() for c in candidate):
                    return candidate
    return ""


def score_text(role_text, sector_text, role_keywords):
    t_role = role_text.lower()
    t_sector = sector_text.lower()
    for neg in NEGATIVE_KEYWORDS:
        if neg in t_role:
            return 0, "", "Filtered out — looks unrelated to JMK's research/consultancy scope."

    matched_roles = [kw for kw in role_keywords if kw in t_role]
    if not matched_roles:
        return 0, "", ""
    role_score = min(70, 45 * len(matched_roles))

    best_sector, best_count = "", 0
    for sector, kws in SECTOR_KEYWORDS.items():
        count = sum(1 for kw in kws if kw in t_sector)
        if count > best_count:
            best_sector, best_count = sector, count
    sector_score = min(40, 20 * best_count)

    score = min(100, role_score + sector_score)
    if score == 0:
        return 0, "", ""

    bits = []
    if matched_roles:
        bits.append(f"matches role terms ({', '.join(kw.strip() for kw in matched_roles[:2])})")
    if best_sector:
        bits.append(f"fits {best_sector}")
    reason = "; ".join(bits) if bits else "Keyword match."
    return score, best_sector, reason


def extract_candidates(html, base_url):
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    seen_text = set()
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        if not (MIN_TITLE_LEN <= len(text) <= MAX_TITLE_LEN):
            continue
        if text.lower() in seen_text:
            continue
        seen_text.add(text.lower())
        href = urljoin(base_url, a["href"])
        parent_text = ""
        if a.parent:
            parent_text = " ".join(a.parent.get_text(" ", strip=True).split())[:500]
        candidates.append({"title": text, "url": href, "context": parent_text or text})
    return candidates


def item_hash(kind, source_name, title):
    raw = f"{kind}|{source_name}|{title}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _exists(db: Session, item_id: str) -> bool:
    return db.query(models.Opportunity.id).filter(models.Opportunity.id == item_id).first() is not None


def crawl_tenders(db: Session, new_items: list):
    for source in TENDER_SOURCES:
        print(f"[tenders] Checking {source['name']}...")
        html = fetch_html(source["url"])
        for c in extract_candidates(html, source["url"]):
            score, sector, reason = score_text(c["title"], c["title"] + " " + c["context"], RESEARCH_CONSULTANCY_KEYWORDS)
            if score < settings.MIN_MATCH_SCORE:
                continue
            item_id = item_hash("tender", source["name"], c["title"])
            if _exists(db, item_id):
                continue
            record = models.Opportunity(
                id=item_id, kind="tender", title=c["title"], org=extract_org_from_title(c["title"]),
                sector=sector, deadline=find_nearby_deadline(c["context"]),
                match_score=score, match_reason=reason,
                source=source["name"], source_url=c["url"],
            )
            db.add(record)
            new_items.append(record)
        time.sleep(0.3)
    db.commit()


def crawl_jobs(db: Session, new_items: list):
    ghana_qualifying = 0
    for source in GHANA_JOB_SOURCES:
        print(f"[jobs:ghana] Checking {source['name']}...")
        html = fetch_html(source["url"])
        for c in extract_candidates(html, source["url"]):
            score, sector, reason = score_text(c["title"], c["title"] + " " + c["context"], RESEARCH_CONSULTANCY_KEYWORDS)
            if score < settings.MIN_MATCH_SCORE:
                continue
            ghana_qualifying += 1
            item_id = item_hash("job", source["name"], c["title"])
            if _exists(db, item_id):
                continue
            record = models.Opportunity(
                id=item_id, kind="job", title=c["title"], org=extract_org_from_title(c["title"]), location="Ghana",
                sector=sector, deadline=find_nearby_deadline(c["context"]),
                match_score=score, match_reason=reason,
                source=source["name"], source_url=c["url"], source_tier="Ghana",
            )
            db.add(record)
            new_items.append(record)
        time.sleep(0.3)
    db.commit()

    print(f"[jobs] {ghana_qualifying} qualifying match(es) on Ghana platforms.")

    if ghana_qualifying < settings.MIN_GHANA_JOB_RESULTS:
        print(f"[jobs] Below {settings.MIN_GHANA_JOB_RESULTS} — checking international sources too.")
        for source in INTERNATIONAL_JOB_SOURCES:
            print(f"[jobs:intl] Checking {source['name']}...")
            html = fetch_html(source["url"])
            for c in extract_candidates(html, source["url"]):
                score, sector, reason = score_text(c["title"], c["title"] + " " + c["context"], RESEARCH_CONSULTANCY_KEYWORDS)
                if score < settings.MIN_MATCH_SCORE:
                    continue
                item_id = item_hash("job", source["name"], c["title"])
                if _exists(db, item_id):
                    continue
                record = models.Opportunity(
                    id=item_id, kind="job", title=c["title"], org=extract_org_from_title(c["title"]), location="",
                    sector=sector, deadline=find_nearby_deadline(c["context"]),
                    match_score=score, match_reason=reason,
                    source=source["name"], source_url=c["url"], source_tier="International",
                )
                db.add(record)
                new_items.append(record)
            time.sleep(0.3)
        db.commit()
    else:
        print("[jobs] Ghana platforms yielded enough matches — skipping international sources today.")


def prune_old(db: Session):
    cutoff = datetime.utcnow() - timedelta(days=settings.FEED_WINDOW_DAYS)
    stale_cutoff_str = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")

    all_items = db.query(models.Opportunity).all()
    for item in all_items:
        expired_by_deadline = False
        if item.deadline:
            try:
                expired_by_deadline = item.deadline < stale_cutoff_str
            except Exception:
                pass
        aged_out = (not item.deadline) and item.first_seen and item.first_seen.replace(tzinfo=None) < cutoff
        if expired_by_deadline or aged_out:
            db.delete(item)
    db.commit()


def build_digest_html(new_items):
    new_tenders = [i for i in new_items if i.kind == "tender"]
    new_jobs = [i for i in new_items if i.kind == "job"]
    ghana_jobs = [i for i in new_jobs if i.source_tier == "Ghana"]
    intl_jobs = [i for i in new_jobs if i.source_tier == "International"]

    def table(items):
        if not items:
            return "<p style='color:#888;'>None today.</p>"
        rows = "".join(f"""<tr>
            <td style='padding:8px;border-bottom:1px solid #eee;'>{i.title}</td>
            <td style='padding:8px;border-bottom:1px solid #eee;'>{i.source}</td>
            <td style='padding:8px;border-bottom:1px solid #eee;'>{i.sector}</td>
            <td style='padding:8px;border-bottom:1px solid #eee;'>{i.deadline or '—'}</td>
            <td style='padding:8px;border-bottom:1px solid #eee;'>{i.match_score}</td>
        </tr>""" for i in items)
        return f"""<table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:13px;">
          <tr style="background:#283088;color:#fff;text-align:left;">
            <th style='padding:8px;'>Title</th><th style='padding:8px;'>Source</th>
            <th style='padding:8px;'>Sector</th><th style='padding:8px;'>Deadline</th><th style='padding:8px;'>Match</th>
          </tr>{rows}</table>"""

    return f"""
    <div style="font-family:Arial,sans-serif;">
      <h2 style="color:#283088;">JMK Tender Monitor AI — Daily Digest</h2>
      <p style="color:#555;">Run at {time.strftime('%Y-%m-%d %H:%M UTC')}. Free rule-based scoring — treat this as a
      shortlist to review, not a guarantee.</p>
      <h3 style="color:#F26522;">New Tenders ({len(new_tenders)})</h3>
      {table(new_tenders)}
      <h3 style="color:#F26522;">New Research &amp; Consultancy Jobs — Ghana ({len(ghana_jobs)})</h3>
      {table(ghana_jobs)}
      <h3 style="color:#F26522;">New Research &amp; Consultancy Jobs — International ({len(intl_jobs)})</h3>
      {table(intl_jobs)}
    </div>"""


def send_email(html_body):
    recipients = [r.strip() for r in settings.DIGEST_RECIPIENTS.split(",") if r.strip()]
    if not recipients:
        return False, "DIGEST_RECIPIENTS not set"

    original_getaddrinfo = socket.getaddrinfo

    def ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    hour = datetime.utcnow().hour
    run_label = "Morning" if hour < 12 else "Afternoon"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"JMK Tender Monitor AI — {run_label} Digest — {time.strftime('%d %b %Y')}"
        msg["From"] = settings.DIGEST_FROM or settings.SMTP_USER
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html_body, "html"))

        socket.getaddrinfo = ipv4_only
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], recipients, msg.as_string())
        finally:
            socket.getaddrinfo = original_getaddrinfo

        return True, f"Emailed {len(recipients)} recipient(s)"
    except Exception as e:
        return False, str(e)


def run_crawl(db: Session):
    """The single entry point the API route (and external cron ping) calls."""
    new_items = []
    crawl_tenders(db, new_items)
    crawl_jobs(db, new_items)
    prune_old(db)

    tenders_count = db.query(models.Opportunity).filter(models.Opportunity.kind == "tender").count()
    jobs_count = db.query(models.Opportunity).filter(models.Opportunity.kind == "job").count()

    email_sent, email_note = send_email(build_digest_html(new_items))

    return {
        "tendersInFeed": tenders_count,
        "jobsInFeed": jobs_count,
        "newItemsThisRun": len(new_items),
        "emailSent": email_sent,
        "emailNote": email_note,
    }
