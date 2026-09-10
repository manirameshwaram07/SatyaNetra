"""Pydantic v2 schemas for API requests/responses."""
from __future__ import annotations

from pydantic import BaseModel, Field


# --- Auth ---
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str


# --- Documents ---
class UploadResponse(BaseModel):
    document_id: int
    filename: str
    document_hash: str
    status: str = "uploaded"
    demo_mode: bool = False


class ClassifyResponse(BaseModel):
    document_type: str
    confidence: float


class ScreeningStartResponse(BaseModel):
    verification_id: str
    status: str


class StepStatus(BaseModel):
    name: str
    status: str  # PENDING / PROCESSING / COMPLETED / FAILED / SKIPPED
    detail: str = ""


class ScreeningStatusResponse(BaseModel):
    status: str
    progress: int
    current_step: str
    steps: list[StepStatus] = []


# --- Face ---
class FaceVerifyResponse(BaseModel):
    match: bool
    similarity: float
    status: str  # MATCH / REVIEW / MISMATCH / NO_FACE / FAILED
    faces_detected_document: int = 0
    faces_detected_presented: int = 0
    message: str = ""


# --- Alerts / Cases ---
class AlertOut(BaseModel):
    id: int
    screening_id: int
    verification_id: str | None = None
    severity: str
    category: str
    message: str
    status: str
    created_at: str | None = None


class AlertUpdate(BaseModel):
    status: str = Field(pattern="^(OPEN|ACKNOWLEDGED|RESOLVED)$")


class CaseCreate(BaseModel):
    screening_id: int
    title: str = Field(min_length=1, max_length=255)
    assigned_to: str = ""
    notes: str = ""


class CaseUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(OPEN|IN_PROGRESS|ESCALATED|RESOLVED)$")
    assigned_to: str | None = None
    notes: str | None = None
    title: str | None = None


class CaseOut(BaseModel):
    id: int
    screening_id: int
    verification_id: str | None = None
    title: str
    status: str
    assigned_to: str
    notes: str
    created_at: str | None = None
    updated_at: str | None = None


# --- Watchlist ---
class WatchlistCheckResponse(BaseModel):
    document_number: str
    found: bool
    status: str = "NOT_FOUND"
    source: str = "DEMO_WATCHLIST"
    details: dict = {}


# --- Dashboard ---
class DashboardStats(BaseModel):
    total_screenings: int
    high_risk: int
    medium_risk: int
    low_risk: int
    critical_risk: int = 0
    tampering_detections: int
    face_mismatches: int
    expired_documents: int
    avg_processing_ms: int
    demo_mode: bool


# --- Audit ---
class AuditVerifyResponse(BaseModel):
    verification_id: str
    chain_valid: bool
    records: list[dict] = []
    message: str = ""


# --- Health ---
class HealthResponse(BaseModel):
    status: str
    database: str
    demo_mode: bool
    version: str