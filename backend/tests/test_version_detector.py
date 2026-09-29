import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.domain import Base, Regulation, DocumentVersion, RegulatoryChange
from app.services.version_detector import detect_and_record_version
from datetime import datetime, date

engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_detect_and_record_version_new(db):
    reg = Regulation(
        id="reg-1",
        title="Test Reg",
        authority="Test",
        content_text="Initial content"
    , publication_date=date(2026,1,1), sector="Test", region="Test")
    db.add(reg)
    db.commit()

    result = detect_and_record_version(
        regulation_id="reg-1",
        content_text="Initial content",
        db=db,
        source_url="http://test",
        resolved_source_url="http://test",
        ingestion_method="TEST"
    )
    
    assert result["change_type"] == "NEW"
    
    versions = db.query(DocumentVersion).all()
    assert len(versions) == 1
    assert versions[0].version_no == 1
    
    changes = db.query(RegulatoryChange).all()
    assert len(changes) == 1
    assert changes[0].change_type == "NEW"

def test_detect_and_record_version_no_change(db):
    result = detect_and_record_version(
        regulation_id="reg-1",
        content_text="Initial content",
        db=db,
        source_url="http://test",
        resolved_source_url="http://test",
        ingestion_method="TEST"
    )
    
    assert result["change_type"] == "NO_CHANGE"
    versions = db.query(DocumentVersion).all()
    assert len(versions) == 1

def test_detect_and_record_version_updated(db):
    result = detect_and_record_version(
        regulation_id="reg-1",
        content_text="Updated content block. Much longer to trigger diff.",
        db=db,
        source_url="http://test",
        resolved_source_url="http://test",
        ingestion_method="TEST"
    )
    
    assert result["change_type"] == "UPDATED"
    versions = db.query(DocumentVersion).all()
    assert len(versions) == 2
    
    changes = db.query(RegulatoryChange).all()
    assert len(changes) == 2
    assert changes[0].change_type == "NEW"
    assert changes[1].change_type == "UPDATED"
