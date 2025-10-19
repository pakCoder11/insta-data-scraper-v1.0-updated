import os
import json
import glob
import asyncio
import sys
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO
from dotenv import load_dotenv
from urllib.parse import urlparse
# import instagram_scraper as scraper
# Tweets scraper will be imported within route to avoid hard dependency at startup

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_secret_key')
# Force threading mode so we don't require eventlet/gevent
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, 'logs.txt')

# Flag to track first request
_first_request_complete = False

# ------------------ Utilities ------------------

def ensure_logs_file():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write("Insta Data Scraper logs initialized.\n")

def log(message: str):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {message}"
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except Exception:
        pass
    socketio.emit('log', {'message': line})


def clean_files():
    """Remove .xlsx, .json and .txt files in BASE_DIR except logs.txt.
    Runs once on first request to keep workspace clean."""
    try:
        allowed_exts = {'.xlsx', '.json', '.txt'}
        for name in os.listdir(BASE_DIR):
            path = os.path.join(BASE_DIR, name)
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in allowed_exts and name != 'logs.txt' and name != 'config.json':
                try:
                    os.remove(path)
                    log(f"Cleanup – removed file: {name}")
                except Exception as e:
                    log(f"Cleanup – failed to remove {name}: {e}")
    except Exception as e:
        log(f"Cleanup – error: {e}")


def start_background_coro(coro, task_name: str):
    def runner():
        log(f"{task_name} – started")

        # Redirect prints from this background task to Live Logs
        old_stdout, old_stderr = sys.stdout, sys.stderr

        class _Redirector:
            def __init__(self, original_stream):
                self.original = original_stream
                self.buf = ''
            def write(self, s):
                # Always write-through to the original stream
                try:
                    self.original.write(s)
                except Exception:
                    pass
                # Buffer and emit complete lines to socket logs
                self.buf += s
                while '\n' in self.buf:
                    line, self.buf = self.buf.split('\n', 1)
                    msg = line.rstrip('\r')
                    if msg:
                        log(msg)
                return len(s)
            def flush(self):
                try:
                    self.original.flush()
                except Exception:
                    pass

        sys.stdout = _Redirector(old_stdout)
        sys.stderr = _Redirector(old_stderr)

        try:
            asyncio.run(coro)
            log(f"{task_name} – completed successfully")
            # Emit explicit event so UI can react without parsing logs
            try:
                socketio.emit('task_completed', {'task_name': task_name})
            except Exception:
                pass
        except Exception as e:
            log(f"{task_name} – failed: {e}")
        finally:
            # Flush any remaining buffered content
            try:
                if getattr(sys.stdout, 'buf', ''):
                    log(sys.stdout.buf)
            except Exception:
                pass
            try:
                if getattr(sys.stderr, 'buf', ''):
                    log(sys.stderr.buf)
            except Exception:
                pass
            # Restore original streams
            sys.stdout, sys.stderr = old_stdout, old_stderr

        
    socketio.start_background_task(runner)


# ------------------ Routes (Pages) ------------------
@app.before_request
def on_startup():
    global _first_request_complete
    if not _first_request_complete:
        ensure_logs_file()
        # Reset the log file on app start so old history is not shown unless user opens /logs explicitly
        try:
            with open(LOG_FILE, 'w', encoding='utf-8'):
                pass
        except Exception:
            pass
        # clean_files()
        log("Application started.")
        _first_request_complete = True


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/logs')
def logs_page():
    ensure_logs_file()
    return render_template('logs.html')


@app.route('/screenshot-guide')
def screenshot_guide():
    return render_template('screenshot.html')


@app.route('/screenshots/<path:filename>')
def serve_screenshot(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'Screenshots'), filename)


# ------------------ API Endpoints ------------------

@app.route('/api/logs', methods=['GET'])
def api_logs():
    ensure_logs_file()
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-300:]
        return jsonify({"lines": lines})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/file-exists', methods=['GET'])
def api_file_exists():
    file = request.args.get('file')
    if not file:
        return jsonify({"exists": False})
    path = os.path.join(BASE_DIR, file)
    return jsonify({"exists": os.path.exists(path) and os.path.getsize(path) > 0})


