import pytest
import socket
from unittest.mock import patch
from app.acl.adapters import _validate_url, SSRFSafeRedirectHandler
from app.services.discovery_crawler import SSRFSafeSession
import requests

socket._original_getaddrinfo = socket.getaddrinfo

@pytest.fixture
def mock_dns():
    def _mock_getaddrinfo(host, port, *args, **kwargs):
        if host == "nat64-loopback.internal":
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::127.0.0.1", 0, 0, 0))]
        if host == "nat64-rfc1918.internal":
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::10.0.0.1", 0, 0, 0))]
        if host == "nat64-rfc1918-2.internal":
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::172.16.0.1", 0, 0, 0))]
        if host == "nat64-rfc1918-3.internal":
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::192.168.1.1", 0, 0, 0))]
        if host == "nat64-metadata.internal":
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::169.254.169.254", 0, 0, 0))]
        if host == "nat64-public.external":
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::8.8.8.8", 0, 0, 0))]
        if host == "ipv4-loopback.internal":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]
        if host == "ipv6-loopback.internal":
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 0, 0, 0))]
        if host == "ipv4-public.external":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))]
        return socket._original_getaddrinfo(host, port, *args, **kwargs)
    
    with patch("socket.getaddrinfo", side_effect=_mock_getaddrinfo):
        yield

def test_ssrf_nat64_loopback_blocked(mock_dns):
    with pytest.raises(ValueError, match="SSRF"):
        _validate_url("http://nat64-loopback.internal")

def test_ssrf_nat64_rfc1918_blocked(mock_dns):
    with pytest.raises(ValueError, match="SSRF"):
        _validate_url("http://nat64-rfc1918.internal")
    with pytest.raises(ValueError, match="SSRF"):
        _validate_url("http://nat64-rfc1918-2.internal")
    with pytest.raises(ValueError, match="SSRF"):
        _validate_url("http://nat64-rfc1918-3.internal")

def test_ssrf_nat64_metadata_blocked(mock_dns):
    with pytest.raises(ValueError, match="SSRF"):
        _validate_url("http://nat64-metadata.internal")

def test_ssrf_nat64_public_allowed(mock_dns):
    _validate_url("http://nat64-public.external")

def test_ssrf_ordinary_ipv4_blocked(mock_dns):
    with pytest.raises(ValueError, match="SSRF|blocked"):
        _validate_url("http://ipv4-loopback.internal")
    with pytest.raises(ValueError, match="SSRF|blocked"):
        _validate_url("http://127.0.0.1")

def test_ssrf_ordinary_ipv6_blocked(mock_dns):
    with pytest.raises(ValueError, match="SSRF|blocked"):
        _validate_url("http://ipv6-loopback.internal")

def test_redirect_to_private_ipv4_blocked():
    handler = SSRFSafeRedirectHandler()
    with pytest.raises(ValueError, match="SSRF|blocked"):
        handler.redirect_request(None, None, 302, "Found", None, "http://10.0.0.1")

def test_redirect_to_nat64_private_ipv4_blocked(mock_dns):
    handler = SSRFSafeRedirectHandler()
    with pytest.raises(ValueError, match="SSRF"):
        handler.redirect_request(None, None, 302, "Found", None, "http://nat64-rfc1918.internal")

def test_redirect_to_metadata_blocked():
    handler = SSRFSafeRedirectHandler()
    with pytest.raises(ValueError, match="SSRF|blocked"):
        handler.redirect_request(None, None, 302, "Found", None, "http://169.254.169.254")

def test_public_to_public_redirect_works(mock_dns):
    handler = SSRFSafeRedirectHandler()
    # Mock redirect_request to not throw but we must mock the super call since it actually connects
    # Wait, HTTPRedirectHandler's redirect_request does some setup. We can just test _validate_url.
    # We already know handler calls _validate_url. 
    # But let's mock super so it doesn't try to fetch.
    with patch("urllib.request.HTTPRedirectHandler.redirect_request", return_value="success"):
        res = handler.redirect_request(None, None, 302, "Found", None, "http://ipv4-public.external")
        assert res == "success"

def test_requests_redirect_to_private_ipv4_blocked():
    session = SSRFSafeSession()
    resp = requests.Response()
    resp.url = "http://public.com"
    resp.headers["Location"] = "http://10.0.0.1"
    resp.status_code = 302
    with pytest.raises(ValueError, match="SSRF|blocked"):
        session.get_redirect_target(resp)

def test_requests_redirect_to_nat64_private_ipv4_blocked(mock_dns):
    session = SSRFSafeSession()
    resp = requests.Response()
    resp.url = "http://public.com"
    resp.headers["Location"] = "http://nat64-rfc1918.internal"
    resp.status_code = 302
    with pytest.raises(ValueError, match="SSRF"):
        session.get_redirect_target(resp)

def test_requests_public_to_public_redirect_works(mock_dns):
    session = SSRFSafeSession()
    resp = requests.Response()
    resp.url = "http://public.com"
    resp.headers["Location"] = "http://ipv4-public.external"
    resp.status_code = 302
    target = session.get_redirect_target(resp)
    assert target == "http://ipv4-public.external"
