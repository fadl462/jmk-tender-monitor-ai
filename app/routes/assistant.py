"""
The "AI Assistant" — despite the name, this is NOT a call to Claude, GPT, or
any paid model. It's a rule-based natural-language-ish query parser: it
looks for sector names, organization names, deadline phrases ("this week",
"this month"), and kind words ("tender"/"job") in the question, and filters
the opportunity list accordingly. This keeps it genuinely free to run.

It's honest about this in its own responses — see `_explain` below.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..crawler import SECTORS
from ..schemas import AssistantQuery

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

TIME_WINDOWS = {
    "today": 1,
    "this week": 7,
    "next 7 days": 7,
    "this month": 30,
    "next 30 days": 30,
}


@router.post("/ask")
def ask_assistant(query: AssistantQuery, db: Session = Depends(get_db)):
    q = query.question.lower().strip()
    items = db.query(models.Opportunity).all()

    matched_sector = next((s for s in SECTORS if s.lower().split(",")[0].split("&")[0].strip() in q), None)
    matched_kind = "tender" if "tender" in q else ("job" if "job" in q or "consultanc" in q else None)
    matched_window = next((days for phrase, days in TIME_WINDOWS.items() if phrase in q), None)

    # crude org-name detection: capitalized words in the ORIGINAL question,
    # excluding common leading words
    stopwords = {"show", "me", "which", "what", "find", "list", "all", "the", "opportunities",
                 "tenders", "jobs", "closing", "close", "this", "week", "month", "fit", "for"}
    org_terms = [w.strip(",.?!") for w in query.question.split()
                 if w[:1].isupper() and w.lower() not in stopwords and len(w) > 2]

    results = items
    explanation_bits = []

    if matched_kind:
        results = [i for i in results if i.kind == matched_kind]
        explanation_bits.append(f"kind = {matched_kind}")

    if matched_sector:
        results = [i for i in results if matched_sector.lower() in (i.sector or "").lower()]
        explanation_bits.append(f"sector contains '{matched_sector}'")

    if org_terms:
        results = [i for i in results if any(term.lower() in (i.org or "").lower() or term.lower() in i.title.lower() for term in org_terms)]
        explanation_bits.append(f"mentions {', '.join(org_terms)}")

    if matched_window:
        today = datetime.utcnow().date()
        cutoff = today + timedelta(days=matched_window)
        def in_window(i):
            if not i.deadline:
                return False
            try:
                d = datetime.strptime(i.deadline, "%Y-%m-%d").date()
                return today <= d <= cutoff
            except ValueError:
                return False
        results = [i for i in results if in_window(i)]
        explanation_bits.append(f"deadline within {matched_window} day(s)")

    results = sorted(results, key=lambda i: -i.match_score)[:25]

    if not explanation_bits:
        explanation = "Didn't detect a specific filter in that question, so here are the top matches overall."
    else:
        explanation = "Filtered by: " + "; ".join(explanation_bits) + "."

    return {
        "explanation": explanation,
        "count": len(results),
        "results": [
            {
                "id": i.id, "kind": i.kind, "title": i.title, "org": i.org,
                "sector": i.sector, "deadline": i.deadline, "matchScore": i.match_score,
                "matchReason": i.match_reason, "source": i.source, "sourceUrl": i.source_url,
                "sourceTier": i.source_tier,
            }
            for i in results
        ],
    }
