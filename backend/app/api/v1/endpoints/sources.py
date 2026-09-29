from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.domain import EnterpriseProfile
import datetime
import uuid
from app.core.database import get_db
from app.core.security import get_current_user, get_current_organization, require_roles
from app.models.domain import RegulatorySource, Regulation, Section, Obligation, Requirement, KnowledgeGraphChain, AuditLog

from app.schemas.schemas import SourceResponse, SourceCreate
from app.acl.adapters import LiveStatutoryCrawlerEngine
from app.services.ai_engine import MultiAgentAIOrchestrator


router = APIRouter()

@router.get("", response_model=List[SourceResponse])
def list_sources(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    return db.query(RegulatorySource).order_by(RegulatorySource.created_at.desc()).all()

@router.post("", response_model=SourceResponse)
def create_source(
    source_in: SourceCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["ADMIN", "COMPLIANCE_OFFICER"])),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    source = RegulatorySource(**source_in.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source

@router.delete("/{source_id}", response_model=dict)
def delete_source(
    source_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["ADMIN", "COMPLIANCE_OFFICER"])),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    source = db.query(RegulatorySource).filter(RegulatorySource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source feed not found")

    user_name = getattr(current_user, "full_name", None) or getattr(current_user, "user_name", None) or getattr(current_user, "email", "Compliance Manager")
    user_role = getattr(current_user, "role", "COMPLIANCE_OFFICER")

    db.delete(source)
    db.commit()

    audit = AuditLog(
        user_name=user_name,
        user_role=user_role,
        action="STATUTORY_FEED_REMOVED",
        target_type="REGULATORY_SOURCE",
        target_id=source_id,
        details={"authority": source.authority_name}
    )
    db.add(audit)
    db.commit()

    return {"message": f"Statutory feed '{source.authority_name}' removed successfully", "status": "SUCCESS"}

@router.post("/{source_id}/trigger", response_model=dict)
def trigger_fetch(
    source_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["ADMIN", "COMPLIANCE_OFFICER"])),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    source = db.query(RegulatorySource).filter(RegulatorySource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source feed not found")


    # Execute Live Web Scraper HTTP Crawl over the internet
    crawl_result = LiveStatutoryCrawlerEngine.scrape_live_source(source.feed_url, source.authority_name)

    # Update Source Timestamp
    source.last_fetched_at = datetime.datetime.utcnow()
    
    extracted_titles = crawl_result.get("extracted_titles", [])

    # Ingest Extracted Statutory Directives as Regulatory Knowledge only.
    # ComplianceTask creation is NEVER performed here. Operational tasks
    # are created exclusively via TaskEngine.generate_tasks after:
    #   1. Applicability assessment is established
    #   2. Active RegulatoryObligations exist
    #   3. Required control mappings exist
    #   4. Tenant organization is known
    ingested_count = 0
    ai_recommendations = []  # Non-persisted advisory data for UI display only
    if extracted_titles:
        for t in extracted_titles[:2]:
            existing = db.query(Regulation).filter(Regulation.title == t).first()
            if not existing:
                reg_id = f"reg-live-{uuid.uuid4().hex[:8]}"
                content_text = f"Official statutory circular fetched live over HTTP from {source.feed_url} on {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}.\n\nSubject: {t}\n\nThis statutory directive was automatically processed by the Anti-Corruption Layer (ACL) feed adapter and mapped to enterprise risk compliance controls."
                
                # Phase 1: AI Extraction & Classification (knowledge extraction only)
                ai_phase1 = MultiAgentAIOrchestrator.process_extraction_only(
                    title=t, authority=source.authority_name, sector=source.sector, text=content_text
                )
                
                classification = ai_phase1.get("classification", {})
                new_reg = Regulation(
                    id=reg_id,
                    title=t,
                    authority=source.authority_name,
                    doc_number=f"{source.authority_name.split()[0].upper()}/2026/{uuid.uuid4().hex[:4].upper()}",
                    publication_date=datetime.date.today(),
                    effective_date=None,
                    sector=source.sector,
                    region=source.region,
                    status="INGESTED",
                    source_url=source.feed_url,
                    content_text=content_text
                )
                db.add(new_reg)
                db.flush()

                # Save Sections, Obligations, and Requirements (regulatory knowledge only)
                persisted_reqs = []
                for sec_dict in ai_phase1.get("sections", []):
                    sec_obj = Section(
                        id=f"sec-{uuid.uuid4().hex[:8]}",
                        regulation_id=reg_id,
                        section_number=sec_dict.get("section_number", "Section 1"),
                        title=sec_dict.get("title", "General Provisions"),
                        content_text=sec_dict.get("content_text", content_text)
                    )
                    db.add(sec_obj)
                    db.flush()

                    for obl_dict in sec_dict.get("obligations", []):
                        obl_obj = Obligation(
                            id=f"ob-{uuid.uuid4().hex[:8]}",
                            section_id=sec_obj.id,
                            summary=obl_dict.get("summary", f"Mandatory compliance control for {t}")
                        )
                        db.add(obl_obj)
                        db.flush()

                        for req_dict in obl_dict.get("requirements", []):
                            req_obj = Requirement(
                                id=f"req-{uuid.uuid4().hex[:8]}",
                                obligation_id=obl_obj.id,
                                requirement_text=req_dict.get("requirement_text", content_text[:200]),
                                deadline=req_dict.get("deadline") if isinstance(req_dict.get("deadline"), datetime.date) else None,
                                penalty_description=req_dict.get("penalty_description", "Statutory penalties under applicable law."),
                                statutory_reference=req_dict.get("statutory_reference", f"{source.authority_name} Order"),
                                affected_entities=req_dict.get("affected_entities", ["Regulated Entities"])
                            )
                            db.add(req_obj)
                            db.flush()
                            persisted_reqs.append(req_obj)

                db.commit()

                # Phase 2: AI Impact Mapping (knowledge graph chains only — NO task creation)
                ai_phase2 = MultiAgentAIOrchestrator.process_impact_and_tasks(
                    title=t, persisted_requirements=persisted_reqs, db=db
                )

                for chain_dict in ai_phase2.get("graph_chains", []):
                    db.add(KnowledgeGraphChain(
                        id=f"kg-{uuid.uuid4().hex[:8]}",
                        regulation_id=reg_id,
                        requirement_id=chain_dict.get("requirement_id"),
                        control_code=chain_dict.get("control_code", "CTRL-SEC-01"),
                        policy_code=chain_dict.get("policy_code", "POL-CLOUD-SEC-2026"),
                        process_code=chain_dict.get("process_code", "PRC-INFRA-SCANNING"),
                        department_name=chain_dict.get("department_name", "Compliance Operations"),
                        application_code=chain_dict.get("application_code", "APP-CLOUD-INFRA")
                    ))

                # AI recommended_tasks are NEVER persisted as ComplianceTask records.
                # They are returned as non-operational advisory recommendations only.
                for task_dict in ai_phase2.get("recommended_tasks", []):
                    ai_recommendations.append({
                        "type": "AI_RECOMMENDATION",
                        "status": "NON_OPERATIONAL",
                        "regulation_title": t,
                        "regulation_id": reg_id,
                        "suggested_title": task_dict.get("title", f"Review {t[:40]}"),
                        "suggested_description": task_dict.get("description", ""),
                        "suggested_control_code": task_dict.get("control_code", ""),
                        "suggested_priority": task_dict.get("priority", "HIGH"),
                        "note": "This is an AI-generated recommendation only. "
                                "Operational compliance tasks must be created through "
                                "the applicability assessment and obligation workflow."
                    })

                db.commit()
                ingested_count += 1


    # Audit Log Entry with Empirical Scraped Metadata
    user_name = getattr(current_user, "full_name", None) or getattr(current_user, "user_name", None) or getattr(current_user, "email", "Compliance Officer")
    user_role = getattr(current_user, "role", "COMPLIANCE_OFFICER")
    audit = AuditLog(
        organization_id=current_profile.id,
        user_name=user_name,
        user_role=user_role,
        action="LIVE_STATUTORY_CRAWL_EXECUTED",
        target_type="REGULATORY_SOURCE",
        target_id=source.id,
        details={
            "authority": source.authority_name,
            "feed_url": source.feed_url,
            "bytes_scraped": crawl_result.get("bytes_scraped"),
            "items_extracted": crawl_result.get("items_extracted"),
            "extracted_titles": extracted_titles[:3],
            "new_regulations_ingested": ingested_count
        }
    )
    db.add(audit)
    db.commit()

    return {
        "message": f"Live statutory web crawl completed for '{source.authority_name}'",
        "authority": source.authority_name,
        "feed_url": source.feed_url,
        "http_status": crawl_result.get("http_status"),
        "bytes_scraped": crawl_result.get("bytes_scraped"),
        "items_extracted": crawl_result.get("items_extracted"),
        "new_regulations_ingested": ingested_count,
        "extracted_titles": extracted_titles,
        "ai_recommendations": ai_recommendations,
        "last_scraped_at": str(source.last_fetched_at),
        "status": "SUCCESS"
    }

