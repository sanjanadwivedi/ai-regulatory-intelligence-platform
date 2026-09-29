import logging
from datetime import datetime, timedelta
from typing import Optional, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.domain import EnterpriseUser

logger = logging.getLogger("compliance_platform.security")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(subject: Any, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

from fastapi import Depends, HTTPException, status, Request

def get_current_user(
    request: Request = None,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme)
) -> EnterpriseUser:
    if not token and request and getattr(request, "cookies", None):
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing",
            headers={"WWW-Authenticate": "Bearer"}
        )


    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token payload",
                headers={"WWW-Authenticate": "Bearer"}
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.query(EnterpriseUser).filter(EnterpriseUser.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


def require_roles(allowed_roles: list[str]):
    """
    Dependency factory for Role-Based Access Control (RBAC).
    Normalizes roles (e.g. COMPLIANCE_OFFICER, ADMIN).
    """
    def role_checker(current_user: EnterpriseUser = Depends(get_current_user)) -> EnterpriseUser:
        user_role = (current_user.role or "").upper().replace(" ", "_")
        normalized_allowed = [r.upper().replace(" ", "_") for r in allowed_roles]
        if user_role not in normalized_allowed and "ADMIN" not in user_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of the following roles: {allowed_roles}"
            )
        return current_user
    return role_checker

from app.models.domain import EnterpriseProfile

def get_current_organization(
    current_user: EnterpriseUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> EnterpriseProfile:
    """
    Strictly resolves the multi-tenant identity.
    Fails closed if the user lacks a valid explicit organization mapping.
    """
    logger.debug("get_current_organization: User ID=%s, Org ID=%s", current_user.id, current_user.organization_id)
    if not current_user.organization_id:
        logger.debug("get_current_organization: failing because organization_id is None")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User identity is not mapped to an organization."
        )
    profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == current_user.organization_id).first()
    if not profile:
        logger.debug("get_current_organization: failing because profile not found for ID %s", current_user.organization_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User organization context is invalid."
        )
    logger.debug("get_current_organization: successfully resolved profile %s", profile.id)
    return profile



from typing import Optional

def get_current_organization_optional(
    current_user: EnterpriseUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Optional[EnterpriseProfile]:
    if not current_user.organization_id:
        return None
    profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == current_user.organization_id).first()
    return profile

