"""Case model - human review workflow."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import utcnow


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screenings.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False)  # OPEN/IN_PROGRESS/ESCALATED/RESOLVED
    assigned_to: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    screening: Mapped["Screening"] = relationship(back_populates="cases")  # noqa: F821

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "screening_id": self.screening_id,
            "verification_id": self.screening.verification_id if self.screening else None,
            "title": self.title,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }