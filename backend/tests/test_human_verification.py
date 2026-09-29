import pytest
from unittest.mock import patch, MagicMock
from app.services.human_verification_service import HumanVerificationService
from app.models.domain import Regulation

# Helper mock for urlopen response
class MockResponse:
    def __init__(self, content, status=200, content_type="application/pdf"):
        self.content = content
        self.status = status
        self.headers = {"Content-Type": content_type}
        
    def read(self):
        return self.content
        
    def __enter__(self):
        return self
        
    def __exit__(self, *args):
        pass

def mock_urlopen_success(content=b"Dummy content", content_type="application/pdf"):
    def mock(*args, **kwargs):
        return MockResponse(content, content_type=content_type)
    return mock

@pytest.fixture
def mock_reg():
    reg = Regulation()
    reg.id = "test-reg"
    reg.authority = "RBI"
    reg.doc_number = "RBI/2026-27/203 A.P. (DIR Series) Circular No.19"
    reg.title = "Special Rupee Vostro Accounts (SRVAs)"
    return reg


# 1. Valid exact official source -> accepted
@patch("urllib.request.urlopen")
def test_valid_exact_source(mock_urlopen, mock_reg):
    mock_urlopen.side_effect = mock_urlopen_success(b"This is RBI/2026-27/203 A.P. (DIR Series) Circular No.19")
    result = HumanVerificationService.verify_source(mock_reg, "https://rbi.org.in/valid.pdf")
    assert result["valid"] is True
    assert result["checks"]["https"] is True
    assert result["checks"]["authoritative_domain"] is True
    assert result["checks"]["reference_match"] is True

# 2. Wrong RBI official PDF -> rejected
@patch("urllib.request.urlopen")
def test_wrong_rbi_pdf(mock_urlopen, mock_reg):
    mock_urlopen.side_effect = mock_urlopen_success(b"This is an unrelated RBI Vision document.")
    result = HumanVerificationService.verify_source(mock_reg, "https://rbidocs.rbi.org.in/wrong.pdf")
    assert result["valid"] is False
    assert result["status"] == "SOURCE_IDENTITY_MISMATCH"

# 3. Reachable non-authoritative URL -> rejected
@patch("urllib.request.urlopen")
def test_non_authoritative_domain(mock_urlopen, mock_reg):
    mock_urlopen.side_effect = mock_urlopen_success(b"RBI/2026-27/203 A.P. (DIR Series) Circular No.19")
    result = HumanVerificationService.verify_source(mock_reg, "https://random-news-site.com/article.pdf")
    assert result["valid"] is False
    assert result["status"] == "DOMAIN_VALIDATION_FAILED"

# 4. Unreachable URL -> rejected
@patch("urllib.request.urlopen")
def test_unreachable_url(mock_urlopen, mock_reg):
    mock_urlopen.side_effect = Exception("Connection refused")
    result = HumanVerificationService.verify_source(mock_reg, "https://rbi.org.in/missing.pdf")
    assert result["valid"] is False
    assert result["status"] == "UNREACHABLE"

# 5. HTTP / non-HTTPS URL -> rejected
@patch("urllib.request.urlopen")
def test_http_url(mock_urlopen, mock_reg):
    mock_urlopen.side_effect = mock_urlopen_success()
    result = HumanVerificationService.verify_source(mock_reg, "http://rbi.org.in/valid.pdf")
    assert result["valid"] is False
    assert result["status"] == "DOMAIN_VALIDATION_FAILED"
    assert result["checks"]["https"] is False

# 6. Unsupported document type -> rejected
@patch("urllib.request.urlopen")
def test_unsupported_document_type(mock_urlopen, mock_reg):
    mock_urlopen.side_effect = mock_urlopen_success(b"video data", content_type="video/mp4")
    result = HumanVerificationService.verify_source(mock_reg, "https://rbi.org.in/video.mp4")
    assert result["valid"] is False
    assert result["status"] == "UNSUPPORTED_DOCUMENT"
    assert result["checks"]["document_type"] is False

