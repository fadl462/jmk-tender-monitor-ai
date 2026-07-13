from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from .. import models
from ..schemas import OpportunityOut

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.get("", response_model=list[OpportunityOut])
def list_opportunities(kind: str | None = None, db: Session = Depends(get_db)):
    q = db.query(models.Opportunity)
    if kind:
        q = q.filter(models.Opportunity.kind == kind)
    q = q.order_by(desc(models.Opportunity.match_score))
    return q.limit(200).all()


@router.get("/stats")
def opportunity_stats(db: Session = Depends(get_db)):
    from datetime import datetime, timedelta
    from collections import Counter, defaultdict

    tenders = db.query(models.Opportunity).filter(models.Opportunity.kind == "tender").all()
    jobs = db.query(models.Opportunity).filter(models.Opportunity.kind == "job").all()
    all_items = tenders + jobs

    now = datetime.utcnow()
    today = now.date()

    # ---------- core KPIs ----------
    closing_week = 0
    closing_48h = 0
    for item in all_items:
        if item.deadline:
            try:
                d = datetime.strptime(item.deadline, "%Y-%m-%d").date()
                days = (d - today).days
                if 0 <= days <= 7:
                    closing_week += 1
                if 0 <= (datetime.strptime(item.deadline, "%Y-%m-%d") - now).total_seconds() <= 172800:
                    closing_48h += 1
            except ValueError:
                pass

    new_today = 0
    this_month_count = 0
    budget_known_count = 0
    for item in all_items:
        if item.first_seen:
            fs_date = item.first_seen.replace(tzinfo=None).date()
            if fs_date == today:
                new_today += 1
            if fs_date.year == today.year and fs_date.month == today.month:
                this_month_count += 1
        if item.budget_text:
            budget_known_count += 1

    high_priority = len([i for i in all_items if i.match_score >= 80])
    avg_score = round(sum(i.match_score for i in all_items) / len(all_items), 1) if all_items else 0

    sector_counts = Counter(i.sector for i in all_items if i.sector)
    org_counts = Counter(i.org for i in all_items if i.org)
    active_donors = len(org_counts)

    # ---------- chart: opportunities over the last 30 days ----------
    last_30_days = []
    day_counts = defaultdict(int)
    for item in all_items:
        if item.first_seen:
            day_counts[item.first_seen.replace(tzinfo=None).date()] += 1
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        last_30_days.append({"date": d.strftime("%Y-%m-%d"), "count": day_counts.get(d, 0)})

    # ---------- chart: deadlines this week ----------
    deadlines_this_week = []
    deadline_counts = defaultdict(int)
    for item in all_items:
        if item.deadline:
            deadline_counts[item.deadline] += 1
    for i in range(0, 7):
        d = today + timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        deadlines_this_week.append({"date": d_str, "count": deadline_counts.get(d_str, 0)})

    # ---------- chart: average AI match over time (last 30 days) ----------
    avg_match_over_time = []
    day_scores = defaultdict(list)
    for item in all_items:
        if item.first_seen:
            day_scores[item.first_seen.replace(tzinfo=None).date()].append(item.match_score)
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        scores = day_scores.get(d, [])
        avg = round(sum(scores) / len(scores), 1) if scores else None
        avg_match_over_time.append({"date": d.strftime("%Y-%m-%d"), "average": avg})

    # ---------- chart: sector trend (last 8 weeks) ----------
    def week_start(d):
        return d - timedelta(days=d.weekday())

    weeks = []
    cur = week_start(today - timedelta(weeks=7))
    while cur <= week_start(today):
        weeks.append(cur)
        cur += timedelta(weeks=1)

    top_sectors = [s for s, _ in sector_counts.most_common(5)]
    sector_trend_series = {s: [0] * len(weeks) for s in top_sectors}
    for item in all_items:
        if item.sector in sector_trend_series and item.first_seen:
            ws = week_start(item.first_seen.replace(tzinfo=None).date())
            if ws in weeks:
                sector_trend_series[item.sector][weeks.index(ws)] += 1

    # ---------- chart: country distribution ----------
    location_counts = Counter((i.location or "Not specified") for i in all_items)
    top_locations = location_counts.most_common(5)
    other_count = sum(c for _, c in location_counts.most_common()[5:])
    country_distribution = [{"name": n, "count": c} for n, c in top_locations]
    if other_count:
        country_distribution.append({"name": "Other", "count": other_count})

    # ---------- chart: monthly activity (last 6 months) ----------
    def month_key(d):
        return f"{d.year}-{d.month:02d}"

    month_labels = []
    m = today.replace(day=1)
    for _ in range(6):
        month_labels.append(month_key(m))
        m = (m - timedelta(days=1)).replace(day=1)
    month_labels.reverse()
    month_counts = defaultdict(int)
    for item in all_items:
        if item.first_seen:
            month_counts[month_key(item.first_seen.replace(tzinfo=None).date())] += 1
    monthly_activity = [{"month": ml, "count": month_counts.get(ml, 0)} for ml in month_labels]

    # ---------- chart: pipeline status ----------
    board_items = db.query(models.BoardItem).all()
    pipeline_status_counts = Counter(b.status for b in board_items)

    return {
        "totalOpportunities": len(tenders) + len(jobs),
        "tenders": len(tenders),
        "jobs": len(jobs),
        "highPriority": high_priority,
        "closingThisWeek": closing_week,
        "closingIn48h": closing_48h,
        "activeDonors": active_donors,
        "averageMatch": avg_score,
        "newToday": new_today,
        "opportunitiesThisMonth": this_month_count,
        "budgetKnownCount": budget_known_count,
        "sectorBreakdown": dict(sector_counts.most_common()),
        "topDonors": [{"name": name, "count": count} for name, count in org_counts.most_common(5)],
        "charts": {
            "last30Days": last_30_days,
            "deadlinesThisWeek": deadlines_this_week,
            "avgMatchOverTime": avg_match_over_time,
            "sectorTrend": {"weeks": [w.strftime("%Y-%m-%d") for w in weeks], "series": sector_trend_series},
            "countryDistribution": country_distribution,
            "monthlyActivity": monthly_activity,
            "pipelineStatus": [{"status": s, "count": c} for s, c in pipeline_status_counts.items()],
        },
    }
