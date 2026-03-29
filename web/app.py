"""Flask web application layer for CactiAutomation.

Security hardened with:
- Restricted CORS origins (configurable)
- URL allowlist validation (SSRF protection)
- Health check endpoints
- Production-safe defaults
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from threading import Lock, Thread

from flask import Flask, Response, jsonify, render_template, request, send_file
from flask_cors import CORS

from tracking.progress import progress
from utils.logging_config import setup_logging
from utils.summary_parser import list_runs, load_summary, tail_app_log

# Import configuration
try:
    from config import mask_sensitive, settings, validate_cacti_url
except ImportError:
    # Fallback if config not yet created
    class _FallbackSettings:
        DEBUG = False
        cors_origins_list = ["*"]
        HOST = "127.0.0.1"
        PORT = 5000
    settings = _FallbackSettings()
    def validate_cacti_url(url): return (True, "")
    def mask_sensitive(v, c=4): return "***"

# Import observability (metrics)
try:
    from observability.metrics import metrics_bp
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

setup_logging(app_name="cacti_app")
# Ensure Flask uses root-level templates/ and static/ directories
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "templates")
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)

# Register metrics blueprint if available
if METRICS_AVAILABLE:
    app.register_blueprint(metrics_bp)
    app.logger.info("Prometheus metrics available at /metrics")

# SECURITY: Restrict CORS to configured origins only
if settings.cors_origins_list and settings.cors_origins_list != ["*"]:
    CORS(app, origins=settings.cors_origins_list)
else:
    # Wide-open CORS only in development
    if getattr(settings, 'is_production', False):
        app.logger.warning("CORS is unrestricted in production! Configure CORS_ORIGINS.")
    CORS(app)

worker_thread = None
pipeline_lock = Lock()

# Application start time for health checks
_app_start_time = datetime.now()



def execute_pipeline(date1, date2, target_url, user_login, user_pass, usernames):
    app.logger.info(
        "Starting pipeline | date1=%s date2=%s target_url=%s usernames=%s",
        date1, date2, target_url, ",".join(usernames) if isinstance(usernames, list) else usernames,
    )
    try:
        from main_pipeline import step1_scrape_images, step2_ocr_images, step3_clean_csv

        step1_scrape_images(date1, date2, target_url, user_login, user_pass, usernames)

        active_folder = progress.scraping.get('current_folder')
        if not active_folder:
            raise Exception("Step 1 failed to produce an output folder.")

        # Pass the images folder (raw_screenshots) to the OCR step
        images_folder = os.path.join(active_folder, "raw_screenshots")
        resulting_csv_path = step2_ocr_images(folder=images_folder)
        if not resulting_csv_path:
            raise Exception("Step 2 (OCR) failed to produce a CSV file.")

        step3_clean_csv(csv_input=resulting_csv_path)

        with pipeline_lock:
            progress.scraping.update({
                'status': 'complete',
                'message': 'Pipeline complete!'
            })

    except Exception as e:
        app.logger.exception("Pipeline error: %s", e)
        with pipeline_lock:
            progress.scraping.update({
                'status': 'error',
                'message': f"Error: {str(e)}"
            })


@app.route('/list_folders')
def list_folders():
    base_folder = os.path.join(PROJECT_ROOT, "output")
    folders = []

    if os.path.exists(base_folder):
        for item in os.listdir(base_folder):
            item_path = os.path.join(base_folder, item)
            if os.path.isdir(item_path):
                images_dir = os.path.join(item_path, 'raw_screenshots')
                image_count = 0
                if os.path.exists(images_dir):
                    image_count = len([f for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
                folders.append({
                    'name': item,
                    'path': item_path,
                    'image_count': image_count,
                    'created': datetime.fromtimestamp(os.path.getctime(item_path)).strftime("%Y-%m-%d %H:%M:%S")
                })

    folders.sort(key=lambda x: x['created'], reverse=True)
    return jsonify(folders)


@app.route('/')
def index():
    today = datetime.now()
    one_month_ago = today - timedelta(days=30)

    default_date1 = one_month_ago.strftime("%Y-%m-%dT%H:%M")
    default_date2 = today.strftime("%Y-%m-%dT%H:%M")

    return render_template('index.html',
                           default_date1=default_date1,
                           default_date2=default_date2,
                           default_url="")


# ==========================================================================
# Health Check Endpoints
# ==========================================================================
@app.route('/health')
def health_check():
    """Basic health check endpoint for load balancers."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": (datetime.now() - _app_start_time).total_seconds()
    }), 200


