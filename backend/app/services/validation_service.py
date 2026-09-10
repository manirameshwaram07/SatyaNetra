"""Deterministic document validation engine."""
from __future__ import annotations

import re
from datetime import datetime

DATE_FMT = "%d/%m/%Y"

PASSPORT_RE = re.compile(r"^[A-Z][0-9]{7}$")        # e.g. P1234567
PAN_RE = re.compile(r"^[A-Z]{3}[PGHTF][0-9]{4}[A-Z]$")
AADHAAR_RE = re.compile(r"^\d{4}\s?\d{4}\s?\d{4}$")
DL_IN_RE = re.compile(r"^[A-Z]{2}[-\s]?\d{2}[-\s]?(?:19|20)\d{2}\d{7}$")


def _parse(dt: str):
    if not dt:
        return None
    try:
        return datetime.strptime(dt, DATE_FMT)
    except ValueError:
        return None


def _chk(name: str, status: str, message: str, **extra) -> dict:
    d = {"name": name, "status": status, "message": message}
    d.update(extra)
    return d


def validate_fields(fields: dict, doc_type: str, mrz_summary: dict | None = None,
                    duplicate_number: bool = False) -> dict:
    """Run all validation checks. Returns {overall_status, checks[], score_penalty}."""
    checks: list[dict] = []
    today = datetime.now()

    full_name = (fields.get("full_name") or "").strip()
    doc_number = (fields.get("passport_number") or fields.get("document_number") or "").strip()
    dob = fields.get("date_of_birth") or ""
    expiry = fields.get("expiry_date") or ""
    issue = fields.get("issue_date") or ""

    # 1. Required fields
    required = {"full_name": full_name, "document_number": doc_number, "date_of_birth": dob}
    missing = [k for k, v in required.items() if not v]
    if missing:
        checks.append(_chk(
            "Required Fields", "FAIL" if len(missing) >= 2 else "WARNING",
            f"Missing or unreadable required field(s): {', '.join(missing)}"
        ))
    else:
        checks.append(_chk("Required Fields", "PASS", "All required fields present"))

    # 2. Date formats
    parsed = {k: _parse(fields.get(k) or "") for k in ("date_of_birth", "issue_date", "expiry_date")}
    bad_dates = [k for k, v in parsed.items() if v is None and (fields.get(k) or None) is not None]
    # Only flag when a date field has content but is unparseable is handled above; empty is OK for issue_date
    dob_bad = dob and parsed["date_of_birth"] is None
    exp_bad = expiry and parsed["expiry_date"] is None
    if dob_bad or exp_bad:
        checks.append(_chk("Date Formats", "WARNING", "One or more dates could not be parsed reliably"))
    else:
        checks.append(_chk("Date Formats", "PASS", "Extracted dates are well-formed"))

    # 3. DOB plausibility
    if parsed["date_of_birth"]:
        d = parsed["date_of_birth"]
        age = (today - d).days / 365.25
        if d > today:
            checks.append(_chk("Date of Birth", "FAIL", "Date of birth is in the future"))
        elif age > 110 or age < 0:
            checks.append(_chk("Date of Birth", "WARNING", "Date of birth implies implausible age"))
        else:
            checks.append(_chk("Date of Birth", "PASS", f"Plausible age ({int(age)} years)"))

    # 4. Expiration
    expired = False
    if parsed["expiry_date"]:
        if parsed["expiry_date"] < today:
            expired = True
            days = (today - parsed["expiry_date"]).days
            checks.append(_chk("Expiry", "FAIL", f"Document expired {days} day(s) ago", expired=True))
        else:
            checks.append(_chk("Expiry", "PASS", "Document is currently valid"))

    # 5. Issue < Expiry
    if parsed["issue_date"] and parsed["expiry_date"]:
        if parsed["issue_date"] >= parsed["expiry_date"]:
            checks.append(_chk("Issue/Expiry Order", "FAIL", "Issue date is not before expiry date"))
        else:
            checks.append(_chk("Issue/Expiry Order", "PASS", "Issue date precedes expiry date"))

    # 6. Document number format
    if doc_number:
        if doc_type == "PASSPORT":
            ok = bool(PASSPORT_RE.match(doc_number))
        elif doc_type == "NATIONAL_ID" and re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", doc_number):
            ok = True
        elif doc_type == "DRIVING_LICENSE":
            ok = bool(DL_IN_RE.match(doc_number)) or bool(re.match(r"^[A-Z0-9\-/ ]{6,20}$", doc_number))
        else:
            ok = bool(re.match(r"^[A-Z0-9\-/ ]{5,20}$", doc_number))
        if ok:
            checks.append(_chk("Number Format", "PASS", "Document number matches expected pattern"))
        else:
            checks.append(_chk("Number Format", "WARNING",
                               f"Number '{doc_number}' does not match {doc_type} pattern"))
    # 7. MRZ consistency (summary from mrz_service)
    if mrz_summary is not None:
        if not mrz_summary.get("found"):
            checks.append(_chk("MRZ", "SKIPPED", "No MRZ detected on document (not necessarily an error)"))
        else:
            mismatches = [c for c in mrz_summary.get("comparisons", []) if c.get("status") == "MISMATCH"]
            if mismatches:
                flds = ", ".join(m["field"] for m in mismatches)
                checks.append(_chk("MRZ", "FAIL", f"MRZ vs OCR mismatch in: {flds}"))
            elif not mrz_summary.get("check_digits_valid", False):
                checks.append(_chk("MRZ", "WARNING", "MRZ check digit verification failed"))
            else:
                checks.append(_chk("MRZ", "PASS", "MRZ matches extracted fields; check digits valid"))

    # 8. Duplicate document number (within previously screened docs - demo scope)
    if duplicate_number:
        checks.append(_chk("Duplicate Number", "WARNING",
                           "This document number was seen in a previous screening"))

    failures = sum(1 for c in checks if c["status"] == "FAIL")
    warnings = sum(1 for c in checks if c["status"] == "WARNING")

    if failures >= 2:
        overall = "FAIL"
    elif failures == 1:
        overall = "ERROR"
    elif warnings >= 1:
        overall = "WARNING"
    else:
        overall = "PASS"

    return {
        "overall_status": overall,
        "checks": checks,
        "expired": expired,
        "fail_count": failures,
        "warning_count": warnings,
    }