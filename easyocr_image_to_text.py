from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
from datetime import datetime

import cv2
import easyocr
import numpy as np

from progress_tracker import progress
from utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


def ensure_dir(directory: str) -> None:
    """Create directory if it does not exist."""
    if not os.path.exists(directory):
        os.makedirs(directory)


def fix_common_ocr_errors(text: str) -> str:
    """Fix common OCR misreads in extracted text."""
    # Fix decimal numbers split by space: 79. 00 => 79.00
    text = re.sub(r'(\d+)\.\s+(\d+)', r'\1.\2', text)
    text = re.sub(r'(\d+)\s+\.\s+(\d+)', r'\1.\2', text)
    text = re.sub(r'(\d+)\s+(\.\d+)', r'\1\2', text)

    text = re.sub(r'(?<=\d)\s(?=\d{2}\b)', '.', text)
    # Fix common OCR misreads in timestamps
    text = text.replace('OO', '00').replace('CO', '00').replace('O@', '00')

    return text


def clean_ocr_text(raw_text: str) -> dict:
    """Clean and parse raw OCR text into structured traffic data."""
    raw_text = fix_common_ocr_errors(raw_text)
    raw_text = ' '.join(raw_text.split())

    # Correction dictionary
    corrections = {
        r'\bQutbound\b': 'Outbound',
        r'\bQoutbound\b': 'Outbound',
        r'\bCurent\b': 'Current',
        r'\bCur ent\b': 'Current',
        r'\bCurant\b': 'Current',
        r'\bMarimum\b': 'Maximum',
        r'\bMaxinum\b': 'Maximum',
        r'\bMaxmum\b': 'Maximum',
        r'(\d{4})[-\s](\d{3,})': r'\1-\2',
        r'\bCutbound\b': 'Outbound',
        r'\bCur\s*ent\b': 'Current',
        r'\bFron\b': 'From',
        r'\bTo\b\s*(\d{4})\s*-\s*(\d{2})\s*-\s*(\d{2})': r'To \1-\2-\3',
        r'\bNeek\b': 'Week',
        r'\bWeek\s+1[45]\b': lambda m: m.group(0).replace(" ", ""),
        r'(\d)\s*\.\s*(\d)': r'\1.\2',
        r'(\d)\s*,\s*(\d)': r'\1.\2',
        r'(\d{2,4})\s*\.\s*(\d{3,5})': r'\1.\2',
        r'\bPo2o\b': '020',
        r'\bO0\b': '00',
        r'Maximum\s*;': 'Maximum:',
        r'Maximum(\d)': r'Maximum: \1',
        r'Maximum\s*(\d+\.\d+)': r'Maximum: \1',
        r'Average(\d)': r'Average: \1',
        r'Current(\d)': r'Current: \1',
        r'Average:\s*(\d+)\s+(\d+)': r'Average: \1.\2',
        r'Maximum\s+(\d+)\s+(\d+)': r'Maximum: \1.\2',
        r'\s*;\s*': '',
        r'~Pre\b': '',
        r'Od&': '00:00',
        r'(?<=Maximum\s)(\d{1,2})\b': lambda m: f"{int(m.group(1)) / 100:.2f}",
        r"'(\d{1,2})": lambda m: f"{int(m.group(1)) / 100:.2f}",
        r'H\s*Maximum': 'Maximum',
        r'Average:\s+1\.19\s+H': 'Average: 1.19 Maximum:',
        r'Maximum\s*\'?(\d{1,2})': lambda m: f"Maximum: {int(m.group(1)) / 100:.2f}",
        r':\s*O0': ': 00',
        r'Week\s+(\d{2})': r'Week\1',
        r'\bPozo\b': 'Vlan',
    }
    for pattern, repl in corrections.items():
        raw_text = re.sub(pattern, repl, raw_text, flags=re.IGNORECASE)

    result = {}

    vlan_service_match = re.search(r'(\d{3,4})-(\d{10,})', raw_text)
    if vlan_service_match:
        result['vlan_id'] = vlan_service_match.group(1).strip()
        result['service_id'] = vlan_service_match.group(2).strip()
    else:
        # Fallback for format xxxx.yyyy
        vlan_fallback_match = re.search(r'\d{3,4}\.\s*(\d{3,4})', raw_text)
        if vlan_fallback_match:
            result['vlan_id'] = vlan_fallback_match.group(1).strip()

    general_patterns = {
        'service_id': r'-(\d{10,})',
        'isp': r'isp-cust(?:-pre)?\s*(.*?)\s*\/',
        'period': r'From\s*(.*?)\s*To\s*(.*?)\s*Inbound',
        'vlan_id': r'(\d{3,4})\s*\.\s*(\d{3,4})'
    }


    for key, pattern in general_patterns.items():
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            if key == 'period':
                from_date = match.group(1).strip().replace(';', '').replace('QQ', '00')
                to_date = match.group(2).strip().replace(';', '').replace('QQ', '00')
                result[key] = {'from': from_date, 'to': to_date}
            else:
                result[key] = match.group(1).strip()


    def parse_traffic_data(text_chunk: str) -> dict:
        """Parse traffic statistics from a text block."""
        data = {}
        current_match = re.search(r'Current:?\s*(\d+(?:\.\d+)?(?:\s*[kM])?)', text_chunk, re.IGNORECASE)
        average_match = re.search(r'Average:?\s*(\d+(?:\.\d+)?(?:\s*[kM])?)', text_chunk, re.IGNORECASE)
        max_match = re.search(r'Maximum:?\s*(\d+(?:\.\d+)?(?:\s*[kM])?)', text_chunk, re.IGNORECASE)

        data['current'] = current_match.group(1).strip() if current_match else 'N/A'
        data['average'] = average_match.group(1).strip() if average_match else 'N/A'
        data['max'] = max_match.group(1).strip() if max_match else 'N/A'
        return data

    inbound_block_match = re.search(r'Inbound.*?(?=Outbound|$)', raw_text, re.IGNORECASE | re.DOTALL)
    outbound_block_match = re.search(r'Outbound.*', raw_text, re.IGNORECASE | re.DOTALL)

    if inbound_block_match:
        inbound_text = inbound_block_match.group(0)
        result['inbound'] = parse_traffic_data(inbound_text)

    if outbound_block_match:
        outbound_text = outbound_block_match.group(0)
        result['outbound'] = parse_traffic_data(outbound_text)

    logger.debug("--- Processed Text ---")
    logger.debug(raw_text)
    logger.debug("--- Extraction Results ---")
    logger.debug(result)
    logger.debug("--------------------------")

    if 'inbound' in result or 'outbound' in result:
        return result
    else:
        result['error'] = 'No Inbound/Outbound traffic data matched'
        result['raw_text'] = raw_text
        return result



