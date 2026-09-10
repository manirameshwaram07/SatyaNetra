"""Document model - uploaded files and their metadata."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import utcnow


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_type: Mapped[str] = mapped_column(String(32), default="UNKNOWN", nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    document_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), default="UPLOADED", nullable=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    screening: Mapped["Screening | None"] = relationship(  # noqa: F821
        back_populates="document", uselist=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "document_type": self.document_type,
            "original_filename": self.original_filename,
            "file_path": self.file_path,
            "document_hash": self.document_hash,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "processing_status": self.processing_status,
            "ocr_confidence": self.ocr_confidence,
        }