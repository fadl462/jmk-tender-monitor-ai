from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from .. import models
from ..schemas import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(db: Session = Depends(get_db)):
    rows = db.query(models.Notification).order_by(desc(models.Notification.created_at)).limit(50).all()
    unread_count = db.query(models.Notification).filter(models.Notification.is_read == 0).count()
    return {
        "unreadCount": unread_count,
        "notifications": [NotificationOut.model_validate(r).model_dump() for r in rows],
    }


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db)):
    row = db.query(models.Notification).filter(models.Notification.id == notification_id).first()
    if row:
        row.is_read = 1
        db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db)):
    db.query(models.Notification).filter(models.Notification.is_read == 0).update({"is_read": 1})
    db.commit()
    return {"ok": True}
