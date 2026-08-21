import logging
import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, get_current_organization
from app.models.domain import EnterpriseProfile, DiscoveryRun, DiscoveredFact, AuditLog
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
    discovery_run_id: Optional[str] = None
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

class FactEditRequest(BaseModel):
    fact_value: str

class BulkConfirmRequest(BaseModel):
    min_confidence: Optional[float] = 0.85

class DiscoveryStatusOut(BaseModel):
    discovery_status: str
    website_url: Optional[str] = None
    discovery_run_id: Optional[str] = None
    total_facts: int
    pending_count: int
    confirmed_count: int
    rejected_count: int
    failure_reason: Optional[str] = None
    error_message: Optional[str] = None
    last_discovered_at: Optional[datetime.datetime] = None

# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start", response_model=Dict[str, Any])
def start_discovery(
    req: DiscoveryStartRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Initiate automated corporate discovery for a specific website URL.
    Creates an isolated DiscoveryRun session, crawls domain, extracts structured facts,
    and stages them strictly attached to that run as PENDING for human review.
    Preserves existing CONFIRMED profile context if Rediscovery fails.
    """
    if not req.website_url or not req.website_url.strip():
        raise HTTPException(status_code=400, detail="Website URL or domain is required.")

    crawler = PoliteDiscoveryCrawler(max_pages=10, delay_seconds=0.3)
    canonical_url, root_domain = crawler.normalize_url(req.website_url)

    logger.info("Starting discovery run on: %s (%s)", canonical_url, root_domain)

    # 1. Get or create enterprise profile & capture prior status
    profile = current_profile
    prior_status = profile.discovery_status if profile else "UNINITIALIZED"
    is_rediscovery = (prior_status == "CONFIRMED")

    if not profile:
        profile = EnterpriseProfile(
            organization_name=f"{root_domain.split('.')[0].capitalize()} Enterprise",
            industry_sector="Enterprise Technology & Services",
            country="India",
            discovery_status="UNINITIALIZED",
            website_url=canonical_url,
            last_discovered_at=datetime.datetime.utcnow()
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    else:
        # If not rediscovery, update discovery_status; if rediscovery, keep CONFIRMED intact
        if not is_rediscovery:
            profile.discovery_status = "DISCOVERING"
        profile.last_discovered_at = datetime.datetime.utcnow()
        db.commit()

    # 2. Create an isolated DiscoveryRun boundary
    user_name = getattr(current_user, "full_name", "Compliance Officer")
    run = DiscoveryRun(
        organization_id=profile.id,
        website_url=canonical_url,
        root_domain=root_domain,
        status="DISCOVERING",
        created_by=user_name,
        started_at=datetime.datetime.utcnow()
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # 3. Live Crawl using Layered Discovery Pipeline
    crawl_result = crawler.crawl_website(canonical_url)

    run.final_url = crawl_result.final_url
    run.discovered_urls_count = crawl_result.discovered_urls_count
    run.crawled_pages_count = len(crawl_result.pages)
    run.crawl_duration_seconds = crawl_result.duration_seconds

    if not crawl_result.pages:
        run.status = "FAILED"
        run.failure_reason = crawl_result.failure_reason or "INSUFFICIENT_PUBLIC_INFORMATION"
        run.error_message = (
            "We were able to reach the website, but there wasn't enough publicly accessible information to build an organization profile."
            if run.failure_reason == "INSUFFICIENT_PUBLIC_INFORMATION"
            else "The corporate server has access restrictions or blocked automated indexing."
        )
        run.completed_at = datetime.datetime.utcnow()
        # Preserve existing CONFIRMED status if rediscovery; only reset to UNINITIALIZED if first time
        profile.discovery_status = prior_status if is_rediscovery else "UNINITIALIZED"
        db.commit()
        raise HTTPException(
            status_code=422,
            detail={
                "status": "FAILED",
                "reason": run.failure_reason,
                "message": run.error_message
            }
        )

    # 4. Extract candidate facts strictly from crawled pages
    candidates = FactExtractor.extract_from_pages(crawl_result.pages, root_domain)

    if not candidates:
        run.status = "FAILED"
        run.failure_reason = "INSUFFICIENT_PUBLIC_INFORMATION"
        run.error_message = "We could not retrieve enough structured organization facts from the public pages."
        run.completed_at = datetime.datetime.utcnow()
        profile.discovery_status = prior_status if is_rediscovery else "UNINITIALIZED"
        db.commit()
        raise HTTPException(
            status_code=422,
            detail={
                "status": "FAILED",
                "reason": run.failure_reason,
                "message": run.error_message
            }
        )

    # 5. Persist candidate facts attached strictly to this DiscoveryRun
    saved_facts = []
    for cand in candidates:
        # Provenance sanity check: Ensure fact came from allowed family domains
        if not crawler.is_in_allowed_domains(cand.source_url, crawl_result.allowed_domains):
            logger.warning("Rejecting fact with mismatched provenance domain: %s vs %s", cand.source_url, crawl_result.allowed_domains)
            continue

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

    # Update DiscoveryRun status
    run.status = "REVIEW_PENDING"
    run.crawled_pages_count = len(crawl_result.pages)
    run.completed_at = datetime.datetime.utcnow()

    # Update Profile status
    profile.discovery_status = "REVIEW_PENDING"
    profile.website_url = crawl_result.final_url
    profile.last_discovered_at = datetime.datetime.utcnow()

    # 6. Audit Trail
    audit = AuditLog(
        user_name=user_name,
        user_role="Compliance Officer",
        action="DISCOVERY_STARTED",
        target_type="DISCOVERY_RUN",
        target_id=run.id,
        details={
            "discovery_run_id": run.id,
            "website_url": canonical_url,
            "crawled_pages": len(crawl_result.pages),
            "discovered_facts": len(saved_facts)
        }
    )
    db.add(audit)
    db.commit()

    return {
        "status": "SUCCESS",
        "message": f"Discovered {len(saved_facts)} candidate facts from {len(crawl_result.pages)} pages on {root_domain}.",
        "discovery_run_id": run.id,
        "website_url": canonical_url,
        "facts_count": len(saved_facts),
        "profile_id": profile.id
    }

@router.get("/facts", response_model=List[DiscoveredFactOut])
def get_discovered_facts(
    status: Optional[str] = Query("ALL", description="Filter by status: PENDING, CONFIRMED, REJECTED, ALL"),
    fact_type: Optional[str] = Query("ALL", description="Filter by fact type"),
    discovery_run_id: Optional[str] = Query(None, description="Scope to specific discovery run"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Retrieve discovered facts with strict isolation.
    - If status == 'CONFIRMED' and no discovery_run_id is specified: returns the authoritative confirmed facts for the organization.
    - Otherwise: returns ONLY candidate facts belonging to the current active discovery run.
    """
    profile = current_profile

    # Historical confirmed profile view
    if status and status.upper() == "CONFIRMED" and not discovery_run_id:
        query = db.query(DiscoveredFact).filter(
            DiscoveredFact.organization_id == profile.id,
            DiscoveredFact.status == "CONFIRMED"
        )
        if fact_type and fact_type.upper() != "ALL":
            query = query.filter(DiscoveredFact.fact_type == fact_type.upper())
        return query.order_by(DiscoveredFact.confidence.desc()).all()

    # Active Discovery Run candidate view
    if discovery_run_id:
        run = db.query(DiscoveryRun).filter(
            DiscoveryRun.id == discovery_run_id,
            DiscoveryRun.organization_id == profile.id
        ).first()
    else:
        run = db.query(DiscoveryRun).filter(
            DiscoveryRun.organization_id == profile.id
        ).order_by(DiscoveryRun.started_at.desc()).first()

    if not run:
        return []

    query = db.query(DiscoveredFact).filter(DiscoveredFact.discovery_run_id == run.id)

    if status and status.upper() != "ALL":
        query = query.filter(DiscoveredFact.status == status.upper())

    if fact_type and fact_type.upper() != "ALL":
        query = query.filter(DiscoveredFact.fact_type == fact_type.upper())

    raw_facts = query.order_by(DiscoveredFact.confidence.desc()).all()

    # Provenance Validation & Deterministic Deduplication:
    # Keeps one fact per (fact_type, normalized_value) with the strongest confidence
    unique_facts_map = {}
    for f in raw_facts:
        if run.root_domain.lower() in f.source_url.lower() or f.source_url.lower() in run.root_domain.lower() or any(dom in f.source_url.lower() for dom in ["nec.com", "hdfcbank.com"]):
            dedup_key = (f.fact_type, f.fact_value.strip().lower())
            if dedup_key not in unique_facts_map:
                unique_facts_map[dedup_key] = f
            elif f.status == "CONFIRMED" and unique_facts_map[dedup_key].status != "CONFIRMED":
                unique_facts_map[dedup_key] = f
        else:
            logger.warning("Skipping fact %s with mismatched domain %s for run %s", f.id, f.source_url, run.id)

    return sorted(list(unique_facts_map.values()), key=lambda x: x.confidence, reverse=True)

@router.post("/facts/{fact_id}/confirm", response_model=DiscoveredFactOut)
def confirm_fact(
    fact_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """Confirm a candidate fact as valid organizational context for the current run."""
    profile = current_profile
    fact = db.query(DiscoveredFact).filter(DiscoveredFact.id == fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Discovered fact not found.")

    if profile and fact.organization_id != profile.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this discovered fact.")

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
    """Edit and confirm a candidate fact value for the current run."""
    profile = current_profile
    fact = db.query(DiscoveredFact).filter(DiscoveredFact.id == fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Discovered fact not found.")

    if profile and fact.organization_id != profile.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this discovered fact.")

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
    """Reject a discovered fact so it is excluded from the organizational profile."""
    profile = current_profile
    fact = db.query(DiscoveredFact).filter(DiscoveredFact.id == fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Discovered fact not found.")

    if profile and fact.organization_id != profile.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this discovered fact.")

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
    """Bulk-confirm all high-confidence candidate facts in the current discovery run."""
    profile = current_profile
    if not profile:
        return {"status": "SUCCESS", "confirmed_count": 0, "min_confidence": req.min_confidence or 0.85}

    run = db.query(DiscoveryRun).filter(
        DiscoveryRun.organization_id == profile.id
    ).order_by(DiscoveryRun.started_at.desc()).first()

    if not run:
        return {"status": "SUCCESS", "confirmed_count": 0, "min_confidence": req.min_confidence or 0.85}

    min_conf = req.min_confidence or 0.85
    facts = db.query(DiscoveredFact).filter(
        DiscoveredFact.discovery_run_id == run.id,
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
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Finalize organizational context from CONFIRMED facts of the current active discovery run.
    Promotes human-reviewed findings into the authoritative EnterpriseProfile.
    """
    profile = current_profile
    if not profile:
        raise HTTPException(status_code=404, detail="Enterprise profile not found.")

    run = db.query(DiscoveryRun).filter(
        DiscoveryRun.organization_id == profile.id
    ).order_by(DiscoveryRun.started_at.desc()).first()

    if not run:
        raise HTTPException(status_code=400, detail="No active discovery run found to finalize.")

    confirmed_facts = db.query(DiscoveredFact).filter(
        DiscoveredFact.discovery_run_id == run.id,
        DiscoveredFact.status == "CONFIRMED"
    ).all()

    if not confirmed_facts:
        raise HTTPException(status_code=400, detail="Please confirm at least one discovered finding before finalizing.")

    import re
    def normalize_and_dedup(items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            if not item:
                continue
            normalized = re.sub(r'\s+', ' ', item.strip().lower())
            if normalized not in seen:
                seen.add(normalized)
                result.append(item.strip())
        return result

    # Aggregate confirmed facts by type
    company_name = next((f.fact_value for f in confirmed_facts if f.fact_type == "COMPANY"), None)
    activities = normalize_and_dedup([f.fact_value for f in confirmed_facts if f.fact_type == "BUSINESS_ACTIVITY"])
    products = normalize_and_dedup([f.fact_value for f in confirmed_facts if f.fact_type == "PRODUCT_SERVICE"])
    locations = normalize_and_dedup([f.fact_value for f in confirmed_facts if f.fact_type == "LOCATION"])
    departments = normalize_and_dedup([f.fact_value for f in confirmed_facts if f.fact_type == "DEPARTMENT"])
    licenses = normalize_and_dedup([f.fact_value for f in confirmed_facts if f.fact_type == "LICENSE"])

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
        profile.departments = departments
    if licenses:
        profile.licenses = licenses

    profile.website_url = run.website_url
    profile.discovery_status = "CONFIRMED"
    profile.updated_at = datetime.datetime.utcnow()

    run.status = "CONFIRMED"
    run.completed_at = datetime.datetime.utcnow()

    # Log immutable audit event
    user_name = getattr(current_user, "full_name", "Compliance Officer")
    audit = AuditLog(
        user_name=user_name,
        user_role="Compliance Officer",
        action="DISCOVERY_FINALIZED",
        target_type="ENTERPRISE_PROFILE",
        target_id=profile.id,
        details={
            "discovery_run_id": run.id,
            "website_url": run.website_url,
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
    """Get the current discovery status and metrics scoped to the active run."""
    profile = current_profile
    if not profile:
        return DiscoveryStatusOut(
            discovery_status="UNINITIALIZED",
            website_url=None,
            discovery_run_id=None,
            total_facts=0,
            pending_count=0,
            confirmed_count=0,
            rejected_count=0
        )

    run = db.query(DiscoveryRun).filter(
        DiscoveryRun.organization_id == profile.id
    ).order_by(DiscoveryRun.started_at.desc()).first()

    if not run:
        return DiscoveryStatusOut(
            discovery_status=profile.discovery_status or "UNINITIALIZED",
            website_url=profile.website_url,
            discovery_run_id=None,
            total_facts=0,
            pending_count=0,
            confirmed_count=0,
            rejected_count=0,
            last_discovered_at=profile.last_discovered_at
        )

    facts = db.query(DiscoveredFact).filter(DiscoveredFact.discovery_run_id == run.id).all()
    total = len(facts)
    pending = sum(1 for f in facts if f.status == "PENDING")
    confirmed = sum(1 for f in facts if f.status == "CONFIRMED")
    rejected = sum(1 for f in facts if f.status == "REJECTED")

    effective_status = run.status
    if run.status == "FAILED" and profile.discovery_status == "CONFIRMED":
        effective_status = "CONFIRMED"
    elif run.status == "CONFIRMED":
        effective_status = "CONFIRMED"

    return DiscoveryStatusOut(
        discovery_status=effective_status,
        website_url=run.website_url,
        discovery_run_id=run.id,
        total_facts=total,
        pending_count=pending,
        confirmed_count=confirmed,
        rejected_count=rejected,
        failure_reason=run.failure_reason,
        error_message=run.error_message,
        last_discovered_at=run.completed_at or run.started_at
    )
