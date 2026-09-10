"""Alert model - automatically created screening alerts."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import utcnow


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screenings.id"), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # LOW/MEDIUM/HIGH/CRITICAL
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False)  # OPEN/ACKNOWLEDGED/RESOLVED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    screening: Mapped["Screening"] = relationship(back_populates="alerts")  # noqa: F821

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "screening_id": self.screening_id,
            "verification_id": self.screening.verification_id if self.screening else None,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }