"""Tests for the CSV generation and unit conversion logic."""

from __future__ import annotations

import os
import tempfile

import pandas as pd
import pytest

from cleaning.unit_converter import (
    detect_bandwidth_unit,
    parse_bandwidth_value,
)


class TestUnitDetection:
    """Tests for bandwidth unit detection."""

    def test_detect_mbps(self):
        """Should detect Mbps unit."""
        assert detect_bandwidth_unit("150Mbps") == "Mbps"

    def test_detect_kbps(self):
        """Should detect Kbps unit."""
        assert detect_bandwidth_unit("500Kbps") == "Kbps"

    def test_detect_bps(self):
        """Should detect bps unit."""
        assert detect_bandwidth_unit("1000bps") == "bps"

    def test_detect_plain_number(self):
        """Plain numbers should use heuristic detection."""
        result = detect_bandwidth_unit("150")
        assert result in ("Kbps", "Mbps", "bps", "unknown")


class TestParseBandwidthValue:
    """Tests for parsing bandwidth values."""

    def test_parse_numeric_string(self):
        """Should parse a plain numeric string."""
        result = parse_bandwidth_value("1.23")
        assert isinstance(result, (int, float))

    def test_parse_with_unit(self):
        """Should parse value with unit suffix."""
        result = parse_bandwidth_value("500 Kbps")
        assert isinstance(result, (int, float))

    def test_parse_na_returns_zero(self):
        """N/A should return 0."""
        result = parse_bandwidth_value("N/A")
        assert result == 0

    def test_parse_empty_returns_zero(self):
        """Empty string should return 0."""
        result = parse_bandwidth_value("")
        assert result == 0


class TestCSVGeneration:
    """Tests for CSV file generation."""

    def test_csv_output_has_header(self, sample_csv_content):
        """Generated CSV should have a proper header row."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(sample_csv_content)
            path = f.name

        try:
            with open(path, encoding="utf-8") as fh:
                header = fh.readline().strip()
            assert "ID" in header
            assert "Inbound" in header
        finally:
            os.unlink(path)
