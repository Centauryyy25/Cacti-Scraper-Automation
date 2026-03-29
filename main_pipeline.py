"""Orchestrates the 3-step pipeline: scrape -> OCR -> CSV cleaning.

Outputs are stored under `output/<timestamp>/` with:
- raw_screenshots/: raw scraped images
- processed_output/: OCR JSONs
- traffic_<timestamp>.csv and traffic_mbps_<timestamp>.csv
- summary.log and summary.json
"""

from __future__ import annotations

import csv as _csv
import glob
import logging
import os
import time
from datetime import datetime

from cleaning.csv_generator import generate_all_csv_variants
from ocr.ocr_processor import process_images_in_folder_with_custom_output
from scraping.scraper import login_and_scrape
from tracking.progress import progress
from utils.logging_config import setup_logging

logger = logging.getLogger(__name__)

def step1_scrape_images(
    date1: str = "2025-03-01 00:00",
    date2: str = "2025-04-01 00:00",
    target_url: str = "",
    user_login: str = "",
    user_pass: str = "",
    usernames: list[str] | str = "",
) -> None:
    """Step 1: Scrape traffic graph images from Cacti NMS."""
    logger.info("STEP 1: Scraping traffic graph images...")

    # Create timestamped output folder
    now = datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d_%H-%M-%S")
    # Track run start time and input size
    try:
        progress.scraping['start_time'] = now.isoformat(timespec='seconds')
        if isinstance(usernames, list):
            progress.scraping['usernames_count'] = len(usernames)
        else:
            progress.scraping['usernames_count'] = 0
    except Exception:
        pass

    base_output = os.path.abspath(os.path.join("output", timestamp_str))
    images_dir = os.path.join(base_output, "raw_screenshots")
    os.makedirs(images_dir, exist_ok=True)

    progress.scraping['current_folder'] = base_output

    logger.info("Output folder: %s", base_output)

    login_and_scrape(
        date1, date2, target_url, user_login, user_pass, usernames, custom_folder=images_dir
    )

    logger.info("Scraping complete. Images saved to: %s", images_dir)


def step2_ocr_images(folder: str | None = None, csv_output: str | None = None):
    """Step 2: Run OCR on scraped images."""
    base_output = progress.scraping.get('current_folder')
    # If a base output folder is passed, prefer its raw_screenshots subfolder
    folder_to_process = folder or (os.path.join(base_output, "raw_screenshots") if base_output else None)
    if folder_to_process and os.path.isdir(folder_to_process):
        # If the provided folder is the base output, redirect to raw_screenshots
        if os.path.basename(folder_to_process) != "raw_screenshots":
            candidate = os.path.join(folder_to_process, "raw_screenshots")
            if os.path.isdir(candidate):
                folder_to_process = candidate

    if not folder_to_process:
        logger.error("No target folder for OCR. Run Step 1 first.")
        progress.ocr.update({'status': 'error', 'message': 'Target folder not found.'})
        return None

    logger.info("STEP 2: Running OCR on images in: %s", folder_to_process)

    if not os.path.exists(folder_to_process):
        logger.error("Folder %s not found!", folder_to_process)
        return

    images = []
    for ext in ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG']:
        images.extend([f for f in os.listdir(folder_to_process) if f.endswith(ext)])

    if not images:
        logger.warning("No images found in folder %s", folder_to_process)
        logger.debug("Isi folder: %s", os.listdir(folder_to_process))
        return

    logger.info("Found %d images for OCR processing", len(images))
    logger.info("Results will be saved to: %s", folder_to_process)

    try:
        logger.info("Starting OCR with EasyOCR...")

        progress.ocr.update({
            'current': 0,
            'total': len(images),
            'status': 'running',
            'message': f'Starting OCR for {len(images)} images...'
        })

        all_results, json_path, csv_path = process_images_in_folder_with_custom_output(
            folder=folder_to_process,
            custom_output_folder=base_output or os.path.dirname(folder_to_process),
            lang="en",
            use_gpu=False,
        )

        logger.info("OCR complete. Processed %d images", len(all_results))

        progress.ocr.update({'status': 'complete', 'message': 'OCR processing complete!'})

        logger.info("JSON file saved to: %s", json_path)
        logger.info("CSV file saved to: %s", csv_path)

        return csv_path

    except ImportError as e:
        logger.error("Import error: %s", e)
        logger.error("Ensure easyocr_image_to_text.py is in the project directory")
        return None

    except Exception as e:
        logger.error("OCR processing error: %s", e)
        progress.ocr.update({'status': 'error', 'message': f'Error: {str(e)}'})
        return None


