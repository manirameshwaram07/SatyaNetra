"""Audit service - local blockchain-style SHA-256 hash chain per screening.

current_hash = SHA256(previous_hash + event_type + event_data + timestamp)
No raw biometric or identity data is hashed into the chain - only event metadata.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit import AuditRecord
from app.utils.logging_conf import get_logger

logger = get_logger("audit")

GENESIS = "0" * 64


def _compute_hash(previous_hash: str, event_type: str, event_data: str, timestamp: str) -> str:
    material = f"{previous_hash}|{event_type}|{event_data}|{timestamp}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def record_event(db: Session, screening_id: int, event_type: str,
                 document_hash: str = "", event_data: str = "") -> AuditRecord:
    """Append an event to the audit chain for a screening.

    NOTE: timezone-naive UTC is used deliberately - SQLite strips timezone info on
    round-trip, so naive UTC keeps the stored timestamp byte-identical for verification.
    """
    last = (
        db.query(AuditRecord)
        .filter(AuditRecord.screening_id == screening_id)
        .order_by(AuditRecord.id.desc())
        .first()
    )
    previous_hash = last.current_hash if last else GENESIS
    ts = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC
    ts_str = ts.isoformat()
    current_hash = _compute_hash(previous_hash, event_type, event_data, ts_str)
    rec = AuditRecord(
        screening_id=screening_id,
        event_type=event_type,
        document_hash=document_hash,
        previous_hash=previous_hash,
        current_hash=current_hash,
        event_data=event_data[:1000],
        timestamp=ts,  # explicit timestamp so hash remains verifiable
    )
    db.add(rec)
    db.flush()
    logger.info("Audit event appended: screening=%s event=%s", screening_id, event_type)
    return rec


def verify_chain(db: Session, screening_id: int) -> tuple[bool, list[AuditRecord], str]:
    """Recompute the chain for a screening. Returns (valid, records, message)."""
    records = (
        db.query(AuditRecord)
        .filter(AuditRecord.screening_id == screening_id)
        .order_by(AuditRecord.id.asc())
        .all()
    )
    prev = GENESIS
    for rec in records:
        expected = _compute_hash(
            prev, rec.event_type, rec.event_data or "",
            rec.timestamp.isoformat() if rec.timestamp else "",
        )
        if rec.previous_hash != prev or rec.current_hash != expected:
            return False, records, "AUDIT INTEGRITY FAILURE: hash chain mismatch detected."
        prev = rec.current_hash
    return True, records, "Audit chain verified: all hashes valid."