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

# Default server URL changed to 127.0.0.1
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

def clean_generated_code(code: str) -> str:
    """Clean and prepare the generated code for execution"""
    # Remove asyncio.run calls and fix common issues
    code = code.replace('asyncio.run(main())', '')
    code = code.replace('asyncio.run(run())', '')
    code = code.replace('asyncio.run(', '# asyncio.run removed: ')

    # Remove duplicate imports and function definitions we'll handle
    lines = code.splitlines()
    cleaned_lines = []

    for line in lines:
        # Skip lines we'll handle in our wrapper
        if any(skip in line for skip in [
            'import asyncio',
            'from playwright.async_api import async_playwright',
            'async def main():',
            'async def run():',
            'asyncio.run(',
            'playwright = await async_playwright().start()',
            'await playwright.stop()'
        ]):
            continue

        # Keep everything else
        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)

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
    screenshot_filename = 'screenshot.png'
    expected_screenshot_path = os.path.join(temp_dir, screenshot_filename)
    original_dir = os.getcwd()

    try:
        os.chdir(temp_dir)
        log(f"Working in temporary directory: {temp_dir}")

        # Clean the generated code
        cleaned_code = clean_generated_code(code)
        log("Code cleaned and prepared for execution")

        # Create a proper Python file with correct indentation and ASCII-only characters
        test_script_content = f'''import asyncio
from playwright.async_api import async_playwright

async def execute_playwright_test(log):
    playwright = None
    browser = None
    page = None
    try:
        log("Starting Playwright...")
        playwright = await async_playwright().start()

        log("Launching {browser_type} browser...")
        browser = await playwright.{browser_type}.launch(headless=True)

        log("Creating new context and page...")
        context = await browser.new_context()
        page = await context.new_page()

        # User's test code
{chr(10).join("        " + line for line in cleaned_code.splitlines())}

        # Ensure screenshot is taken at the end
        log("Taking final screenshot...")
        if page and not page.is_closed():
            await page.screenshot(path="{screenshot_filename}", full_page=True)
            log("SUCCESS: Screenshot saved successfully")
        else:
            log("WARNING: Cannot take screenshot - page is closed")

    except Exception as e:
        log(f"Error during test execution: {{str(e)}}")
        raise
    finally:
        # Cleanup resources
        try:
            if browser:
                await browser.close()
        except:
            pass
        try:
            if playwright:
                await playwright.stop()
        except:
            pass
'''

        # Write the test script to a file with UTF-8 encoding
        test_script_path = os.path.join(temp_dir, 'test_script.py')
        with open(test_script_path, 'w', encoding='utf-8') as f:
            f.write(test_script_content)

        # Execute the test script
        namespace = {
            'asyncio': asyncio,
            'async_playwright': async_playwright,
            'log': log
        }

        # Read and execute the script with UTF-8 encoding
        with open(test_script_path, 'r', encoding='utf-8') as f:
            script_code = f.read()

        exec(script_code, namespace)
        await namespace['execute_playwright_test'](log)

        # Check for screenshot and encode it
        screenshot_data = None
        if os.path.exists(expected_screenshot_path):
            with open(expected_screenshot_path, 'rb') as f:
                screenshot_data = base64.b64encode(f.read()).decode('utf-8')
            log("SUCCESS: Screenshot captured and ready to send")
        else:
            log("WARNING: Screenshot file not found after test execution")
            # List files for debugging
            files = os.listdir(temp_dir)
            log(f"Files in temp directory: {files}")

        log("SUCCESS: Test completed successfully")

        # Send completion with base64 screenshot
        sio.emit('execution_complete', {
            'test_id': test_id,
            'status': 'completed',
            'logs': '\\n'.join(log_buffer),
            'screenshot': screenshot_data
        }, namespace='/agent')

    except Exception as e:
        error_msg = f"Test execution failed: {str(e)}\\n{traceback.format_exc()}"
        log(error_msg)

        sio.emit('execution_complete', {
            'test_id': test_id,
            'status': 'failed',
            'logs': '\\n'.join(log_buffer),
            'screenshot': None
        }, namespace='/agent')

    finally:
        os.chdir(original_dir)
        try:
            # Clean up temp directory
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(temp_dir)
        except Exception as e:
            log(f"Warning: Failed to clean up temp directory: {e}")

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