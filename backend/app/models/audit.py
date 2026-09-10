"""Audit model - blockchain-style local hash chain."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import utcnow


class AuditRecord(Base):
    __tablename__ = "audit_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screenings.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    document_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_data: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    screening: Mapped["Screening"] = relationship(back_populates="audit_records")  # noqa: F821

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "screening_id": self.screening_id,
            "verification_id": self.screening.verification_id if self.screening else None,
            "event_type": self.event_type,
            "document_hash": self.document_hash,
            "previous_hash": self.previous_hash,
            "current_hash": self.current_hash,
            "event_data": self.event_data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }