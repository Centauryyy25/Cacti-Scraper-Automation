"""Unit tests for storage/database module."""

from __future__ import annotations

import os

import pytest

from storage.database import Database, ErrorRecord, GraphRecord


class TestDatabase:
    """Tests for the Database class."""

    def test_database_init_creates_file(self, temp_db_path):
        """Database initialization should create the database file."""
        _db = Database(temp_db_path)  # noqa: F841
        assert os.path.exists(temp_db_path)

    def test_save_graph_returns_id(self, temp_db_path):
        """save_graph should return the record ID."""
        db = Database(temp_db_path)
        record = GraphRecord(
            title="Test Graph",
            graph_url="http://example.com/graph.png",
            local_path="/path/to/graph.png"
        )
        record_id = db.save_graph(record)
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_get_graphs_by_title(self, temp_db_path, sample_graph_data):
        """get_graphs_by_title should return matching records."""
        db = Database(temp_db_path)
        record = GraphRecord(**sample_graph_data)
        db.save_graph(record)

        results = db.get_graphs_by_title("Test Graph")
        assert len(results) == 1
        assert results[0]['title'] == "Test Graph"

    def test_save_error(self, temp_db_path):
        """save_error should save error records."""
        db = Database(temp_db_path)
        record = ErrorRecord(
            title="Error Test",
            graph_url="http://example.com/",
            local_path="",
            error_message="Test error message"
        )
        record_id = db.save_error(record)
        assert record_id > 0

        errors = db.get_all_errors()
        assert len(errors) == 1
        assert errors[0]['error_message'] == "Test error message"

    def test_run_tracking(self, temp_db_path):
        """Run tracking should record start and end of runs."""
        db = Database(temp_db_path)
        run_id = "test-run-123"

        db.start_run(run_id, total_items=10)
        run = db.get_run(run_id)
        assert run is not None
        assert run['status'] == 'running'
        assert run['total_items'] == 10

        db.end_run(run_id, success_count=8, fail_count=2, csv_output="output.csv")
        run = db.get_run(run_id)
        assert run['status'] == 'complete'
        assert run['success_count'] == 8
        assert run['fail_count'] == 2

    def test_statistics(self, temp_db_path, sample_graph_data):
        """get_statistics should return counts."""
        db = Database(temp_db_path)

        # Add some data
        db.save_graph(GraphRecord(**sample_graph_data))
        db.save_graph(GraphRecord(**sample_graph_data))
        db.save_error(ErrorRecord(
            title="Error",
            graph_url="",
            local_path="",
            error_message="Error"
        ))

        stats = db.get_statistics()
        assert stats['total_graphs'] == 2
        assert stats['total_errors'] == 1
        assert stats['success_rate'] == pytest.approx(66.67, rel=0.1)


class TestBackwardCompatibility:
    """Tests for backward-compatible API functions."""

    def test_save_graph_info_returns_bool(self, temp_db_path, monkeypatch):
        """save_graph_info should return True on success."""
        from storage import database
        monkeypatch.setattr(database, 'DB_PATH', temp_db_path)
        monkeypatch.setattr(database, '_db_instance', None)

        from storage.database import save_graph_info
        result = save_graph_info(
            title="Test",
            graph_url="http://example.com/",
            local_path="/path/to/file.png"
        )
        assert result is True
