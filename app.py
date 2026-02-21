"""
Scout Intelligence Agent — Engine Room AI
Daily autonomous scanning for agentic web opportunities.
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import traceback
import threading
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'scout-secret-change-in-production')

# Import Scout modules
from scout.database import init_db, get_opportunities, get_stats, dismiss_opportunity, bookmark_opportunity, get_bookmarked, get_scan_history
from scout.orchestrator import ScoutOrchestrator

# Initialize database on startup
init_db()

# APScheduler for daily scans
from apscheduler.schedulers.background import BackgroundScheduler

DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD', 'scout2024')

# Track scan status in memory
scan_status = {
    'running': False,
    'last_result': None,
    'last_error': None,
    'started_at': None,
    'finished_at': None,
}
scan_lock = threading.Lock()


def run_scan_background():
    """Run scan in background thread."""
    global scan_status
    try:
        orchestrator = ScoutOrchestrator()
        result = orchestrator.run_daily_scan()
        with scan_lock:
            scan_status['running'] = False
            scan_status['last_result'] = result
            scan_status['last_error'] = None
            scan_status['finished_at'] = datetime.now().isoformat()
        print(f"[Scan] Complete: {result}")
    except Exception as e:
        with scan_lock:
            scan_status['running'] = False
            scan_status['last_error'] = str(e)
            scan_status['finished_at'] = datetime.now().isoformat()
        print(f"[Scan] Error: {traceback.format_exc()}")


def scheduled_scan():
    """Run the daily scan (called by APScheduler)."""
    print(f"[Scheduler] Starting scheduled scan at {datetime.now()}")
    with scan_lock:
        if scan_status['running']:
            print("[Scheduler] Scan already running, skipping")
            return
        scan_status['running'] = True
        scan_status['started_at'] = datetime.now().isoformat()
    run_scan_background()


# Set up scheduler
scheduler = BackgroundScheduler()
scan_hour = int(os.environ.get('SCAN_HOUR', '7'))
scan_minute = int(os.environ.get('SCAN_MINUTE', '0'))
scheduler.add_job(scheduled_scan, 'cron', hour=scan_hour, minute=scan_minute, id='daily_scan')
scheduler.start()
print(f"[Scout] Scheduler started — daily scan at {scan_hour:02d}:{scan_minute:02d} UTC")


# ============================================
# AUTH
# ============================================

def login_required(f):
    """Decorator to require login."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            if request.path.startswith('/api/'):
                return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == DASHBOARD_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('dashboard'))
        error = 'Wrong password'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))


# ============================================
# DASHBOARD
# ============================================

@app.route('/')
def index():
    if session.get('authenticated'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    filter_type = request.args.get('filter', 'all')

    if filter_type == 'bookmarked':
        opportunities = get_bookmarked()
    else:
        opportunities = get_opportunities(limit=50)

    stats = get_stats()
    return render_template('dashboard.html', opportunities=opportunities, stats=stats)


# ============================================
# API ENDPOINTS
# ============================================

@app.route('/api/scan', methods=['POST'])
@login_required
def api_scan():
    """Kick off scan in background thread, return immediately."""
    global scan_status
    with scan_lock:
        if scan_status['running']:
            return jsonify({'status': 'already_running', 'message': 'Scan is already in progress', 'started_at': scan_status['started_at']})
        scan_status['running'] = True
        scan_status['started_at'] = datetime.now().isoformat()
        scan_status['last_result'] = None
        scan_status['last_error'] = None
        scan_status['finished_at'] = None

    thread = threading.Thread(target=run_scan_background, daemon=True)
    thread.start()

    return jsonify({'status': 'started', 'message': 'Scan started in background. Check /api/scan/status for progress.'})


@app.route('/api/scan/status')
@login_required
def api_scan_status():
    """Check if a scan is running and get results."""
    with scan_lock:
        return jsonify({
            'running': scan_status['running'],
            'started_at': scan_status['started_at'],
            'finished_at': scan_status['finished_at'],
            'result': scan_status['last_result'],
            'error': scan_status['last_error'],
        })


@app.route('/api/dismiss/<int:opp_id>', methods=['POST'])
@login_required
def api_dismiss(opp_id):
    try:
        dismiss_opportunity(opp_id)
        return jsonify({'status': 'dismissed', 'id': opp_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/bookmark/<int:opp_id>', methods=['POST'])
@login_required
def api_bookmark(opp_id):
    try:
        bookmark_opportunity(opp_id)
        return jsonify({'status': 'bookmarked', 'id': opp_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/stats')
@login_required
def api_stats():
    return jsonify(get_stats())


@app.route('/api/history')
@login_required
def api_history():
    return jsonify(get_scan_history())


# ============================================
# HEALTH CHECK (for Render)
# ============================================

@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'service': 'scout',
        'version': '1.1',
        'scheduler_running': scheduler.running,
        'scan_running': scan_status['running'],
        'next_scan': str(scheduler.get_job('daily_scan').next_run_time) if scheduler.get_job('daily_scan') else 'not scheduled'
    })


if __name__ == '__main__':
    app.run(debug=True, port=5002)
