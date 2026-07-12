from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..schemas import BoardItemIn, BoardItemUpdate, BoardItemOut

router = APIRouter(prefix="/api/board", tags=["board"])


@router.get("", response_model=list[BoardItemOut])
def list_board(db: Session = Depends(get_db)):
    return db.query(models.BoardItem).order_by(models.BoardItem.added_at.desc()).all()


@router.post("", response_model=BoardItemOut, status_code=201)
def create_board_item(item: BoardItemIn, db: Session = Depends(get_db)):
    record = models.BoardItem(**item.dict())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.put("/{item_id}", response_model=BoardItemOut)
def update_board_item(item_id: str, update: BoardItemUpdate, db: Session = Depends(get_db)):
    record = db.query(models.BoardItem).filter(models.BoardItem.id == item_id).first()
    if not record:
        raise HTTPException(404, "not found")
    for field, value in update.dict(exclude_unset=True).items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{item_id}")
def delete_board_item(item_id: str, db: Session = Depends(get_db)):
    record = db.query(models.BoardItem).filter(models.BoardItem.id == item_id).first()
    if not record:
        raise HTTPException(404, "not found")
    db.delete(record)
    db.commit()
    return {"deleted": item_id}


@router.post("/from-opportunity/{opportunity_id}", response_model=BoardItemOut, status_code=201)
def add_from_opportunity(opportunity_id: str, db: Session = Depends(get_db)):
    """One-click 'track this' — copies a crawled opportunity into the board."""
    opp = db.query(models.Opportunity).filter(models.Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(404, "opportunity not found")
    record = models.BoardItem(
        title=opp.title,
        funder=opp.org,
        sector=opp.sector,
        status="New",
        deadline=opp.deadline,
        ref="",
        link=opp.source_url,
        notes=f"Match score: {opp.match_score}/100 — {opp.match_reason}\n\nFound via daily crawl ({opp.source}).",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