@app.route('/api/results', methods=['GET'])
def api_results():
    kind = request.args.get('type', 'latest')
    mapping = {
        'latest': 'data.json',
        'followers': 'profile_followers_data.json',
        'comments': 'data.json',
        'posts': 'data.json'
    }
    file = mapping.get(kind, 'data.json')
    path = os.path.join(BASE_DIR, file)
    if not os.path.exists(path):
        return jsonify({"data": []})
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({"data": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------ Helpers: ENV & URL validation ------------------

def has_valid_env_credentials():
    env_path = os.path.join(BASE_DIR, '.env')
    has_env_file = os.path.exists(env_path)
    username = os.getenv('INSTAGRAM_USERNAME', '').strip()
    password = os.getenv('INSTAGRAM_PASSWORD', '').strip()
    has_creds = bool(username) and bool(password)
    missing = []
    if not username:
        missing.append('INSTAGRAM_USERNAME')
    if not password:
        missing.append('INSTAGRAM_PASSWORD')
    return (has_env_file and has_creds), has_env_file, missing


def _is_instagram_host(host: str) -> bool:
    host = (host or '').lower()
    return host == 'instagram.com' or host.endswith('.instagram.com') or host == 'www.instagram.com' or host == 'm.instagram.com'


def is_valid_instagram_url(url: str) -> bool:
    try:
        u = urlparse(url if '://' in url else f'https://{url}')
        if u.scheme not in ('http', 'https'):
            return False
        if not _is_instagram_host(u.hostname or ''):
            return False
        if not u.path or u.path == '/':
            return False
        return True
    except Exception:
        return False

def is_valid_twitter_url(url: str) -> bool:
    """Validate Twitter/X profile URL."""
    try:
        u = urlparse(url if '://' in url else f'https://{url}')
        if u.scheme not in ('http', 'https'):
            return False
        host = (u.hostname or '').lower()
        valid_host = host in {'twitter.com', 'www.twitter.com', 'x.com', 'www.x.com'}
        if not valid_host:
            return False
        if not u.path or u.path == '/':
            return False
        return True
    except Exception:
        return False

# ------------------ API: ENV status & Clear logs ------------------

@app.route('/api/env-status', methods=['GET'])
def api_env_status():
    ok, has_env_file, missing = has_valid_env_credentials()
    return jsonify({
        'ok': ok,
        'has_env_file': has_env_file,
        'missing': missing,
        'message': ('' if ok else (
            'Please add a .env file with INSTAGRAM_USERNAME & INSTAGRAM_PASSWORD.' if not has_env_file or missing else ''
        ))
    })


@app.route('/api/clear-logs', methods=['POST'])
def api_clear_logs():
    try:
        ensure_logs_file()
        with open(LOG_FILE, 'w', encoding='utf-8'):
            pass
        return jsonify({'ok': True, 'message': 'Logs cleared successfully.'})
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)}), 500

# ------------------ API: Task endpoints with ENV/URL checks ------------------

@app.route('/api/write-comments', methods=['POST'])
def api_write_comments():
    ok_env, _, _ = has_valid_env_credentials()
    if not ok_env:
        return jsonify({'ok': False, 'message': 'Please add a .env file with INSTAGRAM_USERNAME & INSTAGRAM_PASSWORD before starting.'}), 400
    try:
        import instagram_scraper as scraper
    except ModuleNotFoundError as e:
        return jsonify({"ok": False, "message": f"Dependency missing to start task: {e}"}), 500

    payload = request.get_json(force=True) or {}
    accounts = payload.get('accounts', [])
    profiles = payload.get('profiles', [])
    number_of_comments = int(payload.get('number_of_comments', 5))
    comments_list = payload.get('comments', [])

    invalid = next((p for p in profiles if not is_valid_instagram_url(p)), None)
    if invalid:
        return jsonify({'ok': False, 'message': f'Invalid Instagram URL detected: {invalid}'}), 400

    if not accounts or not profiles or not comments_list:
        return jsonify({"ok": False, "message": "Accounts, profiles and comments are required."}), 400

    login_dict = {
        'usernames_list': [a.get('username', '') for a in accounts],
        'passwords_list': [a.get('password', '') for a in accounts]
    }

    coro = scraper.write_comments_on_instagram_posts(login_dict, profiles, number_of_comments, comments_list)
    start_background_coro(coro, 'Write Comments on Posts')
    return jsonify({"ok": True, "message": "Task started"})