@app.route('/ready')
def readiness_check():
    """Readiness check - verifies dependencies are available."""
    checks = {
        "templates": os.path.exists(TEMPLATE_DIR),
        "static": os.path.exists(STATIC_DIR),
        "output_dir": os.path.exists(os.path.join(PROJECT_ROOT, "output")) or True,  # Optional
    }

    all_ready = all(checks.values())
    status_code = 200 if all_ready else 503

    return jsonify({
        "status": "ready" if all_ready else "not_ready",
        "checks": checks,
        "timestamp": datetime.now().isoformat()
    }), status_code


@app.route('/progress')
def progress_stream():
    def generate():
        last_id = 0
        while True:
            try:
                with pipeline_lock:
                    data = {
                        'scraping': progress.scraping,
                        'ocr': progress.ocr
                    }
                yield f"id: {last_id}\ndata: {json.dumps(data)}\n\n"
                last_id += 1
                time.sleep(0.5)
            except GeneratorExit:
                app.logger.info("Client disconnected")
                break
            except Exception as e:
                app.logger.error(f"SSE Error: {str(e)}")
                time.sleep(1)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache'}
    )


@app.route('/run_pipeline', methods=['POST'])
def run_pipeline():
    global worker_thread
    try:
        with pipeline_lock:
            progress.scraping.update({
                'current': 0,
                'total': 4,
                'message': 'Starting pipeline...',
                'status': 'running',
                'current_file': ''
            })
            progress.ocr.update({
                'current': 0,
                'total': 1,
                'message': 'Waiting...',
                'status': 'idle',
                'current_file': ''
            })

        data = request.get_json(silent=True)
        if not data:
            app.logger.error("/run_pipeline called without JSON payload or wrong Content-Type")
            return jsonify({"status": "error", "message": "No data provided"}), 400

        usernames_input = (data.get('usernames') or '').strip()
        if not usernames_input:
            return jsonify({"status": "error", "message": "Usernames cannot be empty"}), 400
        usernames = [u.strip() for u in usernames_input.split(",") if u.strip()]
        if not usernames:
            return jsonify({"status": "error", "message": "No valid usernames provided"}), 400

        date1 = data.get('date1')
        date2 = data.get('date2')
        target_url = data.get('target_url')

        # SECURITY: Validate URL against allowlist (SSRF protection)
        is_valid, error_msg = validate_cacti_url(target_url)
        if not is_valid:
            app.logger.warning("URL validation failed: %s (URL: %s)", error_msg, target_url)
            return jsonify({"status": "error", "message": f"Invalid URL: {error_msg}"}), 400

        user_login = data.get('user_login')
        user_pass = data.get('user_pass')

        app.logger.info(
            "Received /run_pipeline payload | date1=%s date2=%s target_url=%s usernames=%d",
            date1, date2, target_url, len(usernames),
        )

        worker_thread = Thread(
            target=execute_pipeline,
            args=(date1, date2, target_url, user_login, user_pass, usernames),
            daemon=True
        )
        worker_thread.start()

        return jsonify({"status": "started"}), 202

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/download')
def download_csv():
    """Download CSV file with format selection (original, mbps, kbps)."""
    try:
        # Get format parameter (default: mbps)
        csv_format = request.args.get('format', 'mbps').lower()
        if csv_format not in ['original', 'mbps', 'kbps']:
            csv_format = 'mbps'

        target_folder = progress.scraping.get('current_folder')
        # Normalize to absolute path rooted at project directory
        if target_folder and not os.path.isabs(target_folder):
            target_folder = os.path.join(PROJECT_ROOT, target_folder)

        if not target_folder or not os.path.exists(target_folder):
            base_folder = os.path.join(PROJECT_ROOT, "output")
            if os.path.exists(base_folder):
                folders = [f for f in os.listdir(base_folder) if os.path.isdir(os.path.join(base_folder, f))]
                if folders:
                    folders.sort(reverse=True)
                    target_folder = os.path.join(base_folder, folders[0])
                else:
                    return "No output folder found", 404
            else:
                return "Output folder not found", 404

        folder_name = os.path.basename(target_folder)

        # Map format to filename pattern
        format_patterns = {
            'original': [f"traffic_original_{folder_name}.csv", f"traffic_{folder_name}.csv"],
            'mbps': [f"traffic_mbps_{folder_name}.csv"],
            'kbps': [f"traffic_kbps_{folder_name}.csv"]
        }

        csv_files = format_patterns.get(csv_format, format_patterns['mbps'])

        csv_path = None
        for csv_file in csv_files:
            potential_path = os.path.join(target_folder, csv_file)
            if os.path.exists(potential_path):
                csv_path = potential_path
                break

        if csv_path:
            app.logger.info(f"Downloading file: {csv_path}")
            return send_file(csv_path, as_attachment=True, download_name=os.path.basename(csv_path))
        else:
            return f"CSV file format '{csv_format}' not found in folder: {target_folder}", 404

    except Exception as e:
        return f"Download error: {str(e)}", 500


