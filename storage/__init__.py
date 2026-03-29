"""Storage package initialization."""

from __future__ import annotations

from storage.database import (
    Database,
    ErrorRecord,
    GraphRecord,
    get_all_errors,
    get_all_graph_data,
    get_graph_by_title,
    get_recent_graphs,
    save_error,
    save_graph_info,
)

__all__ = [
    "Database",
    "GraphRecord",
    "ErrorRecord",
    "save_graph_info",
    "save_error",
    "get_all_graph_data",
    "get_all_errors",
    "get_graph_by_title",
    "get_recent_graphs",
]
