"""MRZ (Machine Readable Zone) detection and parsing for TD3 passports and TD1/TD2 IDs."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# MRZ charset: digits 0-9, letters A-Z and filler '<'
MRZ_LINE_RE = re.compile(r"^[A-Z0-9<]{30,44}$")

MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
          "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


@dataclass
class MrzResult:
    found: bool = False
    format: str = ""  # TD3 / TD1 / TD2
    fields: dict = field(default_factory=dict)
    check_digits_valid: bool = False
    raw_lines: list[str] = field(default_factory=list)
    parse_error: str = ""


def _char_value(c: str) -> int:
    if c.isdigit():
        return int(c)
    if c == "<":
        return 0
    return ord(c) - 55  # A=10 ... Z=35


def compute_check_digit(s: str) -> int:
    weights = [7, 3, 1]
    return sum(_char_value(c) * weights[i % 3] for i, c in enumerate(s)) % 10


def _valid_check(data: str, check: str) -> bool:
    if not check or not check.isdigit():
        return False
    return compute_check_digit(data) == int(check)


def _mrz_date_to_iso(s: str, century_hint: str = "YY") -> str:
    """YYMMDD (MRZ) -> DD/MM/YYYY. century: birth gets 19/20 logic, expiry 20."""
    if len(s) != 6 or not s.isdigit():
        return ""
    yy, mm, dd = int(s[0:2]), int(s[2:4]), int(s[4:6])
    if century_hint == "birth":
        year = 1900 + yy if yy > 25 else 2000 + yy
    else:
        year = 2000 + yy
    if not (1 <= mm <= 12 and 1 <= dd <= 31):
        return ""
    return f"{dd:02d}/{mm:02d}/{year:04d}"


def find_mrz_lines(lines: list[str]) -> list[str]:
    """Locate MRZ-style lines (>=30 chars of A-Z0-9<) among OCR lines."""
    candidates = []
    for ln in lines:
        ln_clean = re.sub(r"[^A-Z0-9<]", "", ln.upper().replace(" ", ""))
        if len(ln_clean) >= 30 and MRZ_LINE_RE.match(ln_clean):
            candidates.append(ln_clean)
    return candidates


def parse_mrz(lines: list[str]) -> MrzResult:
    """Parse MRZ from OCR output lines. Supports TD3 (2x44) and TD1 (3x30)."""
    mrz_lines = find_mrz_lines(lines)
    if not mrz_lines:
        return MrzResult(parse_error="No MRZ lines detected")

    # TD3: passport, two 44-char lines starting with 'P<'
    if len(mrz_lines) >= 2 and mrz_lines[0].startswith("P<"):
        l1, l2 = mrz_lines[0][:44], mrz_lines[1][:44]
        try:
            surname_given = l1[5:44].split("<<", 1)
            surname = surname_given[0].replace("<", " ").strip()
            given = (surname_given[1].replace("<", " ").strip() if len(surname_given) > 1 else "")
            passport_no = l2[0:9].replace("<", "")
            passport_cd = l2[9:10]
            nationality = l2[10:13].replace("<", "")
            dob = _mrz_date_to_iso(l2[13:19], "birth")
            dob_cd = l2[19:20]
            sex = l2[20:21]
            expiry = _mrz_date_to_iso(l2[21:27], "expiry")
            expiry_cd = l2[27:28]
            personal_no = l2[28:41].replace("<", "")
            composite_cd = l2[41:43] if len(l2) >= 43 else ""

            checks = [
                _valid_check(l2[0:9], passport_cd),
                _valid_check(l2[13:19], dob_cd),
                _valid_check(l2[21:27], expiry_cd),
            ]
            return MrzResult(
                found=True, format="TD3",
                fields={
                    "surname": surname, "given_names": given,
                    "full_name": f"{given} {surname}".strip(),
                    "passport_number": passport_no,
                    "nationality": nationality,
                    "date_of_birth": dob, "gender": sex if sex in {"M", "F"} else "",
                    "expiry_date": expiry, "personal_number": personal_no,
                },
                check_digits_valid=all(checks),
                raw_lines=[l1, l2],
            )
        except Exception as e:
            return MrzResult(found=True, format="TD3", raw_lines=[l1, l2],
                             parse_error=f"TD3 parse failure: {type(e).__name__}")

    # TD1: 3 x 30 lines (ID cards)
    if len(mrz_lines) >= 3 and all(len(x) >= 30 for x in mrz_lines[:3]):
        a, b, c = mrz_lines[0][:30], mrz_lines[1][:30], mrz_lines[2][:30]
        try:
            doc_no = a[5:14].replace("<", "")
            dob = _mrz_date_to_iso(b[0:6], "birth")
            sex = b[7:8]
            expiry = _mrz_date_to_iso(b[8:14], "expiry")
            nationality = b[15:18].replace("<", "")
            name_part = (c[0:30] + a[60:0] if False else c[0:30])  # name on line 3
            surname_given = name_part.split("<<", 1)
            surname = surname_given[0].replace("<", " ").strip()
            given = surname_given[1].replace("<", " ").strip() if len(surname_given) > 1 else ""
            checks = [_valid_check(a[5:14], a[14:15]), _valid_check(b[0:6], b[6:7]),
                      _valid_check(b[8:14], b[14:15])]
            return MrzResult(
                found=True, format="TD1",
                fields={
                    "full_name": f"{given} {surname}".strip(),
                    "document_number": doc_no,
                    "nationality": nationality,
                    "date_of_birth": dob, "gender": sex if sex in {"M", "F"} else "",
                    "expiry_date": expiry,
                },
                check_digits_valid=all(checks),
                raw_lines=[a, b, c],
            )
        except Exception as e:
            return MrzResult(found=True, format="TD1", raw_lines=[a, b, c],
                             parse_error=f"TD1 parse failure: {type(e).__name__}")

    return MrzResult(found=False, raw_lines=mrz_lines,
                     parse_error="MRZ-like lines found but format not recognized")


def compare_mrz_vs_ocr(mrz: MrzResult, ocr_fields: dict) -> list[dict]:
    """Compare MRZ fields vs OCR-extracted fields. Returns comparison list."""
    comparisons = []

    def add(field_name, mrz_val, ocr_val):
        mv = (mrz_val or "").strip().upper()
        ov = (ocr_val or "").strip().upper()
        if not mv or not ov:
            return
        status = "MATCH" if mv == ov else "MISMATCH"
        comparisons.append({
            "field": field_name, "mrz": mrz_val, "ocr": ocr_val, "status": status,
        })

    f = mrz.fields
    add("document_number", f.get("passport_number") or f.get("document_number"),
        ocr_fields.get("passport_number") or ocr_fields.get("document_number"))
    add("date_of_birth", f.get("date_of_birth"), ocr_fields.get("date_of_birth"))
    add("expiry_date", f.get("expiry_date"), ocr_fields.get("expiry_date"))
    add("gender", f.get("gender"), ocr_fields.get("gender"))
    add("nationality", f.get("nationality"), ocr_fields.get("nationality"))
    add("full_name", f.get("full_name"), ocr_fields.get("full_name"))
    return comparisons