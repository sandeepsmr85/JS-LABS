import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from jira_client import JiraClient
from test_case_generator import TestCaseGenerator

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'your-secret-key-here')

# Initialize components
jira_client = JiraClient()
test_case_generator = TestCaseGenerator()

# Simple in-memory storage for conversations (in production, use a database)
conversations = {}

@app.route('/')
def index():
    """Main page with the ChatGPT-inspired interface"""
    return render_template('index.html')

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get all conversations for the current session"""
    session_id = session.get('session_id')
    if not session_id:
        return jsonify([])
    
    user_conversations = [
        conv for conv in conversations.values() 
        if conv.get('session_id') == session_id
    ]
    return jsonify(user_conversations)

@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    """Create a new conversation"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    conversation_id = str(uuid.uuid4())
    conversations[conversation_id] = {
        'id': conversation_id,
        'session_id': session['session_id'],
        'title': 'New Conversation',
        'created_at': datetime.now().isoformat(),
        'messages': []
    }
    
    return jsonify(conversations[conversation_id])

@app.route('/api/conversations/<conversation_id>/messages', methods=['POST'])
def add_message(conversation_id):
    """Add a message to a conversation and process Jira story"""
    data = request.get_json() or {}
    jira_story_id = data.get('jira_story_id')
    custom_prompt = data.get('custom_prompt', '')
    jira_username = data.get('jira_username')
    jira_password = data.get('jira_password')
    jira_url = data.get('jira_url')
    selected_model = data.get('ai_model')
    
    if not conversation_id or conversation_id not in conversations:
        return jsonify({'error': 'Conversation not found'}), 404
    
    try:
        # Fetch Jira story details
        story_details = jira_client.fetch_story(
            jira_url, jira_username, jira_password, jira_story_id
        )
        
        # Update conversation title with story title
        if not conversations[conversation_id]['messages']:
            conversations[conversation_id]['title'] = f"{jira_story_id}: {story_details['title'][:50]}..."
        
        # Add user message
        user_message = {
            'id': str(uuid.uuid4()),
            'type': 'user',
            'content': f"Generate test cases for Jira Story: {jira_story_id}",
            'timestamp': datetime.now().isoformat(),
            'jira_story': story_details,
            'custom_prompt': custom_prompt
        }
        conversations[conversation_id]['messages'].append(user_message)
        
        # Generate test cases using AI
        test_cases = test_case_generator.generate_test_cases(
            story_details, custom_prompt, conversations[conversation_id]['messages'], selected_model
        )
        
        # Add AI response
        ai_message = {
            'id': str(uuid.uuid4()),
            'type': 'assistant',
            'content': test_cases,
            'timestamp': datetime.now().isoformat()
        }
        conversations[conversation_id]['messages'].append(ai_message)
        
        return jsonify({
            'conversation': conversations[conversation_id],
            'test_cases': test_cases
        })
        
    except Exception as e:
        error_message = {
            'id': str(uuid.uuid4()),
            'type': 'error',
            'content': f"Error: {str(e)}",
            'timestamp': datetime.now().isoformat()
        }
        conversations[conversation_id]['messages'].append(error_message)
        return jsonify({'error': str(e)}), 400

@app.route('/api/conversations/<conversation_id>/refine', methods=['POST'])
def refine_test_cases(conversation_id):
    """Refine existing test cases based on user feedback"""
    data = request.get_json() or {}
    refinement_prompt = data.get('refinement_prompt')
    selected_model = data.get('ai_model')
    
    if not conversation_id or conversation_id not in conversations:
        return jsonify({'error': 'Conversation not found'}), 404
    
    try:
        # Get conversation context
        conversation = conversations[conversation_id]
        
        # Add user refinement message
        user_message = {
            'id': str(uuid.uuid4()),
            'type': 'user',
            'content': f"Refine test cases: {refinement_prompt}",
            'timestamp': datetime.now().isoformat()
        }
        conversation['messages'].append(user_message)
        
        # Generate refined test cases
        refined_test_cases = test_case_generator.refine_test_cases(
            conversation['messages'], refinement_prompt, selected_model
        )
        
        # Add AI response
        ai_message = {
            'id': str(uuid.uuid4()),
            'type': 'assistant',
            'content': refined_test_cases,
            'timestamp': datetime.now().isoformat()
        }
        conversation['messages'].append(ai_message)
        
        return jsonify({
            'conversation': conversation,
            'test_cases': refined_test_cases
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/conversations/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """Get a specific conversation"""
    if conversation_id not in conversations:
        return jsonify({'error': 'Conversation not found'}), 404
    
    return jsonify(conversations[conversation_id])

@app.route('/api/models', methods=['GET'])
def get_available_models():
    """Get list of available AI models"""
    return jsonify({
        'models': test_case_generator.available_models,
        'default': test_case_generator.default_model
    })

if __name__ == '__main__':
    # Set host to 0.0.0.0 and port to 5000 for Replit compatibility
    app.run(host='0.0.0.0', port=5000, debug=True)