def save_processed_data(data: dict, output_dir: str = "processed_output", custom_folder: str | None = None) -> str:
    """Save processed OCR data to a JSON file."""
    if custom_folder:
        # Create processed_output subfolder in timestamp folder
        final_output_dir = os.path.join(custom_folder, "processed_output")
    else:
        final_output_dir = output_dir

    ensure_dir(final_output_dir)

    filename = f"{final_output_dir}/processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f"Processed data saved to: {filename}")
    return filename


def preprocess_image(image_path: str, target_width: int = 2000) -> np.ndarray:
    """Preprocess image for better OCR accuracy."""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Image not found!")
    h, w = img.shape[:2]
    ratio = target_width / float(w)
    dim = (target_width, int(h * ratio))
    img = cv2.resize(img, dim, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # Denoising
    img = cv2.fastNlMeansDenoising(img, h=10)

    # Apply sharpening kernel
    kernel = np.array([[0, -1, 0],
                    [-1, 5,-1],
                    [0, -1, 0]])
    img = cv2.filter2D(img, -1, kernel)

    return img


def image_to_text(image_path: str, languages: list[str] | None = None, use_gpu: bool = False) -> str:
    """Extract text from an image using EasyOCR."""
    if languages is None:
        languages = ['en']
    progress.ocr['current_file'] = os.path.basename(image_path)
    progress.ocr['message'] = f'Processing {progress.ocr["current_file"]}'

    if not hasattr(image_to_text, 'reader'):
        progress.ocr['message'] = 'Initializing OCR model...'
        image_to_text.reader = easyocr.Reader(
            languages,
            gpu=use_gpu,
            model_storage_directory='./models',
            download_enabled=True
        )
    processed_img = preprocess_image(image_path)
    results = image_to_text.reader.readtext(
        processed_img,
        decoder='greedy',
        batch_size=4,
        paragraph=False,
        detail=0
    )
    progress.ocr['message'] = f'Finished processing {progress.ocr["current_file"]}'
    return " ".join(results)


def process_images_in_folder(folder: str, output_dir: str, lang: str, use_gpu: bool) -> dict:
    """Process all images in a folder and return OCR results."""
    supported_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
    files = [f for f in os.listdir(folder) if f.lower().endswith(supported_exts)]

    progress.ocr.update({
    'current': 0,
    'total': len(files),
    'status': 'running',
    'message': 'Preparing OCR processing...',
    'current_file': ''
    })

    all_results = {}
    for i, filename in enumerate(files, 1):
        progress.ocr.update({
            'current': i,
            'total': len(files),
            'status': 'running',
            'message': 'Preparing OCR processing...',
            'current_file': ''
        })

        img_path = os.path.join(folder, filename)
        try:
            extracted_text = image_to_text(img_path, lang.split(','), use_gpu)
            cleaned_data = clean_ocr_text(extracted_text)
            all_results[os.path.splitext(filename)[0]] = cleaned_data
        except Exception as e:
            progress.ocr['message'] = f'Error processing {filename}: {str(e)}'
            continue

    progress.ocr['status'] = 'complete'
    return all_results


def convert_json_to_csv(json_file_path: str, csv_file_path: str, custom_folder: str | None = None) -> str:
    """Convert OCR JSON results to CSV format."""
    # Use custom folder if provided
    if custom_folder:
        csv_filename = os.path.basename(csv_file_path)
        csv_file_path = os.path.join(custom_folder, csv_filename)

    # Ensure directory exists
    ensure_dir(os.path.dirname(csv_file_path))

    # Read JSON file
    with open(json_file_path, encoding='utf-8') as file:
        data = json.load(file)

    # Open CSV file and write header
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'ID', 'ISP', 'VLAN ID', 'Service ID',
            'Inbound Current', 'Inbound Average', 'Inbound Max',
            'Outbound Current', 'Outbound Average', 'Outbound Max',
            'Period From', 'Period To'
        ]


        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # Write one row per item
        for key, value in data.items():
            writer.writerow({
                'ID': key,
                'Service ID': value.get('service_id', ''),
                'ISP': value.get('isp', ''),
                'VLAN ID': value.get('vlan_id', ''),
                'Inbound Current': value.get('inbound', {}).get('current', ''),
                'Inbound Average': value.get('inbound', {}).get('average', ''),
                'Inbound Max': value.get('inbound', {}).get('max', ''),
                'Outbound Current': value.get('outbound', {}).get('current', ''),
                'Outbound Average': value.get('outbound', {}).get('average', ''),
                'Outbound Max': value.get('outbound', {}).get('max', ''),
                'Period From': value.get('period', {}).get('from', ''),
                'Period To': value.get('period', {}).get('to', ''),
            })

    logger.info(f"CSV file saved to: {os.path.abspath(csv_file_path)}")
    return csv_file_path


