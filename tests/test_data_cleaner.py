"""Unit tests for data_cleaner module."""

from __future__ import annotations

import os
import tempfile

import pandas as pd
import pytest

# Import after conftest adds project to path
from data_cleaner import _convert_kbps_to_mbps, process_csv


class TestConvertKbpsToMbps:
    """Tests for the _convert_kbps_to_mbps function."""

    def test_convert_100_to_mbps(self):
        """100 Kbps should convert to 0.1 Mbps."""
        assert _convert_kbps_to_mbps(100) == 0.1

    def test_convert_500_to_mbps(self):
        """500 Kbps should convert to 0.5 Mbps."""
        assert _convert_kbps_to_mbps(500) == 0.5

    def test_convert_999_to_mbps(self):
        """999 Kbps should convert to 0.999 Mbps."""
        assert _convert_kbps_to_mbps(999) == 0.999

    def test_no_convert_below_100(self):
        """Values below 100 should not be converted."""
        assert _convert_kbps_to_mbps(99) == 99
        assert _convert_kbps_to_mbps(50) == 50
        assert _convert_kbps_to_mbps(0) == 0

    def test_no_convert_above_999(self):
        """Values above 999 should not be converted."""
        assert _convert_kbps_to_mbps(1000) == 1000
        assert _convert_kbps_to_mbps(5000) == 5000

    def test_float_in_range(self):
        """Float values in range should be converted."""
        assert _convert_kbps_to_mbps(150.5) == pytest.approx(0.1505)

    def test_non_numeric_passthrough(self):
        """Non-numeric values should pass through unchanged."""
        assert _convert_kbps_to_mbps("N/A") == "N/A"
        assert _convert_kbps_to_mbps(None) is None
        assert _convert_kbps_to_mbps("") == ""


class TestProcessCsv:
    """Tests for the process_csv function."""

    def test_process_csv_converts_values(self, sample_csv_content):
        """CSV processing should convert Kbps values to Mbps."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as input_file:
            input_file.write(sample_csv_content)
            input_path = input_file.name

        output_path = input_path.replace('.csv', '_output.csv')

        try:
            process_csv(input_path, output_path)

            # Read output and verify conversion
            df = pd.read_csv(output_path)

            # 150 Kbps should become 0.15 Mbps
            assert df['Inbound Current'].iloc[0] == pytest.approx(0.15)
            # 200 Kbps should become 0.2 Mbps
            assert df['Inbound Average'].iloc[0] == pytest.approx(0.2)
            # 500 Kbps should become 0.5 Mbps
            assert df['Inbound Max'].iloc[0] == pytest.approx(0.5)

        finally:
            os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_process_csv_creates_output_file(self, sample_csv_content):
        """process_csv should create output file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as input_file:
            input_file.write(sample_csv_content)
            input_path = input_file.name

        output_path = input_path.replace('.csv', '_output.csv')

        try:
            process_csv(input_path, output_path)
            assert os.path.exists(output_path)
        finally:
            os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)