@app.route('/api/available_downloads')
def available_downloads():
    """Return list of available CSV formats for download."""
    try:
        target_folder = progress.scraping.get('current_folder')
        if target_folder and not os.path.isabs(target_folder):
            target_folder = os.path.join(PROJECT_ROOT, target_folder)

        if not target_folder or not os.path.exists(target_folder):
            base_folder = os.path.join(PROJECT_ROOT, "output")
            if os.path.exists(base_folder):
                folders = [f for f in os.listdir(base_folder) if os.path.isdir(os.path.join(base_folder, f))]
                if folders:
                    folders.sort(reverse=True)
                    target_folder = os.path.join(base_folder, folders[0])
                else:
                    return jsonify({"available": [], "folder": None}), 200
            else:
                return jsonify({"available": [], "folder": None}), 200

        folder_name = os.path.basename(target_folder)

        available = []
        format_files = {
            'original': [f"traffic_original_{folder_name}.csv", f"traffic_{folder_name}.csv"],
            'mbps': [f"traffic_mbps_{folder_name}.csv"],
            'kbps': [f"traffic_kbps_{folder_name}.csv"]
        }

        for fmt, patterns in format_files.items():
            for pattern in patterns:
                if os.path.exists(os.path.join(target_folder, pattern)):
                    available.append(fmt)
                    break

        return jsonify({"available": available, "folder": folder_name}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/summary')
def summary_page():
    try:
        runs = list_runs()
        summary = load_summary(None)
        logs = tail_app_log(200)
        return render_template('summary.html', runs=runs, summary=summary, logs=logs)
    except Exception as e:
        app.logger.exception('Failed to render summary: %s', e)
        return render_template('summary.html', runs=[], summary=None, logs=[])


@app.route('/api/summary/latest')
def api_summary_latest():
    data = load_summary(None)
    return jsonify(data or {}), (200 if data else 404)
@app.route('/logs')
def logs_page():
    try:
        from utils.summary_parser import list_runs, load_summary
        base = os.path.join(PROJECT_ROOT, 'output')
        runs = list_runs()
        run = runs[0] if runs else None
        summary = load_summary(run)
        summary_log = None
        if run:
            spath = os.path.join(base, run, 'summary.log')
            if os.path.exists(spath):
                with open(spath, encoding='utf-8', errors='ignore') as f:
                    summary_log = f.read()
        return render_template('logs.html', runs=runs, active_run=run, summary=summary, summary_log=summary_log)
    except Exception as e:
        app.logger.exception('Failed to render logs: %s', e)
        return render_template('logs.html', runs=[], active_run=None, summary=None, summary_log=None)

@app.route('/logs/<run_id>')
def logs_page_run(run_id):
    try:
        from utils.summary_parser import list_runs, load_summary
        base = os.path.join(PROJECT_ROOT, 'output')
        runs = list_runs()
        summary = load_summary(run_id)
        summary_log = None
        spath = os.path.join(base, run_id, 'summary.log')
        if os.path.exists(spath):
            with open(spath, encoding='utf-8', errors='ignore') as f:
                summary_log = f.read()
        return render_template('logs.html', runs=runs, active_run=run_id, summary=summary, summary_log=summary_log)
    except Exception as e:
        app.logger.exception('Failed to render logs run: %s', e)
        return render_template('logs.html', runs=[], active_run=None, summary=None, summary_log=None)


if __name__ == '__main__':
    # SECURITY: Never use debug=True in production
    # For production, use a WSGI server:
    #   waitress-serve --host=127.0.0.1 --port=5000 web.app:app
    #   gunicorn -b 127.0.0.1:5000 web.app:app
    debug_mode = getattr(settings, 'DEBUG', False)
    host = getattr(settings, 'HOST', '127.0.0.1')
    port = getattr(settings, 'PORT', 5000)

    if debug_mode:
        app.logger.warning("Running in DEBUG mode. Do not use in production!")

    app.run(debug=debug_mode, host=host, port=port, use_reloader=False)