# 7. Correct domain + wrong regulation title -> rejected
@patch("urllib.request.urlopen")
def test_correct_domain_wrong_title(mock_urlopen):
    reg = Regulation(authority="RBI", title="Master Direction on KYC", doc_number="")
    mock_urlopen.side_effect = mock_urlopen_success(b"Master Direction on Information Technology")
    result = HumanVerificationService.verify_source(reg, "https://rbi.org.in/it.pdf")
    assert result["valid"] is False
    assert result["status"] == "SOURCE_IDENTITY_MISMATCH"
    assert result["checks"]["title_match"] is False

# 8. Correct domain + wrong circular number -> rejected
@patch("urllib.request.urlopen")
def test_correct_domain_wrong_circular(mock_urlopen, mock_reg):
    mock_urlopen.side_effect = mock_urlopen_success(b"This is RBI/2026-27/204")
    result = HumanVerificationService.verify_source(mock_reg, "https://rbi.org.in/204.pdf")
    assert result["valid"] is False
    assert result["status"] == "SOURCE_IDENTITY_MISMATCH"
    assert result["checks"]["reference_match"] is False

# 9. Correct title but generic/ambiguous identity -> rejected
@patch("urllib.request.urlopen")
def test_generic_title_rejected(mock_urlopen):
    reg = Regulation(authority="RBI", title="Amendment Circular", doc_number="")
    mock_urlopen.side_effect = mock_urlopen_success(b"Amendment Circular about something else")
    result = HumanVerificationService.verify_source(reg, "https://rbi.org.in/amendment.pdf")
    assert result["valid"] is False
    assert result["status"] == "SOURCE_IDENTITY_MISMATCH"

# 10. Correct reference + strong identity -> accepted
@patch("urllib.request.urlopen")
def test_correct_ref_strong_identity(mock_urlopen, mock_reg):
    mock_urlopen.side_effect = mock_urlopen_success(b"SpecialRupeeVostroAccounts RBI/2026-27/203 A.P. (DIR Series) Circular No.19")
    result = HumanVerificationService.verify_source(mock_reg, "https://rbi.org.in/srva.pdf")
    assert result["valid"] is True
    assert result["checks"]["reference_match"] is True

# 11. Missing reference but strong title -> may accept
@patch("urllib.request.urlopen")
def test_strong_title_without_reference(mock_urlopen):
    reg = Regulation(authority="RBI", title="Master Direction on Core Investment Companies", doc_number="")
    mock_urlopen.side_effect = mock_urlopen_success(b"This is the Master Direction on Core Investment Companies for 2026.")
    result = HumanVerificationService.verify_source(reg, "https://rbi.org.in/cic.pdf")
    assert result["valid"] is True
    assert result["checks"]["title_match"] is True

# 12. Failed validation does not persist URL
def test_failed_validation_response_structure():
    reg = Regulation(authority="RBI", title="", doc_number="")
    result = HumanVerificationService.verify_source(reg, "not-a-url")
    assert result["valid"] is False
    assert result["canonical_url"] is None

# 13. Tenant isolation check
@patch("urllib.request.urlopen")
def test_tenant_sebi_authority_enforcement(mock_urlopen):
    reg = Regulation(authority="SEBI", doc_number="SEBI/HO/123")
    mock_urlopen.side_effect = mock_urlopen_success(b"SEBI/HO/123")
    result = HumanVerificationService.verify_source(reg, "https://rbi.org.in/sebi_doc.pdf")
    assert result["valid"] is False
    assert result["status"] == "DOMAIN_VALIDATION_FAILED"

