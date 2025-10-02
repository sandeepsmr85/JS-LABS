import os
import ast
import logging
import base64
import threading
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from openai import OpenAI
from user_agents import parse
import database

# ---------------------------
# Basic configuration & setup
# ---------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')

# Keep the same async_mode (you requested to keep eventlet usage).
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# NOTE: As requested -- do NOT change the hardcoded API key in this file.
client = OpenAI(api_key="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")

# Initialize DB (ensure your database module handles concurrency or use the provided lock below)
database.init_db()

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------
# Concurrency primitives
# ---------------------------
executor = ThreadPoolExecutor(max_workers=4)
db_lock = threading.Lock()  # use this to protect DB operations from concurrent threads

# ---------------------------
# Agent tracking (metadata)
# ---------------------------
connected_agents = {}  # { sid: {"addr": <ip>, "user_agent": <ua>, ...} }


# ---------------------------
# Utility functions
# ---------------------------
def detect_browser(user_agent_string: str) -> str:
    try:
        user_agent = parse(user_agent_string or "")
        family = (user_agent.browser.family or "").lower()
    except Exception:
        family = ""

    if family in ['chrome', 'chromium', 'edge']:
        return 'chromium'
    elif family == 'firefox':
        return 'firefox'
    elif family == 'safari':
        return 'webkit'
    else:
        return 'chromium'


def _clean_code_fences(code: str) -> str:
    if not code:
        return code
    code = code.strip()
    if code.startswith("```"):
        parts = code.split("\n")
        if len(parts) > 1 and parts[0].startswith("```"):
            code = "\n".join(parts[1:])
    if code.endswith("```"):
        code = code[:-3].rstrip()
    return code


def ensure_screenshot_in_code(code: str) -> str:
    """Ensure screenshot code uses the exact expected filename and path"""
    if "screenshot.png" in code and "path=\"screenshot.png\"" in code:
        return code

    lines = code.rstrip().splitlines()
    indent = " " * 4
    screenshot_line = f'{indent}await page.screenshot(path="screenshot.png")'

    # Remove any existing screenshot lines to avoid duplicates
    cleaned_lines = []
    for line in lines:
        if "screenshot" in line and ("path=" in line or "full_page=True" in line):
            continue
        cleaned_lines.append(line)

    lines = cleaned_lines

    # Insert before return statement or at the end
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith("return"):
            lines.insert(i, screenshot_line)
            return "\n".join(lines)

    # If no return statement found, add at the end before context/browser close
    for i in range(len(lines) - 1, -1, -1):
        if any(close_cmd in lines[i] for close_cmd in
               ['await context.close()', 'await browser.close()', 'browser.close()']):
            lines.insert(i, screenshot_line)
            return "\n".join(lines)

    # Last resort: append to the end
    lines.append(screenshot_line)
    return "\n".join(lines)

def validate_python_syntax(code: str):
    ast.parse(code)


def generate_playwright_code(nl_command: str, browser: str) -> str:
    prompt = f"""Convert this natural language test command into executable Playwright Python code.
Use the browser type: {browser}

Natural language command: {nl_command}

Generate the core test logic that:
1. Uses the provided page object
2. Performs the requested actions
3. Includes proper error handling
4. Uses async/await pattern

DO NOT include:
- asyncio.run() calls
- Playwright setup/teardown (browser launch, context creation, etc.)
- Import statements

Example of what to generate:
    await page.goto('https://example.com')
    await page.click('button#submit')
    # ... more actions ...

Return ONLY the core test logic without any setup/teardown code."""

    logger.info("Requesting code generation from OpenAI...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a Playwright test automation expert. Generate clean, executable Python code."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=2000
    )

    content = None
    try:
        content = response.choices[0].message.content
    except Exception:
        content = getattr(response, "content", None) or str(response)

    if not content:
        raise ValueError("No code generated by OpenAI")

    code = _clean_code_fences(content)
    code = ensure_screenshot_in_code(code)

    try:
        validate_python_syntax(code)
    except SyntaxError as e:
        logger.error("Generated code failed Python syntax validation.", exc_info=True)
        raise SyntaxError(f"Generated code is syntactically invalid: {e}") from e

    return code.strip()