def process_images_and_save_csv(folder: str, custom_output_folder: str, lang: str = 'en', use_gpu: bool = False) -> str | None:
    """Process images and save results as CSV."""
    # Run OCR
    all_results = process_images_in_folder(folder, "processed_output", lang, use_gpu)

    if not all_results:
        logger.warning("No OCR results obtained")
        return None

    # Save JSON to processed_output subfolder
    json_output_dir = os.path.join(custom_output_folder, "processed_output")
    json_path = save_processed_data(all_results, json_output_dir)

    # Generate CSV filename from folder timestamp
    folder_name = os.path.basename(custom_output_folder)
    csv_filename = f"traffic_{folder_name}.csv"

    # Save CSV directly to timestamp folder
    csv_path = convert_json_to_csv(json_path, csv_filename, custom_folder=custom_output_folder)

    logger.info(f"CSV file saved to: {csv_path}")
    return csv_path


def process_images_in_folder_with_custom_output(folder: str, custom_output_folder: str, lang: str = 'en', use_gpu: bool = False) -> tuple[dict, str, str]:
    """Process images with output directed to a custom folder."""
    supported_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
    files = [f for f in os.listdir(folder) if f.lower().endswith(supported_exts)]

    progress.ocr.update({
        'current': 0,
        'total': len(files),
        'status': 'running',
        'message': 'Preparing OCR processing...',
        'current_file': ''
    })

    all_results = {}

    for i, filename in enumerate(files, 1):
        progress.ocr.update({
            'current': i,
            'total': len(files),
            'status': 'running',
            'message': f'Processing {filename}...',
            'current_file': filename
        })

        img_path = os.path.join(folder, filename)
        try:
            extracted_text = image_to_text(img_path, lang.split(','), use_gpu)
            cleaned_data = clean_ocr_text(extracted_text)
            all_results[os.path.splitext(filename)[0]] = cleaned_data
            logger.info(f"Successfully processed: {filename}")
        except Exception as e:
            progress.ocr['message'] = f'Error processing {filename}: {str(e)}'
            logger.error(f"Failed to process {filename}: {e}")
            continue

    progress.ocr['status'] = 'complete'

    # Save results to custom folder
    json_path = save_processed_data(all_results, custom_folder=custom_output_folder)

    # Generate CSV filename from folder timestamp
    folder_name = os.path.basename(custom_output_folder)
    csv_filename = f"traffic_{folder_name}.csv"
    csv_path = convert_json_to_csv(json_path, csv_filename, custom_folder=custom_output_folder)

    return all_results, json_path, csv_path

