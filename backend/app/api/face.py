"""Face verification endpoints (document portrait vs presented face)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.document import Document
from app.models.screening import Screening
from app.models.user import User
from app.schemas.schemas import FaceVerifyResponse
from app.services.face_service import _decode_data_url, verify_faces
from app.utils.files import FileValidationError, validate_upload
from app.utils.logging_conf import get_logger

logger = get_logger("face")
router = APIRouter(prefix="/api/face", tags=["face"])


def _store_face_result(verification_id: str, payload: dict) -> None:
    out = Path(settings.PROCESSED_DIR) / f"face_{verification_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload))


@router.post("/verify", response_model=FaceVerifyResponse,
             summary="Verify presented face against document portrait")
def verify_face(
    verification_id: str = Form(...),
    image: UploadFile | None = File(default=None),
    image_data: str = Form(default=""),  # base64 data URL from camera capture
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.query(Screening).filter(Screening.verification_id == verification_id).first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Screening not found")
    doc = db.query(Document).get(s.document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    from app.services.face_service import extract_document_face
    doc_face = extract_document_face(doc.file_path)
    if doc_face is None:
        return FaceVerifyResponse(
            match=False, similarity=0.0, status="NO_FACE",
            faces_detected_document=0, faces_detected_presented=0,
            message="No face detected on the uploaded document. Cannot compare.",
        )

    presented = None
    if image is not None and image.filename:
        content = image.file.read()
        try:
            validate_upload(image.filename, content)
        except FileValidationError as e:
            raise HTTPException(e.status_code, e.message)
        import cv2
        import numpy as np
        arr = np.frombuffer(content, dtype=np.uint8)
        presented = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    elif image_data:
        presented = _decode_data_url(image_data)

    if presented is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Provide a face photo via 'image' file or base64 'image_data'.")

    res = verify_faces(doc_face, presented)
    _store_face_result(verification_id, res)
    logger.info("Face verify for %s: %s (%.2f)", verification_id, res["status"], res["similarity"])
    return FaceVerifyResponse(**res)


@router.get("/document-face/{verification_id}",
            summary="Check whether a portrait was detected on the document")
def document_face(verification_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    s = db.query(Screening).filter(Screening.verification_id == verification_id).first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Screening not found")
    doc = db.query(Document).get(s.document_id)
    from app.services.face_service import detect_faces
    from app.services.ocr_service import load_image
    try:
        img = load_image(doc.file_path)
        det = detect_faces(img)
        return {"faces_detected": det.count, "boxes": det.boxes, "quality": det.quality}
    except Exception:
        return {"faces_detected": 0, "boxes": [], "quality": 0.0}