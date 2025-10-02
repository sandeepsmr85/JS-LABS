import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('tests.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nl_command TEXT NOT NULL,
            generated_code TEXT NOT NULL,
            browser TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            execution_logs TEXT,
            screenshot_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def save_test_run(nl_command, generated_code, browser):
    conn = sqlite3.connect('tests.db')
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO test_runs (nl_command, generated_code, browser) VALUES (?, ?, ?)',
        (nl_command, generated_code, browser)
    )
    
    test_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return test_id

def update_test_run(test_id, status=None, execution_logs=None, screenshot_path=None):
    conn = sqlite3.connect('tests.db')
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if status:
        updates.append('status = ?')
        params.append(status)
    
    if execution_logs:
        updates.append('execution_logs = ?')
        params.append(execution_logs)
    
    if screenshot_path:
        updates.append('screenshot_path = ?')
        params.append(screenshot_path)
    
    if status in ['completed', 'failed']:
        updates.append('completed_at = ?')
        params.append(datetime.now().isoformat())
    
    if updates:
        params.append(test_id)
        query = f"UPDATE test_runs SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
    
    conn.close()

def get_test_run(test_id):
    conn = sqlite3.connect('tests.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM test_runs WHERE id = ?', (test_id,))
    result = cursor.fetchone()
    
    conn.close()
    return dict(result) if result else None

def get_all_test_runs():
    conn = sqlite3.connect('tests.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM test_runs ORDER BY created_at DESC')
    results = cursor.fetchall()
    
    conn.close()
    return [dict(row) for row in results]
