"""
intelligence.py — Compliance Intelligence & Defense Pack API Endpoints

Provides:
  POST /compliance/intelligence/snapshot
  GET  /compliance/intelligence/snapshot
  GET  /compliance/intelligence/snapshot/{snapshot_id}
  POST /compliance/defense-pack/generate
  GET  /compliance/defense-pack
  GET  /compliance/defense-pack/{pack_id}
  GET  /compliance/defense-pack/{pack_id}/manifest
  GET  /compliance/defense-pack/{pack_id}/export

Security:
  - All endpoints require authentication.
  - Organisation isolation is enforced server-side: users can only
    access snapshots and packs belonging to their own organisation.
  - RBAC: only COMPLIANCE_OFFICER or ADMIN roles may generate snapshots
    and packs. Read endpoints are available to any authenticated user
    within the same organisation.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.domain import EnterpriseProfile
from app.schemas.schemas import (
    SnapshotGenerateRequest,
    ComplianceIntelligenceSnapshotResponse,
    DefensePackGenerateRequest,
    ComplianceDefensePackResponse,
    ComplianceEvidenceManifestResponse,
    DefensePackExportResponse,
)
from app.services.compliance_intelligence_service import ComplianceIntelligenceService
from app.services.defense_pack_service import DefensePackService

router = APIRouter()

ALLOWED_GENERATE_ROLES = {"COMPLIANCE_OFFICER", "ADMIN", "admin", "compliance_officer"}


def _resolve_org(current_user, db: Session) -> EnterpriseProfile:
    """Return the organisation for the current user. Raises 404 if not found."""
    user_org_id = getattr(current_user, "organization_id", None)
    if user_org_id:
        profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == user_org_id).first()
    else:
        profile = db.query(EnterpriseProfile).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Enterprise Profile found. Complete organisation discovery first.",
        )
    return profile


def _require_generate_role(current_user):
    """Enforce RBAC: only compliance officers and admins may generate snapshots/packs."""
    role = getattr(current_user, "role", None)
    normalized_role = (role or "").upper().replace(" ", "_")
    if normalized_role not in ALLOWED_GENERATE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions: COMPLIANCE_OFFICER or ADMIN role required.",
        )


# ---------------------------------------------------------------------------
# Snapshot endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/intelligence/snapshot",
    response_model=ComplianceIntelligenceSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new immutable compliance intelligence snapshot",
)
def generate_snapshot(
    request: SnapshotGenerateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate a new point-in-time compliance intelligence snapshot.

    Each call creates a NEW immutable record. Existing snapshots are never
    mutated. The caller must be a COMPLIANCE_OFFICER or ADMIN.
    """
    _require_generate_role(current_user)
    profile = _resolve_org(current_user, db)
    actor = getattr(current_user, "email", None) or getattr(current_user, "id", "system")
    try:
        snapshot = ComplianceIntelligenceService.generate_snapshot(
            organization_id=profile.id,
            db=db,
            generated_by=actor,
        )
        return snapshot
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/intelligence/snapshot",
    response_model=ComplianceIntelligenceSnapshotResponse,
    summary="Get the most recent compliance intelligence snapshot",
)
def get_current_snapshot(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return the most recently generated compliance intelligence snapshot."""
    profile = _resolve_org(current_user, db)
    snapshot = ComplianceIntelligenceService.get_current_snapshot(profile.id, db)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No compliance intelligence snapshot found. Generate one first.",
        )
    return snapshot


@router.get(
    "/intelligence/snapshot/{snapshot_id}",
    response_model=ComplianceIntelligenceSnapshotResponse,
    summary="Get a specific compliance intelligence snapshot by ID",
)
def get_snapshot_by_id(
    snapshot_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Retrieve a specific snapshot. Returns 404 if it does not belong to the caller's organisation."""
    profile = _resolve_org(current_user, db)
    snapshot = ComplianceIntelligenceService.get_snapshot_by_id(snapshot_id, profile.id, db)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found or does not belong to your organisation.",
        )
    return snapshot


# ---------------------------------------------------------------------------
# Defense Pack endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/defense-pack/generate",
    response_model=ComplianceDefensePackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a versioned Compliance Defense Pack from a snapshot",
)
def generate_defense_pack(
    request: DefensePackGenerateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate a new versioned Defense Pack from the specified snapshot.

    Previous packs are marked SUPERSEDED. Historical packs remain immutable.
    SHA-256 hash is computed over stable canonical content (volatile fields excluded).
    The caller must be a COMPLIANCE_OFFICER or ADMIN.
    """
    _require_generate_role(current_user)
    profile = _resolve_org(current_user, db)
    actor = getattr(current_user, "email", None) or getattr(current_user, "id", "system")
    try:
        pack = DefensePackService.generate_defense_pack(
            snapshot_id=request.snapshot_id,
            organization_id=profile.id,
            db=db,
            generated_by=actor,
        )
        return pack
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/defense-pack",
    response_model=List[ComplianceDefensePackResponse],
    summary="List all Compliance Defense Pack versions for this organisation",
)
def list_defense_packs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return all Defense Pack versions for the authenticated organisation."""
    profile = _resolve_org(current_user, db)
    packs = DefensePackService.get_defense_packs(profile.id, db)
    return packs


@router.get(
    "/defense-pack/{pack_id}",
    response_model=ComplianceDefensePackResponse,
    summary="Get a specific Compliance Defense Pack",
)
def get_defense_pack(
    pack_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Retrieve a specific Defense Pack. Returns 404 if not owned by caller's organisation."""
    profile = _resolve_org(current_user, db)
    pack = DefensePackService.get_defense_pack(pack_id, profile.id, db)
    if not pack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Defense Pack not found or does not belong to your organisation.",
        )
    return pack


@router.get(
    "/defense-pack/{pack_id}/manifest",
    response_model=List[ComplianceEvidenceManifestResponse],
    summary="Get the full evidence manifest for a Defense Pack",
)
def get_defense_pack_manifest(
    pack_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return all manifest entries for the specified Defense Pack.
    Includes both PRESENT evidence and MISSING gaps.
    """
    profile = _resolve_org(current_user, db)
    pack = DefensePackService.get_defense_pack(pack_id, profile.id, db)
    if not pack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Defense Pack not found or does not belong to your organisation.",
        )
    manifests = DefensePackService.get_defense_pack_manifest(pack_id, profile.id, db)
    return manifests


@router.get(
    "/defense-pack/{pack_id}/export",
    response_model=DefensePackExportResponse,
    summary="Export a Defense Pack as a canonical JSON artifact",
)
def export_defense_pack(
    pack_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Export the full canonical Defense Pack JSON.
    This operation emits an immutable COMPLIANCE_DEFENSE_PACK_EXPORTED audit log entry.
    """
    profile = _resolve_org(current_user, db)
    actor = getattr(current_user, "email", None) or getattr(current_user, "id", "system")
    try:
        result = DefensePackService.export_defense_pack_json(
            pack_id=pack_id,
            organization_id=profile.id,
            db=db,
            actor=actor,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


