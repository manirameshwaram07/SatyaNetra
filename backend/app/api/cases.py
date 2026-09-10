"""Case management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.case import Case
from app.models.screening import Screening
from app.models.user import User
from app.schemas.schemas import CaseCreate, CaseOut, CaseUpdate

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.post("", response_model=CaseOut, summary="Create a review case for a screening")
def create_case(body: CaseCreate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    s = db.query(Screening).get(body.screening_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Screening not found")
    case = Case(
        screening_id=body.screening_id,
        title=body.title,
        assigned_to=body.assigned_to or user.username,
        notes=body.notes,
    )
    db.add(case)
    db.commit()
    return case.to_dict()


@router.get("", response_model=list[CaseOut], summary="List cases")
def list_cases(case_status: str | None = None, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    q = db.query(Case).order_by(Case.id.desc())
    if case_status:
        q = q.filter(Case.status == case_status)
    return [c.to_dict() for c in q.limit(200).all()]


@router.get("/{case_id}", response_model=CaseOut, summary="Get a case")
def get_case(case_id: int, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    case = db.query(Case).get(case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return case.to_dict()


@router.patch("/{case_id}", response_model=CaseOut, summary="Update a case (assign/notes/status)")
def update_case(case_id: int, body: CaseUpdate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    case = db.query(Case).get(case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    if body.status is not None:
        case.status = body.status
    if body.assigned_to is not None:
        case.assigned_to = body.assigned_to
    if body.notes is not None:
        case.notes = body.notes
    if body.title is not None:
        case.title = body.title
    db.commit()
    return case.to_dict()