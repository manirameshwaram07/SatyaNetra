"""SatyaNetra FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (alerts, audit, auth, cases, dashboard, documents, face, screening)
from app.config import settings
from app.database import Base, check_database, engine
from app.utils.logging_conf import get_logger, setup_logging

setup_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (idempotent). Seeding is separate: python -m app.seed
    Base.metadata.create_all(bind=engine)
    logger.info("SatyaNetra startup complete (demo_mode=%s)", settings.DEMO_MODE)
    yield
    logger.info("SatyaNetra shutdown")


app = FastAPI(
    title="SatyaNetra API",
    description="AI-Based Fake Identity & Document Screening System - SIH 26188. "
                "All screening intelligence runs in this backend.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(screening.router)
app.include_router(face.router)
app.include_router(alerts.router)
app.include_router(cases.router)
app.include_router(dashboard.router)
app.include_router(audit.router)


@app.get("/health", tags=["health"], summary="Health check")
def health():
    return {
        "status": "ok",
        "database": "connected" if check_database() else "disconnected",
        "demo_mode": settings.DEMO_MODE,
        "version": settings.APP_VERSION,
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s: %s", request.url.path, type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})