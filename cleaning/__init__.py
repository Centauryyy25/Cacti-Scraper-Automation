"""Cleaning package: CSV post-processing utilities.

Provides:
- unit_converter: Intelligent bandwidth unit detection and conversion
- csv_generator: Generate 3 CSV variants (original, Mbps, Kbps)
"""

from __future__ import annotations

from cleaning.csv_generator import (
    BANDWIDTH_COLUMNS,
    generate_all_csv_variants,
    process_csv,
    process_ocr_output_to_csv,
)
from cleaning.unit_converter import (
    BandwidthUnit,
    ParsedValue,
    convert_dataframe_to_kbps,
    convert_dataframe_to_mbps,
    convert_to_unit,
    convert_value_to_kbps,
    convert_value_to_mbps,
    parse_bandwidth_value,
)

__all__ = [
    # Unit converter
    'BandwidthUnit',
    'ParsedValue',
    'parse_bandwidth_value',
    'convert_to_unit',
    'convert_value_to_mbps',
    'convert_value_to_kbps',
    'convert_dataframe_to_mbps',
    'convert_dataframe_to_kbps',
    # CSV generator
    'generate_all_csv_variants',
    'process_ocr_output_to_csv',
    'process_csv',
    'BANDWIDTH_COLUMNS',
]
