from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import datetime
from pydantic import BaseModel
from typing import List, Optional
from app.core.database import get_db
from app.core.security import get_current_user, get_current_organization, require_roles
from app.models.domain import EnterpriseProfile

router = APIRouter()

class EnterpriseProfileIn(BaseModel):
    organization_name: str
    industry_sector: str
    departments: Optional[List[str]] = []
    country: Optional[str] = None
    regulator_region: Optional[str] = None
    website_url: Optional[str] = None
    business_activities: Optional[List[str]] = []
    products_services: Optional[List[str]] = []
    licenses: Optional[List[str]] = []
    locations: Optional[List[str]] = []
    discovery_status: Optional[str] = "UNINITIALIZED"

class EnterpriseProfileOut(BaseModel):
    id: str
    organization_name: str
    industry_sector: str
    departments: Optional[List[str]] = []
    country: Optional[str] = None
    regulator_region: Optional[str] = None
    website_url: Optional[str] = None
    business_activities: Optional[List[str]] = []
    products_services: Optional[List[str]] = []
    licenses: Optional[List[str]] = []
    locations: Optional[List[str]] = []
    discovery_status: Optional[str] = "UNINITIALIZED"
    last_discovered_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True

from typing import Union, Dict, Any
@router.get("/profile", response_model=Union[EnterpriseProfileOut, Dict[str, Any]])
def get_profile(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    from app.core.security import get_current_organization_optional
    profile = get_current_organization_optional.__wrapped__(current_user, db) if hasattr(get_current_organization_optional, '__wrapped__') else get_current_organization_optional(current_user, db)
    
    if not profile:
        return {"onboarding_required": True, "message": "User is not mapped to any organization. Please start discovery."}
        
    return profile

@router.post("/profile", response_model=EnterpriseProfileOut)
def save_profile(
    profile_in: EnterpriseProfileIn,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["ADMIN", "COMPLIANCE_OFFICER"])),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """Upsert enterprise profile — creates if none exists, updates if one does."""
    profile = current_profile
    if profile:
        profile.organization_name = profile_in.organization_name
        profile.industry_sector = profile_in.industry_sector
        profile.departments = profile_in.departments
        profile.country = profile_in.country
        profile.regulator_region = profile_in.regulator_region
        if profile_in.website_url:
            profile.website_url = profile_in.website_url
        if profile_in.business_activities:
            profile.business_activities = profile_in.business_activities
        if profile_in.products_services:
            profile.products_services = profile_in.products_services
        if profile_in.licenses:
            profile.licenses = profile_in.licenses
        if profile_in.locations:
            profile.locations = profile_in.locations
        if profile_in.discovery_status:
            profile.discovery_status = profile_in.discovery_status
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
def list_users(
    db: Session = Depends(get_db),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    return db.query(EnterpriseUser).filter(EnterpriseUser.organization_id == current_profile.id).order_by(EnterpriseUser.created_at).all()

@router.post("/users", response_model=UserOut)
def create_user(
    user_in: UserIn, 
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(require_roles(["ADMIN"])),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    user = EnterpriseUser(**user_in.model_dump())
    user.organization_id = current_profile.id
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{user_id}", response_model=dict)
def delete_user(
    user_id: str, 
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(require_roles(["ADMIN"])),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    user = db.query(EnterpriseUser).filter(EnterpriseUser.id == user_id, EnterpriseUser.organization_id == current_profile.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": f"User '{user.full_name}' removed", "status": "SUCCESS"}
