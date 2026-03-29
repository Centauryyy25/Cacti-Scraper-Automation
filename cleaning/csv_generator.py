"""CSV Generator - Produces 3 variants of output CSV.

Generates:
1. traffic_original.csv - Raw values as extracted from OCR
2. traffic_mbps.csv - All bandwidth values converted to Mbps
3. traffic_kbps.csv - All bandwidth values converted to Kbps

Uses intelligent unit detection from unit_converter module.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

from cleaning.unit_converter import (
    convert_dataframe_to_kbps,
    convert_dataframe_to_mbps,
)

logger = logging.getLogger(__name__)

# Columns containing bandwidth values
BANDWIDTH_COLUMNS = [
    'Inbound Current', 'Inbound Average', 'Inbound Max',
    'Outbound Current', 'Outbound Average', 'Outbound Max'
]


def generate_all_csv_variants(
    source_csv: str,
    output_dir: str = None
) -> tuple[str, str, str]:
    """
    Generate all 3 CSV variants from a source CSV file.

    Args:
        source_csv: Path to the original CSV from OCR
        output_dir: Directory to save output files. Defaults to same as source.

    Returns:
        Tuple of (original_path, mbps_path, kbps_path)
    """
    source_path = Path(source_csv)

    if output_dir is None:
        output_dir = source_path.parent
    else:
        os.makedirs(output_dir, exist_ok=True)

    # Read source CSV
    logger.info("Reading source CSV: %s", source_csv)
    df = pd.read_csv(source_csv)

    # Columns to remove from converted CSVs
    COLUMNS_TO_REMOVE = ['ISP', 'VLAN ID', 'Service ID', 'Inbound Current', 'Outbound Current']

    # Get timestamp from source filename if present
    base_name = source_path.stem
    if base_name.startswith('traffic_'):
        timestamp_part = base_name.replace('traffic_', '')
    else:
        timestamp_part = base_name

    # Generate output paths
    original_path = os.path.join(output_dir, f"traffic_original_{timestamp_part}.csv")
    mbps_path = os.path.join(output_dir, f"traffic_mbps_{timestamp_part}.csv")
    kbps_path = os.path.join(output_dir, f"traffic_kbps_{timestamp_part}.csv")

    # 1. Save original (copy)
    df.to_csv(original_path, index=False)
    logger.info("Saved original CSV: %s", original_path)

    # 2. Convert to Mbps
    df_mbps = convert_dataframe_to_mbps(df.copy(), BANDWIDTH_COLUMNS)
    # Remove unwanted columns
    df_mbps = df_mbps.drop(columns=[c for c in COLUMNS_TO_REMOVE if c in df_mbps.columns], errors='ignore')
    # Round and add unit suffix
    for col in BANDWIDTH_COLUMNS:
        if col in df_mbps.columns:
            df_mbps[col] = df_mbps[col].apply(lambda x: f"{x:.2f} Mbps" if pd.notna(x) and x != 0 else "0 Mbps")
    df_mbps.to_csv(mbps_path, index=False)
    logger.info("Saved Mbps CSV: %s", mbps_path)

    # 3. Convert to Kbps
    df_kbps = convert_dataframe_to_kbps(df.copy(), BANDWIDTH_COLUMNS)
    # Remove unwanted columns
    df_kbps = df_kbps.drop(columns=[c for c in COLUMNS_TO_REMOVE if c in df_kbps.columns], errors='ignore')
    # Round and add unit suffix
    for col in BANDWIDTH_COLUMNS:
        if col in df_kbps.columns:
            df_kbps[col] = df_kbps[col].apply(lambda x: f"{int(round(x))} Kbps" if pd.notna(x) and x != 0 else "0 Kbps")
    df_kbps.to_csv(kbps_path, index=False)
    logger.info("Saved Kbps CSV: %s", kbps_path)

    return original_path, mbps_path, kbps_path


def process_ocr_output_to_csv(
    original_csv: str,
    output_dir: str = None
) -> dict[str, str]:
    """
    Process OCR output CSV and generate all 3 variants.

    Args:
        original_csv: Path to the original CSV from OCR
        output_dir: Output directory (defaults to same as source)

    Returns:
        Dictionary with keys 'original', 'mbps', 'kbps' and their paths
    """
    try:
        original_path, mbps_path, kbps_path = generate_all_csv_variants(
            original_csv, output_dir
        )

        return {
            'original': original_path,
            'mbps': mbps_path,
            'kbps': kbps_path
        }

    except Exception as e:
        logger.error("Failed to generate CSV variants: %s", e)
        raise


# ==========================================================================
# Legacy compatibility - replaces old process_csv function
# ==========================================================================
def process_csv(input_file: str, output_file: str = None) -> dict[str, str]:
    """
    Process CSV with unit conversion.

    This is a backward-compatible wrapper that now generates all 3 variants.

    Args:
        input_file: Input CSV path
        output_file: Ignored (for backward compatibility)

    Returns:
        Dictionary with paths to all 3 generated files
    """
    output_dir = os.path.dirname(input_file)
    return process_ocr_output_to_csv(input_file, output_dir)


__all__ = [
    'generate_all_csv_variants',
    'process_ocr_output_to_csv',
    'process_csv',
    'BANDWIDTH_COLUMNS'
]
