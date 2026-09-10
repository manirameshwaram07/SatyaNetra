"""Authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.schemas import LoginRequest, TokenResponse, UserOut
from app.utils.security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, summary="Login and receive a JWT")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    token = create_access_token(subject=user.username, role=user.role.value)
    return TokenResponse(access_token=token, username=user.username, role=user.role.value)


@router.get("/me", response_model=UserOut, summary="Get current authenticated user")
def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, username=user.username, email=user.email, role=user.role.value)