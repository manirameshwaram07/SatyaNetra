"""Secure file upload validation: extension, MIME signature sniffing, size limits, safe naming."""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.config import settings

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "pdf"}

# Magic-byte signatures for allowed types
SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"%PDF-", "application/pdf"),
]


def _sniff_mime(head: bytes) -> str:
    for sig, mime in SIGNATURES:
        if head.startswith(sig):
            return mime
    # WEBP: RIFF....WEBP
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return ""


class FileValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def sanitize_filename(name: str) -> str:
    name = Path(name).name
    name = re.sub(r"[^A-Za-z0-9._\- ]", "_", name).strip()
    return name[:180] or "upload"


def validate_upload(filename: str, content: bytes) -> tuple[str, str]:
    """Validate an upload. Returns (safe_extension, sniffed_mime). Raises FileValidationError."""
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Unsupported file type '.{ext}'. Allowed: JPG, JPEG, PNG, WEBP, PDF.", 400
        )
    if len(content) == 0:
        raise FileValidationError("Uploaded file is empty.", 400)
    if len(content) > settings.max_upload_bytes:
        raise FileValidationError(
            f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB} MB.", 413
        )
    mime = _sniff_mime(content[:16])
    if not mime:
        raise FileValidationError(
            "File content does not match a supported image/PDF format (possible spoofed extension).",
            400,
        )
    # Cross-check extension vs content
    ext_mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "webp": "image/webp", "pdf": "application/pdf"}[ext]
    if mime != ext_mime:
        # jpg/jpeg interchangeable
        if not (mime == "image/jpeg" and ext in {"jpg", "jpeg"}):
            raise FileValidationError(
                f"File extension '.{ext}' does not match detected content type '{mime}'.", 400
            )
    return ext, mime


def save_upload(content: bytes, ext: str) -> tuple[Path, str]:
    """Persist bytes under storage/uploads with an unguessable name. Returns (path, sha256_hex)."""
    import hashlib

    doc_hash = hashlib.sha256(content).hexdigest()
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    dest = Path(settings.UPLOAD_DIR) / stored_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return dest, doc_hash