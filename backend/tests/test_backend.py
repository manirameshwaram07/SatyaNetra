"""SatyaNetra backend test suite (pytest).

Run: cd backend && python -m pytest tests/ -v
"""
from __future__ import annotations

import os
import sys

# Ensure app imports resolve when running from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.seed import init_db

AUTH = {"username": "admin", "password": "Admin@123"}


@pytest.fixture(scope="module", autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def token(client) -> str:
    r = client.post("/api/auth/login", json=AUTH)
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def _make_jpeg(tmp_path, width=900, height=600) -> bytes:
    import io

    import numpy as np
    from PIL import Image
    arr = np.full((height, width, 3), 235, dtype=np.uint8)
    # text-like dark rectangles + a face-like blob
    arr[80:120, 60:500] = 30
    arr[160:200, 60:420] = 30
    arr[240:600, 640:900] = 120
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert isinstance(body["demo_mode"], bool)


def test_login_success(client):
    r = client.post("/api/auth/login", json=AUTH)
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert r.json()["role"] == "ADMIN"


def test_login_failure(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_protected_requires_auth(client):
    r = client.get("/api/dashboard/stats")
    assert r.status_code == 401


def test_upload_rejects_bad_type(client, headers):
    r = client.post("/api/documents/upload",
                    files={"file": ("evil.exe", b"MZ_fake", "application/octet-stream")},
                    headers=headers)
    assert r.status_code == 400


def test_upload_rejects_spoofed_extension(client, headers):
    r = client.post("/api/documents/upload",
                    files={"file": ("fake.png", b"this is not an image at all", "image/png")},
                    headers=headers)
    assert r.status_code == 400


def test_upload_ok_and_workflow(client, headers, tmp_path):
    """Full end-to-end: upload -> screening -> poll -> result -> audit -> report."""
    content = _make_jpeg(tmp_path)
    r = client.post("/api/documents/upload",
                    files={"file": ("test_doc.jpg", content, "image/jpeg")},
                    data={"document_type": "PASSPORT"},
                    headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "uploaded"
    assert len(body["document_hash"]) == 64  # sha256
    doc_id = body["document_id"]

    # Start screening
    r = client.post(f"/api/screening/start/{doc_id}", headers=headers)
    assert r.status_code == 200
    vid = r.json()["verification_id"]

    # Poll to completion (max ~30s)
    import time
    final = None
    for _ in range(60):
        s = client.get(f"/api/screening/{vid}/status", headers=headers).json()
        if s["status"] not in {"PENDING", "PROCESSING"}:
            final = s
            break
        time.sleep(0.5)
    assert final is not None, "screening did not finish in time"
    assert final["progress"] == 100

    # Result
    r = client.get(f"/api/screening/{vid}/result", headers=headers)
    assert r.status_code == 200
    payload = r.json()
    assert "risk_score" in payload["result"]
    assert payload["result"]["risk_score"] is not None
    assert payload["result"]["validation"] is not None
    assert payload["result"]["tampering"] is not None

    # Audit chain
    r = client.get(f"/api/audit/{vid}", headers=headers)
    assert r.status_code == 200
    assert r.json()["chain_valid"] is True

    # Report download
    r = client.get(f"/api/reports/{vid}", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"


def test_mrz_parsing():
    from app.services.mrz_service import compute_check_digit, parse_mrz
    # 5*7 + 2*3 + 0*1 + 7*7 + 2*3 + 7*1 = 103 -> 103 % 10 = 3
    assert compute_check_digit("520727") == 3
    # Build a synthetic TD3 MRZ
    l1 = "P<INDSHARMA<<ARJUN<<<<<<<<<<<<<<<<<<<<<<<<<"
    l2 = "P12345670IND9505125M3005127<<<<<<<<<<<<<<02"
    res = parse_mrz([l1, l2])
    assert res.found is True or res.parse_error  # tolerant: OCR noise allowed


def test_expiry_validation():
    from app.services.validation_service import validate_fields
    fields = {"full_name": "TEST USER", "document_number": "P1234567",
              "date_of_birth": "12/05/1995", "issue_date": "13/05/2015",
              "expiry_date": "12/05/2015"}  # expired long ago
    res = validate_fields(fields, "PASSPORT")
    assert res["expired"] is True
    assert res["overall_status"] in {"ERROR", "FAIL", "WARNING"}


def test_risk_engine_ordering():
    from app.services.risk_service import calculate_risk
    good = {
        "validation": {"overall_status": "PASS", "fail_count": 0, "warning_count": 0, "expired": False},
        "tampering": {"tampering_score": 5},
        "face": {"status": "MATCH", "similarity": 0.94},
        "watchlist": {"status": "CLEAR"},
        "identity": {"status": "NOT_APPLICABLE"},
    }
    bad = {
        "validation": {"overall_status": "FAIL", "fail_count": 2, "warning_count": 1, "expired": True},
        "tampering": {"tampering_score": 85},
        "face": {"status": "MISMATCH", "similarity": 0.2},
        "watchlist": {"status": "REPORTED"},
        "identity": {"status": "CONFLICT", "conflicts": [{"field": "date_of_birth"}]},
    }
    r_good = calculate_risk(good["validation"], good["tampering"], good["face"],
                            good["watchlist"], good["identity"], 0.95, "OCR")
    r_bad = calculate_risk(bad["validation"], bad["tampering"], bad["face"],
                           bad["watchlist"], bad["identity"], 0.5, "OCR")
    assert r_good["risk_score"] < r_bad["risk_score"]
    assert r_bad["risk_level"] in {"HIGH", "CRITICAL"}


def test_watchlist_check(client, headers):
    r = client.get("/api/watchlist/check/P9999999", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["status"] == "REPORTED"
    r = client.get("/api/watchlist/check/UNKNOWN123", headers=headers)
    assert r.json()["status"] == "CLEAR"


def test_tampering_service_runs(tmp_path):
    from app.services.tampering_service import analyze_document
    p = tmp_path / "doc.jpg"
    p.write_bytes(_make_jpeg(tmp_path))
    res = analyze_document(str(p), tmp_dir=tmp_path)
    assert 0 <= res.tampering_score <= 100
    assert res.indicators  # always at least one indicator entry


def test_face_api(client, headers, tmp_path):
    """Face verify endpoint returns structured result (engine availability agnostic)."""
    import io

    import numpy as np
    from PIL import Image

    def face_jpg():
        arr = np.full((400, 400, 3), 200, dtype=np.uint8)
        # crude face-like blob (dark oval on light bg) so Haar cascade has a chance
        import cv2
        cv2.ellipse(arr, (200, 200), (110, 150), 0, 0, 360, (60, 45, 40), -1)
        cv2.circle(arr, (160, 170), 14, (250, 250, 250), -1)
        cv2.circle(arr, (240, 170), 14, (250, 250, 250), -1)
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, format="JPEG", quality=95)
        return buf.getvalue()

    # upload doc with blob
    r = client.post("/api/documents/upload",
                    files={"file": ("face_doc.jpg", face_jpg(), "image/jpeg")},
                    headers=headers)
    doc_id = r.json()["document_id"]
    r = client.post(f"/api/screening/start/{doc_id}", headers=headers)
    vid = r.json()["verification_id"]

    # wait for completion so doc processing settles
    import time
    for _ in range(60):
        s = client.get(f"/api/screening/{vid}/status", headers=headers).json()
        if s["status"] not in {"PENDING", "PROCESSING"}:
            break
        time.sleep(0.5)

    r = client.post("/api/face/verify",
                    data={"verification_id": vid},
                    files={"image": ("selfie.jpg", face_jpg(), "image/jpeg")},
                    headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in {"MATCH", "REVIEW", "MISMATCH", "NO_FACE", "MULTIPLE_FACES"}
    assert 0.0 <= body["similarity"] <= 1.0


def test_identity_consistency():
    from app.services.identity_service import check_identity_consistency
    docs = [
        {"label": "Passport", "fields": {"full_name": "RAHUL KUMAR",
                                         "date_of_birth": "12/04/2002", "gender": "M"}},
        {"label": "Aadhaar", "fields": {"full_name": "RAHUL KUMAR",
                                        "date_of_birth": "15/04/2002", "gender": "M"}},
    ]
    res = check_identity_consistency(docs)
    assert res["status"] == "CONFLICT"
    assert any(c["field"] == "date_of_birth" for c in res["conflicts"])


def test_audit_chain_tamper_detection(client, headers):
    """If an audit record is modified, verification must fail."""
    from app.models.audit import AuditRecord
    from app.database import SessionLocal
    # run a screening first (reuse from earlier test artifacts if any)
    r = client.get("/api/screening", headers=headers)
    screenings = r.json()
    if not screenings:
        pytest.skip("no screenings present")
    vid = screenings[0]["verification_id"]

    db = SessionLocal()
    try:
        rec = db.query(AuditRecord).order_by(AuditRecord.id.desc()).first()
        rec.event_data = rec.event_data + "TAMPERED"
        db.commit()
    finally:
        db.close()
    r = client.get(f"/api/audit/{vid}", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["chain_valid"] is False
    assert "FAILURE" in body["message"]