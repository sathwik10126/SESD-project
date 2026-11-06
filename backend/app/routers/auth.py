import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from google.auth.exceptions import TransportError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas import AuthResponse, GoogleLoginRequest, LoginRequest, RegisterRequest, UserResponse

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

router = APIRouter(prefix="/auth", tags=["Authentication"])


def public_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        name=user.full_name,
        email=user.email,
        role=user.role,
    )


def auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.id, user.role),
        user=public_user(user),
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    email = str(data.email).lower().strip()

    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        full_name=data.full_name.strip(),
        email=email,
        password_hash=hash_password(data.password),
        google_id=None,
        role="student",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    email = str(data.email).lower().strip()
    user = db.scalar(select(User).where(User.email == email))

    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.role != data.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This account is registered as {user.role}. Please select {user.role} to continue.",
        )

    return auth_response(user)


@router.post("/login/form", response_model=AuthResponse)
def login_form(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return login(LoginRequest(email=form_data.username, password=form_data.password), db=db)


@router.post("/google", response_model=AuthResponse)
def google_login(data: GoogleLoginRequest, db: Session = Depends(get_db)):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google login is not configured on the server",
        )

    try:
        google_user = id_token.verify_oauth2_token(
            data.credential,
            google_requests.Request(),
            client_id,
        )
    except TransportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google verification service is temporarily unavailable",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or incorrectly configured Google credential",
        )

    if google_user.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token issuer",
        )

    if google_user.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email has not been verified",
        )

    google_sub = google_user.get("sub")
    email = str(google_user.get("email") or "").lower().strip()
    full_name = str(google_user.get("name") or email.split("@", 1)[0]).strip()

    if not google_sub or not email or not full_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google credential is missing required account information",
        )

    # 1. Check if user already exists by google_id
    user = db.scalar(select(User).where(User.google_id == google_sub))
    if user is not None:
        return auth_response(user)

    # 2. Check if user already exists by email
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        if user.google_id and user.google_id != google_sub:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is linked to a different Google account",
            )
        user.google_id = google_sub
        db.commit()
        db.refresh(user)
        return auth_response(user)

    # 3. Create new student user with Google credentials
    user = User(
        full_name=full_name,
        email=email,
        password_hash=None,
        google_id=google_sub,
        role="student",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return auth_response(user)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return public_user(current_user)
