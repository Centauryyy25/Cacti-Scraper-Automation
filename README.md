# Cacti NMS Pipeline

Automated network traffic data extraction from Cacti NMS using Selenium, EasyOCR, and intelligent unit conversion.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0+-green?logo=flask)
![Selenium](https://img.shields.io/badge/Selenium-4.15+-orange?logo=selenium)
![EasyOCR](https://img.shields.io/badge/EasyOCR-1.7+-purple)
![License](https://img.shields.io/badge/License-MIT-yellow)
![CI](https://github.com/Centauryyy25/cacti-automation-indonesia/actions/workflows/ci.yml/badge.svg)

---

## Architecture

```
                    Cacti NMS
                        |
           Step 1: Selenium Scraper
           (login, navigate, screenshot)
                        |
                 raw_screenshots/
                        |
            Step 2: EasyOCR Processing
            (preprocess, extract, parse)
                        |
              processed_output/*.json
                        |
           Step 3: CSV Generation
           (unit detection & conversion)
                        |
        traffic_original.csv  traffic_mbps.csv  traffic_kbps.csv
```

## Features

- **Automated scraping** of Cacti NMS traffic graphs via Selenium with configurable headless mode
- **OCR text extraction** using EasyOCR with image preprocessing for improved accuracy
- **Intelligent unit conversion** with automatic bandwidth unit detection (bps, Kbps, Mbps)
- **Three CSV output variants**: original values, normalized to Mbps, normalized to Kbps
- **Web dashboard** built with Flask for one-click pipeline execution with real-time progress
- **Observability** via Prometheus metrics endpoint, structured logging, and pipeline summaries

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Web Framework | Flask + Flask-CORS |
| Scraping | Selenium + ChromeDriver |
| OCR | EasyOCR + OpenCV |
| Data Processing | Pandas + NumPy |
| Configuration | Pydantic Settings |
| Database | SQLite (pipeline metadata) |
| CI/CD | GitHub Actions (ruff + pytest) |

## Project Structure

```
cacti-nms-pipeline/
├── web/                    # Flask web application
├── scraping/               # Selenium scraper module
├── ocr/                    # OCR processing (parallel support)
├── cleaning/               # CSV generation & unit conversion
├── storage/                # SQLite database layer
├── observability/          # Prometheus metrics
├── services/               # Email & Slack notifications
├── tracking/               # Progress tracking for UI
├── utils/                  # Logging, retry, summary parser
├── templates/              # HTML templates (dashboard, logs, summary)
├── tests/                  # Unit tests
├── config.py               # Pydantic-based configuration
├── main_pipeline.py        # 3-step pipeline orchestrator
├── easyocr_image_to_text.py # OCR extraction engine
└── graph_storage.py        # JSON-based graph data storage
```

## Getting Started

### Prerequisites

- Python 3.10+
- Chrome or Chromium browser
- ChromeDriver (auto-managed by `webdriver-manager`)

### Installation

```bash
# Clone the repository
git clone https://github.com/Centauryyy25/cacti-automation-indonesia.git
cd cacti-automation-indonesia

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your Cacti NMS credentials and server URL
```

### Usage

#### Web Dashboard

```bash
python -m web.app
# Open http://localhost:5000
```

1. Enter your Cacti NMS URL, credentials, and device names
2. Select the date range
3. Click **Run Pipeline**
4. Download results in your preferred format (Original / Mbps / Kbps)

#### CLI

```bash
# Run the full pipeline
python main_pipeline.py

# Run OCR only on existing screenshots
python easyocr_image_to_text.py --folder output/<timestamp>/raw_screenshots
```

## Output

After a pipeline run, results are saved to `output/<timestamp>/`:

```
output/2026-01-03_14-30-00/
├── raw_screenshots/            # Scraped graph images
├── processed_output/           # OCR results (JSON)
├── traffic_original_*.csv      # Raw extracted values
├── traffic_mbps_*.csv          # All values in Mbps
├── traffic_kbps_*.csv          # All values in Kbps
├── summary.json                # Machine-readable run summary
└── summary.log                 # Human-readable run summary
```

## Testing

```bash
# Run all tests
python -m pytest

# With coverage report
python -m pytest --cov=. --cov-report=term-missing

# Run specific test file
python -m pytest tests/test_database.py -v
```

## Docker

```bash
docker-compose up -d
# Open http://localhost:5000
```

## Configuration Reference

See [`.env.example`](.env.example) for all available configuration options including:

- Cacti NMS URL and credentials
- Selenium headless mode and timeouts
- OCR settings (GPU, batch size, languages)
- Retry configuration with exponential backoff
- CORS origins and web server settings

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