if __name__ == "__main__":
    setup_logging(app_name="easyocr_cli")
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, help="Path to a single image")
    parser.add_argument("--folder", type=str, help="Path to folder containing images")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory")
    parser.add_argument("--lang", type=str, default="en", help="OCR language(s) (e.g. 'en,id')")
    parser.add_argument("--gpu", action="store_true", help="Use GPU if available")
    args = parser.parse_args()

    all_results = {}

    # Run OCR processing
    if args.folder:
        supported_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
        for filename in os.listdir(args.folder):
            if filename.lower().endswith(supported_exts):
                img_path = os.path.join(args.folder, filename)
                logger.info(f"Processing: {filename}")
                try:
                    extracted_text = image_to_text(img_path, args.lang.split(','), args.gpu)
                    cleaned_data = clean_ocr_text(extracted_text)
                    all_results[os.path.splitext(filename)[0]] = cleaned_data
                except Exception as e:
                    logger.error(f"Failed to process {filename}: {e}")
    elif args.image:
        logger.info(f"Processing: {args.image}")
        extracted_text = image_to_text(args.image, args.lang.split(','), args.gpu)
        cleaned_data = clean_ocr_text(extracted_text)
        all_results[os.path.splitext(os.path.basename(args.image))[0]] = cleaned_data
    else:
        logger.error("Please provide --image or --folder")
        exit(1)

    # 1. Save JSON and get its path
    json_path = save_processed_data(all_results, args.output_dir)

    # 2. Generate CSV filename automatically
    csv_filename = f"converted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    csv_path = os.path.join(args.output_dir, csv_filename)

    # 3. Convert JSON to CSV
    logger.info("Starting JSON to CSV conversion...")
    try:
        convert_json_to_csv(json_path, csv_path)
        logger.info(f"CSV saved to: {csv_path}")
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
