# Cacti Scraper Automation

Automated network traffic data extraction pipeline for [Cacti NMS](https://www.cacti.net/). Scrapes traffic graphs via Selenium, extracts bandwidth values using OCR, and outputs clean CSV reports in multiple unit formats.

Built to replace hours of manual screenshot-and-copy workflows with a single command or web UI trigger.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0+-000000?logo=flask)
![Selenium](https://img.shields.io/badge/Selenium-Headless-43B02A?logo=selenium&logoColor=white)
![EasyOCR](https://img.shields.io/badge/EasyOCR-Text_Extraction-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![CI](https://img.shields.io/github/actions/workflow/status/Centauryyy25/netflow-automation/ci.yml?label=CI&logo=githubactions&logoColor=white)

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────────────┐
│  Cacti NMS   │────▶│  Selenium     │────▶│  EasyOCR     │────▶│  CSV Generator │
│  Web UI      │     │  Scraper      │     │  Processor   │     │  (3 formats)   │
└─────────────┘     └──────────────┘     └──────────────┘     └────────────────┘
       │                    │                    │                      │
       │              raw_screenshots/     processed_output/     hasil_*.csv
       │                                                        (original/mbps/kbps)
       ▼
  Flask Dashboard (localhost:5000)
  - Configure targets & date ranges
  - Trigger pipeline runs
  - Download results
```

## Features

- **Automated scraping** — Logs into Cacti NMS, navigates to traffic graphs, captures screenshots for specified devices and date ranges using headless Chrome.
- **OCR extraction** — Processes graph screenshots with EasyOCR to extract bandwidth values (inbound/outbound traffic, peak/average).
- **Multi-format output** — Generates three CSV variants per run: original values, normalized to Mbps, and normalized to Kbps.
- **Web dashboard** — Flask-based UI for configuring scrape parameters, monitoring progress in real-time, and downloading results.
- **Run tracking** — Each pipeline run is timestamped and produces a `summary.json` with success/failure counts, timing, and output paths.
- **Configurable retries** — Exponential backoff for flaky network requests, configurable timeouts and retry limits.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Scraping | Selenium + ChromeDriver (auto-managed via `webdriver-manager`) |
| OCR | EasyOCR (CPU or GPU) |
| Web UI | Flask 3.x + Jinja2 templates |
| Data Processing | Python `csv` module, custom unit converters |
| Configuration | python-dotenv, environment variables |
| Testing | pytest + pytest-cov |

## Project Structure

```
netflow-automation/
├── .github/
│   └── workflows/
│       └── ci.yml              # Lint + test pipeline
├── web/                        # Flask application & routes
├── scraping/                   # Selenium-based Cacti scraper
├── ocr/                        # EasyOCR image processing
├── cleaning/                   # CSV generation & unit conversion
├── tracking/                   # Pipeline progress tracker
├── observability/              # Logging & monitoring utilities
├── services/                   # Shared service layer
├── storage/                    # File storage abstractions
├── utils/                      # Logging config, helpers
├── templates/                  # Jinja2 HTML templates
├── tests/                      # Unit & integration tests
├── main_pipeline.py            # Pipeline orchestrator (scrape → OCR → CSV)
├── config.py                   # Centralized configuration
├── pyproject.toml              # Project metadata & tool config
├── requirements.txt            # Python dependencies
└── .env.example                # Environment template (copy to .env)
```

## Getting Started

### Prerequisites

- Python 3.10+
- Google Chrome or Chromium
- ChromeDriver (auto-installed by `webdriver-manager`)

### Installation

```bash
# Clone the repository
git clone https://github.com/Centauryyy25/netflow-automation.git
cd netflow-automation

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Cacti NMS credentials
```

### Usage

**Option A — Web Dashboard**

```bash
python -m web.app
# Open http://localhost:5000
```

1. Enter your Cacti target URL, credentials, and device names.
2. Select a date range.
3. Click **Run Pipeline** and monitor progress.
4. Download results in your preferred format (Original / Mbps / Kbps).

**Option B — CLI**

```bash
python main_pipeline.py
```

The pipeline runs all three steps sequentially: scrape → OCR → CSV generation.

### Output

Each run creates a timestamped directory under `output/`:

```
output/2026-01-03_14-30-00/
├── raw_screenshots/        # Captured traffic graph images
├── processed_output/       # OCR results (JSON)
├── hasil_original_*.csv    # Raw extracted values
├── hasil_mbps_*.csv        # Bandwidth in Mbps
├── hasil_kbps_*.csv        # Bandwidth in Kbps
└── summary.json            # Run metadata & statistics
```

## Testing

```bash
# Run all tests
python -m pytest

# Run with coverage report
python -m pytest --cov=. --cov-report=term-missing

# Run specific test module
python -m pytest tests/test_cleaning.py -v
```

## Docker

```bash
docker-compose up -d
# Dashboard available at http://localhost:5000
```

## Configuration

All configuration is managed through environment variables. See [`.env.example`](.env.example) for the full list of available options including Selenium timeouts, OCR settings, and retry behavior.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

Please ensure all tests pass and code follows the project's linting rules before submitting.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

<p align="center">
  Built by <a href="https://www.linkedin.com/in/ilham-ahsan-saputra/"><b>Ilham Ahsan Saputra</b></a><br/>
  <sub>Computer Science Student · Junior Network Engineer · <a href="https://medium.com/@centauryy">Tech Writer</a></sub>
</p>