def step3_clean_csv(csv_input: str | None = None, csv_output: str | None = None):
    """Generate 3 CSV variants: original, Mbps, and Kbps.

    Output files:
    - traffic_original_<timestamp>.csv - Raw values as extracted
    - traffic_mbps_<timestamp>.csv - All bandwidth values in Mbps
    - traffic_kbps_<timestamp>.csv - All bandwidth values in Kbps
    """
    active_folder = progress.scraping.get('current_folder')

    if csv_input is None and active_folder:
        folder_name = os.path.basename(active_folder)
        csv_input = os.path.join(active_folder, f"traffic_{folder_name}.csv")
    elif csv_input is None:
        return "[ERROR] No input CSV file or active folder found."

    logger.info("STEP 3: Generating 3 CSV variants (Original, Mbps, Kbps)")
    logger.info("Input file: %s", csv_input)

    if not os.path.exists(csv_input):
        logger.error("File %s not found!", csv_input)
        return

    try:
        # Generate all 3 CSV variants using the new generator
        # Returns tuple: (original_path, mbps_path, kbps_path)
        original_csv, mbps_csv, kbps_csv = generate_all_csv_variants(csv_input, active_folder)

        logger.info("Generated CSV files:")
        logger.info("  Original: %s", original_csv)
        logger.info("  Mbps:     %s", mbps_csv)
        logger.info("  Kbps:     %s", kbps_csv)

        # For backward compatibility, set csv_output to mbps version
        csv_output = mbps_csv

        # Generate summary.log and summary.json
        try:
            images_dir = os.path.join(active_folder, "raw_screenshots")
            scraped = len([f for f in os.listdir(images_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]) if os.path.exists(images_dir) else 0

            # Find latest processed_*.json to count OCR results
            processed_dir = os.path.join(active_folder, "processed_output")
            json_files = sorted(glob.glob(os.path.join(processed_dir, "processed_*.json")), reverse=True)
            ocr_count = 0
            if json_files:
                import json as _json
                with open(json_files[0], encoding="utf-8") as jf:
                    data = _json.load(jf)
                    if isinstance(data, dict):
                        ocr_count = len(data)

            # Count cleaned CSV rows (excluding header)
            cleaned_rows = 0
            with open(csv_output, newline="", encoding="utf-8") as cf:
                reader = _csv.reader(cf)
                cleaned_rows = sum(1 for _ in reader) - 1

            summary_path = os.path.join(active_folder, "summary.log")
            with open(summary_path, "w", encoding="utf-8") as sf:
                sf.write(f"Scraping timestamp: {os.path.basename(active_folder)}\n")
                sf.write(f"Raw images scraped: {scraped}\n")
                sf.write(f"OCR items processed: {ocr_count}\n")
                sf.write(f"Cleaned CSV rows: {max(cleaned_rows, 0)}\n")
                sf.write(f"CSV output: {csv_output}\n")

            logger.info("Summary saved to: %s", summary_path)

            # Build machine-readable summary.json for dashboard
            try:
                import json as _json
                run_id = os.path.basename(active_folder) if active_folder else datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                # Parse optional scraping_report.txt for success/fail and reasons
                report_path = os.path.join(os.path.dirname(__file__), 'scraping_report.txt')
                success_count = None
                fail_count = None
                fail_reasons = []
                if os.path.exists(report_path):
                    try:
                        with open(report_path, encoding='utf-8') as rf:
                            for line in rf:
                                line = line.strip()
                                if line.startswith('Successful:'):
                                    try:
                                        success_count = int(line.split(':',1)[1].strip())
                                    except Exception:
                                        pass
                                elif line.startswith('Failed:'):
                                    try:
                                        fail_count = int(line.split(':',1)[1].strip())
                                    except Exception:
                                        pass
                                elif ':' in line and not line.upper().startswith(('SCRAPING REPORT','DATE RANGE','TOTAL USERNAMES','UNPROCESSED USERNAMES','ERROR DETAILS')):
                                    # Likely an error detail row like "username: message"
                                    try:
                                        reason = line.split(':',1)[1].strip()
                                        if reason:
                                            fail_reasons.append(reason)
                                    except Exception:
                                        pass
                    except Exception:
                        pass
                # Fallbacks if report missing
                total_usernames = progress.scraping.get('usernames_count') or scraped
                if success_count is None and fail_count is None:
                    # Approximate: assume each saved image indicates success
                    success_count = ocr_count if isinstance(ocr_count, int) else 0
                    fail_count = max(total_usernames - success_count, 0)
                summary_json = {
                    'run_id': run_id,
                    'total_items': int(total_usernames),
                    'success_count': int(success_count),
                    'fail_count': int(fail_count),
                    'fail_reasons': sorted(set(fail_reasons))[:25],
                    'start_time': progress.scraping.get('start_time'),
                    'end_time': datetime.now().isoformat(timespec='seconds'),
                    'raw_images_scraped': int(scraped),
                    'ocr_items_processed': int(ocr_count),
                    'cleaned_csv_rows': int(max(cleaned_rows, 0)),
                    'csv_output': csv_output,
                }
                with open(os.path.join(active_folder, 'summary.json'), 'w', encoding='utf-8') as jf:
                    _json.dump(summary_json, jf, ensure_ascii=False, indent=2)
                logger.info("summary.json saved")
            except Exception as _e:
                logger.warning(f"Failed to write summary.json: {_e}")

        except Exception as e:  # summary failures shouldn't break pipeline
            logger.warning("Failed to create summary.log: %s", e)

        return csv_output
    except ImportError:
        logger.error("Module data_cleaner not found!")
        return None


if __name__ == "__main__":
    setup_logging(app_name="pipeline")
    start = time.time()

    step1_scrape_images()
    step2_ocr_images()
    step3_clean_csv()

    logger.info("Pipeline completed in %.2f seconds.", time.time() - start)
