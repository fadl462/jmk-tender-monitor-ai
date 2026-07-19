from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from collections import defaultdict

from ..database import get_db
from .. import models

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/traffic")
def traffic(db: Session = Depends(get_db)):
    """Honest framing: there's no login system, so this can't tell you WHO
    visited — only how often the dashboard gets opened, and a rough
    same-day 'different people' estimate based on hashed IPs. Good enough
    to answer 'is anyone actually using this,' not built for more than that.
    """
    now = datetime.utcnow()
    today = now.date()

    visits = db.query(models.PageVisit).all()

    visits_today = 0
    visits_week = 0
    day_counts = defaultdict(int)
    ip_set_today = set()

    for v in visits:
        if not v.created_at:
            continue
        d = v.created_at.replace(tzinfo=None).date()
        day_counts[d] += 1
        if d == today:
            visits_today += 1
            if v.ip_hash:
                ip_set_today.add(v.ip_hash)
        if 0 <= (today - d).days <= 6:
            visits_week += 1

    last_14_days = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        last_14_days.append({"date": d.strftime("%Y-%m-%d"), "count": day_counts.get(d, 0)})

    recent = sorted(visits, key=lambda v: v.created_at or now, reverse=True)[:20]

    return {
        "visitsToday": visits_today,
        "uniqueTodayApprox": len(ip_set_today),
        "visitsThisWeek": visits_week,
        "visitsAllTime": len(visits),
        "last14Days": last_14_days,
        "recentVisits": [
            {"path": v.path, "time": v.created_at.isoformat() if v.created_at else None}
            for v in recent
        ],
    }
