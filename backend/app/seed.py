"""Database initialization & demo seeding. Run: python -m app.seed

Creates tables, a demo admin account, and the DEMO watchlist records.
"""
from __future__ import annotations

from app.database import Base, SessionLocal, engine
from app.models import User, UserRole, WatchlistEntry
from app.utils.logging_conf import get_logger, setup_logging
from app.utils.security import hash_password

setup_logging()
logger = get_logger("seed")

DEMO_USERS = [
    {"username": "admin", "email": "admin@satyanetra.local",
     "password": "Admin@123", "role": UserRole.ADMIN},
    {"username": "officer", "email": "officer@satyanetra.local",
     "password": "Officer@123", "role": UserRole.SECURITY_OFFICER},
    {"username": "analyst", "email": "analyst@satyanetra.local",
     "password": "Analyst@123", "role": UserRole.ANALYST},
]

# DEMO WATCHLIST - locally seeded records ONLY. Never a real government database.
DEMO_WATCHLIST = [
    {"document_number": "P1234567", "name": "ARJUN SHARMA", "nationality": "IND",
     "date_of_birth": "12/05/1995", "status": "VALID",
     "notes": "Demo record - genuine document scenario."},
    {"document_number": "P9999999", "name": "Vikram RAO", "nationality": "IND",
     "date_of_birth": "03/11/1988", "status": "REPORTED",
     "notes": "Demo record - reported lost/stolen in demo dataset."},
    {"document_number": "P8888888", "name": "MEERA IYER", "nationality": "IND",
     "date_of_birth": "22/07/1992", "status": "EXPIRED",
     "notes": "Demo record - expired document scenario."},
    {"document_number": "P7777777", "name": "RAKESH VERMA", "nationality": "IND",
     "date_of_birth": "14/02/1990", "status": "DUPLICATE",
     "notes": "Demo record - duplicate submission detected in demo dataset."},
    {"document_number": "P6666666", "name": "SUNITA NAIR", "nationality": "IND",
     "date_of_birth": "30/09/1994", "status": "SUSPICIOUS",
     "notes": "Demo record - suspicious pattern flagged in demo dataset."},
    {"document_number": "ABCPD1234F", "name": "RAHUL KUMAR", "nationality": "IND",
     "date_of_birth": "12/04/2002", "status": "VALID",
     "notes": "Demo PAN-style record."},
    {"document_number": "KA0120220001234", "name": "PRIYA DESAI", "nationality": "IND",
     "date_of_birth": "05/06/1997", "status": "VALID",
     "notes": "Demo driving-licence-style record."},
]


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for u in DEMO_USERS:
            existing = db.query(User).filter(User.username == u["username"]).first()
            if existing is None:
                db.add(User(username=u["username"], email=u["email"],
                            password_hash=hash_password(u["password"]), role=u["role"]))
                logger.info("Seeded user: %s", u["username"])
        for w in DEMO_WATCHLIST:
            existing = db.query(WatchlistEntry).filter(
                WatchlistEntry.document_number == w["document_number"]).first()
            if existing is None:
                db.add(WatchlistEntry(**w))
                logger.info("Seeded watchlist: %s (%s)", w["document_number"], w["status"])
        db.commit()
        logger.info("Database initialization complete.")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("SatyaNetra database initialized.")
    print("Demo logins: admin/Admin@123, officer/Officer@123, analyst/Analyst@123")