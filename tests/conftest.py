"""Pytest configuration and fixtures for CactiAutomation tests."""

from __future__ import annotations

import os
import sys
import tempfile

import pytest

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        yield f.name
    # Cleanup
    if os.path.exists(f.name):
        os.unlink(f.name)


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for testing data processing."""
    return """ID,ISP,VLAN ID,Service ID,Inbound Current,Inbound Average,Inbound Max,Outbound Current,Outbound Average,Outbound Max,Period From,Period To
1,TestISP,100,1234567890,150,200,500,100,150,300,2025-01-01,2025-01-31
2,TestISP,101,1234567891,250,300,600,200,250,400,2025-01-01,2025-01-31
"""


@pytest.fixture
def sample_graph_data():
    """Sample graph data for testing."""
    return {
        "title": "Test Graph",
        "graph_url": "http://example.com/graph.png",
        "local_path": "/path/to/graph.png",
        "description": "Success"
    }


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    class MockSettings:
        ENV = "test"
        DEBUG = True
        CACTI_BASE_URL = "http://test.example.com/"
        CACTI_ALLOWED_URLS = "http://test.example.com/"
        CACTI_USERNAME = "test_user"
        CACTI_PASSWORD = "test_pass"
        CORS_ORIGINS = "http://localhost:3000"
        SELENIUM_HEADLESS = True
        REQUEST_TIMEOUT = 5
        RETRY_MAX_ATTEMPTS = 2
        OUTPUT_DIR = "test_output"

        @property
        def allowed_urls_list(self):
            return ["http://test.example.com/"]

        @property
        def cors_origins_list(self):
            return ["http://localhost:3000"]

        def validate_url(self, url):
            return url.startswith("http://test.example.com/")

    mock = MockSettings()
    return mock
