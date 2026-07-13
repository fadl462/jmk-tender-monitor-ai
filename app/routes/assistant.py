"""
The "AI Assistant" — despite the name, this is NOT a call to Claude, GPT, or
any paid model. It's a rule-based natural-language-ish query parser: it
looks for sector names, known donor names, deadline phrases ("this week",
"this month"), and kind words ("tender"/"job") in the question, and filters
the opportunity list accordingly. This keeps it genuinely free to run.

It's honest about this in its own responses — see the `explanation` built
below.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..crawler import SECTORS, KNOWN_DONORS
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

    # Donor detection: only matched against a known-donor list, deliberately
    # NOT a "any capitalized word is a name" fallback. That fallback used to
    # misfire constantly — sector names in the assistant's own suggestion
    # chips (e.g. "Education opportunities", "WASH opportunities") are also
    # capitalized, and were being treated as an org name to search for
    # inside the title. That collision made sector-only quick filters
    # return 0 matches even when the sector genuinely had results.
    matched_donors = [d for d in KNOWN_DONORS if d in q]

    results = items
    explanation_bits = []

    if matched_kind:
        results = [i for i in results if i.kind == matched_kind]
        explanation_bits.append(f"kind = {matched_kind}")

    if matched_sector:
        results = [i for i in results if matched_sector.lower() in (i.sector or "").lower()]
        explanation_bits.append(f"sector contains '{matched_sector}'")

    if matched_donors:
        results = [i for i in results if any(d in (i.org or "").lower() or d in i.title.lower() for d in matched_donors)]
        explanation_bits.append(f"mentions {', '.join(matched_donors)}")

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
