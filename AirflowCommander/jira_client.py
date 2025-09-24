import requests
import base64
from requests.auth import HTTPBasicAuth

class JiraClient:
    """Client for fetching Jira story details"""
    
    def __init__(self):
        pass
    
    def fetch_story(self, jira_url, username, password, story_id):
        """
        Fetch Jira story details including title, description, and comments
        """
        # Ensure jira_url ends with a slash
        if not jira_url.endswith('/'):
            jira_url += '/'
        
        # Construct the API endpoint
        api_url = f"{jira_url}rest/api/2/issue/{story_id}"
        
        try:
            # Make authenticated request to Jira API
            response = requests.get(
                api_url,
                auth=HTTPBasicAuth(username, password),
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            
            if response.status_code == 401:
                raise Exception("Invalid Jira credentials. Please check your username and password.")
            elif response.status_code == 404:
                raise Exception(f"Jira story {story_id} not found. Please verify the story ID.")
            elif response.status_code != 200:
                raise Exception(f"Failed to fetch Jira story. Status code: {response.status_code}")
            
            issue_data = response.json()
            
            # Extract relevant information
            fields = issue_data.get('fields', {})
            
            story_details = {
                'id': story_id,
                'key': issue_data.get('key', story_id),
                'title': fields.get('summary', 'No title'),
                'description': fields.get('description', 'No description provided'),
                'issue_type': fields.get('issuetype', {}).get('name', 'Unknown'),
                'status': fields.get('status', {}).get('name', 'Unknown'),
                'priority': fields.get('priority', {}).get('name', 'Unknown'),
                'assignee': fields.get('assignee', {}).get('displayName', 'Unassigned') if fields.get('assignee') else 'Unassigned',
                'reporter': fields.get('reporter', {}).get('displayName', 'Unknown') if fields.get('reporter') else 'Unknown',
                'comments': []
            }
            
            # Fetch comments if available
            comments = fields.get('comment', {}).get('comments', [])
            for comment in comments:
                comment_info = {
                    'author': comment.get('author', {}).get('displayName', 'Unknown'),
                    'body': comment.get('body', ''),
                    'created': comment.get('created', '')
                }
                story_details['comments'].append(comment_info)
            
            return story_details
            
        except requests.exceptions.Timeout:
            raise Exception("Request timed out. Please check your Jira URL and try again.")
        except requests.exceptions.ConnectionError:
            raise Exception("Failed to connect to Jira. Please check your Jira URL and network connection.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error connecting to Jira: {str(e)}")
        except Exception as e:
            if "Invalid Jira credentials" in str(e) or "not found" in str(e):
                raise e
            else:
                raise Exception(f"Unexpected error: {str(e)}")