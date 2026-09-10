# SATYANETRA

**See Beyond the Document. Verify the Identity.**

AI-Based Fake Identity & Document Screening System for Smart India Hackathon Problem Statement 26188.

A fully functional end-to-end application where an authorized operator uploads a passport / visa / ID / licence / permit image or PDF, and the Python backend runs a complete AI screening pipeline: OCR, document classification, MRZ analysis, field validation, tampering/forensics analysis, face detection & verification, watchlist check, identity consistency, weighted risk scoring, AI explanation, automated alerts, an audit hash-chain, and PDF report generation.

**The frontend is only the interface. All intelligence runs in the Python backend.**

---

## Quick start (Windows PowerShell)

### Backend

`powershell
cd backend
python -m venv venv
.env\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m app.seed          # creates tables + demo users + demo watchlist
python -m uvicorn app.main:app --reload --port 8000
`

### Frontend (second terminal)

`powershell
cd frontend
npm install
npm run dev
`

Then open http://localhost:5173 and log in with a demo account.

---

## Demo login credentials

| Username | Password    | Role              |
|----------|-------------|-------------------|
| admin    | Admin@123   | ADMIN             |
| officer  | Officer@123 | SECURITY_OFFICER  |
| analyst  | Analyst@123 | ANALYST           |

---

## API documentation

FastAPI auto-generates interactive docs at http://localhost:8000/docs (Swagger) and /redoc.

Key endpoints:

- POST /api/auth/login - JWT login
- POST /api/documents/upload - Upload document (JPG/PNG/WEBP/PDF)
- POST /api/screening/start/{document_id} - Run the full AI pipeline
- GET /api/screening/{verification_id}/status - Poll pipeline progress
- GET /api/screening/{verification_id}/result - Full result payload
- POST /api/face/verify - Face verification (file or camera capture)
- GET /api/dashboard/stats - Real database statistics
- GET /api/audit/{verification_id} - Audit hash chain verification
- GET /api/reports/{verification_id} - Download PDF report
- GET /health - Health check

---

## How the pipeline works

1. Upload -> file is validated (extension, MIME signature, size) and stored with SHA-256 hash
2. Document classification (OCR-content heuristics + optional manual hint)
3. OCR extraction (Tesseract -> Windows built-in WinRT OCR -> clearly-labeled DEMO fallback)
4. Field normalization + persistence
5. MRZ detection & parsing (TD3 passports, TD1 IDs) with check-digit verification
6. Deterministic document validation (required fields, dates, expiry, number format, MRZ consistency, duplicates)
7. Tampering / forensic analysis (ELA, noise inconsistency, metadata, copy-move, photo-region)
8. Face detection (OpenCV Haar cascades)
9. Watchlist check (DEMO local database - never a real government database)
10. Cross-document identity consistency
11. Weighted risk calculation (configurable weights)
12. AI explanation (Gemini via google-genai SDK, or rule-based fallback)
13. Automated alert generation
14. Audit hash-chain (SHA-256)
15. PDF report generation

---

## Demo scenarios

The seeded watchlist supports these demo scenarios:

- P1234567 -> VALID (genuine document, LOW RISK)
- P9999999 -> REPORTED (HIGH RISK - watchlist match)
- P8888888 -> EXPIRED (MEDIUM/HIGH RISK)
- P7777777 -> DUPLICATE (HIGH RISK)
- P6666666 -> SUSPICIOUS (HIGH RISK)

---

## Important disclaimers

- The watchlist is a locally seeded DEMO database. It is never a real government database.
- Forensic indicators are AI-assisted heuristics, not proof of forgery.
- Face verification uses face_recognition (dlib) if installed, otherwise a clearly-labeled structural comparison fallback.
- All results are probabilistic signals. Human review is the final authority for real-world security decisions.
- Uploaded documents are treated as sensitive. Configure DOCUMENT_RETENTION_HOURS for automatic cleanup.

---

## Technology stack

- Frontend: React + TypeScript + Vite + Tailwind CSS + React Router + Axios + Framer Motion + Recharts
- Backend: Python 3.11+ / FastAPI / SQLAlchemy / Pydantic
- Database: SQLite (default) / PostgreSQL-ready
- AI/CV: OpenCV, Pillow, PyMuPDF, pytesseract, WinRT OCR bridge, NumPy
- Security: JWT, PBKDF2-SHA256, CORS, file validation, audit logging
- Reporting: ReportLab PDF
- Optional AI: Google GenAI (google.genai SDK)

---

## Project structure

See the complete tree in the repository. Key directories:

- backend/app/services/ - all AI/analysis services
- backend/app/workers/ - screening pipeline orchestrator
- backend/app/api/ - REST API routers
- frontend/src/pages/ - all 12 UI pages
- frontend/src/services/api.ts - centralized API client
- storage/ - uploads, processed files, reports
