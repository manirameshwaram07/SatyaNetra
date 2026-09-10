"""Watchlist service - DEMO local database checks (never a real government database)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.watchlist import WatchlistEntry
from app.utils.logging_conf import get_logger

logger = get_logger("watchlist")

SOURCE_LABEL = "DEMO_WATCHLIST"


def check_document_number(db: Session, document_number: str) -> dict:
    """Check demo watchlist for a document number. Returns structured result."""
    num = (document_number or "").strip().upper()
    if not num:
        return {"found": False, "status": "NOT_FOUND", "source": SOURCE_LABEL,
                "details": {"message": "No document number available to check."}}
    entry = db.query(WatchlistEntry).filter(
        WatchlistEntry.document_number == num
    ).first()
    if entry is None:
        return {
            "found": False, "status": "CLEAR", "source": SOURCE_LABEL,
            "details": {"message": "No matching record in the demo watchlist."},
        }
    logger.info("Watchlist hit: status=%s", entry.status)
    return {
        "found": True,
        "status": entry.status,  # VALID / EXPIRED / REPORTED / DUPLICATE / SUSPICIOUS
        "source": SOURCE_LABEL,
        "details": {
            "name": entry.name,
            "nationality": entry.nationality,
            "date_of_birth": entry.date_of_birth,
            "notes": entry.notes,
            "message": f"Match found in demo watchlist: {entry.status}",
        },
    }


def list_entries(db: Session) -> list[dict]:
    return [e.to_dict() for e in db.query(WatchlistEntry).all()]