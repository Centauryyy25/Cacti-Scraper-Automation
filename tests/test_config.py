"""Unit tests for config module."""

from __future__ import annotations


class TestValidateCactiUrl:
    """Tests for URL validation (SSRF protection)."""

    def test_valid_url_in_allowlist(self, mock_settings):
        """URLs in allowlist should be valid."""
        assert mock_settings.validate_url("http://test.example.com/")
        assert mock_settings.validate_url("http://test.example.com/graph.php")

    def test_invalid_url_not_in_allowlist(self, mock_settings):
        """URLs not in allowlist should be invalid."""
        assert not mock_settings.validate_url("http://malicious.com/")
        assert not mock_settings.validate_url("http://other.example.com/")


class TestSettingsProperties:
    """Tests for settings properties."""

    def test_allowed_urls_list(self, mock_settings):
        """allowed_urls_list should return a list."""
        assert isinstance(mock_settings.allowed_urls_list, list)
        assert len(mock_settings.allowed_urls_list) > 0

    def test_cors_origins_list(self, mock_settings):
        """cors_origins_list should return a list."""
        assert isinstance(mock_settings.cors_origins_list, list)
        assert "http://localhost:3000" in mock_settings.cors_origins_list
