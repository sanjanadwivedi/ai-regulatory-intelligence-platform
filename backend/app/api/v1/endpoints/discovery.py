import logging
import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles, get_current_organization
from app.models.domain import EnterpriseProfile, DiscoveredFact, AuditLog, DiscoveryRun
from app.services.discovery_crawler import PoliteDiscoveryCrawler, DiscoveredPage
from app.services.fact_extractor import FactExtractor, ExtractedFactCandidate

logger = logging.getLogger("compliance_platform.discovery_api")
router = APIRouter()

# ─── Pydantic Schemas ───────────────────────────────────────────────────────────

class DiscoveryStartRequest(BaseModel):
    website_url: str

class DiscoveredFactOut(BaseModel):
    id: str
    organization_id: Optional[str] = None
    fact_type: str
    fact_value: str
    source_url: str
    source_title: Optional[str] = None
    source_tier: int = 2
    snippet: str
    extraction_method: str
    confidence: float
    status: str
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class ManualFactCreate(BaseModel):
    fact_type: str
    fact_value: str
    source_url: Optional[str] = None
    snippet: Optional[str] = None
    provenance_type: str = "USER_ATTESTATION"
    confidence_score: float = 1.0

class FactEditRequest(BaseModel):
    fact_value: str

class BulkConfirmRequest(BaseModel):
    min_confidence: Optional[float] = 0.85

class DiscoveryStatusOut(BaseModel):
    discovery_status: str
    website_url: Optional[str] = None
    total_facts: int
    pending_count: int
    confirmed_count: int
    rejected_count: int
    last_discovered_at: Optional[datetime.datetime] = None

