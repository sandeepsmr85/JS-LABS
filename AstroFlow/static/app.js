const socket = io('/');

let currentTestId = null;

function detectBrowser() {
    const userAgent = navigator.userAgent.toLowerCase();
    
    if (userAgent.includes('chrome') || userAgent.includes('chromium') || userAgent.includes('edge')) {
        return 'chromium';
    } else if (userAgent.includes('firefox')) {
        return 'firefox';
    } else if (userAgent.includes('safari')) {
        return 'webkit';
    }
    return 'chromium';
}

document.addEventListener('DOMContentLoaded', () => {
    const detectedBrowser = detectBrowser();
    document.getElementById('detected-browser').textContent = detectedBrowser;
    
    const form = document.getElementById('test-form');
    const submitBtn = document.getElementById('submit-btn');
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const command = document.getElementById('command').value.trim();
        if (!command) return;
        
        submitBtn.disabled = true;
        submitBtn.textContent = 'Generating...';
        
        showSection('test-status');
        document.getElementById('status-badge').textContent = 'Generating...';
        document.getElementById('status-badge').className = 'status-badge';
        
        hideSection('generated-code');
        hideSection('execution-logs');
        hideSection('screenshot-viewer');
        
        try {
            const response = await fetch('/api/test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ command })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                currentTestId = data.test_id;
                
                document.getElementById('test-id').textContent = data.test_id;
                document.getElementById('test-browser').textContent = data.browser;
                
                showSection('generated-code');
                document.getElementById('code-content').textContent = data.generated_code;
                
                document.getElementById('status-badge').textContent = 'Waiting for agent...';
                document.getElementById('status-badge').className = 'status-badge status-pending';
                
                showSection('execution-logs');
                document.getElementById('logs-content').innerHTML = '<div class="log-entry">Waiting for agent to connect and execute test...</div>';
            } else {
                alert('Error: ' + data.error);
                submitBtn.disabled = false;
                submitBtn.textContent = 'Generate & Run Test';
            }
        } catch (error) {
            alert('Error: ' + error.message);
            submitBtn.disabled = false;
            submitBtn.textContent = 'Generate & Run Test';
        }
    });
});

socket.on('log_update', (data) => {
    if (data.test_id === currentTestId) {
        const logsContent = document.getElementById('logs-content');
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.textContent = data.message;
        logsContent.appendChild(logEntry);
        logsContent.scrollTop = logsContent.scrollHeight;
        
        document.getElementById('status-badge').textContent = 'Executing...';
        document.getElementById('status-badge').className = 'status-badge status-pending';
    }
});

socket.on('test_complete', (data) => {
    if (data.test_id === currentTestId) {
        const statusBadge = document.getElementById('status-badge');
        statusBadge.textContent = data.status;
        statusBadge.className = 'status-badge status-' + data.status;
        
        if (data.screenshot_path) {
            showSection('screenshot-viewer');
            document.getElementById('screenshot').src = '/' + data.screenshot_path + '?t=' + Date.now();
        }
        
        const submitBtn = document.getElementById('submit-btn');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Generate & Run Test';
        
        document.getElementById('command').value = '';
    }
});

function showSection(sectionId) {
    document.getElementById(sectionId).classList.remove('hidden');
}

function hideSection(sectionId) {
    document.getElementById(sectionId).classList.add('hidden');
}