# ---------------------------
# Flask routes
# ---------------------------
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/history')
def history():
    with db_lock:
        test_runs = database.get_all_test_runs()
    return render_template('history.html', test_runs=test_runs)


@app.route('/setup')
def setup():
    server_url = request.host_url.rstrip('/')
    return render_template('setup.html', server_url=server_url)


@app.route('/download/agent')
def download_agent():
    filename = 'install_and_run_agent.sh'
    safe_name = os.path.basename(filename)
    return send_from_directory(os.path.abspath('.'), safe_name, as_attachment=True)


@app.route('/api/agent/status')
def agent_status():
    return jsonify({
        'connected': len(connected_agents) > 0,
        'count': len(connected_agents),
        'agents': list(connected_agents.values())
    })


@app.route('/api/test', methods=['POST'])
def create_test():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    nl_command = data.get('command')
    if not nl_command:
        return jsonify({'error': 'Command is required'}), 400

    user_agent = request.headers.get('User-Agent', '')
    browser = detect_browser(user_agent)

    try:
        future = executor.submit(generate_playwright_code, nl_command, browser)
        generated_code = future.result()

        if "screenshot.png" not in generated_code:
            generated_code = ensure_screenshot_in_code(generated_code)

        try:
            validate_python_syntax(generated_code)
        except SyntaxError as e:
            logger.error("Final validation failed for generated code.", exc_info=True)
            return jsonify({'error': 'Generated Playwright code is invalid Python'}), 500

        with db_lock:
            test_id = database.save_test_run(nl_command, generated_code, browser)

        socketio.emit('test_created', {
            'test_id': test_id,
            'code': generated_code,
            'browser': browser
        }, namespace='/')

        return jsonify({
            'test_id': test_id,
            'generated_code': generated_code,
            'browser': browser
        })

    except Exception as e:
        logger.error(f"Test generation failed: {e}", exc_info=True)
        return jsonify({'error': 'Failed to generate Playwright code. Check server logs.'}), 500


@app.route('/api/test/<int:test_id>')
def get_test(test_id):
    with db_lock:
        test_run = database.get_test_run(test_id)
    if test_run:
        return jsonify(test_run)
    return jsonify({'error': 'Test not found'}), 404


@app.route('/screenshots/<path:filename>')
def serve_screenshot(filename):
    screenshots_dir = os.path.abspath('screenshots')
    safe_filename = os.path.basename(filename)
    return send_from_directory(screenshots_dir, safe_filename)


