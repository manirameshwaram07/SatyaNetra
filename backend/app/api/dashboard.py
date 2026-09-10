"""Dashboard statistics - all values computed from the real database."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.alert import Alert
from app.models.screening import ExtractedData, Screening
from app.models.user import User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", summary="Real dashboard statistics from the database")
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    total = db.query(Screening).count()
    completed = db.query(Screening).filter(
        Screening.status.in_(["COMPLETED", "COMPLETED_WITH_WARNINGS"])).all()

    high = sum(1 for s in completed if (s.risk_level or "") == "HIGH")
    critical = sum(1 for s in completed if (s.risk_level or "") == "CRITICAL")
    medium = sum(1 for s in completed if (s.risk_level or "") == "MEDIUM")
    low = sum(1 for s in completed if (s.risk_level or "") == "LOW")

    tampering = db.query(Screening).filter(Screening.tampering_score >= 60).count()
    face_mismatch = db.query(Screening).filter(Screening.face_match_score.isnot(None)).filter(
        Screening.face_match_score < settings.FACE_REVIEW_THRESHOLD).count()

    # Expired documents: expiry date in the past among extracted data
    today = datetime.now().strftime("%d/%m/%Y")
    expired = 0
    rows = db.query(ExtractedData.expiry_date).all()
    for (exp,) in rows:
        if not exp:
            continue
        try:
            if datetime.strptime(exp, "%d/%m/%Y") < datetime.now():
                expired += 1
        except ValueError:
            continue

    avg_ms = db.query(func.avg(Screening.processing_ms)).filter(
        Screening.processing_ms.isnot(None)).scalar()
    open_alerts = db.query(Alert).filter(Alert.status == "OPEN").count()

    # 7-day trend (screenings per day)
    trend = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).date()
        day_start = datetime(day.year, day.month, day.day)
        day_end = day_start + timedelta(days=1)
        count = db.query(Screening).filter(
            Screening.created_at >= day_start,
            Screening.created_at < day_end).count()
        trend.append({"date": day.isoformat(), "count": count})

    # Risk distribution for charts
    risk_dist = [
        {"level": "LOW", "count": low},
        {"level": "MEDIUM", "count": medium},
        {"level": "HIGH", "count": high},
        {"level": "CRITICAL", "count": critical},
    ]

    return {
        "total_screenings": total,
        "high_risk": high,
        "medium_risk": medium,
        "low_risk": low,
        "critical_risk": critical,
        "tampering_detections": tampering,
        "face_mismatches": face_mismatch,
        "expired_documents": expired,
        "avg_processing_ms": int(avg_ms or 0),
        "open_alerts": open_alerts,
        "trend": trend,
        "risk_distribution": risk_dist,
        "demo_mode": settings.DEMO_MODE,
    }