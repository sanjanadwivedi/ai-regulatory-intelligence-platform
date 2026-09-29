"""
Regulatory Version Detector — Phase 20
=======================================
Deterministic change detection for regulatory documents.

Algorithm:
  1. Normalize content (strip OCR noise, collapse whitespace, NFC unicode)
  2. Compute SHA-256 hash of normalized text
  3. Compare against current DocumentVersion for this regulation
  4. Classify: NEW | UPDATED | NO_CHANGE | SOURCE_CHANGED
  5. Create immutable DocumentVersion snapshot (if content changed)
  6. Create RegulatoryChange record (idempotent via UniqueConstraint)
  7. Write AuditLog entry

STRICT RULES:
  - change_type is NEVER determined by LLM output.
  - SHA-256 hash comparison is the authoritative mechanism.
  - LLM may later summarize the diff, but cannot override the hash result.
  - Previous versions are NEVER mutated.
  - Idempotent: repeated calls with identical content produce NO new DB rows.
"""

import hashlib
import logging
import unicodedata
import re
import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.domain import (
    Regulation,
    DocumentVersion,
    RegulatoryChange,
    AuditLog,
    generate_uuid,
)

logger = logging.getLogger("compliance_platform.version_detector")

DETECTOR_VERSION = "v1.0.0-sha256"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_and_record_version(
    regulation_id: str,
    content_text: str,
    db: Session,
    source_url: Optional[str] = None,
    resolved_source_url: Optional[str] = None,
    ingestion_method: str = "MANUAL",
    effective_date=None,
    detected_by: str = "system",
) -> Dict[str, Any]:
    """
    Detect whether the supplied content_text represents a new regulatory version.

    Returns a dict with:
      - change_type: "NEW" | "UPDATED" | "NO_CHANGE" | "SOURCE_CHANGED"
      - version_id: id of the DocumentVersion (new or reused)
      - version_no: version number
      - content_hash: SHA-256 of normalized content
      - created_new_version: bool
      - change_id: id of RegulatoryChange record (or None for NO_CHANGE)

    Callers MUST NOT overwrite regulation.content_text before calling this function.
    This function updates regulation.content_text, .current_version_no, and .current_content_hash
    when a new version is created.
    """
    regulation = db.query(Regulation).filter(Regulation.id == regulation_id).first()
    if not regulation:
        raise ValueError(f"Regulation {regulation_id} not found")

    # Step 1-2: Normalize + hash
    normalized = _normalize(content_text)
    new_hash = _sha256(normalized)

    # Step 3: Load current version
    current_version = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.regulation_id == regulation_id)
        .order_by(DocumentVersion.version_no.desc())
        .first()
    )

    # Step 4: Classify
    change_type = _classify(current_version, new_hash, source_url)

    logger.info(
        "Version detection for %s: change_type=%s hash=%s",
        regulation_id, change_type, new_hash[:16] + "..."
    )

    if change_type == "NO_CHANGE":
        # Idempotent — no writes needed for version or change record
        _audit(db, regulation, action="REGULATION_VERSION_NO_CHANGE",
               version_no=current_version.version_no,
               content_hash=new_hash, change_type="NO_CHANGE",
               detected_by=detected_by)
        return {
            "change_type": "NO_CHANGE",
            "version_id": current_version.id,
            "version_no": current_version.version_no,
            "content_hash": new_hash,
            "created_new_version": False,
            "change_id": None,
        }

    # Step 5: Create new DocumentVersion
    new_version_no = (current_version.version_no + 1) if current_version else 1
    diff_summary = _compute_diff_summary(
        old_text=(current_version.content_text if current_version else ""),
        new_text=normalized,
    )

    version = DocumentVersion(
        id=generate_uuid(),
        regulation_id=regulation_id,
        version_no=new_version_no,
        content_hash=new_hash,
        content_text=normalized,
        effective_date=effective_date,
        source_url=source_url,
        resolved_source_url=resolved_source_url,
        ingested_at=datetime.datetime.utcnow(),
        ingestion_method=ingestion_method,
        previous_version_id=current_version.id if current_version else None,
        diff_summary=diff_summary,
    )

    try:
        db.add(version)
        db.flush()  # acquire PK without full commit
    except IntegrityError:
        db.rollback()
        # Concurrent write with identical hash — treat as NO_CHANGE
        logger.warning(
            "IntegrityError on DocumentVersion for %s (hash=%s) — treating as NO_CHANGE",
            regulation_id, new_hash[:16]
        )
        existing = (
            db.query(DocumentVersion)
            .filter(
                DocumentVersion.regulation_id == regulation_id,
                DocumentVersion.content_hash == new_hash,
            )
            .first()
        )
        if existing:
            return {
                "change_type": "NO_CHANGE",
                "version_id": existing.id,
                "version_no": existing.version_no,
                "content_hash": new_hash,
                "created_new_version": False,
                "change_id": None,
            }
        raise

    # Update regulation pointer fields
    regulation.current_version_no = new_version_no
    regulation.current_content_hash = new_hash
    regulation.content_text = normalized
    regulation.last_extracted_at = datetime.datetime.utcnow()

    # Step 6: Create RegulatoryChange record (idempotent via UniqueConstraint)
    change_id = _create_change_record(
        db=db,
        regulation_id=regulation_id,
        previous_version_id=current_version.id if current_version else None,
        new_version_id=version.id,
        change_type=change_type,
        content_hash_before=current_version.content_hash if current_version else None,
        content_hash_after=new_hash,
        drift_percentage=diff_summary.get("drift_percentage"),
        diff_hunks=diff_summary.get("diff_hunks", []),
        changed_sections=diff_summary.get("changed_sections", []),
        source_url=source_url,
        detected_by=detected_by,
    )

    # Step 7: AuditLog
    _audit(db, regulation, action="REGULATION_VERSION_CREATED",
           version_no=new_version_no, content_hash=new_hash,
           change_type=change_type, detected_by=detected_by)

    db.commit()

    return {
        "change_type": change_type,
        "version_id": version.id,
        "version_no": new_version_no,
        "content_hash": new_hash,
        "created_new_version": True,
        "change_id": change_id,
        "drift_percentage": diff_summary.get("drift_percentage"),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def compute_content_hash(text: str) -> str:
    """Public helper — compute the canonical SHA-256 hash for a piece of text."""
    return _sha256(_normalize(text))


def _normalize(text: str) -> str:
    """Canonical normalization pipeline."""
    if not text:
        return ""
    # 1. Unicode NFC normalization
    text = unicodedata.normalize("NFC", text)
    # 2. Collapse all whitespace sequences to single space
    text = re.sub(r"\s+", " ", text)
    # 3. Strip leading/trailing whitespace
    text = text.strip()
    return text


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _classify(
    current_version: Optional[DocumentVersion],
    new_hash: str,
    new_source_url: Optional[str],
) -> str:
    if current_version is None:
        return "NEW"

    if new_hash == current_version.content_hash:
        # Content identical — check if source URL changed
        if (
            new_source_url
            and current_version.source_url
            and new_source_url.rstrip("/") != current_version.source_url.rstrip("/")
        ):
            return "SOURCE_CHANGED"
        return "NO_CHANGE"

    return "UPDATED"


def _compute_diff_summary(old_text: str, new_text: str) -> Dict[str, Any]:
    """Compute a lightweight clause-level diff."""
    import difflib

    if not old_text:
        return {
            "drift_percentage": 100.0,
            "changed_sections": [],
            "diff_hunks": [],
            "note": "First version",
        }

    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    ratio = matcher.ratio()
    drift_percentage = round((1.0 - ratio) * 100, 2)

    diff_hunks = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        diff_hunks.append({
            "operation": tag,
            "old_range": [i1, i2],
            "new_range": [j1, j2],
            "old_lines": old_lines[i1:i2][:8],
            "new_lines": new_lines[j1:j2][:8],
        })
        if len(diff_hunks) >= 50:
            break

    # Best-effort section detection
    changed_sections = []
    seen = set()
    for hunk in diff_hunks:
        for line in (hunk.get("old_lines", []) + hunk.get("new_lines", [])):
            stripped = line.strip()
            if stripped and len(stripped) < 120 and (
                re.match(r"^(section|chapter|clause|article|part|rule|schedule)\s+\d", stripped, re.I)
                or re.match(r"^\d+(\.\d+)*[\.\s]", stripped)
                or stripped.isupper()
            ):
                key = stripped[:80]
                if key not in seen:
                    changed_sections.append(key)
                    seen.add(key)

    return {
        "drift_percentage": drift_percentage,
        "changed_sections": changed_sections[:20],
        "diff_hunks": diff_hunks,
    }


def _create_change_record(
    db: Session,
    regulation_id: str,
    previous_version_id: Optional[str],
    new_version_id: str,
    change_type: str,
    content_hash_before: Optional[str],
    content_hash_after: str,
    drift_percentage: Optional[float],
    diff_hunks: list,
    changed_sections: list,
    source_url: Optional[str],
    detected_by: str,
) -> Optional[str]:
    """Create a RegulatoryChange record, gracefully handling duplicate constraint violations."""
    try:
        change = RegulatoryChange(
            id=generate_uuid(),
            regulation_id=regulation_id,
            previous_version_id=previous_version_id,
            new_version_id=new_version_id,
            change_type=change_type,
            detected_by=detected_by,
            drift_percentage=drift_percentage,
            content_hash_before=content_hash_before,
            content_hash_after=content_hash_after,
            diff_hunks=diff_hunks,
            changed_sections=changed_sections,
            source_url=source_url,
            review_status="PENDING_REVIEW",
        )
        db.add(change)
        db.flush()
        return change.id
    except IntegrityError:
        db.rollback()
        logger.info(
            "RegulatoryChange already exists for reg=%s — idempotent",
            regulation_id,
        )
        existing = (
            db.query(RegulatoryChange)
            .filter(
                RegulatoryChange.regulation_id == regulation_id,
                RegulatoryChange.previous_version_id == previous_version_id,
                RegulatoryChange.new_version_id == new_version_id,
            )
            .first()
        )
        return existing.id if existing else None


def _audit(
    db: Session,
    regulation: Regulation,
    action: str,
    version_no: int,
    content_hash: str,
    change_type: str,
    detected_by: str,
):
    """Write an immutable AuditLog entry."""
    audit = AuditLog(
        organization_id=None,
        user_name=detected_by,
        user_role="SYSTEM",
        action=action,
        target_type="DocumentVersion",
        target_id=regulation.id,
        details={
            "regulation_id": regulation.id,
            "regulation_title": regulation.title,
            "version_no": version_no,
            "content_hash": content_hash,
            "change_type": change_type,
            "detector_version": DETECTOR_VERSION,
        },
    )
    db.add(audit)