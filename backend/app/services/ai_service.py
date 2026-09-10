"""Optional AI explanation layer using the CURRENT Google GenAI SDK (google.genai).

Falls back to a deterministic rule-based explanation when Gemini is not configured.
Only minimal structured signals are sent to Gemini - never raw identity data.
"""
from __future__ import annotations

import json

from app.config import settings
from app.utils.logging_conf import get_logger

logger = get_logger("ai")

# Keys allowed to leave the machine (minimum necessary information)
_ALLOWED_KEYS = [
    "risk_score", "risk_level", "document_type", "validation_overall",
    "tampering_score", "face_status", "watchlist_status", "identity_status",
    "ocr_confidence", "indicators",
]


def _build_signal_payload(risk: dict, context: dict) -> dict:
    payload = {
        "risk_score": risk.get("risk_score"),
        "risk_level": risk.get("risk_level"),
        "document_type": context.get("document_type", "UNKNOWN"),
        "validation_overall": (context.get("validation") or {}).get("overall_status"),
        "expired": bool((context.get("validation") or {}).get("expired")),
        "tampering_score": context.get("tampering_score"),
        "face_status": (context.get("face") or {}).get("status"),
        "watchlist_status": (context.get("watchlist") or {}).get("status"),
        "identity_status": (context.get("identity") or {}).get("status"),
        "ocr_confidence": context.get("ocr_confidence"),
        "indicators": [
            i.get("message", "")[:160]
            for i in (context.get("tampering_indicators") or [])
        ][:8],
        "risk_factors": risk.get("factors", [])[:6],
    }
    return {k: v for k, v in payload.items() if k in _ALLOWED_KEYS or k in
            {"expired", "risk_factors"}}


def _gemini_explain(signal: dict) -> str | None:
    """Generate explanation with Gemini via the current google-genai SDK."""
    if not settings.GEMINI_API_KEY:
        return None
    try:
        from google import genai

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = (
            "You are a document screening assistant for trained verification officers. "
            "Given these structured screening signals from an AI document analysis pipeline, "
            "write a concise professional explanation (max 180 words) with sections: "
            "Summary, Suspicious Indicators, Recommended Review Steps. "
            "Use cautious language - these are AI-assisted indicators, not proof of fraud. "
            "Do not invent facts beyond the signals. Signals JSON:\n"
            + json.dumps(signal, ensure_ascii=False)
        )
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        text = (resp.text or "").strip()
        return text or None
    except Exception as e:
        logger.warning(f"Gemini explanation failed: {type(e).__name__}; using rule-based fallback.")
        return None


def _rule_based_explain(signal: dict) -> str:
    """Deterministic template explanation from screening signals."""
    lines: list[str] = []
    level = signal.get("risk_level", "UNKNOWN")
    score = signal.get("risk_score", "-")
    lines.append(f"Summary: The document screening produced a {level} risk result "
                 f"(score {score}/100). This is an AI-assisted assessment; human review "
                 f"remains the final authority.")

    suspicious: list[str] = []
    if signal.get("tampering_score") is not None and signal["tampering_score"] >= 40:
        suspicious.append(
            f"Potential manipulation indicators detected in the document image "
            f"(forensic indicator score {signal['tampering_score']}/100). The document should be "
            f"manually inspected before a final determination.")
    if signal.get("validation_overall") in {"ERROR", "FAIL"}:
        suspicious.append("Field validation reported failed checks - verify details against the physical document.")
    elif signal.get("expired"):
        suspicious.append("The document appears to be expired according to extracted dates.")
    if signal.get("face_status") == "MISMATCH":
        suspicious.append("The presented face did not sufficiently match the document portrait.")
    elif signal.get("face_status") == "REVIEW":
        suspicious.append("Face similarity was inconclusive and requires manual comparison.")
    wl = signal.get("watchlist_status")
    if wl and wl not in {"CLEAR", "NOT_FOUND", None}:
        suspicious.append(f"The document number matched a record in the demo watchlist ({wl}). "
                          "This is a locally seeded demo database, not a government database.")
    if signal.get("identity_status") == "CONFLICT":
        suspicious.append("Conflicting identity fields were detected across submitted documents.")
    if signal.get("ocr_confidence") is not None and signal["ocr_confidence"] < 0.6:
        suspicious.append("OCR confidence was low - re-scan the document at higher quality for reliable extraction.")

    if not suspicious:
        suspicious.append("No significant risk indicators were detected by the automated pipeline. "
                          "This does not guarantee authenticity.")

    lines.append("Suspicious Indicators:")
    for s in suspicious:
        lines.append(f"- {s}")

    lines.append("Recommended Review Steps:")
    steps = ["Compare the uploaded image with the physical document.",
             "Check security features (holograms, microtext, MRZ) manually."]
    if signal.get("face_status") in {"REVIEW", "MISMATCH", None}:
        steps.append("Re-verify the person's identity with an additional official document.")
    if signal.get("expired"):
        steps.append("Request an updated, valid document.")
    if wl and wl not in {"CLEAR", "NOT_FOUND", None}:
        steps.append("Route this case to a senior officer for escalation (demo watchlist match).")
    steps.append("Record the final human decision in the case management module.")
    for s in steps:
        lines.append(f"- {s}")

    return "\n".join(lines)


def generate_explanation(risk: dict, context: dict) -> dict:
    """Return {summary, source}. context must contain only structured signals."""
    signal = _build_signal_payload(risk, context)
    text = _gemini_explain(signal)
    if text:
        return {"summary": text, "ai_source": "gemini"}
    return {"summary": _rule_based_explain(signal), "ai_source": "rule_based_fallback"}