# New: Accept direct uploads of screenshot files (multipart/form-data).
@app.route('/api/test/<int:test_id>/upload_screenshot', methods=['POST'])
def upload_screenshot(test_id):
    """
    Allows an agent to upload a screenshot file directly.
    Form field name: 'screenshot' (file)
    """
    if 'screenshot' not in request.files:
        return jsonify({'error': "No 'screenshot' file in request"}), 400

    file = request.files['screenshot']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    try:
        os.makedirs('screenshots', exist_ok=True)
        safe_filename = f'test_{test_id}.png'
        safe_filename = os.path.basename(safe_filename)
        filepath = os.path.join(os.path.abspath('screenshots'), safe_filename)
        file.save(filepath)

        # Update DB with screenshot path
        with db_lock:
            database.update_test_run(
                test_id,
                screenshot_path=filepath
            )

        # Notify clients
        socketio.emit('test_complete', {
            'test_id': test_id,
            'status': 'completed',
            'logs': None,
            'screenshot_path': filepath
        }, namespace='/')

        return jsonify({'ok': True, 'screenshot_path': filepath})
    except Exception as e:
        logger.error(f"Failed to save uploaded screenshot for test {test_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to save screenshot'}), 500


# ---------------------------
# Socket.IO event handlers
# ---------------------------
@socketio.on('connect', namespace='/agent')
def agent_connect():
    sid = request.sid
    addr = request.remote_addr
    ua = request.headers.get('User-Agent', '')

    connected_agents[sid] = {
        'sid': sid,
        'addr': addr,
        'user_agent': ua
    }

    logger.info(f'Agent connected: {sid} (Total agents: {len(connected_agents)})')
    emit('connected', {'message': 'Connected to server'})
    socketio.emit('agent_status_update', {
        'connected': True,
        'count': len(connected_agents)
    }, namespace='/')


@socketio.on('disconnect', namespace='/agent')
def agent_disconnect():
    sid = request.sid
    if sid in connected_agents:
        connected_agents.pop(sid, None)
    logger.info(f'Agent disconnected: {sid} (Total agents: {len(connected_agents)})')
    socketio.emit('agent_status_update', {
        'connected': len(connected_agents) > 0,
        'count': len(connected_agents)
    }, namespace='/')


@socketio.on('execution_log', namespace='/agent')
def handle_execution_log(data):
    test_id = data.get('test_id')
    log_message = data.get('message', '')
    logger.info(f'Test {test_id} log: {log_message}')

    socketio.emit('log_update', {
        'test_id': test_id,
        'message': log_message
    }, namespace='/')


@socketio.on('execution_complete', namespace='/agent')
def handle_execution_complete(data):
    """
    Accepted shapes of `data`:
    - {'test_id': id, 'status': 'completed', 'logs': '...', 'screenshot': '<base64 string>'}
    - {'test_id': id, 'status': 'completed', 'logs': '...', 'screenshot_path': '/some/path/on/shared/fs.png'}
    - {'test_id': id, 'status': 'completed', 'logs': '...'}  (no screenshot)
    """
    test_id = data.get('test_id')
    status = data.get('status', 'completed')
    logs = data.get('logs', '')
    screenshot_data = data.get('screenshot')
    screenshot_path_field = data.get('screenshot_path')

    screenshot_path = None

    # 1) If agent sent base64-encoded image, decode and save
    if screenshot_data:
        try:
            os.makedirs('screenshots', exist_ok=True)
            safe_filename = f'test_{test_id}.png'
            safe_filename = os.path.basename(safe_filename)
            screenshot_path = os.path.join(os.path.abspath('screenshots'), safe_filename)

            image_data = base64.b64decode(screenshot_data)
            with open(screenshot_path, 'wb') as f:
                f.write(image_data)
            logger.info(f"Saved base64 screenshot for test {test_id} -> {screenshot_path}")
        except Exception as e:
            logger.error(f'Error saving base64 screenshot for test {test_id}: {e}', exc_info=True)
            screenshot_path = None

    # 2) If agent provided a 'screenshot_path' (shared FS), try to copy/move or at least record it.
    elif screenshot_path_field:
        # Sanitize input: get basename and, if path exists on server, copy it into screenshots dir.
        try:
            candidate = os.path.abspath(screenshot_path_field)
            if os.path.exists(candidate) and os.path.isfile(candidate):
                os.makedirs('screenshots', exist_ok=True)
                safe_filename = f'test_{test_id}.png'
                dest = os.path.join(os.path.abspath('screenshots'), os.path.basename(safe_filename))
                # Attempt to copy (best-effort)
                with open(candidate, 'rb') as src, open(dest, 'wb') as dst:
                    dst.write(src.read())
                screenshot_path = dest
                logger.info(f"Copied shared screenshot for test {test_id} -> {screenshot_path}")
            else:
                # Record the provided path (but only after sanitizing basename)
                logger.warning(f"Agent provided screenshot_path that is not readable by server: {screenshot_path_field}")
                screenshot_path = None
        except Exception as e:
            logger.error(f'Error handling screenshot_path for test {test_id}: {e}', exc_info=True)
            screenshot_path = None

    else:
        # No screenshot provided
        logger.warning(f"No screenshot provided for test {test_id} in execution_complete payload. "
                       "Agent should either send base64 under 'screenshot' or upload via the /upload_screenshot endpoint.")
        screenshot_path = None

    # Update DB safely
    try:
        with db_lock:
            database.update_test_run(
                test_id,
                status=status,
                execution_logs=logs,
                screenshot_path=screenshot_path
            )
    except Exception as e:
        logger.error(f"Database update failed for test {test_id}: {e}", exc_info=True)

    socketio.emit('test_complete', {
        'test_id': test_id,
        'status': status,
        'logs': logs,
        'screenshot_path': screenshot_path
    }, namespace='/')


# ---------------------------
# App entrypoint
# ---------------------------
if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)
