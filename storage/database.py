"""SQLite database layer for CactiAutomation.

Replaces JSON file storage with SQLite for better:
- Query performance (indexed columns)
- Concurrent access (proper locking)
- Data integrity (ACID transactions)
- Scalability (handles larger datasets)

Usage:
    from storage.database import Database, GraphRecord, ErrorRecord

    db = Database()
    db.save_graph(GraphRecord(title="...", graph_url="...", local_path="..."))
    records = db.get_graphs_by_date_range(start, end)
"""

from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

try:
    from config import settings
except ImportError:
    class _FallbackSettings:
        OUTPUT_DIR = "output"
    settings = _FallbackSettings()

logger = logging.getLogger(__name__)

# Database path
DB_PATH = os.path.join(getattr(settings, 'OUTPUT_DIR', 'output'), 'cacti_data.db')


@dataclass
class GraphRecord:
    """Represents a scraped graph record."""
    title: str
    graph_url: str
    local_path: str
    description: str = "Success"
    run_id: str = ""
    id: int | None = None
    timestamp: str | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class ErrorRecord:
    """Represents an error record."""
    title: str
    graph_url: str
    local_path: str
    error_message: str
    run_id: str = ""
    id: int | None = None
    timestamp: str | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    """SQLite database manager with connection pooling and transactions."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_directory()
        self._init_schema()

    def _ensure_directory(self) -> None:
        """Ensure database directory exists."""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")  # Better concurrent access
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                -- Graphs table
                CREATE TABLE IF NOT EXISTS graphs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    graph_url TEXT NOT NULL,
                    local_path TEXT NOT NULL,
                    description TEXT DEFAULT 'Success',
                    run_id TEXT,
                    timestamp TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Errors table
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    graph_url TEXT,
                    local_path TEXT,
                    error_message TEXT NOT NULL,
                    run_id TEXT,
                    timestamp TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Runs table for tracking pipeline executions
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT UNIQUE NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    status TEXT DEFAULT 'running',
                    total_items INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    csv_output TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_graphs_timestamp ON graphs(timestamp);
                CREATE INDEX IF NOT EXISTS idx_graphs_run_id ON graphs(run_id);
                CREATE INDEX IF NOT EXISTS idx_graphs_title ON graphs(title);
                CREATE INDEX IF NOT EXISTS idx_errors_run_id ON errors(run_id);
                CREATE INDEX IF NOT EXISTS idx_runs_run_id ON runs(run_id);
                CREATE INDEX IF NOT EXISTS idx_runs_start_time ON runs(start_time);
            """)
        logger.info("Database schema initialized: %s", self.db_path)

    # ==========================================================================
    # Graph Operations
    # ==========================================================================
    def save_graph(self, record: GraphRecord) -> int:
        """Save a graph record and return its ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO graphs (title, graph_url, local_path, description, run_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (record.title, record.graph_url, record.local_path,
                  record.description, record.run_id, record.timestamp))
            record_id = cursor.lastrowid
            logger.debug("Saved graph record: %s (ID: %d)", record.title, record_id)
            return record_id

    def get_all_graphs(self, limit: int = 1000) -> list[dict]:
        """Get all graph records."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM graphs ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_graphs_by_title(self, title: str) -> list[dict]:
        """Find graphs by title."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM graphs WHERE title = ? ORDER BY timestamp DESC",
                (title,)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_graphs_by_date_range(self, start: str, end: str) -> list[dict]:
        """Get graphs within a date range."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM graphs
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp DESC
            """, (start, end)).fetchall()
            return [dict(row) for row in rows]

    def get_graphs_by_run(self, run_id: str) -> list[dict]:
        """Get all graphs for a specific run."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM graphs WHERE run_id = ? ORDER BY timestamp",
                (run_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_recent_graphs(self, limit: int = 50) -> list[dict]:
        """Get most recent graphs."""
        return self.get_all_graphs(limit=limit)

    # ==========================================================================
    # Error Operations
    # ==========================================================================
    def save_error(self, record: ErrorRecord) -> int:
        """Save an error record and return its ID."""
        # Truncate error message if too long
        error_msg = record.error_message[:500] if record.error_message else ""

        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO errors (title, graph_url, local_path, error_message, run_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (record.title, record.graph_url, record.local_path,
                  error_msg, record.run_id, record.timestamp))
            record_id = cursor.lastrowid
            logger.debug("Saved error record: %s (ID: %d)", record.title, record_id)
            return record_id

    def get_all_errors(self, limit: int = 1000) -> list[dict]:
        """Get all error records."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM errors ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_errors_by_run(self, run_id: str) -> list[dict]:
        """Get all errors for a specific run."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM errors WHERE run_id = ? ORDER BY timestamp",
                (run_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    # ==========================================================================
    # Run Operations
    # ==========================================================================
    def start_run(self, run_id: str, total_items: int = 0) -> None:
        """Record the start of a pipeline run."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO runs (run_id, start_time, status, total_items)
                VALUES (?, ?, 'running', ?)
            """, (run_id, datetime.now().isoformat(), total_items))
        logger.info("Started run: %s", run_id)

    def end_run(self, run_id: str, success_count: int, fail_count: int,
                csv_output: str = "", status: str = "complete") -> None:
        """Record the end of a pipeline run."""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE runs
                SET end_time = ?, status = ?, success_count = ?, fail_count = ?, csv_output = ?
                WHERE run_id = ?
            """, (datetime.now().isoformat(), status, success_count, fail_count, csv_output, run_id))
        logger.info("Ended run: %s (success=%d, fail=%d)", run_id, success_count, fail_count)

    def get_run(self, run_id: str) -> dict | None:
        """Get a specific run."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?",
                (run_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_recent_runs(self, limit: int = 20) -> list[dict]:
        """Get most recent runs."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY start_time DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    # ==========================================================================
    # Statistics
    # ==========================================================================
    def get_statistics(self) -> dict:
        """Get overall statistics."""
        with self._get_connection() as conn:
            stats = {}

            # Total counts
            stats['total_graphs'] = conn.execute(
                "SELECT COUNT(*) FROM graphs"
            ).fetchone()[0]

            stats['total_errors'] = conn.execute(
                "SELECT COUNT(*) FROM errors"
            ).fetchone()[0]

            stats['total_runs'] = conn.execute(
                "SELECT COUNT(*) FROM runs"
            ).fetchone()[0]

            # Success rate
            total = stats['total_graphs'] + stats['total_errors']
            stats['success_rate'] = (
                (stats['total_graphs'] / total * 100) if total > 0 else 0
            )

            return stats


# ==========================================================================
# Backward Compatibility Layer
# ==========================================================================
# These functions maintain compatibility with existing code

_db_instance: Database | None = None

def _get_db() -> Database:
    """Get or create database singleton."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


def save_graph_info(title: str, graph_url: str, local_path: str,
                    description: str = "Success", run_id: str = "") -> bool:
    """Backward-compatible wrapper for save_graph."""
    try:
        record = GraphRecord(
            title=title,
            graph_url=graph_url,
            local_path=local_path,
            description=description,
            run_id=run_id
        )
        _get_db().save_graph(record)
        return True
    except Exception as e:
        logger.error("Failed to save graph info: %s", e)
        return False


def save_error(title: str, graph_url: str, local_path: str,
               error_message: str, run_id: str = "") -> bool:
    """Backward-compatible wrapper for save_error."""
    try:
        record = ErrorRecord(
            title=title,
            graph_url=graph_url,
            local_path=local_path,
            error_message=error_message,
            run_id=run_id
        )
        _get_db().save_error(record)
        return True
    except Exception as e:
        logger.error("Failed to save error: %s", e)
        return False


def get_all_graph_data() -> list[dict]:
    """Backward-compatible wrapper."""
    return _get_db().get_all_graphs()


def get_all_errors() -> list[dict]:
    """Backward-compatible wrapper."""
    return _get_db().get_all_errors()


def get_graph_by_title(title: str) -> list[dict]:
    """Backward-compatible wrapper."""
    return _get_db().get_graphs_by_title(title)


def get_recent_graphs(limit: int = 50) -> list[dict]:
    """Backward-compatible wrapper."""
    return _get_db().get_recent_graphs(limit)


# ==========================================================================
# CLI / Debug
# ==========================================================================
if __name__ == "__main__":
    from utils.logging_config import setup_logging
    setup_logging(app_name="database_cli")

    db = Database()
    print("Database initialized at:", db.db_path)
    print("Statistics:", db.get_statistics())

    # Test save
    test_record = GraphRecord(
        title="Test Graph",
        graph_url="http://example.com/graph",
        local_path="/path/to/graph.png",
        run_id="test-run"
    )
    record_id = db.save_graph(test_record)
    print(f"Saved test record with ID: {record_id}")

    # Test query
    print("Recent graphs:", db.get_recent_graphs(5))
