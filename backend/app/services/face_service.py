"""Face detection and verification service.

Detection: OpenCV Haar cascades (no heavy deps).
Verification: face_recognition (dlib) if installed; otherwise a clearly-labeled
demo fallback that compares structural image features (NOT a true biometric match).
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from app.config import settings
from app.utils.logging_conf import get_logger

logger = get_logger("face")

_CASCADES: dict = {}


def _cascades() -> dict:
    if not _CASCADES:
        base = cv2.data.haarcascades
        _CASCADES["frontal"] = cv2.CascadeClassifier(base + "haarcascade_frontalface_default.xml")
        _CASCADES["alt"] = cv2.CascadeClassifier(base + "haarcascade_frontalface_alt2.xml")
        _CASCADES["profile"] = cv2.CascadeClassifier(base + "haarcascade_profileface.xml")
    return _CASCADES


@dataclass
class FaceDetection:
    count: int = 0
    boxes: list = field(default_factory=list)
    quality: float = 0.0
    largest_face_img: "np.ndarray | None" = None


def detect_faces(img_bgr) -> FaceDetection:
    """Detect faces in a BGR image. Returns count, boxes, quality, largest face crop."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    min_size = (int(max(h, w) * 0.04),) * 2

    c = _cascades()
    faces = list(c["frontal"].detectMultiScale(gray, 1.1, 5, minSize=min_size))
    if not faces:
        faces = list(c["alt"].detectMultiScale(gray, 1.1, 5, minSize=min_size))
    if not faces:
        profile = c["profile"].detectMultiScale(gray, 1.1, 5, minSize=min_size)
        faces = list(profile)
        flipped = c["profile"].detectMultiScale(cv2.flip(gray, 1), 1.1, 5, minSize=min_size)
        for (x, y, fw, fh) in flipped:
            faces.append((w - x - fw, y, fw, fh))

    boxes = [[int(x), int(y), int(fw), int(fh)] for (x, y, fw, fh) in faces]
    detection = FaceDetection(count=len(boxes), boxes=boxes)

    if boxes:
        # Quality: sharpness (Laplacian var) + resolution of the largest face
        x, y, fw, fh = max(boxes, key=lambda b: b[2] * b[3])
        roi = gray[y:y + fh, x:x + fw]
        laplacian_var = cv2.Laplacian(roi, cv2.CV_64F).var()
        sharpness = min(laplacian_var / 300.0, 1.0)
        resolution = min((fw * fh) / (150 * 150), 1.0)
        detection.quality = round((sharpness * 0.6 + resolution * 0.4), 2)
        crop = img_bgr[y:y + fh, x:x + fw].copy()
        detection.largest_face_img = crop
    return detection


def _decode_data_url(data: str) -> np.ndarray | None:
    """Decode base64/URL-encoded image (from camera capture or upload)."""
    try:
        if "," in data and data.strip().startswith("data:"):
            data = data.split(",", 1)[1]
        raw = base64.b64decode(data)
        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def _face_embedding(img_bgr) -> "np.ndarray | None":
    """Try real face embedding via face_recognition; returns None if unavailable."""
    try:
        import face_recognition  # type: ignore
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        encs = face_recognition.face_encodings(rgb)
        if encs:
            return encs[0]
    except ImportError:
        return None
    except Exception:
        return None
    return None


def _demo_similarity(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """DEMO fallback similarity: compares downscaled luminance structure.

    Clearly NOT biometric verification. Returns 0-1.
    """
    a = cv2.resize(cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY), (64, 64)).astype(np.float32)
    b = cv2.resize(cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY), (64, 64)).astype(np.float32)
    a = (a - a.mean()) / (a.std() + 1e-6)
    b = (b - b.mean()) / (b.std() + 1e-6)
    corr = float(np.clip((a * b).mean(), -1, 1))
    # Normalize correlation from [-1,1] to [0,1]
    return round((corr + 1.0) / 2.0, 4)


def verify_faces(doc_face_img: np.ndarray, presented_img: np.ndarray) -> dict:
    """Compare document portrait vs presented face. Configurable thresholds."""
    det_doc = detect_faces(doc_face_img)
    det_pre = detect_faces(presented_img)

    if det_doc.count == 0 or det_pre.count == 0:
        which = "document" if det_doc.count == 0 else "presented"
        return {
            "match": False, "similarity": 0.0, "status": "NO_FACE",
            "faces_detected_document": det_doc.count,
            "faces_detected_presented": det_pre.count,
            "message": f"No face detected in the {which} image. Upload a clearer photo.",
            "demo_mode": False, "engine": "opencv",
        }
    if det_doc.count > 1 or det_pre.count > 1:
        return {
            "match": False, "similarity": 0.0, "status": "MULTIPLE_FACES",
            "faces_detected_document": det_doc.count,
            "faces_detected_presented": det_pre.count,
            "message": "Multiple faces detected - provide single-person images for reliable comparison.",
            "demo_mode": False, "engine": "opencv",
        }

    doc_crop = det_doc.largest_face_img
    pre_crop = det_pre.largest_face_img

    emb_a = _face_embedding(doc_crop)
    emb_b = _face_embedding(pre_crop)
    if emb_a is not None and emb_b is not None:
        similarity = round(1.0 - float(np.linalg.norm(emb_a - emb_b)) / 1.6, 4)
        similarity = float(np.clip(similarity, 0.0, 1.0))
        engine = "face_recognition"
        demo = False
    else:
        similarity = _demo_similarity(doc_crop, pre_crop)
        engine = "demo_structural"
        demo = True
        logger.warning("face_recognition unavailable - DEMO structural comparison used (clearly labeled).")

    t_match = settings.FACE_MATCH_THRESHOLD
    t_review = settings.FACE_REVIEW_THRESHOLD
    if similarity >= t_match:
        status = "MATCH"
    elif similarity >= t_review:
        status = "REVIEW"
    else:
        status = "MISMATCH"

    return {
        "match": status == "MATCH",
        "similarity": similarity,
        "status": status,
        "faces_detected_document": det_doc.count,
        "faces_detected_presented": det_pre.count,
        "quality_document": det_doc.quality,
        "quality_presented": det_pre.quality,
        "message": {
            "MATCH": "Presented face sufficiently matches the document portrait.",
            "REVIEW": "Similarity is inconclusive - manual review recommended.",
            "MISMATCH": "Presented face does not sufficiently match the document portrait.",
        }[status] + (" (DEMO comparison engine - not biometric verification)" if demo else ""),
        "demo_mode": demo,
        "engine": engine,
    }


def extract_document_face(file_path: str | Path) -> np.ndarray | None:
    """Load a document image and return the largest detected face crop (or None)."""
    from app.services.ocr_service import load_image
    try:
        img = load_image(file_path)
    except Exception:
        return None
    det = detect_faces(img)
    return det.largest_face_img