import os
import json
import tiktoken
from openai import OpenAI
from dotenv import load_dotenv


class TestCaseGenerator:
    def __init__(self):
        # Load variables from .env file
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found. Please add it to your .env file.")

        # the newest OpenAI model is "gpt-5" which was released August 7, 2025.
        # do not change this unless explicitly requested by the user
        self.client = OpenAI(api_key=api_key)

        # Available models with their specifications
        self.available_models = {
            "gpt-5": {"context_limit": 128000, "name": "GPT-5 (Latest)", "cost": "High"},
            "gpt-4o": {"context_limit": 128000, "name": "GPT-4o (Multimodal)", "cost": "High"},
            "gpt-4": {"context_limit": 8192, "name": "GPT-4 (Reliable)", "cost": "Medium"},
            "gpt-4-turbo": {"context_limit": 128000, "name": "GPT-4 Turbo (Fast)", "cost": "Medium"},
            "gpt-3.5-turbo": {"context_limit": 16384, "name": "GPT-3.5 Turbo (Economic)", "cost": "Low"}
        }

        self.default_model = "gpt-5"

        # Initialize tokenizer for GPT-4/5 models
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        except KeyError:
            # Fallback to cl100k_base encoding used by GPT-4/5
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

        # Token settings
        self.safety_buffer = 500  # Reserved tokens for safety
        self.min_completion_tokens = 500  # Minimum viable response
        self.max_completion_tokens = 4000  # Maximum response length
    
    def generate_test_cases(self, story_details, custom_prompt="", conversation_history=None, model=None):
        """
        Generate comprehensive test cases from Jira story details
        """
        # Construct the prompt for test case generation
        base_prompt = self._build_base_prompt(story_details, custom_prompt)
        
        # Use provided model or default
        selected_model = model or self.default_model
        
        # Calculate dynamic max tokens based on content
        messages = [
            {
                "role": "system",
                "content": "You are an expert QA engineer who specializes in creating comprehensive, well-structured test cases. Generate test cases that are clear, actionable, and cover both positive and negative scenarios. Format your response as structured test cases with clear steps, expected results, and test data where applicable."
            },
            {
                "role": "user",
                "content": base_prompt
            }
        ]
        
        dynamic_max_tokens = self._calculate_max_completion_tokens(messages, selected_model)
        
        try:
            response = self.client.chat.completions.create(
                model=selected_model,
                messages=messages,  # type: ignore
                max_completion_tokens=dynamic_max_tokens
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            raise Exception(f"Failed to generate test cases: {str(e)}")
    
    def refine_test_cases(self, conversation_history, refinement_prompt, model=None):
        """
        Refine existing test cases based on user feedback
        """
        # Get the last test cases from conversation history
        last_test_cases = ""
        story_context = None
        
        for message in reversed(conversation_history):
            if message['type'] == 'assistant' and 'test_cases' not in message.get('content', '').lower():
                last_test_cases = message['content']
                break
            elif message['type'] == 'user' and message.get('jira_story'):
                story_context = message['jira_story']
        
        refinement_prompt_full = f"""
        Based on the following existing test cases and the original Jira story context, please refine and improve the test cases according to the user's feedback.
        
        Original Story Context:
        - Title: {story_context.get('title', 'N/A') if story_context else 'N/A'}
        - Description: {story_context.get('description', 'N/A') if story_context else 'N/A'}
        
        Existing Test Cases:
        {last_test_cases}
        
        User Feedback/Refinement Request:
        {refinement_prompt}
        
        Please provide the updated and improved test cases, maintaining the same structure and format while incorporating the requested changes.
        """
        
        # Use provided model or default
        selected_model = model or self.default_model
        
        # Calculate dynamic max tokens for refinement
        messages = [
            {
                "role": "system",
                "content": "You are an expert QA engineer. The user wants you to refine existing test cases based on their feedback. Keep the good parts and improve based on their specific requests. Maintain professional test case formatting."
            },
            {
                "role": "user",
                "content": refinement_prompt_full
            }
        ]
        
        dynamic_max_tokens = self._calculate_max_completion_tokens(messages, selected_model)
        
        try:
            response = self.client.chat.completions.create(
                model=selected_model,
                messages=messages,  # type: ignore
                max_completion_tokens=dynamic_max_tokens
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            raise Exception(f"Failed to refine test cases: {str(e)}")
    
    def _build_base_prompt(self, story_details, custom_prompt=""):
        """
        Build the base prompt for test case generation
        """
        prompt = f"""
        Please generate comprehensive test cases for the following Jira story:
        
        **Story Details:**
        - ID: {story_details['key']}
        - Title: {story_details['title']}
        - Type: {story_details['issue_type']}
        - Status: {story_details['status']}
        - Priority: {story_details['priority']}
        
        **Description:**
        {story_details['description']}
        
        **Comments:**
        """
        
        if story_details['comments']:
            for i, comment in enumerate(story_details['comments']):
                prompt += f"\n{i+1}. {comment['author']}: {comment['body']}"
        else:
            prompt += "\nNo comments available."
        
        if custom_prompt:
            prompt += f"""
            
        **Additional Requirements/Focus Areas:**
        {custom_prompt}
        """
        
        prompt += """
        
        Please generate test cases that include:
        1. **Positive Test Cases** - Happy path scenarios
        2. **Negative Test Cases** - Error conditions and edge cases
        3. **Boundary Test Cases** - Testing limits and constraints
        4. **Integration Test Cases** - If the story involves integrations
        5. **User Experience Test Cases** - Usability and accessibility aspects
        
        For each test case, please provide:
        - **Test Case ID** (e.g., TC001)
        - **Test Case Title**
        - **Preconditions**
        - **Test Steps** (numbered)
        - **Expected Results**
        - **Test Data** (if applicable)
        - **Priority** (High/Medium/Low)
        
        Format the response in a clear, structured manner that can be easily understood and executed by QA testers.
        """
        
        return prompt
    
    def _estimate_prompt_tokens(self, messages):
        """
        Estimate the number of tokens in the prompt messages
        """
        try:
            total_tokens = 0
            
            # Count tokens for each message
            for message in messages:
                content = message.get('content', '')
                # Add tokens for the content
                total_tokens += len(self.tokenizer.encode(content))
                # Add overhead for message formatting (role, etc.)
                total_tokens += 4  # Approximate overhead per message
            
            # Add overhead for the message array structure
            total_tokens += 3
            
            return total_tokens
            
        except Exception as e:
            # Fallback: rough estimation based on character count
            total_chars = sum(len(msg.get('content', '')) for msg in messages)
            return int(total_chars / 3.5)  # Rough approximation: ~3.5 chars per token
    
    def _calculate_max_completion_tokens(self, messages, model=None):
        """
        Calculate dynamic max completion tokens based on prompt content
        """
        try:
            # Use provided model or default
            selected_model = model or self.default_model
            model_context_limit = self.available_models.get(selected_model, {}).get("context_limit", 128000)
            
            # Estimate tokens used by the prompt
            prompt_tokens = self._estimate_prompt_tokens(messages)
            
            # Calculate available tokens for completion
            available_tokens = model_context_limit - prompt_tokens - self.safety_buffer
            
            # Apply dynamic scaling based on prompt size
            if prompt_tokens < 500:
                # Small prompts: Allow generous completion
                target_completion = min(available_tokens, 3000)
            elif prompt_tokens < 1500:
                # Medium prompts: Balanced allocation
                target_completion = min(available_tokens, 2500)
            else:
                # Large prompts: Conservative but adequate
                target_completion = min(available_tokens, 1500)
            
            # Ensure we stay within bounds
            final_tokens = max(
                min(target_completion, self.max_completion_tokens),
                self.min_completion_tokens
            )
            
            # Log the token calculation for debugging
            print(f"Token calculation: prompt={prompt_tokens}, available={available_tokens}, final={final_tokens}")
            
            return final_tokens
            
        except Exception as e:
            # Fallback to conservative default
            print(f"Token calculation failed: {e}. Using fallback.")
            return 1500