@app.route('/api/send-dm', methods=['POST'])
def api_send_dm():
    ok_env, _, _ = has_valid_env_credentials()
    if not ok_env:
        return jsonify({'ok': False, 'message': 'Please add a .env file with INSTAGRAM_USERNAME & INSTAGRAM_PASSWORD before starting.'}), 400
    try:
        import instagram_scraper as scraper
    except ModuleNotFoundError as e:
        return jsonify({"ok": False, "message": f"Dependency missing to start task: {e}"}), 500

    payload = request.get_json(force=True) or {}
    followers_list = payload.get('followers', [])
    messages_list = payload.get('messages', [])
    total_messages_to_send = int(payload.get('count', 5))
    time_gap = int(payload.get('interval', 60))

    invalid = next((u for u in followers_list if not is_valid_instagram_url(u)), None)
    if invalid:
        return jsonify({'ok': False, 'message': f'Invalid Instagram URL detected: {invalid}'}), 400

    if not followers_list or not messages_list:
        return jsonify({"ok": False, "message": "Followers and messages are required."}), 400

    coro = scraper.send_bulk_messages_to_followers(followers_list, messages_list, total_messages_to_send, time_gap)
    start_background_coro(coro, 'Send Direct Messages')
    return jsonify({"ok": True, "message": "Task started"})


@app.route('/api/scrape-posts', methods=['POST'])
def api_scrape_posts():
    ok_env, _, _ = has_valid_env_credentials()
    if not ok_env:
        return jsonify({'ok': False, 'message': 'Please add a .env file with INSTAGRAM_USERNAME & INSTAGRAM_PASSWORD before starting.'}), 400
    try:
        import instagram_scraper as scraper
    except ModuleNotFoundError as e:
        return jsonify({"ok": False, "message": f"Dependency missing to start task: {e}"}), 500

    payload = request.get_json(force=True) or {}
    profile_url = payload.get('profile_url', '').strip()
    num_posts = int(payload.get('num_posts', 10))
    scrape_comments = bool(payload.get('scrape_comments', False))

    if not profile_url:
        return jsonify({"ok": False, "message": "Profile URL is required."}), 400
    if not is_valid_instagram_url(profile_url):
        return jsonify({'ok': False, 'message': f'Invalid Instagram URL: {profile_url}'}), 400

    coro = scraper.scrap_instagram_posts(scrape_comments, profile_url, num_posts)
    start_background_coro(coro, 'Scrape Post Data')
    return jsonify({"ok": True, "message": "Task started"})

@app.route('/api/scrape-followers', methods=['POST'])
def api_scrape_followers():
    try:
        import instagram_scraper as scraper
    except ModuleNotFoundError as e:
        return jsonify({"ok": False, "message": f"Dependency missing to start task: {e}"}), 500

    payload = request.get_json(force=True)
    profile_url = payload.get('profile_url', '').strip()
    scroll_count = int(payload.get('scroll_count', 5))

    if not profile_url:
        return jsonify({"ok": False, "message": "Profile URL is required."}), 400

    if not is_valid_instagram_url(profile_url):
        return jsonify({'ok': False, 'message': f'Invalid Instagram URL: {profile_url}'}), 400

    coro = scraper.scrap_instagram_profile_public_followers_data(profile_url, scroll_count)
    start_background_coro(coro, 'Scrape Followers')

    return jsonify({"ok": True, "message": "Task started, Logs are saved in a logs.txt you can view it later."})


def backend_dummy_function(p1,p2):
    print(p1,p2)
    pass


@app.route('/api/scrape-tweets', methods=['POST'])
def api_scrape_tweets():
    try:
        import tweets_scraper as ts
    except ModuleNotFoundError as e:
        return jsonify({"ok": False, "message": f"Dependency missing to start task: {e}"}), 500

    payload = request.get_json(force=True) or {}
    profile_url = (payload.get('profile_url') or '').strip()
    scroll_count = int(payload.get('scroll_count', 5))

    if not profile_url:
        return jsonify({"ok": False, "message": "Profile URL is required."}), 400
    if not is_valid_twitter_url(profile_url):
        return jsonify({'ok': False, 'message': f'Invalid Twitter/X URL: {profile_url}'}), 400

    # Run tweets backend function as background coroutine
    coro = ts.scrape_tweets_using_selenium(profile_url, scroll_count)
    # coro = backend_dummy_function(profile_url, scroll_count)

    start_background_coro(coro, 'Scrape Tweets from any Twitter/X profile')

    return jsonify({"ok": True, "message": "Task started"})

@app.route('/analyze')
def analyze_dashboard():
    return render_template('analyze.html')


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    try:
        import ai_function
    except ModuleNotFoundError as e:
        return jsonify({"ok": False, "message": f"Dependency missing to start analysis: {e}"}), 500

    def runner():
        log("AI Analysis – started")
        try:
            ai_function.perform_sentiment_analysis()
            log("AI Analysis – report generated: sentiment_analysis_report.md")
        except Exception as e:
            log(f"AI Analysis – failed: {e}")
    socketio.start_background_task(runner)
    return jsonify({"ok": True, "message": "Analysis started"})