# 14. SRVA specific test: An unrelated RBI PDF
@patch("urllib.request.urlopen")
def test_srva_unrelated_rbi_pdf(mock_urlopen, mock_reg):
    mock_urlopen.side_effect = mock_urlopen_success(b"Some text about monetary policy")
    result = HumanVerificationService.verify_source(mock_reg, "https://rbidocs.rbi.org.in/rdocs/content/pdfs/Utkarsh202910042026.pdf")
    assert result["valid"] is False
    assert result["checks"]["reference_match"] is False
    assert result["checks"]["title_match"] is False

# 15. SRVA specific test: Genuine matching source
@patch("urllib.request.urlopen")
def test_srva_genuine_match(mock_urlopen, mock_reg):
    mock_urlopen.side_effect = mock_urlopen_success(b"Special Rupee Vostro Accounts (SRVAs) RBI/2026-27/203 A.P. (DIR Series) Circular No. 19")
    result = HumanVerificationService.verify_source(mock_reg, "https://rbidocs.rbi.org.in/rdocs/notification/PDFs/SRVA.pdf")
    assert result["valid"] is True
    assert result["checks"]["reference_match"] is True
    assert result["checks"]["title_match"] is True


# 11. Normalization tests (spacing, case) -> accepted
@patch('urllib.request.urlopen')
def test_normalization_spacing_case(mock_urlopen, mock_reg):
    # The actual text has weird spaces and cases
    text = b' rbi / 2026-27 / 203  \n\n A.P. (DIR SERIES) CIRCULAR NO. 19 \n Special Rupee Vostro Accounts (SRVAs)'
    mock_urlopen.side_effect = mock_urlopen_success(text)
    result = HumanVerificationService.verify_source(mock_reg, 'https://rbi.org.in/spaced.pdf')
    assert result['valid'] is True
    assert result['checks']['reference_match'] is True
    assert result['checks']['title_match'] is True

# 12. Security Test: Title matches but wrong reference number -> rejected
@patch('urllib.request.urlopen')
def test_security_wrong_reference_number(mock_urlopen, mock_reg):
    text = b'RBI/2026-27/999 A.P. (DIR Series) Circular No. 99 \n Special Rupee Vostro Accounts (SRVAs)'
    mock_urlopen.side_effect = mock_urlopen_success(text)
    result = HumanVerificationService.verify_source(mock_reg, 'https://rbi.org.in/wrong_ref.pdf')
    assert result['valid'] is False
    assert result['checks']['reference_match'] is False
    assert result['checks']['title_match'] is True
    assert result['status'] == 'SOURCE_IDENTITY_MISMATCH'

# 13. Security Test: Title matches but missing reference number entirely -> rejected
@patch('urllib.request.urlopen')
def test_security_missing_reference_number(mock_urlopen, mock_reg):
    text = b'We are discussing Special Rupee Vostro Accounts (SRVAs) in this document.'
    mock_urlopen.side_effect = mock_urlopen_success(text)
    result = HumanVerificationService.verify_source(mock_reg, 'https://rbi.org.in/missing_ref.pdf')
    assert result['valid'] is False
    assert result['checks']['reference_match'] is False
    assert result['checks']['title_match'] is True
    assert result['status'] == 'SOURCE_IDENTITY_MISMATCH'


#                                                                                                                                                             
# Anti-bot / SOURCE_RETRIEVAL_BLOCKED tests
#                                                                                                                                                             

# a. Real PDF with matching reference number     VERIFIED (existing behaviour unchanged)
@patch('urllib.request.urlopen')
def test_antibot_real_pdf_verified(mock_urlopen, mock_reg):
    """A genuine PDF with a matching reference must still be VERIFIED."""
    pdf_content = b'%PDF-1.4\n\nRBI/2026-27/203 A.P. (DIR Series) Circular No.19\nSpecial Rupee Vostro Accounts'
    mock_urlopen.side_effect = mock_urlopen_success(pdf_content, content_type='application/pdf')
    result = HumanVerificationService.verify_source(
        mock_reg, 'https://rbidocs.rbi.org.in/rdocs/notification/PDFs/SRVA.pdf'
    )
    assert result['valid'] is True
    assert result['status'] == 'VERIFIED'
    assert result['checks']['reachable'] is True
    assert result['checks']['document_type'] is True
    assert result['checks']['reference_match'] is True


