"""Screening endpoints: start, status, result, history."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.document import Document
from app.models.screening import Screening
from app.models.user import User
from app.schemas.schemas import ScreeningStartResponse, ScreeningStatusResponse, StepStatus
from app.utils.logging_conf import get_logger
from app.workers.screening_pipeline import start_screening

logger = get_logger("screening")
router = APIRouter(prefix="/api/screening", tags=["screening"])


@router.post("/start/{document_id}", response_model=ScreeningStartResponse,
             summary="Start the full AI screening pipeline for a document")
def start(document_id: int, db: Session = Depends(get_db),
          user: User = Depends(get_current_user)):
    doc = db.query(Document).get(document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    try:
        vid = start_screening(document_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    logger.info("Screening started: %s (document %s)", vid, document_id)
    return ScreeningStartResponse(verification_id=vid, status="PROCESSING")


@router.get("/{verification_id}/status", response_model=ScreeningStatusResponse,
            summary="Poll pipeline progress for a screening")
def get_status(verification_id: str, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    s = db.query(Screening).filter(Screening.verification_id == verification_id).first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Screening not found")
    try:
        steps = json.loads(s.steps_json or "[]")
    except Exception:
        steps = []
    return ScreeningStatusResponse(
        status=s.status,
        progress=s.progress,
        current_step=s.current_step,
        steps=[StepStatus(**st) for st in steps],
    )


@router.get("/{verification_id}/result", summary="Full screening result payload")
def get_result(verification_id: str, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    s = db.query(Screening).filter(Screening.verification_id == verification_id).first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Screening not found")
    if s.status in {"PENDING", "PROCESSING"}:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Screening still in progress - poll the status endpoint.")
    try:
        result = json.loads(s.result_json or "{}")
    except Exception:
        result = {}
    payload = s.to_dict(include_result=True)
    payload["result"] = result
    doc = db.query(Document).get(s.document_id)
    payload["document"] = doc.to_dict() if doc else None
    return payload


@router.get("", summary="Screening history (most recent first)")
def list_screenings(limit: int = 50, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    rows = (db.query(Screening, Document)
            .join(Document, Screening.document_id == Document.id)
            .order_by(Screening.id.desc())
            .limit(min(limit, 200))
            .all())
    out = []
    for s, d in rows:
        item = s.to_dict()
        item["document_type"] = d.document_type
        item["filename"] = d.original_filename
        item["document_hash"] = d.document_hash
        out.append(item)
    return out