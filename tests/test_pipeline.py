"""Tests for the main pipeline orchestrator."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from main_pipeline import step2_ocr_images, step3_clean_csv


class TestStep2OCR:
    """Tests for the OCR processing step."""

    def test_returns_none_when_no_folder(self):
        """Step 2 should return None when no folder is available."""
        with patch("main_pipeline.progress") as mock_progress:
            mock_progress.scraping.get.return_value = None
            result = step2_ocr_images()
        assert result is None

    def test_returns_none_for_nonexistent_folder(self, tmp_path):
        """Step 2 should return None for a non-existent folder path."""
        fake_folder = str(tmp_path / "does_not_exist")
        result = step2_ocr_images(folder=fake_folder)
        assert result is None


class TestStep3CleanCSV:
    """Tests for the CSV cleaning step."""

    def test_returns_error_when_no_input(self):
        """Step 3 should return error message when no input is available."""
        with patch("main_pipeline.progress") as mock_progress:
            mock_progress.scraping.get.return_value = None
            result = step3_clean_csv()
        assert result is not None
        assert "ERROR" in str(result)

    def test_returns_none_for_missing_file(self, tmp_path):
        """Step 3 should return None when the CSV file doesn't exist."""
        fake_csv = str(tmp_path / "nonexistent.csv")
        result = step3_clean_csv(csv_input=fake_csv)
        assert result is None