# b. Imperva/TSPD HTML bot-challenge     SOURCE_RETRIEVAL_BLOCKED (signal B: known marker in body)
@patch('urllib.request.urlopen')
def test_antibot_imperva_tspd_marker(mock_urlopen, mock_reg):
    """An HTTP 200 response containing the Imperva TSPD_101 marker must be blocked."""
    tspd_html = (
        b'<!DOCTYPE html><html><head></head><body>'
        b'<script>window["bobcmn"]="101...TSPD_101...";</script>'
        b'</body></html>'
    )
    mock_urlopen.side_effect = mock_urlopen_success(tspd_html, content_type='text/html')
    result = HumanVerificationService.verify_source(
        mock_reg, 'https://rbidocs.rbi.org.in/rdocs/notification/PDFs/NOTI.PDF'
    )
    assert result['valid'] is False
    assert result['status'] == 'SOURCE_RETRIEVAL_BLOCKED'
    assert result['checks']['reachable'] is True
    assert result['checks']['document_type'] is False
    assert 'bot-protection' in result['reason'].lower() or 'challenge' in result['reason'].lower()


# c. PDF URL returning plain HTML without TSPD markers     SOURCE_RETRIEVAL_BLOCKED (signal A)
@patch('urllib.request.urlopen')
def test_antibot_pdf_url_html_content_type(mock_urlopen, mock_reg):
    """A .pdf URL returning text/html (no TSPD markers) must be blocked via signal A."""
    html_content = b'<html><body><p>Some generic HTML page, not a PDF.</p></body></html>'
    mock_urlopen.side_effect = mock_urlopen_success(html_content, content_type='text/html')
    result = HumanVerificationService.verify_source(
        mock_reg, 'https://rbidocs.rbi.org.in/rdocs/notification/PDFs/NOTI.pdf'
    )
    assert result['valid'] is False
    assert result['status'] == 'SOURCE_RETRIEVAL_BLOCKED'
    assert result['checks']['reachable'] is True
    assert result['checks']['document_type'] is False


# d. Mismatched PDF (real PDF, wrong reference)     SOURCE_IDENTITY_MISMATCH (existing behaviour)
@patch('urllib.request.urlopen')
def test_antibot_mismatched_pdf_reference(mock_urlopen, mock_reg):
    """A genuine PDF without the regulation's reference stays SOURCE_IDENTITY_MISMATCH."""
    pdf_content = b'%PDF-1.4\n\nThis is RBI/2026-27/999 Circular No.99 unrelated.'
    mock_urlopen.side_effect = mock_urlopen_success(pdf_content, content_type='application/pdf')
    result = HumanVerificationService.verify_source(
        mock_reg, 'https://rbidocs.rbi.org.in/rdocs/notification/PDFs/OTHER.pdf'
    )
    assert result['valid'] is False
    assert result['status'] == 'SOURCE_IDENTITY_MISMATCH'
    assert result['checks']['reachable'] is True
    assert result['checks']['document_type'] is True
    assert result['checks']['reference_match'] is False


# e. Tenant isolation: SEBI reg + RBI domain     domain gate fires before retrieval
@patch('urllib.request.urlopen')
def test_antibot_tenant_isolation_domain_before_botcheck(mock_urlopen):
    """Domain validation fires before retrieval; wrong-domain submissions are rejected
    without ever hitting the network, even if the response would be a bot-challenge."""
    sebi_reg = Regulation(authority='SEBI', doc_number='SEBI/HO/456', title='SEBI Some Rule')
    result = HumanVerificationService.verify_source(sebi_reg, 'https://rbi.org.in/sebi_doc.pdf')
    assert result['valid'] is False
    assert result['status'] == 'DOMAIN_VALIDATION_FAILED'
    mock_urlopen.assert_not_called()
