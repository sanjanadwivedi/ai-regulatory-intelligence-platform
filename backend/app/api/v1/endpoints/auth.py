from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel

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

@router.post("/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    user = db.query(EnterpriseUser).filter(EnterpriseUser.email == login_data.email).first()
    if user:
        if user.hashed_password and not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Incorrect email or password")
    else:
        # Auto-register new user with hashed password
        user = EnterpriseUser(
            full_name="Sanjana",
            role="Compliance Officer",
            email=login_data.email,
            hashed_password=get_password_hash(login_data.password)
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "full_name": user.full_name,
        "role": user.role
    }
