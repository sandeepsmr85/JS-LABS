from flask import Flask, render_template, request, jsonify, Response
import os
import json
import csv
from io import StringIO
from dotenv import load_dotenv
from jira import JIRA
from openai import OpenAI

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET')

# Initialize OpenAI client
# the newest OpenAI model is "gpt-5" which was released August 7, 2025.
# do not change this unless explicitly requested by the user
openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

class JiraTestCaseGenerator:
    def __init__(self):
        self.jira_client = None
        
    def connect_to_jira(self, server, username, api_token):
        """Connect to Jira using provided credentials"""
        try:
            print(f"Attempting to connect to Jira at: {server}")
            self.jira_client = JIRA(
                server=server,
                basic_auth=(username, api_token)
            )
            # Test the connection by getting server info
            server_info = self.jira_client.server_info()
            print(f"Successfully connected to Jira. Server version: {server_info.get('version', 'Unknown')}")
            return True
        except Exception as e:
            print(f"Failed to connect to Jira: {type(e).__name__}: {str(e)}")
            return False
    
    def get_ticket_details(self, ticket_id):
        """Fetch detailed information about a Jira ticket"""
        if not self.jira_client:
            return None
            
        try:
            issue = self.jira_client.issue(ticket_id, expand='comments,changelog')
            
            # Get basic ticket info
            ticket_info = {
                'id': ticket_id,
                'title': issue.fields.summary,
                'description': issue.fields.description or '',
                'status': issue.fields.status.name,
                'priority': issue.fields.priority.name if issue.fields.priority else 'None',
                'issue_type': issue.fields.issuetype.name,
                'comments': []
            }
            
            # Get comments
            for comment in issue.fields.comment.comments:
                ticket_info['comments'].append({
                    'author': comment.author.displayName,
                    'body': comment.body,
                    'created': comment.created
                })
            
            # Try to get epic information
            epic_link = getattr(issue.fields, 'customfield_10014', None) or getattr(issue.fields, 'epic', None)
            if epic_link:
                ticket_info['epic'] = self.get_epic_details(epic_link)
            
            return ticket_info
            
        except Exception as e:
            print(f"Error fetching ticket details: {e}")
            return None
    
    def get_epic_details(self, epic_key):
        """Get epic details and associated user stories"""
        if not self.jira_client:
            return None
            
        try:
            epic = self.jira_client.issue(epic_key)
            epic_info = {
                'key': epic_key,
                'title': epic.fields.summary,
                'description': epic.fields.description or '',
                'user_stories': []
            }
            
            # Find user stories under this epic
            jql = f'"Epic Link" = {epic_key}'
            user_stories = self.jira_client.search_issues(jql, maxResults=50)
            
            for story in user_stories:
                story_info = {
                    'key': story.key,
                    'title': story.fields.summary,
                    'description': story.fields.description or '',
                    'status': story.fields.status.name
                }
                epic_info['user_stories'].append(story_info)
            
            return epic_info
            
        except Exception as e:
            print(f"Error fetching epic details: {e}")
            return None
    
    def generate_test_cases(self, ticket_data):
        """Use OpenAI to generate test cases based on ticket data"""
        try:
            # Prepare context for AI
            context = self.prepare_ai_context(ticket_data)
            
            prompt = f"""
            Based on the following Jira ticket information, generate comprehensive test cases.
            
            Context:
            {context}
            
            Please generate test cases in the following JSON format:
            {{
                "test_cases": [
                    {{
                        "id": "TC001",
                        "title": "Test case title",
                        "description": "Detailed description",
                        "preconditions": "Setup requirements",
                        "steps": ["Step 1", "Step 2", "Step 3"],
                        "expected_result": "Expected outcome",
                        "priority": "High/Medium/Low",
                        "type": "Functional/Regression/Edge Case"
                    }}
                ]
            }}
            
            Focus on:
            1. Functional test cases covering main requirements
            2. Edge cases and boundary conditions  
            3. Error handling scenarios
            4. Integration points if mentioned
            5. User acceptance criteria if available
            
            Generate at least 5-10 comprehensive test cases.
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-5",  # Using latest model
                messages=[
                    {"role": "system", "content": "You are an expert QA engineer specializing in test case design. Generate thorough, practical test cases based on software requirements."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            if content is None:
                return []
            result = json.loads(content)
            return result.get('test_cases', [])
            
        except Exception as e:
            print(f"Error generating test cases: {e}")
            return []
    
    def prepare_ai_context(self, ticket_data):
        """Prepare structured context for AI processing"""
        context = f"""
        Ticket ID: {ticket_data['id']}
        Title: {ticket_data['title']}
        Description: {ticket_data['description']}
        Status: {ticket_data['status']}
        Priority: {ticket_data['priority']}
        Type: {ticket_data['issue_type']}
        """
        
        if ticket_data.get('comments'):
            context += "\n\nComments:\n"
            for comment in ticket_data['comments']:
                context += f"- {comment['author']}: {comment['body']}\n"
        
        if ticket_data.get('epic'):
            epic = ticket_data['epic']
            context += f"\n\nEpic Information:\n"
            context += f"Epic: {epic['title']}\n"
            context += f"Epic Description: {epic['description']}\n"
            
            if epic['user_stories']:
                context += "\nRelated User Stories:\n"
                for story in epic['user_stories']:
                    context += f"- {story['title']}: {story['description']}\n"
        
        return context

# Initialize the generator
generator = JiraTestCaseGenerator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_test_cases():
    data = request.get_json()
    
    # Get form data
    jira_server = data.get('jira_server')
    username = data.get('username') 
    api_token = data.get('api_token')
    ticket_id = data.get('ticket_id')
    
    if not all([jira_server, username, api_token, ticket_id]):
        return jsonify({'error': 'All fields are required'}), 400
    
    # Connect to Jira
    if not generator.connect_to_jira(jira_server, username, api_token):
        return jsonify({'error': 'Failed to connect to Jira. Please check your credentials.'}), 400
    
    # Get ticket details
    ticket_data = generator.get_ticket_details(ticket_id)
    if not ticket_data:
        return jsonify({'error': f'Could not fetch ticket {ticket_id}. Please check the ticket ID.'}), 400
    
    # Generate test cases
    test_cases = generator.generate_test_cases(ticket_data)
    
    return jsonify({
        'ticket_info': ticket_data,
        'test_cases': test_cases
    })

@app.route('/export/<format>')
def export_test_cases(format):
    # Get test cases from session or request
    test_cases_data = request.args.get('data')
    if not test_cases_data:
        return jsonify({'error': 'No test cases to export'}), 400
    
    try:
        test_cases = json.loads(test_cases_data)
    except:
        return jsonify({'error': 'Invalid test case data'}), 400
    
    if format == 'csv':
        return export_csv(test_cases)
    elif format == 'json':
        return export_json(test_cases)
    else:
        return jsonify({'error': 'Unsupported format'}), 400

def export_csv(test_cases):
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['ID', 'Title', 'Description', 'Preconditions', 'Steps', 'Expected Result', 'Priority', 'Type'])
    
    # Data
    for tc in test_cases:
        steps = '; '.join(tc.get('steps', []))
        writer.writerow([
            tc.get('id', ''),
            tc.get('title', ''),
            tc.get('description', ''),
            tc.get('preconditions', ''),
            steps,
            tc.get('expected_result', ''),
            tc.get('priority', ''),
            tc.get('type', '')
        ])
    
    response = Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=test_cases.csv'}
    )
    return response

def export_json(test_cases):
    response = Response(
        json.dumps(test_cases, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=test_cases.json'}
    )
    return response

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)