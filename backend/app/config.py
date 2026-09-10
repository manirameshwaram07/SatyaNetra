"""SatyaNetra application configuration (environment-driven)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
PROJECT_ROOT = BASE_DIR.parent  # satyanetra/
STORAGE_DIR = PROJECT_ROOT / "storage"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---
    APP_NAME: str = "SatyaNetra"
    APP_VERSION: str = "1.0.0"
    DATABASE_URL: str = "sqlite:///./satyanetra.db"
    SECRET_KEY: str = "change-this-secret-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    ALGORITHM: str = "HS256"

    # --- Behaviour ---
    DEMO_MODE: bool = True
    GEMINI_API_KEY: str = ""
    MAX_UPLOAD_SIZE_MB: int = 10
    DOCUMENT_RETENTION_HOURS: int = 24
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Risk engine (configurable weights, must sum ~1.0) ---
    RISK_WEIGHTS: str = (
        '{"validation":0.20,"tampering":0.25,"face":0.25,'
        '"watchlist":0.15,"identity":0.10,"ocr":0.05}'
    )

    # --- Face thresholds (configurable) ---
    FACE_MATCH_THRESHOLD: float = 0.85
    FACE_REVIEW_THRESHOLD: float = 0.65

    # --- OCR ---
    TESSERACT_CMD: str = ""

    # --- Risk band thresholds ---
    RISK_LOW_MAX: int = 29
    RISK_MEDIUM_MAX: int = 59
    RISK_HIGH_MAX: int = 79

    # --- Storage ---
    UPLOAD_DIR: str = str(STORAGE_DIR / "uploads")
    PROCESSED_DIR: str = str(STORAGE_DIR / "processed")
    REPORTS_DIR: str = str(STORAGE_DIR / "reports")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def risk_weights(self) -> dict[str, float]:
        try:
            w = json.loads(self.RISK_WEIGHTS)
            if isinstance(w, dict) and w:
                return w
        except Exception:  # pragma: no cover - defensive
            pass
        return {
            "validation": 0.20,
            "tampering": 0.25,
            "face": 0.25,
            "watchlist": 0.15,
            "identity": 0.10,
            "ocr": 0.05,
        }

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Ensure storage directories exist at import time (idempotent).
for _d in (settings.UPLOAD_DIR, settings.PROCESSED_DIR, settings.REPORTS_DIR):
    Path(_d).mkdir(parents=True, exist_ok=True)