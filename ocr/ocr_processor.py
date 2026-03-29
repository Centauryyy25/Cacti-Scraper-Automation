"""Wrapper module to expose OCR utilities via the ocr package.

This preserves backward compatibility while providing a structured import path.
"""

from __future__ import annotations

from easyocr_image_to_text import (
    clean_ocr_text,
    convert_json_to_csv,
    image_to_text,
    process_images_in_folder,
    process_images_in_folder_with_custom_output,
    save_processed_data,
)

__all__ = [
    "image_to_text",
    "process_images_in_folder",
    "clean_ocr_text",
    "save_processed_data",
    "convert_json_to_csv",
    "process_images_in_folder_with_custom_output",
]

