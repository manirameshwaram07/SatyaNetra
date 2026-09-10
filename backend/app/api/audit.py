"""Audit chain endpoints + watchlist check + reports download."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.screening import Screening
from app.models.user import User
from app.schemas.schemas import AuditVerifyResponse
from app.services import audit_service, watchlist_service
from app.services.report_service import report_path_for

router = APIRouter(tags=["audit"])


@router.get("/api/audit/{verification_id}", response_model=AuditVerifyResponse,
            summary="Fetch and verify the audit hash chain for a screening")
def get_audit(verification_id: str, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    s = db.query(Screening).filter(Screening.verification_id == verification_id).first()
    if s is None:
        raise HTTPException(404, "Screening not found")
    valid, records, msg = audit_service.verify_chain(db, s.id)
    return AuditVerifyResponse(
        verification_id=verification_id,
        chain_valid=valid,
        records=[r.to_dict() for r in records],
        message=msg,
    )


@router.get("/api/watchlist/check/{document_number}",
            summary="Check the DEMO watchlist for a document number")
def watchlist_check(document_number: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    return watchlist_service.check_document_number(db, document_number)


@router.get("/api/watchlist", summary="List demo watchlist entries")
def watchlist_list(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return watchlist_service.list_entries(db)


@router.get("/api/reports/{verification_id}", summary="Download the PDF verification report")
def download_report(verification_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    s = db.query(Screening).filter(Screening.verification_id == verification_id).first()
    if s is None:
        raise HTTPException(404, "Screening not found")
    path = report_path_for(verification_id)
    if not path.exists():
        raise HTTPException(404, "Report not generated yet. Complete a screening first.")
    return FileResponse(
        str(path), media_type="application/pdf",
        filename=f"SatyaNetra_Report_{verification_id}.pdf",
    )