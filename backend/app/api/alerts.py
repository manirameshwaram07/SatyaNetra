"""Alert endpoints: list + status updates."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.alert import Alert
from app.models.user import User
from app.schemas.schemas import AlertOut, AlertUpdate

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut], summary="List alerts (newest first)")
def list_alerts(alert_status: str | None = None, limit: int = 100,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Alert).order_by(Alert.id.desc())
    if alert_status:
        q = q.filter(Alert.status == alert_status)
    return [a.to_dict() for a in q.limit(min(limit, 300)).all()]


@router.patch("/{alert_id}", response_model=AlertOut, summary="Update alert status")
def update_alert(alert_id: int, body: AlertUpdate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    alert = db.query(Alert).get(alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    alert.status = body.status
    db.commit()
    return alert.to_dict()