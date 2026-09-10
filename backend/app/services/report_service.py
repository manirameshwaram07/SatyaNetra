"""PDF report generation using ReportLab."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.config import settings
from app.utils.logging_conf import get_logger

logger = get_logger("report")

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

BRAND = colors.HexColor("#0B1220")
ACCENT = colors.HexColor("#22D3EE")
DANGER = colors.HexColor("#F87171")
WARN = colors.HexColor("#FBBF24")
OK = colors.HexColor("#34D399")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle(name="Brand", fontName="Helvetica-Bold", fontSize=20,
                          textColor=BRAND, leading=24))
    ss.add(ParagraphStyle(name="Tagline", fontName="Helvetica-Oblique", fontSize=9,
                          textColor=colors.HexColor("#475569"), leading=12))
    ss.add(ParagraphStyle(name="H1", fontName="Helvetica-Bold", fontSize=13,
                          textColor=BRAND, spaceBefore=10, spaceAfter=4))
    ss.add(ParagraphStyle(name="Body", fontName="Helvetica", fontSize=9.5, leading=13))
    ss.add(ParagraphStyle(name="Small", fontName="Helvetica", fontSize=7.5,
                          textColor=colors.HexColor("#475569"), leading=10))
    return ss


def _kv_table(rows: list[tuple[str, str]], ss) -> Table:
    data = [[Paragraph(f"<b>{k}</b>", ss["Body"]), Paragraph(str(v), ss["Body"])] for k, v in rows]
    t = Table(data, colWidths=[55 * mm, 110 * mm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _risk_color(level: str):
    return {"LOW": OK, "MEDIUM": WARN, "HIGH": DANGER, "CRITICAL": DANGER}.get(level, BRAND)


def generate_report(result: dict, out_path: Path) -> Path:
    """Generate the verification PDF report from a full screening result payload."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ss = _styles()
    story = []

    # Header
    story.append(Paragraph("SATYANETRA", ss["Brand"]))
    story.append(Paragraph("See Beyond the Document. Verify the Identity. - SIH Problem 26188", ss["Tagline"]))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT))
    story.append(Spacer(1, 8))

    vid = result.get("verification_id", "-")
    score = result.get("risk_score")
    level = result.get("risk_level", "-")

    risk_color = _risk_color(level)
    story.append(Paragraph("VERIFICATION SUMMARY", ss["H1"]))
    story.append(_kv_table([
        ("Verification ID", vid),
        ("Timestamp", result.get("completed_at") or result.get("created_at") or datetime.now().isoformat()),
        ("Document Type", result.get("document_type", "UNKNOWN")),
        ("RISK SCORE", f"{score if score is not None else '-'} / 100  ({level})"),
        ("Demo Mode", "ACTIVE - demo/fallback data may be present" if result.get("demo_mode") else "OFF"),
    ], ss))

    # Extracted data
    story.append(Paragraph("EXTRACTED DATA (OCR)", ss["H1"]))
    ex = result.get("extracted", {}) or {}
    story.append(_kv_table([
        ("Full Name", ex.get("name", "-")),
        ("Document Number", ex.get("document_number", "-")),
        ("Nationality", ex.get("nationality", "-")),
        ("Date of Birth", ex.get("date_of_birth", "-")),
        ("Gender", ex.get("gender", "-")),
        ("Expiry Date", ex.get("expiry_date", "-")),
        ("Data Source", ex.get("data_source", "-")),
        ("OCR Confidence", f"{round((result.get('ocr_confidence') or 0) * 100)}%"),
    ], ss))

    # Validation checks
    story.append(Paragraph("VALIDATION CHECKS", ss["H1"]))
    val = result.get("validation", {}) or {}
    checks = val.get("checks", [])
    if checks:
        cdata = [[Paragraph("<b>Check</b>", ss["Body"]), Paragraph("<b>Status</b>", ss["Body"]),
                  Paragraph("<b>Message</b>", ss["Body"])]]
        for c in checks:
            cdata.append([Paragraph(str(c.get("name", "")), ss["Body"]),
                          Paragraph(str(c.get("status", "")), ss["Body"]),
                          Paragraph(str(c.get("message", "")), ss["Body"])])
        ct = Table(cdata, colWidths=[40 * mm, 20 * mm, 105 * mm], repeatRows=1)
        ct.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(ct)
        story.append(Spacer(1, 4))
    story.append(Paragraph(f"Overall validation status: <b>{val.get('overall_status', '-')}</b>", ss["Body"]))

    # MRZ
    story.append(Paragraph("MRZ ANALYSIS", ss["H1"]))
    mrz = result.get("mrz", {}) or {}
    if mrz.get("found"):
        story.append(_kv_table([
            ("MRZ Format", mrz.get("format", "-")),
            ("Check Digits", "VALID" if mrz.get("check_digits_valid") else "INVALID/UNVERIFIED"),
            ("Comparisons", "; ".join(
                f"{c.get('field')}: {c.get('status')}" for c in mrz.get("comparisons", [])
            ) or "No comparable fields"),
        ], ss))
    else:
        story.append(Paragraph("No MRZ detected on this document (not necessarily an error).", ss["Body"]))

    # Tampering
    story.append(Paragraph("TAMPERING / FORENSIC ANALYSIS", ss["H1"]))
    tam = result.get("tampering", {}) or {}
    story.append(_kv_table([
        ("Tampering Indicator", f"{tam.get('tampering_score', 0)}/100 ({tam.get('risk_level', '-')})"),
        ("Photo Region Indicator", f"{tam.get('photo_tampering_indicator', 0)}%"),
        ("Engine", tam.get("engine", "-")),
    ], ss))
    for ind in tam.get("indicators", []):
        story.append(Paragraph(f"- [{ind.get('severity', '')}] {ind.get('message', '')}", ss["Body"]))
    story.append(Paragraph("Note: forensic indicators are AI-assisted heuristics and are NOT proof of forgery.",
                           ss["Small"]))

    # Face
    story.append(Paragraph("FACE VERIFICATION", ss["H1"]))
    face = result.get("face", {}) or {}
    if face:
        story.append(_kv_table([
            ("Result", face.get("status", "-")),
            ("Similarity", f"{round(float(face.get('similarity', 0)) * 100)}%"),
            ("Faces (doc/presented)", f"{face.get('faces_detected_document', 0)} / {face.get('faces_detected_presented', 0)}"),
            ("Engine", face.get("engine", "-")),
            ("Message", face.get("message", "-")),
        ], ss))
    else:
        story.append(Paragraph("Face verification was not performed for this screening.", ss["Body"]))

    # Watchlist
    story.append(Paragraph("WATCHLIST CHECK", ss["H1"]))
    wl = result.get("watchlist", {}) or {}
    story.append(Paragraph(
        f"Status: <b>{wl.get('status', '-')}</b> | Source: {wl.get('source', 'DEMO_WATCHLIST')}<br/>"
        f"{(wl.get('details') or {}).get('message', '')}", ss["Body"]))
    story.append(Paragraph("DEMO WATCHLIST: locally seeded records only - never a real government database.",
                           ss["Small"]))

    # Identity consistency
    story.append(Paragraph("IDENTITY CONSISTENCY", ss["H1"]))
    ident = result.get("identity", {}) or {}
    story.append(Paragraph(f"Status: <b>{ident.get('status', 'NOT_APPLICABLE')}</b> - "
                           f"{ident.get('message', '')}", ss["Body"]))

    # AI explanation
    story.append(Paragraph("AI EXPLANATION", ss["H1"]))
    ai = result.get("ai", {}) or {}
    story.append(Paragraph(f"Source: {ai.get('ai_source', 'rule_based_fallback')}", ss["Small"]))
    for line in (ai.get("summary", "") or "").splitlines():
        if line.strip():
            story.append(Paragraph(line.strip().replace("&", "&").replace("<", "<"), ss["Body"]))

    # Risk factors
    story.append(Paragraph("RISK FACTORS", ss["H1"]))
    for f in result.get("risk_factors", []):
        story.append(Paragraph(
            f"- {f.get('description', f.get('factor', ''))}: signal {f.get('signal', 0)} "
            f"(weight {f.get('weight', 0)}, contribution {f.get('contribution', 0)})", ss["Body"]))

    # Audit
    story.append(Paragraph("AUDIT CHAIN", ss["H1"]))
    audit = result.get("audit", {}) or {}
    story.append(_kv_table([
        ("Chain Valid", "YES" if audit.get("chain_valid") else "AUDIT INTEGRITY FAILURE"),
        ("Records", str(len(audit.get("records", [])))),
        ("Latest Hash", (audit.get("records") or [{}])[-1].get("current_hash", "-")[:64]),
    ], ss))

    # Disclaimer
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1")))
    story.append(Paragraph(
        "DISCLAIMER: This report was produced by SatyaNetra, an AI-assisted screening prototype "
        "for Smart India Hackathon 26188. Indicators are probabilistic signals, not legal proof of "
        "fraud. Watchlist data is a locally seeded demo dataset. Human review is the final "
        "authority for any real-world security decision.", ss["Small"]))

    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm,
                            title=f"SatyaNetra Verification Report {vid}")
    doc.build(story)
    logger.info("PDF report generated: %s", out_path.name)
    return out_path


def report_path_for(verification_id: str) -> Path:
    return Path(settings.REPORTS_DIR) / f"report_{verification_id}.pdf"