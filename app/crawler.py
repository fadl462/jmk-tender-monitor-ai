"""
JMK Opportunity Crawler — free, rule-based version.
----------------------------------------------------
No Claude/OpenAI API calls anywhere. Listings are pulled from each source's
HTML and scored with a weighted keyword model against JMK's sectors and the
kind of role/tender language JMK cares about. Ghana job platforms are
checked first; international ones only kick in if Ghana doesn't yield
enough matches.

SCORING MODEL (weighted, out of 100):
  Sector match             30 pts
  Service/consultancy fit  25 pts
  Geography (Ghana)        15 pts
  Client type              10 pts
  Secondary keywords        10 pts
  Budget mentioned           5 pts
  Known donor alignment       5 pts

Each dimension is scored independently and the points are summed, so a
listing's rank reflects several things about it rather than just "how many
keywords appeared." A hit on a NEGATIVE_KEYWORD still zeroes a listing out
immediately — that's a hard filter, not a weighted dimension.

Trade-off, stated plainly: this is noisier than an LLM would be — it can
miss an oddly-worded listing, and deadline/budget detection are regex
guesses, not real understanding. It costs nothing to run, and every result
links back to its source so a person makes the final call.
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
from . import settings_store

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

JOB_ROLE_KEYWORDS = [
    "consultant", "consultancy", "researcher", "research associate", "research fellow",
    "monitoring and evaluation", "m&e", "m & e", "evaluation", "evaluator", "assessment",
    "survey", "terms of reference", " tor ", "feasibility study", "impact assessment",
    "technical assistance", "data collection", "enumerator", "advisor", "advisory",
    "technical advisor", "programme officer", "project officer", "coordinator",
]

TENDER_ROLE_KEYWORDS = [
    "tender", "rfp", "request for proposal", "eoi", "expression of interest",
    "invitation to tender", "procurement", "call for proposals", "terms of reference",
    " tor ", "invitation for bids", "request for quotation", "rfq",
]

NEGATIVE_KEYWORDS = [
    "driver", "cook", "cleaner", "security guard", "waiter", "waitress", "receptionist",
    "sales executive", "sales representative", "cashier", "electrician", "plumber",
    "chef", "hospitality", "housekeeping", "barista", "mechanic", "dispatch rider",
    "massage therapist", "class teacher", "shs teacher",
]

# Recognized by name for the "known donor alignment" scoring dimension and
# the "client type" dimension — an institutional/donor client scores higher
# on client type than an unrecognized private company.
KNOWN_DONORS = [
    "unicef", "usaid", "koica", "giz", "undp", "world bank", "afdb",
    "african development bank", "european union", "eu delegation", "fcdo",
    "dfid", "jica", "unfpa", "who", "fao", "wfp", "un women", "ilo",
    "unesco", "global fund", "gavi", "plan international", "save the children",
    "world vision", "oxfam", "care international", "danida", "sida", "irish aid",
    "usda", "unhcr", "unops", "iom",
]

INSTITUTIONAL_CLIENT_HINTS = KNOWN_DONORS + [
    "government", "ministry", "municipal", "district assembly", "metropolitan assembly",
    "parliament", "embassy", "ngo", "commission", "authority",
]

GENERIC_SIGNAL_KEYWORDS = [
    "capacity building", "stakeholder engagement", "desk review", "inception report",
    "final report", "qualitative", "quantitative", "secondary data", "primary data",
    "workshop", "field work", "report writing", "training needs assessment",
    "baseline", "endline", "midline", "logframe", "theory of change",
]

BUDGET_PATTERN = re.compile(
    r"(?:USD|US\$|GHS|GH¢|GH₵|\$|£|€)\s?[\d][\d,]*(?:\.\d+)?(?:\s?(?:million|m|k))?",
    re.IGNORECASE,
)

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


def _split_csv(text):
    return [w.strip().lower() for w in (text or "").split(",") if w.strip()]


def _tier_points(count, weight):
    """Turn a raw keyword-match count into points out of `weight`, using
    diminishing-returns tiers rather than a straight linear count — a
    single strong hit already counts for a lot, and after 3 matches more
    hits stop adding anything (avoids keyword-stuffed listings dominating
    just by repetition)."""
    if count >= 3:
        frac = 1.0
    elif count == 2:
        frac = 0.85
    elif count == 1:
        frac = 0.6
    else:
        frac = 0.0
    return round(weight * frac)


def score_text_weighted(text, kind, db_settings, geo_hint=None, org_text=""):
    """
    Weighted scoring across 7 dimensions, summing to a 0-100 score.
    `kind` is "tender" or "job" (selects the base role-keyword list).
    `geo_hint` is "Ghana" / "International" / None — set for jobs based on
    which source tier found them; left None for tenders (no such split).
    `org_text` is the funder/employer name if already known, folded into
    the client-type and donor-alignment checks alongside the title text.
    Returns (score, sector, reason, budget_text).
    """
    t = text.lower()
    combined_for_org_checks = (text + " " + (org_text or "")).lower()

    negative_keywords = NEGATIVE_KEYWORDS + _split_csv(db_settings.get("extra_negative_keywords", ""))
    for neg in negative_keywords:
        if neg in t:
            return 0, "", "Filtered out — looks unrelated to JMK's research/consultancy scope.", ""

    # --- Sector (30 pts) ---
    extra_sector = db_settings.get("extra_sector_keywords", {}) or {}
    best_sector, best_count = "", 0
    for sector, kws in SECTOR_KEYWORDS.items():
        all_kws = kws + _split_csv(extra_sector.get(sector, ""))
        count = sum(1 for kw in all_kws if kw in t)
        if count > best_count:
            best_sector, best_count = sector, count
    sector_pts = _tier_points(best_count, 30)

    # --- Service / consultancy fit (25 pts) ---
    base_role_kws = TENDER_ROLE_KEYWORDS if kind == "tender" else JOB_ROLE_KEYWORDS
    role_keywords = base_role_kws + _split_csv(db_settings.get("extra_role_keywords", ""))
    matched_roles = [kw for kw in role_keywords if kw.strip() in t]
    service_pts = _tier_points(len(matched_roles), 25)

    # --- Geography (15 pts) ---
    if "ghana" in t:
        geo_pts = 15
    elif geo_hint == "Ghana":
        geo_pts = 13
    elif geo_hint == "International":
        geo_pts = 5
    else:
        geo_pts = 8  # tenders with no explicit geo mention — unknown but plausibly relevant

    # --- Client type (10 pts) ---
    client_pts = 10 if any(hint in combined_for_org_checks for hint in INSTITUTIONAL_CLIENT_HINTS) else 5

    # --- Secondary/generic keywords (10 pts) ---
    generic_count = sum(1 for kw in GENERIC_SIGNAL_KEYWORDS if kw in t)
    keyword_pts = _tier_points(generic_count, 10)

    # --- Budget mentioned (5 pts) ---
    budget_match = BUDGET_PATTERN.search(text)
    budget_pts = 5 if budget_match else 0
    budget_text = budget_match.group(0) if budget_match else ""

    # --- Known donor alignment (5 pts) ---
    matched_donor = next((d for d in KNOWN_DONORS if d in combined_for_org_checks), None)
    donor_pts = 5 if matched_donor else 0

    score = sector_pts + service_pts + geo_pts + client_pts + keyword_pts + budget_pts + donor_pts
    score = max(0, min(100, score))

    if score == 0:
        return 0, "", "", ""

    bits = [
        f"Sector {sector_pts}/30" + (f" ({best_sector})" if best_sector else ""),
        f"Service {service_pts}/25",
        f"Geography {geo_pts}/15",
        f"Client type {client_pts}/10",
        f"Keywords {keyword_pts}/10",
        f"Budget {budget_pts}/5",
        f"Donor history {donor_pts}/5" + (f" ({matched_donor})" if matched_donor else ""),
    ]
    reason = " · ".join(bits)
    return score, best_sector, reason, budget_text


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


def crawl_tenders(db: Session, new_items: list, db_settings: dict):
    threshold = db_settings.get("match_threshold", 40)
    for source in TENDER_SOURCES:
        print(f"[tenders] Checking {source['name']}...")
        html = fetch_html(source["url"])
        for c in extract_candidates(html, source["url"]):
            score, sector, reason, budget_text = score_text_weighted(c["context"], "tender", db_settings)
            if score < threshold:
                continue
            item_id = item_hash("tender", source["name"], c["title"])
            if _exists(db, item_id):
                continue
            record = models.Opportunity(
                id=item_id, kind="tender", title=c["title"], org="",
                sector=sector, deadline=find_nearby_deadline(c["context"]),
                match_score=score, match_reason=reason, budget_text=budget_text,
                source=source["name"], source_url=c["url"],
            )
            db.add(record)
            new_items.append(record)
        time.sleep(0.3)
    db.commit()


def crawl_jobs(db: Session, new_items: list, db_settings: dict):
    threshold = db_settings.get("match_threshold", 40)
    min_ghana_job_results = db_settings.get("min_ghana_job_results", 5)
    ghana_qualifying = 0
    for source in GHANA_JOB_SOURCES:
        print(f"[jobs:ghana] Checking {source['name']}...")
        html = fetch_html(source["url"])
        for c in extract_candidates(html, source["url"]):
            score, sector, reason, budget_text = score_text_weighted(c["title"], "job", db_settings, geo_hint="Ghana")
            if score < threshold:
                continue
            ghana_qualifying += 1
            item_id = item_hash("job", source["name"], c["title"])
            if _exists(db, item_id):
                continue
            record = models.Opportunity(
                id=item_id, kind="job", title=c["title"], org="", location="Ghana",
                sector=sector, deadline=find_nearby_deadline(c["context"]),
                match_score=score, match_reason=reason, budget_text=budget_text,
                source=source["name"], source_url=c["url"], source_tier="Ghana",
            )
            db.add(record)
            new_items.append(record)
        time.sleep(0.3)
    db.commit()

    print(f"[jobs] {ghana_qualifying} qualifying match(es) on Ghana platforms.")

    if ghana_qualifying < min_ghana_job_results:
        print(f"[jobs] Below {min_ghana_job_results} — checking international sources too.")
        for source in INTERNATIONAL_JOB_SOURCES:
            print(f"[jobs:intl] Checking {source['name']}...")
            html = fetch_html(source["url"])
            for c in extract_candidates(html, source["url"]):
                score, sector, reason, budget_text = score_text_weighted(c["title"], "job", db_settings, geo_hint="International")
                if score < threshold:
                    continue
                item_id = item_hash("job", source["name"], c["title"])
                if _exists(db, item_id):
                    continue
                record = models.Opportunity(
                    id=item_id, kind="job", title=c["title"], org="", location="",
                    sector=sector, deadline=find_nearby_deadline(c["context"]),
                    match_score=score, match_reason=reason, budget_text=budget_text,
                    source=source["name"], source_url=c["url"], source_tier="International",
                )
                db.add(record)
                new_items.append(record)
            time.sleep(0.3)
        db.commit()
    else:
        print("[jobs] Ghana platforms yielded enough matches — skipping international sources today.")


def prune_old(db: Session, db_settings: dict):
    feed_window_days = db_settings.get("feed_window_days", 30)
    cutoff = datetime.utcnow() - timedelta(days=feed_window_days)
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


def generate_notifications(db: Session, new_items: list, db_settings: dict):
    """Populate the in-app notification center. Uses `dedup_key` to avoid
    re-firing the same alert (e.g. a deadline reminder) across multiple
    crawl runs."""

    def _already_sent(key):
        if not key:
            return False
        return db.query(models.Notification.id).filter(models.Notification.dedup_key == key).first() is not None

    if db_settings.get("notify_high_priority", True):
        for item in new_items:
            if item.match_score >= 80:
                key = f"high_priority:{item.id}"
                if not _already_sent(key):
                    db.add(models.Notification(
                        type="high_priority", title="New high-priority opportunity",
                        message=f"{item.title} — {item.match_score}% match ({item.sector or 'Unsectored'}).",
                        opportunity_id=item.id, dedup_key=key,
                    ))

    if db_settings.get("notify_donor_watch", True):
        watch_terms = _split_csv(db_settings.get("donor_watch_keywords", ""))
        for item in new_items:
            text = f"{item.org} {item.title}".lower()
            for term in watch_terms:
                if term in text:
                    key = f"donor_watch:{term}:{item.id}"
                    if not _already_sent(key):
                        db.add(models.Notification(
                            type="donor_watch", title=f"New {term.upper()} opportunity",
                            message=item.title, opportunity_id=item.id, dedup_key=key,
                        ))
                    break

    if db_settings.get("notify_deadline_3_days", True):
        target_date = (datetime.utcnow().date() + timedelta(days=3)).strftime("%Y-%m-%d")
        upcoming = db.query(models.Opportunity).filter(models.Opportunity.deadline == target_date).all()
        for item in upcoming:
            key = f"deadline3:{item.id}"
            if not _already_sent(key):
                db.add(models.Notification(
                    type="deadline", title="Deadline in 3 days",
                    message=f"{item.title} closes on {item.deadline}.",
                    opportunity_id=item.id, dedup_key=key,
                ))

    if db_settings.get("notify_scan_complete", True):
        db.add(models.Notification(
            type="scan_complete", title="Daily scan complete",
            message=f"{len(new_items)} new opportunit{'y' if len(new_items) == 1 else 'ies'} found this run.",
            opportunity_id="", dedup_key="",
        ))

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


def send_email(html_body, db_settings: dict):
    recipients = [r.strip() for r in (db_settings.get("digest_recipients") or "").split(",") if r.strip()]
    if not recipients:
        return False, "digest_recipients not set"

    smtp_host = db_settings.get("smtp_host", "")
    smtp_port = int(db_settings.get("smtp_port", 587) or 587)
    smtp_user = db_settings.get("smtp_user", "")
    smtp_password = db_settings.get("smtp_password", "")
    digest_from = db_settings.get("digest_from") or smtp_user

    # Some hosts (Render included) don't route IPv6 outbound, but Gmail's
    # hostname resolves to an IPv6 address as well as IPv4 — force IPv4-only
    # resolution just for this connection to avoid "Network is unreachable".
    original_getaddrinfo = socket.getaddrinfo

    def ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    # Ghana is UTC+0 year-round (no daylight saving), so the server's UTC
    # hour is also the Accra hour — safe to use directly for the AM/PM label.
    hour = datetime.utcnow().hour
    run_label = "Morning" if hour < 12 else "Afternoon"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"JMK Tender Monitor AI — {run_label} Digest — {time.strftime('%d %b %Y')}"
        msg["From"] = digest_from
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html_body, "html"))

        socket.getaddrinfo = ipv4_only
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(msg["From"], recipients, msg.as_string())
        finally:
            socket.getaddrinfo = original_getaddrinfo

        return True, f"Emailed {len(recipients)} recipient(s)"
    except Exception as e:
        return False, str(e)


def run_crawl(db: Session):
    """The single entry point the API route (and external cron ping) calls."""
    db_settings = settings_store.get_all_settings(db)

    new_items = []
    crawl_tenders(db, new_items, db_settings)
    crawl_jobs(db, new_items, db_settings)
    prune_old(db, db_settings)
    generate_notifications(db, new_items, db_settings)

    tenders_count = db.query(models.Opportunity).filter(models.Opportunity.kind == "tender").count()
    jobs_count = db.query(models.Opportunity).filter(models.Opportunity.kind == "job").count()

    email_sent, email_note = send_email(build_digest_html(new_items), db_settings)

    return {
        "tendersInFeed": tenders_count,
        "jobsInFeed": jobs_count,
        "newItemsThisRun": len(new_items),
        "emailSent": email_sent,
        "emailNote": email_note,
    }
