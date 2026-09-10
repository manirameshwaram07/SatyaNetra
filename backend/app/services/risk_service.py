"""Weighted risk engine - all risk math happens here (never in the frontend)."""
from __future__ import annotations

from app.config import settings
from app.utils.logging_conf import get_logger

logger = get_logger("risk")

WEIGHT_KEYS = ["validation", "tampering", "face", "watchlist", "identity", "ocr"]


def _validation_to_100(validation: dict) -> float:
    """Map validation outcome to a risk contribution 0-100 (higher = worse)."""
    overall = validation.get("overall_status", "PASS")
    fails = validation.get("fail_count", 0)
    warns = validation.get("warning_count", 0)
    expired = bool(validation.get("expired"))
    base = {"PASS": 5.0, "WARNING": 35.0, "ERROR": 65.0, "FAIL": 85.0}.get(overall, 40.0)
    if expired:
        base = max(base, 55.0)
    return min(base + warns * 4.0, 100.0)


def _tampering_to_100(tampering: dict) -> float:
    return float(tampering.get("tampering_score", 0))


def _face_to_100(face: dict | None) -> float:
    """Face result to risk contribution. Not verified/failed => moderate risk, not max."""
    if not face:
        return 30.0  # unverified
    status = face.get("status", "")
    if status == "MATCH":
        return max(0.0, (1.0 - float(face.get("similarity", 0))) * 100.0) * 0.4
    if status == "REVIEW":
        return 55.0
    if status in {"MISMATCH", "MULTIPLE_FACES"}:
        return 95.0
    if status == "NO_FACE":
        return 45.0
    return 30.0


def _watchlist_to_100(watchlist: dict) -> float:
    status = (watchlist.get("status") or "NOT_FOUND").upper()
    return {
        "CLEAR": 0.0, "NOT_FOUND": 0.0,
        "VALID": 0.0,
        "EXPIRED": 55.0,
        "DUPLICATE": 75.0,
        "SUSPICIOUS": 85.0,
        "REPORTED": 100.0,
    }.get(status, 40.0)


def _identity_to_100(identity: dict) -> float:
    status = identity.get("status", "NOT_APPLICABLE")
    if status == "NOT_APPLICABLE":
        return 5.0  # single doc: small neutral contribution
    conflicts = len(identity.get("conflicts", []))
    if status == "CONSISTENT":
        return 0.0
    return min(60.0 + conflicts * 10.0, 100.0)


def _ocr_to_100(ocr_conf: float | None, data_source: str) -> float:
    if data_source == "DEMO":
        return 40.0  # unknown real quality
    if ocr_conf is None:
        return 50.0
    c = float(ocr_conf)
    if c >= 0.9:
        return 0.0
    if c >= 0.75:
        return 20.0
    if c >= 0.6:
        return 45.0
    return 70.0


def calculate_risk(validation: dict, tampering: dict, face: dict | None,
                   watchlist: dict, identity: dict, ocr_conf: float | None,
                   ocr_source: str = "OCR") -> dict:
    """Weighted risk calculation with per-factor explanation."""
    weights = settings.risk_weights
    components = {
        "validation": _validation_to_100(validation),
        "tampering": _tampering_to_100(tampering),
        "face": _face_to_100(face),
        "watchlist": _watchlist_to_100(watchlist),
        "identity": _identity_to_100(identity),
        "ocr": _ocr_to_100(ocr_conf, ocr_source),
    }
    # Normalize weights defensively
    used = {k: float(weights.get(k, 0.0)) for k in WEIGHT_KEYS}
    total_w = sum(used.values()) or 1.0
    score = sum(components[k] * (used[k] / total_w) for k in WEIGHT_KEYS)

    risk_score = int(round(score))
    risk_level = risk_level_for(risk_score)

    # Factor explanations (only include meaningful contributors)
    factors = []
    contrib = {k: components[k] * (used[k] / total_w) for k in WEIGHT_KEYS}
    desc = {
        "validation": "Document field validation",
        "tampering": "Tampering / forensic indicators",
        "face": "Face verification",
        "watchlist": "Watchlist / database check",
        "identity": "Cross-document identity consistency",
        "ocr": "OCR extraction confidence",
    }
    for k in sorted(WEIGHT_KEYS, key=lambda x: -contrib[x]):
        if contrib[k] >= 1.0:
            factors.append({
                "factor": k,
                "description": desc[k],
                "signal": round(components[k], 1),
                "weight": round(used[k] / total_w, 3),
                "contribution": round(contrib[k], 1),
            })
    logger.info("Risk score calculated: %d (%s)", risk_score, risk_level)
    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "components": {k: round(v, 1) for k, v in components.items()},
        "factors": factors,
        "weights": {k: round(used[k] / total_w, 3) for k in WEIGHT_KEYS},
    }


def risk_level_for(score: int) -> str:
    if score <= settings.RISK_LOW_MAX:
        return "LOW"
    if score <= settings.RISK_MEDIUM_MAX:
        return "MEDIUM"
    if score <= settings.RISK_HIGH_MAX:
        return "HIGH"
    return "CRITICAL"