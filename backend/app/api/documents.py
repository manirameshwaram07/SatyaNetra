"""Document upload / classification / listing endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.schemas import ClassifyResponse, UploadResponse
from app.services.document_classifier import DOC_TYPES, classify_document
from app.services.ocr_service import run_ocr
from app.utils.files import FileValidationError, save_upload, validate_upload
from app.utils.logging_conf import get_logger

logger = get_logger("documents")
router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse, summary="Upload a document (JPG/PNG/WEBP/PDF)")
def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(default=""),  # optional manual hint (demo fallback)
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    content = file.file.read()
    original = file.filename or "upload"
    try:
        ext, mime = validate_upload(original, content)
    except FileValidationError as e:
        logger.warning("Upload rejected: %s", e.message)
        raise HTTPException(e.status_code, e.message)
    path, doc_hash = save_upload(content, ext)
    hint = document_type if document_type in DOC_TYPES else ""
    doc = Document(
        document_type=hint or "UNKNOWN",
        original_filename=original,
        file_path=str(path),
        document_hash=doc_hash,
        file_size=len(content),
        mime_type=mime,
        processing_status="UPLOADED",
    )
    db.add(doc)
    db.commit()
    logger.info("Document stored: id=%s hash=%s…", doc.id, doc_hash[:12])
    return UploadResponse(
        document_id=doc.id,
        filename=original,
        document_hash=doc_hash,
        status="uploaded",
        demo_mode=settings.DEMO_MODE,
    )


@router.post("/classify", response_model=ClassifyResponse,
             summary="Classify a previously uploaded document")
def classify(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = db.query(Document).get(document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    ocr = run_ocr(doc.file_path)
    dtype, conf = classify_document(ocr.text)
    if dtype == "UNKNOWN" and doc.document_type != "UNKNOWN":
        dtype, conf = doc.document_type, 0.6
    doc.document_type = dtype
    db.commit()
    return ClassifyResponse(document_type=dtype, confidence=conf)


@router.get("", summary="List uploaded documents (metadata only)")
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    docs = db.query(Document).order_by(Document.id.desc()).limit(100).all()
    return [d.to_dict() for d in docs]


@router.get("/{document_id}", summary="Get one document's metadata")
def get_document(document_id: int, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    doc = db.query(Document).get(document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc.to_dict()