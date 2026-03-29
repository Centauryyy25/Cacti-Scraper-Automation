from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime

from utils.logging_config import setup_logging

# Set up logging
logger = logging.getLogger(__name__)

# Constants
STORAGE_DIR = "graph_data_storage"
GRAPH_DATA_FILE = os.path.join(STORAGE_DIR, "graph_data.json")
ERROR_LOG_FILE = os.path.join(STORAGE_DIR, "error_log.json")

def ensure_storage_dir():
    """Make sure the storage directory exists"""
    os.makedirs(STORAGE_DIR, exist_ok=True)

    # Create the data files if they don't exist
    for filepath in [GRAPH_DATA_FILE, ERROR_LOG_FILE]:
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                json.dump([], f)

    logger.info(f"Storage directory ready: {STORAGE_DIR}")

def load_data(filepath):
    """Load data from a JSON file"""
    try:
        if os.path.exists(filepath):
            with open(filepath) as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Error loading data from {filepath}: {str(e)}")
        return []

def save_data(data, filepath):
    """Save data to a JSON file"""
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving data to {filepath}: {str(e)}")
        return False

def save_graph_info(title: str, graph_url: str, local_path: str, description: str = "Success") -> bool:
    """Save graph information to the JSON storage."""
    ensure_storage_dir()

    # Create record
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = {
        "id": int(time.time() * 1000),  # millisecond timestamp as ID
        "title": title,
        "graph_url": graph_url,
        "local_path": local_path,
        "description": description,
        "timestamp": timestamp
    }

    # Load existing data
    data = load_data(GRAPH_DATA_FILE)

    # Add new record
    data.append(record)

    # Save updated data
    success = save_data(data, GRAPH_DATA_FILE)

    if success:
        logger.info(f"Graph info saved: {title}, {local_path}")
        return True
    else:
        logger.error(f"Failed to save graph info: {title}")
        return False

def save_error(title, graph_url, local_path, error_message):
    """
    Save error information to the error log file
    Replaces the handle_database_error function
    """
    ensure_storage_dir()

    # Create error record
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    error_record = {
        "id": int(time.time() * 1000),  # millisecond timestamp as ID
        "title": title,
        "graph_url": graph_url,
        "local_path": local_path,
        "error": error_message[:500],  # Limit error message length
        "timestamp": timestamp
    }

    # Load existing errors
    errors = load_data(ERROR_LOG_FILE)

    # Add new error
    errors.append(error_record)

    # Save updated error log
    success = save_data(errors, ERROR_LOG_FILE)

    if success:
        logger.info(f"Error saved for {title}")
        return True
    else:
        logger.error(f"Failed to save error for {title}")
        return False

def get_all_graph_data():
    """Retrieve all graph data"""
    ensure_storage_dir()
    return load_data(GRAPH_DATA_FILE)

def get_all_errors():
    """Retrieve all error records"""
    ensure_storage_dir()
    return load_data(ERROR_LOG_FILE)

def get_graph_by_title(title):
    """Find a graph by its title"""
    data = load_data(GRAPH_DATA_FILE)
    return [item for item in data if item["title"] == title]

def get_recent_graphs(limit=50):
    """Get the most recent graphs"""
    data = load_data(GRAPH_DATA_FILE)
    # Sort by timestamp descending
    sorted_data = sorted(data, key=lambda x: x.get("timestamp", ""), reverse=True)
    return sorted_data[:limit]

# For debug and testing
if __name__ == "__main__":
    setup_logging(app_name="graph_storage_cli")
    # Test saving graph info
    save_graph_info("Test Graph", "http://example.com/graph", "/path/to/local/graph.png")
    # Test saving error
    save_error("Error Graph", "http://example.com/error", "N/A", "Test error message")
    # Print all data
    print("Graph Data:", get_all_graph_data())
    print("Error Data:", get_all_errors())
