"""Real OCR service with layered engines and graceful fallbacks.

Engine order:
  1. Tesseract (pytesseract) - if installed and configured
  2. Windows built-in OCR (WinRT) via PowerShell bridge - no install needed on Win10/11
  3. DEMO fallback (DEMO_MODE only) - clearly labeled data_source="DEMO"

The service never silently fabricates results: fallback data is always tagged.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.utils.logging_conf import get_logger

logger = get_logger("ocr")

WINRT_BRIDGE = Path(__file__).resolve().parent.parent / "utils" / "winrt_ocr.ps1"

# ---------------------------------------------------------------- parsing helpers

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

DATE_PATTERNS = [
    (re.compile(r"(\d{2})[./\-](\d{2})[./\-](\d{4})"), "DMY"),   # 12/05/1995
    (re.compile(r"(\d{4})[./\-](\d{2})[./\-](\d{2})"), "YMD"),   # 1995-05-12
    (re.compile(r"(\d{1,2})\s*([A-Z]{3})\s*[./\-]?\s*(\d{4})", re.IGNORECASE), "ABM"),  # 12 MAY 1995
    (re.compile(r"([A-Z]{3})\s*[./\-]?\s*(\d{1,2})[,.]?\s*(\d{4})", re.IGNORECASE), "MAB"),  # MAY 12, 1995
]


@dataclass
class OcrResult:
    text: str = ""
    lines: list[str] = field(default_factory=list)
    confidence: float = 0.0
    data_source: str = "OCR"  # OCR | DEMO | NONE
    engine: str = ""
    fields: dict = field(default_factory=dict)
    error: str = ""


# ---------------------------------------------------------------- image loading

def load_image(path: str | Path) -> "object":
    """Load file path into a numpy BGR image. PDFs are rasterized (first page)."""
    import cv2
    import numpy as np
    from PIL import Image

    path = Path(path)
    if path.suffix.lower() == ".pdf":
        import fitz  # PyMuPDF
        with fitz.open(str(path)) as doc:
            if doc.page_count == 0:
                raise ValueError("PDF has no pages")
            pix = doc[0].get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
        pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    else:
        pil = Image.open(str(path)).convert("RGB")
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def preprocess(img) -> "object":
    """Grayscale, upscale small images, denoise lightly, adaptive threshold."""
    import cv2
    import numpy as np

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    scale = 1.0
    if max(h, w) < 1000:
        scale = min(2000 / max(h, w), 3.0)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, h=7)
    try:
        thr = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 31, 15)
    except cv2.error:
        thr = gray
    return thr


# ---------------------------------------------------------------- engines

_TESS_AVAILABLE: bool | None = None


def _tesseract_available() -> bool:
    global _TESS_AVAILABLE
    if _TESS_AVAILABLE is not None:
        return _TESS_AVAILABLE
    try:
        import pytesseract
        if settings.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        pytesseract.get_tesseract_version()
        _TESS_AVAILABLE = True
    except Exception:
        _TESS_AVAILABLE = False
    return _TESS_AVAILABLE


def _ocr_tesseract(img) -> tuple[str, float] | None:
    if not _tesseract_available():
        return None
    import pytesseract
    processed = preprocess(img)
    for attempt_img in (processed, img):
        try:
            data = pytesseract.image_to_data(
                attempt_img, output_type=pytesseract.Output.DICT, config="--psm 6"
            )
            words, confs = [], []
            for i, txt in enumerate(data["text"]):
                t = txt.strip()
                if t:
                    words.append(t)
                    try:
                        c = float(data["conf"][i])
                        if c >= 0:
                            confs.append(c)
                    except (ValueError, KeyError):
                        pass
            text = " ".join(words)
            if len(text) >= 10:
                conf = sum(confs) / len(confs) / 100.0 if confs else 0.75
                return text, min(conf, 0.99)
        except Exception as e:  # pragma: no cover - environment specific
            logger.warning(f"Tesseract attempt failed: {type(e).__name__}")
    return None


def _ocr_winrt(image_path: str | Path) -> tuple[str, float] | None:
    """Windows built-in OCR via PowerShell bridge. Returns None when unavailable."""
    if sys.platform != "win32" or not WINRT_BRIDGE.exists():
        return None
    ps = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    try:
        proc = subprocess.run(
            [ps, "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(WINRT_BRIDGE), "-ImagePath", str(Path(image_path).resolve())],
            capture_output=True, text=True, timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        return None
    out = (proc.stdout or "").strip()
    if proc.returncode != 0 or "__OCR" in out or not out:
        return None
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    text = "\n".join(lines)
    if len(text) < 5:
        return None
    return text, 0.82  # WinRT does not expose word confidences; use nominal value


# ---------------------------------------------------------------- demo fallback

_DEMO_FIELDS = {
    "full_name": "ARJUN SHARMA",
    "passport_number": "P1234567",
    "nationality": "IND",
    "date_of_birth": "12/05/1995",
    "gender": "M",
    "issue_date": "13/05/2015",
    "expiry_date": "12/05/2030",
    "address": "12 MG ROAD, BANGALORE 560001",
}


def _demo_fallback() -> OcrResult:
    logger.warning("OCR engines unavailable - using DEMO fallback data (clearly labeled).")
    lines = [
        "REPUBLIC OF INDIA  PASSPORT",
        "Surname: SHARMA",
        "Given Name(s): ARJUN",
        "Nationality: IND",
        "Date of Birth: 12/05/1995",
        "Sex: M",
        "Passport No: P1234567",
        "Date of Issue: 13/05/2015",
        "Date of Expiry: 12/05/2030",
    ]
    res = OcrResult(
        text="\n".join(lines),
        lines=lines,
        confidence=0.70,
        data_source="DEMO",
        engine="demo_fallback",
    )
    res.fields = dict(_DEMO_FIELDS)
    return res


# ---------------------------------------------------------------- field parsing

def _parse_date(s: str) -> str | None:
    for rx, kind in DATE_PATTERNS:
        m = rx.search(s)
        if not m:
            continue
        try:
            if kind == "DMY":
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif kind == "YMD":
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif kind == "ABM":
                d, mo_name, y = int(m.group(1)), m.group(2).upper(), int(m.group(3))
                mo = MONTHS.get(mo_name[:3])
                if not mo:
                    continue
            else:  # MAB
                mo_name, d, y = m.group(1).upper(), int(m.group(2)), int(m.group(3))
                mo = MONTHS.get(mo_name[:3])
                if not mo:
                    continue
            if 1900 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{d:02d}/{mo:02d}/{y:04d}"
        except (ValueError, IndexError):
            continue
    return None


_LABEL_MAP = {
    "full_name": [r"surname[:\s]+([A-Z][A-Z\s]+)", r"given\s*names?[:\s]+([A-Z][A-Z\s]+)",
                  r"name[:\s]+([A-Z][A-Z\s]+)"],
    "passport_number": [r"passport\s*(?:no|number)[:\s]*([A-Z0-9]{6,12})"],
    "document_number": [r"(?:id|document|card|licen[cs]e)\s*(?:no|number)[:\s]*([A-Z0-9\/\-]{5,20})",
                        r"\b([A-Z]{3}[0-9]{7})\b",  # PAN style
                        r"\b([A-Z]{2}\s?\d{7})\b"],  # DL style
    "nationality": [r"nationality[:\s]+([A-Z]{3}|[A-Z][A-Z\s]{2,20})"],
    "date_of_birth": [r"(?:date\s*of\s*birth|d\.?o\.?b\.?|dob)[:\s]*([0-9]{2}[./\-][0-9]{2}[./\-][0-9]{4}|[0-9]{4}[./\-][0-9]{2}[./\-][0-9]{2}|\d{1,2}\s*[A-Z]{3}\s*\d{4})"],
    "gender": [r"(?:sex|gender)[:\s]*\b(M|F|MALE|FEMALE)\b"],
    "issue_date": [r"(?:date\s*of\s*issue|issued?)[:\s]*([0-9]{2}[./\-][0-9]{2}[./\-][0-9]{4})"],
    "expiry_date": [r"(?:date\s*of\s*expiry|expiry|valid\s*(?:till|until))[:\s]*([0-9]{2}[./\-][0-9]{2}[./\-][0-9]{4}|\d{1,2}\s*[A-Z]{3}\s*\d{4})"],
}


def parse_fields(text: str, lines: list[str]) -> dict:
    """Extract structured identity fields from OCR text."""
    fields: dict = {}
    upper = "\n".join(lines or text.splitlines()).upper()

    def grab(key: str) -> str:
        for pattern in _LABEL_MAP[key]:
            m = re.search(pattern, upper, re.IGNORECASE)
            if m and m.group(1):
                return m.group(1).strip()
        return ""

    fields["full_name"] = grab("full_name")
    fields["passport_number"] = grab("passport_number")
    fields["document_number"] = grab("document_number")

    nat = grab("nationality")
    if nat:
        nat = re.sub(r"[^A-Z]", "", nat)[:3] if re.fullmatch(r"[A-Z]{3}", nat) else nat
    fields["nationality"] = nat

    for key in ("date_of_birth", "issue_date", "expiry_date"):
        raw = grab(key)
        parsed = _parse_date(raw) if raw else None
        if parsed:
            fields[key] = parsed
        else:
            # heuristic: first date near label
            d = _parse_date(upper)
            fields[key] = d or ""

    g = grab("gender")
    fields["gender"] = "M" if g in {"M", "MALE"} else ("F" if g in {"F", "FEMALE"} else "")

    if fields.get("passport_number") and not fields.get("document_number"):
        fields["document_number"] = fields["passport_number"]

    # Name fallback: first line that looks like ALL-CAPS words (>=2 tokens), not a label line
    if not fields.get("full_name"):
        for ln in (lines or text.splitlines()):
            ln_u = ln.strip().upper()
            if re.fullmatch(r"[A-Z][A-Z\s'.-]{4,60}", ln_u) and len(ln_u.split()) >= 2:
                if not any(k in ln_u for k in ("PASSPORT", "REPUBLIC", "REPUBLIC OF", "GOVERNMENT",
                                               "UNION", "NATIONAL", "LICENCE", "LICENSE")):
                    fields["full_name"] = ln_u
                    break

    return {k: v for k, v in fields.items()}


# ---------------------------------------------------------------- main entry

def run_ocr(file_path: str | Path) -> OcrResult:
    """Run the OCR pipeline on an uploaded document."""
    path = Path(file_path)
    if not path.exists():
        return OcrResult(data_source="NONE", error="File not found")

    try:
        img = load_image(path)
    except Exception as e:
        logger.error(f"OCR image load failed: {type(e).__name__}")
        if settings.DEMO_MODE:
            res = _demo_fallback()
            res.error = f"image_load_failed:{type(e).__name__}"
            return res
        return OcrResult(data_source="NONE", error=f"image_load_failed:{type(e).__name__}")

    # 1) Tesseract
    result = None
    try:
        result = _ocr_tesseract(img)
    except Exception:
        result = None
    if result:
        text, conf = result
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()] or text.split()
        res = OcrResult(text=text, lines=lines, confidence=round(conf, 3),
                        data_source="OCR", engine="tesseract")
        res.fields = parse_fields(text, lines)
        logger.info("OCR completed (engine=tesseract, confidence=%.2f)", res.confidence)
        return res

    # 2) Windows built-in OCR
    result = _ocr_winrt(path)
    if result:
        text, conf = result
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        res = OcrResult(text=text, lines=lines, confidence=conf,
                        data_source="OCR", engine="winrt")
        res.fields = parse_fields(text, lines)
        logger.info("OCR completed (engine=winrt, confidence=%.2f)", res.confidence)
        return res

    # 3) Demo fallback (labeled!)
    if settings.DEMO_MODE:
        return _demo_fallback()
    return OcrResult(data_source="NONE", error="No OCR engine available")