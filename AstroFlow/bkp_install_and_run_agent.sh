#!/bin/bash

set -e

echo "======================================"
echo "Playwright Test Agent Installer"
echo "======================================"
echo ""

AGENT_DIR="$HOME/.playwright_agent"
VENV_DIR="$AGENT_DIR/venv"
AGENT_SCRIPT="$AGENT_DIR/agent.py"

echo "Creating agent directory at $AGENT_DIR..."
mkdir -p "$AGENT_DIR"

if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "Found Python version: $PYTHON_VERSION"

echo ""
echo "Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

# ✅ Detect correct activation path (Windows vs Linux)
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    VENV_PYTHON="$VENV_DIR/bin/python"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    source "$VENV_DIR/Scripts/activate"
    VENV_PYTHON="$VENV_DIR/Scripts/python.exe"
else
    echo "ERROR: Could not find virtualenv activation script."
    exit 1
fi

echo ""
echo "Installing Python dependencies..."
"$VENV_PYTHON" -m pip install --quiet --upgrade pip
"$VENV_PYTHON" -m pip install --quiet playwright python-socketio websocket-client requests

echo ""
echo "Installing Playwright browsers (this may take a few minutes)..."
"$VENV_PYTHON" -m playwright install chromium firefox webkit

echo ""
echo "Creating agent script..."
cat > "$AGENT_SCRIPT" << 'AGENT_SCRIPT_EOF'
import asyncio
import base64
import sys
import os
import tempfile
import traceback
from playwright.async_api import async_playwright
import socketio

# ✅ Default server URL changed to 127.0.0.1
SERVER_URL = os.environ.get('SERVER_URL', 'http://127.0.0.1:5000')

sio = socketio.Client()

@sio.on('connect', namespace='/agent')
def on_connect():
    print(f'Connected to server at {SERVER_URL}')

@sio.on('disconnect', namespace='/agent')
def on_disconnect():
    print('Disconnected from server')

@sio.on('test_created', namespace='/')
def on_test_created(data):
    print(f"\nReceived new test: ID={data['test_id']}, Browser={data['browser']}")
    asyncio.run(execute_test(data))

async def execute_test(test_data):
    test_id = test_data['test_id']
    code = test_data['code']
    browser_type = test_data['browser']

    log_buffer = []

    def log(message):
        print(message)
        log_buffer.append(message)
        try:
            sio.emit('execution_log', {
                'test_id': test_id,
                'message': message
            }, namespace='/agent')
        except Exception as e:
            print(f"Failed to send log: {e}")

    log(f"Starting test execution with {browser_type} browser...")

    temp_dir = tempfile.mkdtemp()
    screenshot_path = os.path.join(temp_dir, 'screenshot.png')
    original_dir = os.getcwd()

    try:
        os.chdir(temp_dir)

        namespace = {
            'asyncio': asyncio,
            'async_playwright': async_playwright,
            '__builtins__': __builtins__,
        }

        exec(f"""
async def run_test():
{chr(10).join('    ' + line for line in code.split(chr(10)))}
""", namespace)

        log("Executing generated test code...")
        await namespace['run_test']()

        screenshot_data = None
        if os.path.exists(screenshot_path):
            with open(screenshot_path, 'rb') as f:
                screenshot_data = base64.b64encode(f.read()).decode('utf-8')
            log("Screenshot captured successfully")
        else:
            log("Warning: Screenshot file not found at expected location")

        log("Test completed successfully")

        sio.emit('execution_complete', {
            'test_id': test_id,
            'status': 'completed',
            'logs': '\n'.join(log_buffer),
            'screenshot': screenshot_data
        }, namespace='/agent')

    except Exception as e:
        error_msg = f"Test execution failed: {str(e)}\n{traceback.format_exc()}"
        log(error_msg)

        sio.emit('execution_complete', {
            'test_id': test_id,
            'status': 'failed',
            'logs': '\n'.join(log_buffer),
            'screenshot': None
        }, namespace='/agent')

    finally:
        os.chdir(original_dir)
        try:
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
            os.rmdir(temp_dir)
        except:
            pass

def main():
    print("====================================")
    print("Playwright Test Agent")
    print("====================================")
    print(f"Server URL: {SERVER_URL}")
    print("")

    try:
        print("Connecting to server...")
        sio.connect(SERVER_URL, namespaces=['/agent', '/'])
        print("Agent is ready and waiting for tests...")
        sio.wait()
    except KeyboardInterrupt:
        print("\nShutting down agent...")
        sio.disconnect()
    except Exception as e:
        print(f"Error: Could not connect to {SERVER_URL}")
        print(f"Details: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
AGENT_SCRIPT_EOF

echo ""
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "To start the agent manually, run:"
echo "  $VENV_PYTHON $AGENT_SCRIPT"
echo ""
echo "Or set SERVER_URL and run:"
echo "  SERVER_URL=http://your-server:5000 $VENV_PYTHON $AGENT_SCRIPT"
echo ""
echo "Starting agent now..."
echo ""

"$VENV_PYTHON" "$AGENT_SCRIPT"