@app.route('/api/analysis-report', methods=['GET'])
def api_analysis_report():
    path = os.path.join(BASE_DIR, 'sentiment_analysis_report.md')
    if not os.path.exists(path):
        return jsonify({"exists": False, "content": ""})
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({"exists": True, "content": content})

# ------------------ New APIs: Files & Analysis ------------------

@app.route('/api/push-log', methods=['POST'])
def api_push_log():
    try:
        data = request.get_json(force=True) or {}
        msg = str(data.get('message', '')).rstrip('\r\n')
        if msg:
            log(msg)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route('/api/list-files', methods=['GET'])
def api_list_files():
    exts = ('.xlsx', '.json')
    files = []
    for name in sorted(os.listdir(BASE_DIR)):
        if name.lower().endswith(exts):
            purpose = "Unknown data"
            if name.startswith('instagram_posts_comments'):
                purpose = "Scrape comments from posts"
            elif name.startswith('instagram_posts_with_likes'):
                purpose = "Scrape posts with likes"
            elif name.startswith('profile_followers_data'):
                purpose = "Scraped followers data"
            elif name.lower().startswith('tweets_data'):
                purpose = "Scraped tweets data"
            # created time
            try:
                ctime = os.path.getctime(os.path.join(BASE_DIR, name))
                created = datetime.fromtimestamp(ctime).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                created = ''
            files.append({
                'file': name,
                'purpose': purpose,
                'is_json': name.lower().endswith('.json'),
                'created': created,
            })
    # add incremental IDs
    for i, f in enumerate(files, start=1):
        f['id'] = i
    return jsonify({'files': files})


@app.route('/api/file-table', methods=['GET'])
def api_file_table():
    file = request.args.get('file')
    if not file:
        return jsonify({"ok": False, "message": "file param required"}), 400
    path = os.path.join(BASE_DIR, file)
    if not os.path.exists(path):
        return jsonify({"ok": False, "message": "file not found"}), 404
    try:
        import pandas as pd
        # Try reading with openpyxl explicitly for .xlsx files to surface a clear error if missing
        try:
            df = pd.read_excel(path, engine='openpyxl')
        except Exception:
            # Fallback to default engine resolution (in case of non-xlsx or different setup)
            df = pd.read_excel(path)

        # Normalize columns to strings (handles MultiIndex and non-string labels)
        def _col_to_str(c):
            if isinstance(c, (list, tuple)):
                return " ".join(str(x) for x in c)
            return str(c)
        df.columns = [_col_to_str(c) for c in df.columns]

        # Replace NaN/NaT with empty string to ensure strict JSON compatibility
        df = df.fillna("")

        # Limit preview and convert to JSON-safe Python types
        df_preview = df.head(100)
        preview = df_preview.to_dict(orient='records')
        columns = list(df_preview.columns)
        return jsonify({"ok": True, "columns": columns, "rows": preview})
    except ImportError as e:
        # Common case: missing openpyxl when reading .xlsx
        return jsonify({"ok": False, "message": f"Dependency missing to read Excel: {e}. Please install 'openpyxl' (e.g., pip install openpyxl)."}), 500
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route('/api/file-json', methods=['GET'])
def api_file_json():
    file = request.args.get('file')
    if not file:
        return jsonify({"ok": False, "message": "file param required"}), 400
    path = os.path.join(BASE_DIR, file)
    if not os.path.exists(path):
        return jsonify({"ok": False, "message": "file not found"}), 404
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

@app.route('/api/run-ai-dummy', methods=['POST'])
def api_run_ai_dummy():
    # Simulate some log lines for demo
    def runner():
        import time
        log("AI Dummy – started")
        for i in range(5):
            time.sleep(0.2)
            log(f"AI Dummy – step {i+1}/5 ...")
        log("AI Dummy – completed successfully")
    socketio.start_background_task(runner)
    return jsonify({"ok": True})

@app.route('/download', methods=['GET'])
def download_file():
    """Download a data file by name (xlsx/json/txt) from BASE_DIR."""
    filename = request.args.get('file', '')
    if not filename:
        return jsonify({"ok": False, "message": "file param required"}), 400
    safe_name = os.path.basename(filename)
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in {'.xlsx', '.json', '.txt'}:
        return jsonify({"ok": False, "message": "unsupported file type"}), 400
    path = os.path.join(BASE_DIR, safe_name)
    if not os.path.exists(path):
        return jsonify({"ok": False, "message": "file not found"}), 404
    try:
        return send_from_directory(BASE_DIR, safe_name, as_attachment=True)
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

if __name__ == '__main__':
    ensure_logs_file()
    socketio.run(app, host='127.0.0.1', port=5000, debug=True)