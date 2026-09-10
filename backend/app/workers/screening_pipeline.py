"""Master screening pipeline orchestrator - runs the full 15-step workflow.

Executed synchronously inside a background thread so the API can return
immediately and the frontend can poll GET /api/screening/{vid}/status.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.database import SessionLocal
from app.models.alert import Alert
from app.models.document import Document
from app.models.screening import ExtractedData, Screening
from app.services import (ai_service, audit_service, face_service, identity_service,
                          mrz_service, ocr_service, report_service, risk_service,
                          validation_service, watchlist_service)
from app.services.document_classifier import classify_document
from app.utils.logging_conf import get_logger

logger = get_logger("pipeline")

STEP_NAMES = [
    "Upload", "Classification", "OCR Extraction", "Field Normalization", "MRZ Analysis",
    "Document Validation", "Tampering Analysis", "Face Detection", "Watchlist Check",
    "Identity Consistency", "Risk Calculation", "AI Explanation", "Alert Generation",
    "Audit Chain", "Report Generation",
]

# In-memory registry of running threads (demo-scale; a real deployment would use a queue)
_running: dict[str, threading.Thread] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_verification_id() -> str:
    year = datetime.now().year
    return f"SN-{year}-{uuid.uuid4().hex[:8].upper()}"


def start_screening(document_id: int) -> str:
    """Create a Screening row and kick off the pipeline in a background thread."""
    db = SessionLocal()
    try:
        doc = db.query(Document).get(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")
        vid = _new_verification_id()
        screening = Screening(
            document_id=document_id,
            verification_id=vid,
            status="PROCESSING",
            progress=0,
            current_step="Queued",
            steps_json=json.dumps([{"name": s, "status": "PENDING", "detail": ""} for s in STEP_NAMES]),
        )
        db.add(screening)
        doc.processing_status = "PROCESSING"
        db.commit()
        screening_id = screening.id
        verification_id = screening.verification_id
    finally:
        db.close()

    t = threading.Thread(target=_run_pipeline, args=(screening_id,), daemon=True)
    _running[verification_id] = t
    t.start()
    return verification_id


def _update_step(steps: list[dict], name: str, status: str, detail: str = "") -> None:
    for s in steps:
        if s["name"] == name:
            s["status"] = status
            s["detail"] = detail
            return
    steps.append({"name": name, "status": status, "detail": detail})


def _persist(db, screening: Screening, steps: list[dict], current_idx: int) -> None:
    screening.steps_json = json.dumps(steps)
    screening.progress = int(round((current_idx) / len(STEP_NAMES) * 100))
    if current_idx < len(STEP_NAMES):
        screening.current_step = STEP_NAMES[current_idx]
    db.commit()


def _run_pipeline(screening_id: int) -> None:
    """The full pipeline. Every stage is failure-isolated: errors mark the step FAILED
    and continue, so one broken module never crashes the screening."""
    db = SessionLocal()
    t0 = time.time()
    screening = db.query(Screening).get(screening_id)
    if screening is None:
        db.close()
        return
    doc = db.query(Document).get(screening.document_id)
    steps = [{"name": s, "status": "PENDING", "detail": ""} for s in STEP_NAMES]

    result: dict = {
        "verification_id": screening.verification_id,
        "document_id": screening.document_id,
        "demo_mode": settings.DEMO_MODE,
        "warnings": [],
    }
    ctx: dict = {}
    ocr_res = None
    extracted = None

    def mark_done(idx: int, detail: str = ""):
        _update_step(steps, STEP_NAMES[idx], "COMPLETED", detail)

    def mark_fail(idx: int, detail: str):
        _update_step(steps, STEP_NAMES[idx], "FAILED", detail)
        result["warnings"].append(f"{STEP_NAMES[idx]}: {detail}")

    def mark_skip(idx: int, detail: str):
        _update_step(steps, STEP_NAMES[idx], "SKIPPED", detail)

    try:
        logger.info("Screening %s started", screening.verification_id)

        # STEP 0: Upload (already done when this runs)
        _update_step(steps, "Upload", "COMPLETED", doc.original_filename)
        _persist(db, screening, steps, 1)

        # STEP 1: Classification
        screening.current_step = "Classification"
        steps[1]["status"] = "PROCESSING"
        _persist(db, screening, steps, 1)
        try:
            ocr_res = ocr_service.run_ocr(doc.file_path)
            dtype, dconf = classify_document(ocr_res.text)
            if dtype == "UNKNOWN":
                dtype = doc.document_type if doc.document_type != "UNKNOWN" else "UNKNOWN"
                dconf = dconf if dconf else 0.3
            result["document_type"] = dtype
            result["classification_confidence"] = dconf
            doc.document_type = dtype
            mark_done(1, f"{dtype} (confidence {dconf:.2f})")
        except Exception as e:
            result["document_type"] = doc.document_type or "UNKNOWN"
            mark_fail(1, f"Classification failed: {type(e).__name__}")
        _persist(db, screening, steps, 2)

        # STEP 2: OCR (re-uses ocr_res if classification already ran it)
        screening.current_step = "OCR Extraction"
        steps[2]["status"] = "PROCESSING"
        _persist(db, screening, steps, 2)
        try:
            if ocr_res is None:
                ocr_res = ocr_service.run_ocr(doc.file_path)
            result["ocr_text_length"] = len(ocr_res.text)
            result["ocr_engine"] = ocr_res.engine
            result["ocr_confidence"] = ocr_res.confidence
            result["ocr_data_source"] = ocr_res.data_source
            result["fields"] = ocr_res.fields
            screening.ocr_confidence = ocr_res.confidence
            doc.ocr_confidence = ocr_res.confidence
            if ocr_res.data_source == "DEMO":
                mark_done(2, "DEMO fallback data used (OCR engine unavailable)")
                result["warnings"].append(
                    "OCR engines unavailable on this machine - DEMO extraction data was used and is clearly labeled.")
            elif ocr_res.data_source == "NONE":
                mark_fail(2, ocr_res.error or "OCR produced no text")
            else:
                mark_done(2, f"engine={ocr_res.engine}, confidence={ocr_res.confidence:.2f}")
        except Exception as e:
            mark_fail(2, f"OCR failed: {type(e).__name__}")
            ocr_res = ocr_service.OcrResult()
        _persist(db, screening, steps, 3)

        # STEP 3: Field normalization + persistence
        screening.current_step = "Field Normalization"
        steps[3]["status"] = "PROCESSING"
        _persist(db, screening, steps, 3)
        try:
            fields = result.get("fields", {}) or {}
            extracted = ExtractedData(
                screening_id=screening.id,
                name=fields.get("full_name", ""),
                document_number=fields.get("document_number", ""),
                nationality=fields.get("nationality", ""),
                date_of_birth=fields.get("date_of_birth", ""),
                gender=fields.get("gender", ""),
                issue_date=fields.get("issue_date", ""),
                expiry_date=fields.get("expiry_date", ""),
                visa_number=fields.get("visa_number", ""),
                visa_type=fields.get("visa_type", ""),
                stay_duration=fields.get("stay_duration", ""),
                mrz_data="",
                data_source=result.get("ocr_data_source", "OCR"),
                raw_text=ocr_res.text[:8000],
            )
            db.add(extracted)
            db.flush()
            mark_done(3, f"{sum(1 for v in fields.values() if v)} fields extracted")
        except Exception as e:
            mark_fail(3, f"Normalization failed: {type(e).__name__}")
        _persist(db, screening, steps, 4)

        # STEP 4: MRZ analysis
        screening.current_step = "MRZ Analysis"
        steps[4]["status"] = "PROCESSING"
        _persist(db, screening, steps, 4)
        try:
            mrz = mrz_service.parse_mrz(ocr_res.lines or ocr_res.text.splitlines())
            comparisons = mrz_service.compare_mrz_vs_ocr(mrz, result.get("fields", {}))
            result["mrz"] = {
                "found": mrz.found,
                "format": mrz.format,
                "fields": mrz.fields,
                "check_digits_valid": mrz.check_digits_valid,
                "comparisons": comparisons,
                "parse_error": mrz.parse_error,
            }
            if extracted is not None and mrz.found:
                import json as _json
                extracted.mrz_data = _json.dumps(mrz.fields)
            if mrz.found:
                mark_done(4, f"TD format={mrz.format}, check digits "
                             f"{'valid' if mrz.check_digits_valid else 'INVALID'}")
            else:
                mark_done(4, "No MRZ found (ok for many document types)")
        except Exception as e:
            result["mrz"] = {"found": False}
            mark_fail(4, f"MRZ analysis failed: {type(e).__name__}")
        _persist(db, screening, steps, 5)

        # STEP 5: Validation
        screening.current_step = "Document Validation"
        steps[5]["status"] = "PROCESSING"
        _persist(db, screening, steps, 5)
        try:
            duplicate = False
            doc_number = (result.get("fields", {}) or {}).get("document_number", "")
            if doc_number:
                dup_count = db.query(Screening).join(ExtractedData).filter(
                    ExtractedData.document_number == doc_number,
                    Screening.id != screening.id,
                ).count()
                duplicate = dup_count > 0
            validation = validation_service.validate_fields(
                result.get("fields", {}), result.get("document_type", "UNKNOWN"),
                mrz_summary=result.get("mrz"), duplicate_number=duplicate,
            )
            result["validation"] = validation
            mark_done(5, validation["overall_status"])
        except Exception as e:
            result["validation"] = {"overall_status": "UNKNOWN", "checks": []}
            mark_fail(5, f"Validation failed: {type(e).__name__}")
        _persist(db, screening, steps, 6)

        # STEP 6: Tampering analysis
        screening.current_step = "Tampering Analysis"
        steps[6]["status"] = "PROCESSING"
        _persist(db, screening, steps, 6)
        try:
            tam = None  # noqa: F841
            from app.services.tampering_service import analyze_document
            tam = analyze_document(doc.file_path)
            result["tampering"] = {
                "tampering_score": tam.tampering_score,
                "risk_level": tam.risk_level,
                "indicators": tam.indicators,
                "photo_tampering_indicator": tam.photo_tampering_indicator,
                "notes": tam.notes,
                "engine": tam.engine,
            }
            screening.tampering_score = tam.tampering_score
            ctx["tampering_score"] = tam.tampering_score
            ctx["tampering_indicators"] = tam.indicators
            mark_done(6, f"score={tam.tampering_score} ({tam.risk_level})")
        except Exception as e:
            result["tampering"] = {"tampering_score": 0, "risk_level": "UNKNOWN",
                                   "indicators": [], "notes": ["Analysis module failed"]}
            mark_fail(6, f"Tampering analysis failed: {type(e).__name__}")
        _persist(db, screening, steps, 7)

        # STEP 7: Face detection (on the document image)
        screening.current_step = "Face Detection"
        steps[7]["status"] = "PROCESSING"
        _persist(db, screening, steps, 7)
        doc_face_img = None
        try:
            doc_face_img = face_service.extract_document_face(doc.file_path)
            if doc_face_img is not None:
                result["face_detection"] = {"faces_detected": 1, "quality": None,
                                            "note": "Portrait extracted from document"}
                mark_done(7, "Portrait found on document")
            else:
                result["face_detection"] = {"faces_detected": 0, "quality": 0.0,
                                            "note": "No face found on document image"}
                mark_done(7, "No face detected on document (face step pending user selfie)")
        except Exception as e:
            mark_fail(7, f"Face detection failed: {type(e).__name__}")
        _persist(db, screening, steps, 8)

        # STEP 8: Watchlist check
        screening.current_step = "Watchlist Check"
        steps[8]["status"] = "PROCESSING"
        _persist(db, screening, steps, 8)
        try:
            doc_number = (result.get("fields", {}) or {}).get(
                "passport_number") or (result.get("fields", {}) or {}).get("document_number", "")
            wl = watchlist_service.check_document_number(db, doc_number)
            result["watchlist"] = wl
            ctx["watchlist"] = wl
            mark_done(8, wl["status"])
        except Exception as e:
            result["watchlist"] = {"found": False, "status": "CHECK_FAILED",
                                   "source": "DEMO_WATCHLIST", "details": {}}
            mark_fail(8, f"Watchlist check failed: {type(e).__name__}")
        _persist(db, screening, steps, 9)

        # STEP 9: Identity consistency (cross-document; needs prior completed screenings
        # in the same session - for the single-doc flow it reports NOT_APPLICABLE).
        screening.current_step = "Identity Consistency"
        steps[9]["status"] = "PROCESSING"
        _persist(db, screening, steps, 9)
        try:
            # Gather prior screenings sharing the session marker if set via API param.
            session_marker = (result.get("fields", {}) or {}).get("full_name", "")
            docs_for_identity = [{"label": result.get("document_type", "DOC"),
                                  "fields": result.get("fields", {})}]
            # include other recent screenings with same name (last 10 min) - simple demo heuristic
            recent = (db.query(Screening)
                      .join(ExtractedData)
                      .filter(Screening.id != screening.id,
                              Screening.created_at >= datetime.now(timezone.utc).replace(tzinfo=None) - __import__("datetime").timedelta(minutes=30))
                      .limit(5).all())
            for r in recent:
                if r.extracted and r.status == "COMPLETED":
                    if (r.extracted.name or "").upper() == session_marker.upper() and session_marker:
                        docs_for_identity.append({
                            "label": r.verification_id,
                            "fields": {
                                "full_name": r.extracted.name,
                                "date_of_birth": r.extracted.date_of_birth,
                                "gender": r.extracted.gender,
                                "nationality": r.extracted.nationality,
                                "document_number": r.extracted.document_number,
                            },
                        })
            identity = identity_service.check_identity_consistency(docs_for_identity)
            result["identity"] = identity
            ctx["identity"] = identity
            mark_done(9, identity["status"])
        except Exception as e:
            result["identity"] = {"status": "UNKNOWN", "conflicts": [], "comparisons": []}
            mark_fail(9, f"Identity consistency failed: {type(e).__name__}")
        _persist(db, screening, steps, 10)

        # STEP 10: Risk calculation (face may be None if user hasn't verified yet)
        screening.current_step = "Risk Calculation"
        steps[10]["status"] = "PROCESSING"
        _persist(db, screening, steps, 10)
        face_result = None
        try:
            # If a stored face verification exists for this verification id, load it
            face_result = _load_face_result(screening.verification_id)
        except Exception:
            face_result = None
        result["face"] = face_result
        try:
            risk = risk_service.calculate_risk(
                validation=result.get("validation", {}),
                tampering=result.get("tampering", {}),
                face=face_result,
                watchlist=result.get("watchlist", {}),
                identity=result.get("identity", {}),
                ocr_conf=result.get("ocr_confidence"),
                ocr_source=result.get("ocr_data_source", "OCR"),
            )
            result["risk_score"] = risk["risk_score"]
            result["risk_level"] = risk["risk_level"]
            result["risk_factors"] = risk["factors"]
            result["risk_components"] = risk["components"]
            screening.risk_score = risk["risk_score"]
            screening.risk_level = risk["risk_level"]
            ctx["validation"] = result.get("validation")
            ctx["face"] = face_result
            ctx["watchlist"] = result.get("watchlist")
            ctx["document_type"] = result.get("document_type")
            ctx["ocr_confidence"] = result.get("ocr_confidence")
            mark_done(10, f"score={risk['risk_score']} ({risk['risk_level']})")
        except Exception as e:
            mark_fail(10, f"Risk calculation failed: {type(e).__name__}")
        _persist(db, screening, steps, 11)

        # STEP 11: AI explanation
        screening.current_step = "AI Explanation"
        steps[11]["status"] = "PROCESSING"
        _persist(db, screening, steps, 11)
        try:
            explanation = ai_service.generate_explanation(
                risk={"risk_score": result.get("risk_score", 0),
                      "risk_level": result.get("risk_level", "UNKNOWN"),
                      "factors": result.get("risk_factors", [])},
                context=ctx,
            )
            result["ai"] = explanation
            mark_done(11, explanation["ai_source"])
        except Exception as e:
            result["ai"] = {"summary": "Explanation module unavailable - manual review recommended.",
                            "ai_source": "rule_based_fallback"}
            mark_fail(11, f"AI explanation failed: {type(e).__name__}")
        _persist(db, screening, steps, 12)

        # STEP 12: Alert generation
        screening.current_step = "Alert Generation"
        steps[12]["status"] = "PROCESSING"
        _persist(db, screening, steps, 12)
        try:
            alerts = _generate_alerts(db, screening, result)
            result["alerts_generated"] = alerts
            mark_done(12, f"{len(alerts)} alert(s) created")
        except Exception as e:
            mark_fail(12, f"Alert generation failed: {type(e).__name__}")
        _persist(db, screening, steps, 13)

        # STEP 13: Audit chain
        screening.current_step = "Audit Chain"
        steps[13]["status"] = "PROCESSING"
        _persist(db, screening, steps, 13)
        try:
            audit_service.record_event(
                db, screening.id, "SCREENING_COMPLETED",
                document_hash=doc.document_hash,
                event_data=json.dumps({
                    "risk_score": result.get("risk_score"),
                    "risk_level": result.get("risk_level"),
                    "document_type": result.get("document_type"),
                }),
            )
            valid, records, msg = audit_service.verify_chain(db, screening.id)
            result["audit"] = {
                "chain_valid": valid,
                "message": msg,
                "records": [r.to_dict() for r in records],
            }
            mark_done(13, "chain verified" if valid else "INTEGRITY FAILURE")
        except Exception as e:
            mark_fail(13, f"Audit failed: {type(e).__name__}")
        _persist(db, screening, steps, 14)

        # STEP 14: Report generation
        screening.current_step = "Report Generation"
        steps[14]["status"] = "PROCESSING"
        _persist(db, screening, steps, 14)
        try:
            out = report_service.report_path_for(screening.verification_id)
            report_service.generate_report(result, out)
            result["report_path"] = str(out)
            mark_done(14, out.name)
        except Exception as e:
            mark_fail(14, f"Report generation failed: {type(e).__name__}")

        # Finalize
        failed = [s for s in steps if s["status"] == "FAILED"]
        screening.status = "COMPLETED_WITH_WARNINGS" if failed else "COMPLETED"
        screening.result_json = json.dumps(result, ensure_ascii=False, default=str)
        screening.steps_json = json.dumps(steps)
        screening.progress = 100
        screening.current_step = "Completed"
        screening.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        screening.processing_ms = int((time.time() - t0) * 1000)
        doc.processing_status = screening.status
        db.commit()
        logger.info("Screening %s finished in %d ms (%d failed steps)",
                    screening.verification_id, screening.processing_ms, len(failed))
    except Exception as e:
        db.rollback()
        screening.status = "FAILED"
        screening.current_step = "Failed"
        screening.result_json = json.dumps({**result, "fatal_error": str(e)[:400]})
        screening.steps_json = json.dumps(steps)
        screening.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        logger.error("Screening %s crashed: %s", screening.verification_id, e)
    finally:
        _running.pop(screening.verification_id, None)
        db.close()


def _load_face_result(verification_id: str) -> dict | None:
    """Load a stored face verification result if one was performed for this screening."""
    from pathlib import Path
    p = Path(settings.PROCESSED_DIR) / f"face_{verification_id}.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


def _generate_alerts(db, screening: Screening, result: dict) -> list[str]:
    """Auto-create alerts based on screening signals."""
    created: list[str] = []

    def add(severity: str, category: str, message: str):
        db.add(Alert(screening_id=screening.id, severity=severity,
                     category=category, message=message[:500]))
        created.append(f"{severity}:{category}")

    risk_level = (result.get("risk_level") or "").upper()
    tam = (result.get("tampering") or {})
    face = (result.get("face") or {})
    wl = (result.get("watchlist") or {})
    ident = (result.get("identity") or {})
    val = (result.get("validation") or {})
    mrz = (result.get("mrz") or {})

    if face.get("status") == "MISMATCH":
        add("HIGH", "FACE_MISMATCH",
            "Presented face does not sufficiently match the document portrait.")
    if face.get("status") == "REVIEW":
        add("MEDIUM", "FACE_REVIEW", "Face similarity inconclusive - manual comparison required.")
    if int(tam.get("tampering_score") or 0) >= 60:
        add("HIGH", "TAMPERING",
            "Potential manipulation indicators detected. Manual inspection recommended.")
    if val.get("expired"):
        add("MEDIUM", "EXPIRED_DOCUMENT", "Document has expired according to extracted dates.")
    if wl.get("found") and wl.get("status") in {"REPORTED", "SUSPICIOUS", "DUPLICATE"}:
        add("CRITICAL" if wl.get("status") == "REPORTED" else "HIGH", "WATCHLIST_MATCH",
            f"Document number matched demo watchlist record with status {wl.get('status')}.")
    if ident.get("status") == "CONFLICT":
        add("HIGH", "IDENTITY_CONFLICT",
            "Identity field conflicts detected across documents: "
            + ", ".join(c.get("field", "?") for c in ident.get("conflicts", [])))
    mismatches = [c for c in (mrz.get("comparisons") or []) if c.get("status") == "MISMATCH"]
    if mismatches:
        add("HIGH", "MRZ_MISMATCH",
            "MRZ vs printed-field mismatch in: " + ", ".join(m.get("field", "") for m in mismatches))
    if risk_level in {"HIGH", "CRITICAL"}:
        add(risk_level, "RISK_LEVEL",
            f"Overall risk score {result.get('risk_score')}/100 ({risk_level}) - enhanced review required.")

    if created:
        db.commit()
    return created