from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import datetime
from pydantic import BaseModel
from typing import List, Optional
from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.domain import EnterpriseProfile

router = APIRouter()

class EnterpriseProfileIn(BaseModel):
    organization_name: str
    industry_sector: str
    departments: Optional[List[str]] = []
    country: Optional[str] = None
    regulator_region: Optional[str] = None

class EnterpriseProfileOut(BaseModel):
    id: str
    organization_name: str
    industry_sector: str
    departments: Optional[List[str]] = []
    country: Optional[str] = None
    regulator_region: Optional[str] = None
    updated_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True

@router.get("/profile", response_model=EnterpriseProfileOut)
def get_profile(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    profile = db.query(EnterpriseProfile).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No enterprise profile configured yet")
    return profile

@router.post("/profile", response_model=EnterpriseProfileOut)
def save_profile(
    profile_in: EnterpriseProfileIn,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["ADMIN", "COMPLIANCE_OFFICER"]))
):

    """Upsert enterprise profile — creates if none exists, updates if one does."""
    profile = db.query(EnterpriseProfile).first()
    if profile:
        profile.organization_name = profile_in.organization_name
        profile.industry_sector = profile_in.industry_sector
        profile.departments = profile_in.departments
        profile.country = profile_in.country
        profile.regulator_region = profile_in.regulator_region
        profile.updated_at = datetime.datetime.utcnow()
    else:
        profile = EnterpriseProfile(**profile_in.model_dump())
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


# ---- User Management ----

class UserIn(BaseModel):
    full_name: str
    role: str
    email: Optional[str] = None

class UserOut(BaseModel):
    id: str
    full_name: str
    role: str
    email: Optional[str] = None
    created_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True

from app.models.domain import EnterpriseUser

@router.get("/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(EnterpriseUser).order_by(EnterpriseUser.created_at).all()

@router.post("/users", response_model=UserOut)
def create_user(user_in: UserIn, db: Session = Depends(get_db)):
    user = EnterpriseUser(**user_in.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{user_id}", response_model=dict)
def delete_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(EnterpriseUser).filter(EnterpriseUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": f"User '{user.full_name}' removed", "status": "SUCCESS"}
