import pytest
import datetime
from app.services.source_url_resolver import resolve_source_url, is_index_page

def test_is_index_page():
    # Direct PDF is not an index page
    assert not is_index_page("https://rbidocs.rbi.org.in/rdocs/content/pdfs/file.pdf")
    
    # Query string ID is not an index page
    assert not is_index_page("https://www.rbi.org.in/scripts/bs_viewcontent.aspx?Id=1234")
    
    # NotificationUser.aspx is an index page
    assert is_index_page("https://www.rbi.org.in/Scripts/NotificationUser.aspx")

def test_resolve_source_url_exact_circular_match(monkeypatch):
    """Priority 1: should match exact circular number from link text."""
    def mock_fetch(req, timeout=12):
        # Mock urllib response
        class MockResp:
            def read(self):
                return b'<html><a href="/fake.pdf">RBI/2026-27/203 A.P. (DIR Series) Circular No.19</a></html>'
            def __enter__(self): return self
            def __exit__(self, *args): pass
        return MockResp()
    
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_fetch)
    
    resolved, was_index, reason = resolve_source_url(
        "https://www.rbi.org.in/Scripts/NotificationUser.aspx",
        regulation_title="Special Rupee Vostro Accounts",
        doc_number="RBI/2026-27/203 A.P. (DIR Series) Circular No.19",
        force_refresh=True
    )
    
    assert resolved == "https://www.rbi.org.in/fake.pdf"
    assert was_index is True
    assert "doc_number" in reason

def test_resolve_source_url_ambiguous_no_fallback(monkeypatch):
    """Should NOT fallback to first PDF if no matching doc number or title is found."""
    def mock_fetch(req, timeout=12):
        # Mock urllib response with an unrelated PDF
        class MockResp:
            def read(self):
                return b'<html><a href="/wrong.pdf">Some unrelated document</a></html>'
            def __enter__(self): return self
            def __exit__(self, *args): pass
        return MockResp()
    
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_fetch)
    
    resolved, was_index, reason = resolve_source_url(
        "https://www.rbi.org.in/Scripts/NotificationUser.aspx",
        regulation_title="Special Rupee Vostro Accounts",
        doc_number="RBI/2026-27/203 A.P. (DIR Series) Circular No.19",
        force_refresh=True
    )
    
    assert resolved is None
    assert "exact circular match could not be established" in reason
