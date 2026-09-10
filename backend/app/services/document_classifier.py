"""Document classification: OCR-content heuristics + optional manual override."""
from __future__ import annotations

import re

DOC_TYPES = ["PASSPORT", "VISA", "NATIONAL_ID", "DRIVING_LICENSE", "PERMIT", "UNKNOWN"]

# Weighted keyword signatures per document type
_SIGNATURES: dict[str, list[tuple[str, float]]] = {
    "PASSPORT": [
        (r"\bPASSPORT\b", 0.5),
        (r"\bREPUBLIC\b|\bGOVERNMENT\b", 0.15),
        (r"P<[A-Z]{3}[A-Z<]{2,}", 0.35),
        (r"\bNATIONALITY\b", 0.2),
        (r"\bSURNAME\b", 0.15),
        (r"DATE OF EXPIRY", 0.15),
    ],
    "VISA": [
        (r"\bVISA\b", 0.55),
        (r"\bVISA TYPE\b|\bENTRY\b|\bSTAY\b|\bDURATION OF STAY\b", 0.2),
        (r"\bVAF\b|\bVISA NUMBER\b", 0.2),
    ],
    "NATIONAL_ID": [
        (r"\bAADHAAR\b|\bAADHAR\b|\bUIDAI\b", 0.5),
        (r"\bNATIONAL ID\b|\bIDENTITY CARD\b|\bVOTER\b|\bEPIC\b", 0.45),
        (r"\bPAN\b\s*CARD", 0.35),
        (r"\bINCOME TAX\b", 0.15),
    ],
    "DRIVING_LICENSE": [
        (r"DRIVING LICEN[CS]E|\bDL\b\s*(NO|NUMBER)", 0.5),
        (r"\bLMV\b|\bMCWG\b|\bAUTHORITY\b|\bCOV\b", 0.2),
        (r"\bTRANSPORT\b|\bNON.TRANSPORT\b", 0.15),
    ],
    "PERMIT": [
        (r"\bPERMIT\b", 0.55),
        (r"\bWORK PERMIT\b|\bRESIDENCE PERMIT\b|\bRESIDENT PERMIT\b", 0.35),
        (r"\bVALID FOR\b|\bEMPLOYER\b", 0.15),
    ],
}


def classify_document(text: str, image_hint: str | None = None) -> tuple[str, float]:
    """Classify a document from OCR text. Returns (type, confidence 0-1)."""
    if not text:
        return "UNKNOWN", 0.0
    upper = text.upper()
    scores: dict[str, float] = {}
    for dtype, sigs in _SIGNATURES.items():
        s = 0.0
        for pattern, weight in sigs:
            if re.search(pattern, upper):
                s += weight
        if s > 0:
            scores[dtype] = s
    if not scores:
        return "UNKNOWN", 0.0
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    total = sum(scores.values())
    confidence = min(scores[best] / max(total, 1e-6) * min(total / 0.7, 1.0), 0.97)
    return best, round(confidence, 2)


def classify_from_file(file_path, hint: str | None = None) -> tuple[str, float]:
    """Classify from the stored file by running OCR text extraction."""
    from app.services.ocr_service import run_ocr

    res = run_ocr(file_path)
    dtype, conf = classify_document(res.text)
    if dtype == "UNKNOWN" and hint:
        hint_u = hint.upper()
        if hint_u in DOC_TYPES:
            return hint_u, 0.6  # manual hint = moderate confidence
    return dtype, conf