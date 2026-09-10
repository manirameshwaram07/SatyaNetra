"""Screening and ExtractedData models - the core verification records."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import utcnow


class Screening(Base):
    __tablename__ = "screenings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    verification_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(16), default="", nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    tampering_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    face_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    steps_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_step: Mapped[str] = mapped_column(String(64), default="Queued", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="screening")  # noqa: F821
    extracted: Mapped["ExtractedData | None"] = relationship(  # noqa: F821
        back_populates="screening", uselist=False, cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(back_populates="screening")  # noqa: F821
    cases: Mapped[list["Case"]] = relationship(back_populates="screening")  # noqa: F821
    audit_records: Mapped[list["AuditRecord"]] = relationship(back_populates="screening")  # noqa: F821

    def to_dict(self, include_result: bool = False) -> dict:
        import json

        d = {
            "id": self.id,
            "document_id": self.document_id,
            "verification_id": self.verification_id,
            "status": self.status,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "ocr_confidence": self.ocr_confidence,
            "tampering_score": self.tampering_score,
            "face_match_score": self.face_match_score,
            "progress": self.progress,
            "current_step": self.current_step,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "processing_ms": self.processing_ms,
        }
        if include_result:
            try:
                d["result"] = json.loads(self.result_json or "{}")
            except Exception:
                d["result"] = {}
            try:
                d["steps"] = json.loads(self.steps_json or "[]")
            except Exception:
                d["steps"] = []
        return d


class ExtractedData(Base):
    __tablename__ = "extracted_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screenings.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    document_number: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    nationality: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    date_of_birth: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    gender: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    issue_date: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    expiry_date: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    visa_number: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    visa_type: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    stay_duration: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    mrz_data: Mapped[str] = mapped_column(Text, default="", nullable=False)
    data_source: Mapped[str] = mapped_column(String(16), default="OCR", nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)

    screening: Mapped["Screening"] = relationship(back_populates="extracted")  # noqa: F821

    def to_dict(self, redact_raw: bool = True) -> dict:
        return {
            "name": self.name,
            "document_number": self.document_number,
            "nationality": self.nationality,
            "date_of_birth": self.date_of_birth,
            "gender": self.gender,
            "issue_date": self.issue_date,
            "expiry_date": self.expiry_date,
            "visa_number": self.visa_number,
            "visa_type": self.visa_type,
            "stay_duration": self.stay_duration,
            "mrz_data": self.mrz_data,
            "data_source": self.data_source,
            "raw_text": "" if redact_raw else self.raw_text,
        }