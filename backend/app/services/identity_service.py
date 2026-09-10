"""Identity consistency service - cross-document comparison within a session."""
from __future__ import annotations

from datetime import datetime

NAME_ALIASES = {"KUMAR": "", "KUMARI": ""}


def _norm_name(n: str) -> str:
    n = (n or "").upper().strip()
    tokens = [t for t in n.split() if t and NAME_ALIASES.get(t, "x") != ""]
    return " ".join(sorted(tokens))


def _norm_date(d: str) -> str:
    d = (d or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(d, fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    return d


def compare_field(values: dict[str, str], field: str) -> dict:
    """Compare a single identity field across documents.

    values: {source_label: raw_value}
    """
    normed: dict[str, str] = {}
    for src, val in values.items():
        if not val:
            continue
        if field == "full_name":
            normed[src] = _norm_name(val)
        elif field in ("date_of_birth", "issue_date", "expiry_date"):
            normed[src] = _norm_date(val)
        else:
            normed[src] = val.strip().upper()

    distinct = {v for v in normed.values() if v}
    if len(normed) == 0:
        return {"field": field, "status": "NO_DATA", "values": normed, "message": "Field not available on any document."}
    if len(distinct) == 1:
        return {"field": field, "status": "MATCH", "values": normed,
                "message": "Consistent across documents."}
    return {
        "field": field, "status": "MISMATCH", "values": normed,
        "message": f"{field.replace('_', ' ').title()} mismatch detected across documents.",
    }


def check_identity_consistency(documents: list[dict]) -> dict:
    """Cross-compare extracted data from multiple documents in one screening session.

    documents: [{"label": "Passport", "fields": {...}}, ...]
    Returns {status, conflicts[], comparisons[]}
    """
    if len(documents) < 2:
        return {
            "status": "NOT_APPLICABLE",
            "conflicts": [],
            "comparisons": [],
            "message": "Single document - cross-document consistency not applicable.",
        }

    fields_to_check = ["full_name", "date_of_birth", "gender", "nationality", "document_number"]
    comparisons = []
    for f in fields_to_check:
        values = {d["label"]: (d.get("fields") or {}).get(f, "") for d in documents}
        comparisons.append(compare_field(values, f))

    conflicts = [c for c in comparisons if c["status"] == "MISMATCH"]
    status = "CONFLICT" if conflicts else "CONSISTENT"
    return {
        "status": status,
        "conflicts": conflicts,
        "comparisons": comparisons,
        "message": (f"{len(conflicts)} identity conflict(s) detected across {len(documents)} documents."
                    if conflicts else
                    f"All identity fields consistent across {len(documents)} documents."),
    }