"""Image/document forensics service (heuristic, AI-assisted indicators).

IMPORTANT: These are heuristic indicators, NOT proof of forgery. The service uses
cautious wording everywhere ("Potential manipulation indicators detected").
"""
from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from app.utils.logging_conf import get_logger

logger = get_logger("tampering")

EDIT_SOFTWARE_MARKERS = [
    "photoshop", "gimp", "paint.net", "paintdotnet", "corel", "pixelmator",
    "affinity", "canva", "snappa", "fotor", "picsart", "lightroom",
    "illustrator", "inkscape", "figma", "pixlr", "infinity",
]


@dataclass
class TamperingResult:
    tampering_score: int = 0          # 0-100
    risk_level: str = "LOW"           # LOW/MEDIUM/HIGH/CRITICAL
    indicators: list[dict] = field(default_factory=list)
    photo_tampering_indicator: int = 0  # 0-100 for portrait region
    notes: list[str] = field(default_factory=list)
    ela_image_path: str = ""
    engine: str = "opencv_heuristics"


def _score_to_level(score: int) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def _add_indicator(indicators: list[dict], itype: str, severity: str, message: str) -> None:
    indicators.append({"type": itype, "severity": severity, "message": message})


def error_level_analysis(img, tmp_dir: Path) -> tuple[float, bytes | None]:
    """Recompress as JPEG q=90 and measure pixel difference energy.

    Returns (ela_score 0-100, ela_png_bytes or None).
    """
    import cv2
    import numpy as np

    gray_scale = False
    temp = tmp_dir / "ela_tmp.jpg"
    cv2.imwrite(str(temp), img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    recompressed = cv2.imread(str(temp))
    if recompressed is None or recompressed.shape != img.shape:
        return 0.0, None

    diff = cv2.absdiff(img, recompressed).astype(np.float32)
    gray = cv2.cvtColor(diff.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    mean_diff = float(diff.mean())
    # High-frequency energy: local std of the difference (manipulated areas often differ more)
    blur = cv2.GaussianBlur(gray, (7, 7), 0)
    hf = cv2.absdiff(gray, blur)
    hf_ratio = float(np.mean(hf > 25))

    # Score: calibrated heuristics (natural photos typically < 12 mean diff)
    score = 0.0
    score += min(mean_diff / 3.0, 55.0)          # up to 55 from mean diff
    score += min(hf_ratio * 180.0, 45.0)         # up to 45 from high-freq outlier ratio
    temp.unlink(missing_ok=True)
    return min(score, 100.0), None


def noise_inconsistency_score(img) -> tuple[float, list[dict]]:
    """Compute noise (high-pass residual) dispersion over an 8x8 grid."""
    import cv2
    import numpy as np

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if max(gray.shape) > 1600:
        scale = 1600 / max(gray.shape)
        gray = cv2.resize(gray, None, fx=scale, fy=scale)
    den = cv2.medianBlur(gray, 3)
    residual = cv2.absdiff(gray, den).astype(np.float32)
    h, w = residual.shape
    gh, gw = h // 8, w // 8
    if gh < 8 or gw < 8:
        return 0.0, []
    vars_ = []
    for r in range(8):
        row = []
        for c in range(8):
            block = residual[r * gh:(r + 1) * gh, c * gw:(c + 1) * gw]
            row.append(float(block.var()))
        vars_.append(row)
    arr = np.array(vars_)
    arr = arr[arr > 0]
    if arr.size < 8:
        return 0.0, []
    spread = float(arr.std() / (arr.mean() + 1e-6))
    # coefficient of variation > 1.2 suggests mixed noise sources
    score = max(0.0, min((spread - 0.6) / 1.4, 1.0)) * 100.0
    # find most anomalous cells
    anomalous_cells = []
    thr = arr.mean() + 2 * arr.std()
    for r in range(8):
        for c in range(8):
            if vars_[r][c] > thr and vars_[r][c] > 0:
                anomalous_cells.append({"grid": [r, c], "variance": round(vars_[r][c], 2)})
    return score, anomalous_cells[:6]


def metadata_analysis(image_path: Path, pil_image) -> tuple[float, list[str], list[dict]]:
    """Look for editing-software traces and missing camera metadata."""
    import numpy as np

    score = 0.0
    notes: list[str] = []
    indicators: list[dict] = []
    info = getattr(pil_image, "info", {}) or {}
    softrw = ""
    # EXIF via PIL (JPEG may carry it)
    exif = {}
    try:
        raw = pil_image.getexif()
        exif = {k: str(v)[:120] for k, v in raw.items()}
    except Exception:
        pass
    softrw = (exif.get(305) or exif.get(40964) or info.get("Software") or info.get("software") or "")
    soft_lower = softrw.lower()
    editor_found = any(m in soft_lower for m in EDIT_SOFTWARE_MARKERS)
    if editor_found:
        score += 60.0
        notes.append(f"Editing software trace in metadata: {softrw[:60]}")
        indicators.append({
            "type": "METADATA", "severity": "MEDIUM",
            "message": f"Image metadata indicates editing software ('{softrw[:40]}'). "
                       "Metadata is supporting evidence only - it can be added or removed legitimately.",
        })
    has_camera_info = any(k in exif for k in (271, 272, 306, 34855))  # Make/Model/DateTime/ISO
    if not has_camera_info and image_path.suffix.lower() in {".jpg", ".jpeg", ".webp"}:
        score += 25.0
        notes.append("No camera make/model/timestamp metadata present")
    return min(score, 80.0), notes, indicators


def copy_move_score(img) -> float:
    """Lightweight copy-move heuristic on downscaled image via small block similarity."""
    import cv2
    import numpy as np

    small = cv2.resize(img, (256, 256))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    block = 8
    hashes = {}
    dup_count = 0
    total = 0
    for r in range(0, 256 - block, block):
        for c in range(0, 256 - block, block):
            blk = gray[r:r + block, c:c + block]
            mean = blk.mean()
            if mean < 5 or mean > 250:  # skip flat blocks
                continue
            bits = (blk > mean).flatten()
            h = "".join("1" if b else "0" for b in bits)
            total += 1
            if h in hashes:
                pr, pc = hashes[h]
                dist = max(abs(pr - r), abs(pc - c))
                if dist > block * 2:  # non-adjacent duplicate
                    dup_count += 1
            else:
                hashes[h] = (r, c)
    if total < 200:
        return 0.0
    ratio = dup_count / total
    return min(ratio * 400.0, 100.0)


def photo_region_analysis(img, face_boxes: list, ela_map: "object | None" = None) -> tuple[float, str]:
    """Compare statistics inside portrait region(s) vs the surrounding document."""
    import cv2
    import numpy as np

    h, w = img.shape[:2]
    boxes = []
    if face_boxes:
        boxes = face_boxes
    else:
        # fallback: largest skin-tone region (rough)
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        skin = cv2.inRange(ycrcb, (0, 135, 85), (255, 180, 135))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(skin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            big = max(contours, key=cv2.contourArea)
            x, y, bw, bh = cv2.boundingRect(big)
            if bw * bh > 0.005 * w * h:
                boxes = [(x, y, bw, bh)]
    if not boxes:
        return 0.0, "no_portrait_region"

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    den = cv2.medianBlur(gray, 3)
    residual = cv2.absdiff(gray, den).astype(np.float32)
    scores = []
    for (x, y, bw, bh) in boxes:
        x, y = max(0, x), max(0, y)
        bw = min(bw, w - x)
        bh = min(bh, h - y)
        if bw < 20 or bh < 20:
            continue
        # pad to compare with a ring around the photo
        pad = int(max(bw, bh) * 0.5)
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)
        inner = residual[y:y + bh, x:x + bw]
        outer_mask = np.ones_like(residual, dtype=bool)
        outer_mask[y:y + bh, x:x + bw] = False
        outer_mask[y0:y1, x0:x1] &= ~np.zeros_like(outer_mask)
        # region strictly around but excluding inner box:
        ring = residual[y0:y1, x0:x1].copy()
        inner_in_ring = np.zeros(ring.shape, dtype=bool)
        inner_in_ring[y - y0:y - y0 + bh, x - x0:x - x0 + bw] = True
        ring = ring[~inner_in_ring]
        if inner.size < 100 or ring.size < 100:
            continue
        vi, vr = float(inner.var()), float(ring.var())
        ci = inner.mean() + 1e-6
        cr = ring.mean() + 1e-6
        noise_ratio = (vi / ci) / (vr / cr + 1e-6)
        s = max(0.0, min(abs(np.log(noise_ratio + 1e-6)) / 1.1, 1.0))
        scores.append(s)
    if not scores:
        return 0.0, "region_too_small"
    return round(float(np.mean(scores)) * 100.0, 1), "analyzed"


def analyze_document(file_path: str | Path, tmp_dir: Path | None = None) -> TamperingResult:
    """Run full forensic heuristic suite on an uploaded document."""
    import cv2
    import numpy as np
    from PIL import Image

    from app.services.ocr_service import load_image

    path = Path(file_path)
    tmp_dir = Path(tmp_dir) if tmp_dir else Path(settings_reports_dir())
    tmp_dir.mkdir(parents=True, exist_ok=True)

    result = TamperingResult()
    try:
        img = load_image(path)
    except Exception as e:
        result.notes.append(f"Image analysis unavailable: {type(e).__name__}")
        result.indicators.append({
            "type": "ANALYSIS_ERROR", "severity": "LOW",
            "message": "Image could not be decoded for forensic analysis. Manual inspection recommended.",
        })
        return result

    if path.suffix.lower() == ".pdf":
        result.notes.append("PDF detected: forensics run on a rasterized page render; "
                            "JPEG ELA is less meaningful for PDF content.")

    # 1) ELA
    try:
        ela_score, _ = error_level_analysis(img, tmp_dir)
    except Exception:
        ela_score = 0.0
        result.notes.append("ELA step skipped (processing error)")

    # 2) Noise inconsistency
    try:
        noise_score, anomalous = noise_inconsistency_score(img)
    except Exception:
        noise_score, anomalous = 0.0, []
    if anomalous:
        result.notes.append(f"{len(anomalous)} grid region(s) show unusual noise levels")

    # 3) Metadata
    try:
        pil_image = Image.open(io.BytesIO(Path(path).read_bytes()))
        meta_score, meta_notes, meta_indicators = metadata_analysis(path, pil_image)
        result.notes.extend(meta_notes)
        for mi in meta_indicators:
            _add_indicator(result.indicators, mi["type"], mi["severity"], mi["message"])
    except Exception:
        meta_score = 0.0

    # 4) Copy-move heuristic
    try:
        cm_score = copy_move_score(img)
    except Exception:
        cm_score = 0.0

    # 5) Portrait region anomaly (uses face boxes if provided later; here quick skin/face)
    face_boxes: list = []
    try:
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        face_boxes = [tuple(map(int, f)) for f in faces]
    except Exception:
        face_boxes = []
    try:
        photo_score, photo_status = photo_region_analysis(img, face_boxes)
        result.photo_tampering_indicator = int(photo_score)
    except Exception:
        photo_score, photo_status = 0.0, "error"
        result.photo_tampering_indicator = 0

    # Weighted fusion (calibrated conservatively)
    combined = (
        ela_score * 0.30
        + noise_score * 0.25
        + meta_score * 0.15
        + cm_score * 0.10
        + photo_score * 0.20
    )
    result.tampering_score = int(min(round(combined), 100))

    # Indicators (cautious wording!)
    if ela_score >= 45:
        _add_indicator(result.indicators, "IMAGE_ANOMALY", "HIGH",
                       "Potential manipulation indicators detected in compression analysis (ELA). "
                       "Manual inspection recommended.")
    elif ela_score >= 28:
        _add_indicator(result.indicators, "IMAGE_ANOMALY", "MEDIUM",
                       "Minor compression inconsistencies observed. May result from normal re-saving.")
    if noise_score >= 45:
        _add_indicator(result.indicators, "NOISE_INCONSISTENCY", "HIGH",
                       "Noise patterns are inconsistent across the image - possible localized editing.")
    elif noise_score >= 28:
        _add_indicator(result.indicators, "NOISE_INCONSISTENCY", "LOW",
                       "Slight noise variation detected; scan/capture artifacts can also cause this.")
    if cm_score >= 50:
        _add_indicator(result.indicators, "CLONE_HINT", "MEDIUM",
                       "Repeated similar regions detected - possible duplicated (cloned) content.")
    if meta_score >= 60:
        pass  # indicator already added inside metadata_analysis
    if photo_score >= 55:
        _add_indicator(result.indicators, "PHOTO_REGION", "HIGH",
                       "Portrait region shows characteristics different from surrounding areas "
                       "(potential photo replacement indicator). Review recommended.")
    elif photo_score >= 35:
        _add_indicator(result.indicators, "PHOTO_REGION", "MEDIUM",
                       "Portrait region statistics differ moderately from surroundings. "
                       "Lighting/quality differences can explain this - verify manually.")

    if not result.indicators:
        _add_indicator(result.indicators, "NO_FLAG", "LOW",
                       "No significant manipulation indicators detected by heuristic analysis. "
                       "This does not guarantee authenticity.")

    result.risk_level = _score_to_level(result.tampering_score)
    logger.info("Tampering analysis done: score=%d level=%s", result.tampering_score, result.risk_level)
    return result


def settings_reports_dir() -> str:
    from app.config import settings
    return settings.PROCESSED_DIR