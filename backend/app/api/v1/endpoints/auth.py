from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, verify_password, get_password_hash
from app.models.domain import EnterpriseUser

router = APIRouter()

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
    role: str

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str
    role: str = "Compliance Officer"

@router.post("/login", response_model=TokenResponse)
def login(
    response: Response,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    OAuth2 compatible token login.
    Sets httpOnly cookie and returns access token.
    """
    user = db.query(EnterpriseUser).filter(EnterpriseUser.email == login_data.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Contact administrator or sign up for an account."
        )
    
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )

    # Set httpOnly cookie for secure session storage
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=(settings.ENVIRONMENT == "production"),
        samesite="lax",
        max_age=60 * 60 * 24
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "full_name": user.full_name,
        "role": user.role
    }


@router.post("/register", response_model=TokenResponse)
def register(
    response: Response,
    register_data: RegisterRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Explicit user registration endpoint.
    Creates account, hashes password, sets httpOnly cookie, and returns access token.
    """
    existing_user = db.query(EnterpriseUser).filter(EnterpriseUser.email == register_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    user = EnterpriseUser(
        full_name=register_data.full_name,
        role=register_data.role or "Compliance Officer",
        email=register_data.email,
        hashed_password=get_password_hash(register_data.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=(settings.ENVIRONMENT == "production"),
        samesite="lax",
        max_age=60 * 60 * 24
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "full_name": user.full_name,
        "role": user.role
    }


