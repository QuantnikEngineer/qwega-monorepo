"""Tests for SSRF URL validation."""

import pytest

from app.core.url_validation import UnsafeURLError, validate_tool_url


# ── Valid URLs ───────────────────────────────────────────────────────────────

class TestValidURLs:
    def test_https_url(self):
        assert validate_tool_url("https://quantnikbuildiq.atlassian.net") == "https://quantnikbuildiq.atlassian.net"

    def test_http_url(self):
        assert validate_tool_url("http://sonarqube.internal.example.com") == "http://sonarqube.internal.example.com"

    def test_strips_trailing_slash(self):
        assert validate_tool_url("https://example.com/") == "https://example.com"

    def test_url_with_port(self):
        assert validate_tool_url("https://example.com:8443") == "https://example.com:8443"

    def test_url_with_path(self):
        assert validate_tool_url("https://example.com/v1/api") == "https://example.com/v1/api"


# ── Blocked URLs ─────────────────────────────────────────────────────────────

class TestBlockedURLs:
    def test_empty_url(self):
        with pytest.raises(UnsafeURLError, match="empty"):
            validate_tool_url("")

    def test_blank_url(self):
        with pytest.raises(UnsafeURLError, match="empty"):
            validate_tool_url("   ")

    def test_ftp_scheme(self):
        with pytest.raises(UnsafeURLError, match="Scheme"):
            validate_tool_url("ftp://example.com/file")

    def test_file_scheme(self):
        with pytest.raises(UnsafeURLError, match="Scheme"):
            validate_tool_url("file:///etc/passwd")

    def test_no_hostname(self):
        with pytest.raises(UnsafeURLError, match="no hostname"):
            validate_tool_url("http://")

    def test_aws_metadata(self):
        with pytest.raises(UnsafeURLError, match="metadata"):
            validate_tool_url("http://169.254.169.254/latest/meta-data/")

    def test_gcp_metadata(self):
        with pytest.raises(UnsafeURLError, match="metadata"):
            validate_tool_url("http://metadata.google.internal/computeMetadata/v1/")

    def test_localhost_ip(self):
        with pytest.raises(UnsafeURLError, match="Loopback"):
            validate_tool_url("http://127.0.0.1:8080")

    def test_localhost_name(self):
        with pytest.raises(UnsafeURLError, match="Loopback"):
            validate_tool_url("http://localhost:8080")

    def test_private_10_range(self):
        with pytest.raises(UnsafeURLError, match="Private"):
            validate_tool_url("http://10.0.0.1:8080")

    def test_private_172_range(self):
        with pytest.raises(UnsafeURLError, match="Private"):
            validate_tool_url("http://172.16.0.1:8080")

    def test_private_192_range(self):
        with pytest.raises(UnsafeURLError, match="Private"):
            validate_tool_url("http://192.168.1.1:8080")

    def test_ipv6_loopback(self):
        with pytest.raises(UnsafeURLError, match="Loopback"):
            validate_tool_url("http://[::1]:8080")


# ── allow_private flag ───────────────────────────────────────────────────────

class TestAllowPrivate:
    def test_localhost_allowed_when_flagged(self):
        result = validate_tool_url("http://localhost:8080", allow_private=True)
        assert result == "http://localhost:8080"

    def test_private_ip_allowed_when_flagged(self):
        result = validate_tool_url("http://10.0.0.1:8080", allow_private=True)
        assert result == "http://10.0.0.1:8080"

    def test_metadata_still_blocked(self):
        """Metadata endpoints are blocked even with allow_private."""
        with pytest.raises(UnsafeURLError, match="metadata"):
            validate_tool_url("http://169.254.169.254", allow_private=True)