# ─── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/start", response_model=Dict[str, Any])
def start_discovery(
    req: DiscoveryStartRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Initiate automated corporate discovery: crawl domain, extract structured facts with evidence,
    and stage them as PENDING for compliance officer review.
    """
    from app.core.security import get_current_organization_optional
    profile = get_current_organization_optional.__wrapped__(current_user, db) if hasattr(get_current_organization_optional, '__wrapped__') else get_current_organization_optional(current_user, db)

    if not req.website_url or not req.website_url.strip():
        raise HTTPException(status_code=400, detail="Website URL or domain is required.")

    crawler = PoliteDiscoveryCrawler(max_pages=10, delay_seconds=0.3)
    canonical_url, root_domain = crawler.normalize_url(req.website_url)

    logger.info("Starting discovery on: %s (%s)", canonical_url, root_domain)

    # 1. Crawl pages
    crawl_result = crawler.crawl_website(canonical_url)
    pages = crawl_result.pages

    if hasattr(crawl_result, 'failure_reason') and crawl_result.failure_reason:
        raise HTTPException(
            status_code=422,
            detail={"status": "FAILED", "reason": crawl_result.failure_reason}
        )

    # 2. Extract candidate facts
    candidates = FactExtractor.extract_from_pages(pages, root_domain)

    if not candidates:
        raise HTTPException(
            status_code=422, 
            detail={"status": "FAILED", "reason": "INSUFFICIENT_PUBLIC_INFORMATION"}
        )

    # 3. Get or initialize enterprise profile
    if not profile:
        profile = EnterpriseProfile(
            organization_name=candidates[0].fact_value if candidates and candidates[0].fact_type == "COMPANY" else "Unknown Organization",
            industry_sector="Unknown",
            departments=[],
            country="",
            discovery_status="REVIEW_PENDING",
            website_url=canonical_url,
            last_discovered_at=datetime.datetime.utcnow()
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        # Update user's organization immediately as per Phase 15B
        current_user.organization_id = profile.id
        db.commit()
        db.refresh(current_user)
    else:
        profile.website_url = canonical_url
        profile.discovery_status = "REVIEW_PENDING"
        profile.last_discovered_at = datetime.datetime.utcnow()
        db.commit()

    run = DiscoveryRun(
        organization_id=profile.id,
        website_url=canonical_url,
        root_domain=root_domain,
        status="REVIEW_PENDING" if candidates else "FAILED",
        started_at=datetime.datetime.utcnow(),
        completed_at=datetime.datetime.utcnow() if candidates else None
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # 4. Clear previous pending facts and persist newly extracted facts
    db.query(DiscoveredFact).filter(
        DiscoveredFact.organization_id == profile.id,
        DiscoveredFact.status == "PENDING"
    ).delete(synchronize_session=False)

    saved_facts = []
    for cand in candidates:
        fact = DiscoveredFact(
            organization_id=profile.id,
            discovery_run_id=run.id,
            fact_type=cand.fact_type,
            fact_value=cand.fact_value,
            source_url=cand.source_url,
            source_title=cand.source_title,
            source_tier=cand.source_tier,
            snippet=cand.snippet,
            extraction_method=cand.extraction_method,
            confidence=cand.confidence,
            status="PENDING"
        )
        db.add(fact)
        saved_facts.append(fact)

    # 5. Log audit trail
    user_name = getattr(current_user, "full_name", "Compliance Officer")
    audit = AuditLog(
        organization_id=profile.id,
        user_name=user_name,
        user_role="Compliance Officer",
        action="DISCOVERY_STARTED",
        target_type="ENTERPRISE_PROFILE",
        target_id=profile.id,
        details={
            "website_url": canonical_url,
            "crawled_pages": len(pages),
            "discovered_facts": len(saved_facts),
            "discovery_run_id": run.id
        }
    )
    db.add(audit)
    db.commit()

    return {
        "status": "SUCCESS",
        "message": f"Discovered {len(saved_facts)} candidate facts from {len(pages)} pages on {root_domain}.",
        "website_url": canonical_url,
        "facts_count": len(saved_facts),
        "profile_id": profile.id,
        "discovery_run_id": run.id
    }


@router.post("/facts/manual", response_model=DiscoveredFactOut)
def add_manual_fact(
    req: ManualFactCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    from app.models.domain import AuditLog
    if not req.fact_value.strip():
        raise HTTPException(status_code=400, detail="Fact value cannot be empty")
        
    valid_types = {"BUSINESS_ACTIVITY", "REGION", "SECTOR", "REVENUE", "EMPLOYEES", "COMPANY", "PRODUCTS", "SERVICES", "JURISDICTION", "LOCATION"}
    if req.fact_type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid fact type")
        
    if req.source_url and not req.source_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid source URL")

    existing = db.query(DiscoveredFact).filter(
        DiscoveredFact.organization_id == current_profile.id,
        DiscoveredFact.fact_type == req.fact_type,
        DiscoveredFact.fact_value == req.fact_value
    ).first()
    
    if existing:
        raise HTTPException(status_code=409, detail="Duplicate")
        
    fact = DiscoveredFact(
        organization_id=current_profile.id,
        fact_type=req.fact_type,
        fact_value=req.fact_value,
        source_url=req.source_url if req.source_url else "User Attestation",
        snippet=req.snippet if req.snippet else "Manual user attestation.",
        extraction_method="USER_PROVIDED",
        confidence=req.confidence_score,
        status="CONFIRMED",
        evidence_type="USER_ATTESTATION",
        evidence_strength="ATTESTED"
    )
    db.add(fact)
    
    if req.fact_type == "BUSINESS_ACTIVITY":
        if current_profile.business_activities:
            if req.fact_value not in current_profile.business_activities:
                current_profile.business_activities = current_profile.business_activities + [req.fact_value]
        else:
            current_profile.business_activities = [req.fact_value]
            
    db.commit()
    db.refresh(fact)
    
    audit = AuditLog(
        organization_id=current_profile.id,
        user_name=current_user.full_name,
        user_role=current_user.role,
        action="MANUAL_FACT_ADDED",
        target_type="DISCOVERED_FACT",
        target_id=fact.id,
        details={"fact_type": fact.fact_type, "fact_value": fact.fact_value}
    )
    db.add(audit)
    db.commit()
    
    return fact

@router.delete("/facts/{fact_id}", response_model=Dict[str, Any])
def delete_fact(
    fact_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    from app.models.domain import AuditLog
    fact = db.query(DiscoveredFact).filter(
        DiscoveredFact.id == fact_id,
        DiscoveredFact.organization_id == current_profile.id
    ).first()
    
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
        
    if fact.fact_type == "BUSINESS_ACTIVITY" and current_profile.business_activities:
        if fact.fact_value in current_profile.business_activities:
            acts = list(current_profile.business_activities)
            acts.remove(fact.fact_value)
            current_profile.business_activities = acts
            
    db.delete(fact)
    
    audit = AuditLog(
        organization_id=current_profile.id,
        user_name=current_user.full_name,
        user_role=current_user.role,
        action="FACT_DELETED",
        target_type="DISCOVERED_FACT",
        target_id=fact.id,
        details={"fact_type": fact.fact_type}
    )
    db.add(audit)
    db.commit()
    
    return {"status": "SUCCESS"}

@router.get("/facts", response_model=List[DiscoveredFactOut])
def get_discovered_facts(
    status: Optional[str] = Query("ALL", description="Filter by status: PENDING, CONFIRMED, REJECTED, ALL"),
    fact_type: Optional[str] = Query("ALL", description="Filter by fact type"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Retrieve discovered facts with optional status and category filters."""
    from app.core.security import get_current_organization_optional
    profile = get_current_organization_optional.__wrapped__(current_user, db) if hasattr(get_current_organization_optional, '__wrapped__') else get_current_organization_optional(current_user, db)

    query = db.query(DiscoveredFact)
    if profile:
        query = query.filter(DiscoveredFact.organization_id == profile.id)
    else:
        return []

    if status and status.upper() != "ALL":
        query = query.filter(DiscoveredFact.status == status.upper())

    if fact_type and fact_type.upper() != "ALL":
        query = query.filter(DiscoveredFact.fact_type == fact_type.upper())

    return query.order_by(DiscoveredFact.confidence.desc()).all()

@router.post("/facts/{fact_id}/confirm", response_model=DiscoveredFactOut)
def confirm_fact(
    fact_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """Confirm a candidate fact as valid organizational context."""
    fact = db.query(DiscoveredFact).filter(
        DiscoveredFact.id == fact_id,
        DiscoveredFact.organization_id == current_profile.id
    ).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Discovered fact not found.")

    fact.status = "CONFIRMED"
    fact.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(fact)
    return fact

@router.put("/facts/{fact_id}/edit", response_model=DiscoveredFactOut)
def edit_fact(
    fact_id: str,
    req: FactEditRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """Edit and confirm a candidate fact value."""
    fact = db.query(DiscoveredFact).filter(
        DiscoveredFact.id == fact_id,
        DiscoveredFact.organization_id == current_profile.id
    ).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Discovered fact not found.")

    fact.fact_value = req.fact_value.strip()
    fact.status = "CONFIRMED"
    fact.extraction_method = "USER_EDITED"
    fact.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(fact)
    return fact

@router.post("/facts/{fact_id}/reject", response_model=DiscoveredFactOut)
def reject_fact(
    fact_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """Reject a discovered fact so it is not included in the organizational profile."""
    fact = db.query(DiscoveredFact).filter(
        DiscoveredFact.id == fact_id,
        DiscoveredFact.organization_id == current_profile.id
    ).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Discovered fact not found.")

    fact.status = "REJECTED"
    fact.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(fact)
    return fact

@router.post("/facts/bulk-confirm", response_model=Dict[str, Any])
def bulk_confirm_facts(
    req: BulkConfirmRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """Bulk-confirm all high-confidence candidate facts."""
    min_conf = req.min_confidence or 0.85
    facts = db.query(DiscoveredFact).filter(
        DiscoveredFact.organization_id == current_profile.id,
        DiscoveredFact.status == "PENDING",
        DiscoveredFact.confidence >= min_conf
    ).all()

    for f in facts:
        f.status = "CONFIRMED"
        f.updated_at = datetime.datetime.utcnow()

    db.commit()
    return {
        "status": "SUCCESS",
        "confirmed_count": len(facts),
        "min_confidence": min_conf
    }

@router.post("/finalize", response_model=Dict[str, Any])
def finalize_discovery(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Finalize organizational context from all CONFIRMED facts.
    Synchronizes EnterpriseProfile with verified departments, activities, products, and licenses.
    """
    from app.core.security import get_current_organization_optional
    profile = get_current_organization_optional.__wrapped__(current_user, db) if hasattr(get_current_organization_optional, '__wrapped__') else get_current_organization_optional(current_user, db)

    # 1. We must have a profile context if facts were discovered for this user.
    if not profile:
        # Create a new profile and bind it to the current user
        profile = EnterpriseProfile(
            organization_name="Unknown Organization",
            industry_sector="Unknown",
            country=""
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        current_user.organization_id = profile.id
        db.commit()
        db.refresh(current_user)

    confirmed_facts = db.query(DiscoveredFact).filter(
        DiscoveredFact.organization_id == profile.id,
        DiscoveredFact.status == "CONFIRMED"
    ).all()

    if not confirmed_facts:
        raise HTTPException(status_code=400, detail="No confirmed facts found to finalize profile.")

    # Aggregate facts by type
    company_name = next((f.fact_value for f in confirmed_facts if f.fact_type == "COMPANY"), None)
    activities = [f.fact_value for f in confirmed_facts if f.fact_type == "BUSINESS_ACTIVITY"]
    products = [f.fact_value for f in confirmed_facts if f.fact_type == "PRODUCT_SERVICE"]
    locations = [f.fact_value for f in confirmed_facts if f.fact_type == "LOCATION"]
    departments = [f.fact_value for f in confirmed_facts if f.fact_type == "DEPARTMENT"]
    licenses = [f.fact_value for f in confirmed_facts if f.fact_type == "LICENSE"]

    if company_name:
        profile.organization_name = company_name
    if activities:
        profile.business_activities = activities
    if products:
        profile.products_services = products
    if locations:
        profile.locations = locations
        profile.country = locations[0]
    if departments:
        # Merge with existing departments without duplicates
        existing_depts = profile.departments or []
        combined_depts = list(dict.fromkeys(departments + existing_depts))
        profile.departments = combined_depts
    if licenses:
        profile.licenses = licenses

    profile.discovery_status = "CONFIRMED"
    profile.updated_at = datetime.datetime.utcnow()

    # Log immutable audit event
    user_name = getattr(current_user, "full_name", "Compliance Officer")
    audit = AuditLog(
        organization_id=profile.id,
        user_name=user_name,
        user_role="Compliance Officer",
        action="DISCOVERY_FINALIZED",
        target_type="ENTERPRISE_PROFILE",
        target_id=profile.id,
        details={
            "organization_name": profile.organization_name,
            "confirmed_departments": len(profile.departments or []),
            "confirmed_activities": len(profile.business_activities or []),
            "confirmed_products": len(profile.products_services or []),
            "confirmed_licenses": len(profile.licenses or [])
        }
    )
    db.add(audit)
    db.commit()
    db.refresh(profile)

    return {
        "status": "SUCCESS",
        "message": "Organization Profile successfully finalized and synchronized with verified evidence.",
        "profile": {
            "id": profile.id,
            "organization_name": profile.organization_name,
            "industry_sector": profile.industry_sector,
            "country": profile.country,
            "departments": profile.departments,
            "business_activities": profile.business_activities,
            "products_services": profile.products_services,
            "licenses": profile.licenses,
            "discovery_status": profile.discovery_status
        }
    }

@router.get("/status", response_model=DiscoveryStatusOut)
def get_discovery_status(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """Get the current discovery status and fact review metrics."""
    profile = current_profile
    discovery_status = profile.discovery_status if profile else "UNINITIALIZED"
    website_url = profile.website_url if profile else None
    last_discovered_at = profile.last_discovered_at if profile else None

    facts = db.query(DiscoveredFact).filter(DiscoveredFact.organization_id == profile.id).all()
    total = len(facts)
    pending = sum(1 for f in facts if f.status == "PENDING")
    confirmed = sum(1 for f in facts if f.status == "CONFIRMED")
    rejected = sum(1 for f in facts if f.status == "REJECTED")

    return DiscoveryStatusOut(
        discovery_status=discovery_status,
        website_url=website_url,
        total_facts=total,
        pending_count=pending,
        confirmed_count=confirmed,
        rejected_count=rejected,
        last_discovered_at=last_discovered_at
    )





import re
def normalize_fact_str(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower()) if s else ""
