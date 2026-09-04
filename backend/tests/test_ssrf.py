"""SSRF protection tests."""

from __future__ import annotations

import pytest

import app.security.ssrf as ssrf_mod
from app.security.ssrf import SSRFError, is_safe_redirect_url, validate_url


@pytest.fixture
def production_mode(monkeypatch):
    """Force production SSRF settings: private/loopback destinations blocked."""
    settings = ssrf_mod.settings
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "ssrf_allow_localhost_dev", False)
    monkeypatch.setattr(settings, "ssrf_block_private", True)
    yield settings


class TestSchemeBlocking:
    def test_file_scheme_rejected(self):
        with pytest.raises(SSRFError):
            validate_url("file:///etc/passwd")

    def test_ftp_rejected(self):
        with pytest.raises(SSRFError):
            validate_url("ftp://example.com/")

    def test_gopher_rejected(self):
        with pytest.raises(SSRFError):
            validate_url("gopher://example.com:70/1foo")


class TestMetadataBlocking:
    def test_aws_metadata_blocked(self):
        with pytest.raises(SSRFError):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_gcp_metadata_blocked(self):
        with pytest.raises(SSRFError):
            validate_url("http://metadata.google.internal/computeMetadata/v1/")

    def test_alibaba_metadata_blocked(self):
        with pytest.raises(SSRFError):
            validate_url("http://100.100.100.200/latest/meta-data/")


class TestPrivateRangeBlocking:
    def test_loopback_blocked(self, production_mode):
        with pytest.raises(SSRFError):
            validate_url("http://127.0.0.1:8000/")

    def test_private_blocked(self, production_mode):
        with pytest.raises(SSRFError):
            validate_url("http://192.168.1.1/")

    def test_link_local_blocked(self, production_mode):
        with pytest.raises(SSRFError):
            validate_url("http://169.254.10.10/")

    def test_localhost_hostname_blocked(self, production_mode):
        with pytest.raises(SSRFError):
            validate_url("http://localhost:8001/")

    def test_hostname_resolving_to_private_blocked(self, production_mode):
        # '0.0.0.0' form IPv4-only hosts resolve to loopback
        with pytest.raises(SSRFError):
            validate_url("http://0.0.0.0/")
        # 'localhost' must always be blocked regardless of resolution
        with pytest.raises(SSRFError):
            validate_url("http://localhost/")
        with pytest.raises(SSRFError):
            validate_url("http://[::1]:8000/")


class TestDevLocalhostAllowed:
    def test_loopback_allowed_in_dev(self):
        validate_url("http://127.0.0.1:8791/")

    def test_localhost_hostname_allowed_in_dev(self):
        validate_url("http://localhost:8001/")


class TestPublicUrlsAllowed:
    def test_https_public_allowed(self):
        validate_url("https://example.com/api/chat")

    def test_http_public_allowed(self):
        validate_url("http://example.com/")

    def test_safe_redirect_check(self, production_mode):
        assert is_safe_redirect_url("https://example.com/foo") is True
        assert is_safe_redirect_url("http://localhost/") is False


class TestMalformed:
    def test_no_host_rejected(self):
        with pytest.raises(SSRFError):
            validate_url("http:///path")