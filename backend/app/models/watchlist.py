"""Watchlist model - DEMO local database of document records (not a real government DB)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import utcnow


class WatchlistEntry(Base):
    __tablename__ = "watchlist_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_number: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    nationality: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    date_of_birth: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # VALID/EXPIRED/REPORTED/DUPLICATE/SUSPICIOUS
    notes: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "document_number": self.document_number,
            "name": self.name,
            "nationality": self.nationality,
            "date_of_birth": self.date_of_birth,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }