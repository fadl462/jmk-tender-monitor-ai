from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from .. import models
from ..schemas import OpportunityOut
from ..config import settings

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.get("", response_model=list[OpportunityOut])
def list_opportunities(kind: str | None = None, db: Session = Depends(get_db)):
    q = db.query(models.Opportunity)
    if kind:
        q = q.filter(models.Opportunity.kind == kind)
    q = q.order_by(desc(models.Opportunity.match_score))
    return q.limit(200).all()


@router.delete("")
def clear_opportunities(token: str = Query(default=""), db: Session = Depends(get_db)):
    if settings.CRON_SECRET and token != settings.CRON_SECRET:
        raise HTTPException(401, "unauthorized")
    count = db.query(models.Opportunity).delete()
    db.commit()
    return {"deleted": count}


@router.get("/stats")
def opportunity_stats(db: Session = Depends(get_db)):
    from datetime import datetime, timedelta
    from collections import Counter

    tenders = db.query(models.Opportunity).filter(models.Opportunity.kind == "tender").all()
    jobs = db.query(models.Opportunity).filter(models.Opportunity.kind == "job").all()
    all_items = tenders + jobs

    now = datetime.utcnow()
    today = now.date()
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

    high_priority = len([i for i in all_items if i.match_score >= 80])
    avg_score = round(sum(i.match_score for i in all_items) / len(all_items), 1) if all_items else 0

    sector_counts = Counter(i.sector for i in all_items if i.sector)
    org_counts = Counter(i.org for i in all_items if i.org)
    active_donors = len(org_counts)

    return {
        "totalOpportunities": len(tenders) + len(jobs),
        "tenders": len(tenders),
        "jobs": len(jobs),
        "highPriority": high_priority,
        "closingThisWeek": closing_week,
        "closingIn48h": closing_48h,
        "activeDonors": active_donors,
        "averageMatch": avg_score,
        "sectorBreakdown": dict(sector_counts.most_common()),
        "topDonors": [{"name": name, "count": count} for name, count in org_counts.most_common(5)],
    }
