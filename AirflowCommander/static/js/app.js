// AI Test Case Generator - Frontend JavaScript

class TestCaseApp {
    constructor() {
        this.currentConversationId = null;
        this.conversations = [];
        this.isGenerating = false;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadConversations();
        this.loadAvailableModels();
    }

    bindEvents() {
        // New conversation button
        document.getElementById('newConversationBtn').addEventListener('click', () => {
            this.createNewConversation();
        });

        // Jira form submission
        document.getElementById('jiraForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.generateTestCases();
        });

        // Satisfaction check buttons
        document.getElementById('satisfiedBtn').addEventListener('click', () => {
            this.handleSatisfied();
        });

        document.getElementById('refineBtn').addEventListener('click', () => {
            this.showRefinementInput();
        });

        // Refinement input
        document.getElementById('refinementBtn').addEventListener('click', () => {
            this.refineTestCases();
        });

        document.getElementById('refinementInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.refineTestCases();
            }
        });
    }

    async loadConversations() {
        try {
            const response = await fetch('/api/conversations');
            const conversations = await response.json();
            this.conversations = conversations;
            this.renderConversationList();
        } catch (error) {
            console.error('Failed to load conversations:', error);
        }
    }

    async loadAvailableModels() {
        try {
            const response = await fetch('/api/models');
            const data = await response.json();
            
            const modelSelect = document.getElementById('aiModel');
            modelSelect.innerHTML = '';
            
            // Add options for each model
            Object.entries(data.models).forEach(([modelId, modelInfo]) => {
                const option = document.createElement('option');
                option.value = modelId;
                option.textContent = `${modelInfo.name} (${modelInfo.cost} Cost)`;
                
                // Select the default model
                if (modelId === data.default) {
                    option.selected = true;
                }
                
                modelSelect.appendChild(option);
            });
            
        } catch (error) {
            console.error('Failed to load models:', error);
            // Fallback to a default option
            const modelSelect = document.getElementById('aiModel');
            modelSelect.innerHTML = '<option value="gpt-5">GPT-5 (Latest)</option>';
        }
    }

    renderConversationList() {
        const listContainer = document.getElementById('conversationList');
        
        if (this.conversations.length === 0) {
            listContainer.innerHTML = `
                <div class="text-center p-3 text-muted">
                    <small>No conversations yet</small>
                </div>
            `;
            return;
        }

        const conversationsHtml = this.conversations.map(conv => `
            <div class="conversation-item ${conv.id === this.currentConversationId ? 'active' : ''}" 
                 onclick="app.selectConversation('${conv.id}')">
                <div class="conversation-title">${conv.title}</div>
                <div class="conversation-date">${this.formatDate(conv.created_at)}</div>
            </div>
        `).join('');

        listContainer.innerHTML = conversationsHtml;
    }

    async createNewConversation() {
        try {
            const response = await fetch('/api/conversations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const conversation = await response.json();
            
            this.conversations.unshift(conversation);
            this.currentConversationId = conversation.id;
            this.renderConversationList();
            this.showInputArea();
            this.clearChat();
            this.updateConversationTitle(conversation.title);
            
        } catch (error) {
            console.error('Failed to create conversation:', error);
            this.showError('Failed to create new conversation. Please try again.');
        }
    }

    async selectConversation(conversationId) {
        try {
            const response = await fetch(`/api/conversations/${conversationId}`);
            const conversation = await response.json();
            
            this.currentConversationId = conversationId;
            this.renderConversationList();
            this.renderConversation(conversation);
            this.updateConversationTitle(conversation.title);
            
        } catch (error) {
            console.error('Failed to load conversation:', error);
        }
    }

    renderConversation(conversation) {
        this.clearChat();
        
        if (conversation.messages.length === 0) {
            this.showInputArea();
            return;
        }

        const messagesContainer = document.getElementById('chatMessages');
        
        conversation.messages.forEach(message => {
            this.appendMessage(message);
        });

        // Show refinement options if the last message is from AI
        const lastMessage = conversation.messages[conversation.messages.length - 1];
        if (lastMessage && lastMessage.type === 'assistant') {
            this.showSatisfactionCheck();
        }

        this.scrollToBottom();
    }

    async generateTestCases() {
        if (this.isGenerating || !this.currentConversationId) return;

        const jiraUrl = document.getElementById('jiraUrl').value;
        const jiraUsername = document.getElementById('jiraUsername').value;
        const jiraPassword = document.getElementById('jiraPassword').value;
        const jiraStoryId = document.getElementById('jiraStoryId').value;
        const customPrompt = document.getElementById('customPrompt').value;
        const aiModel = document.getElementById('aiModel').value;

        if (!jiraUrl || !jiraUsername || !jiraPassword || !jiraStoryId) {
            this.showError('Please fill in all required Jira fields.');
            return;
        }

        this.isGenerating = true;
        this.showLoadingModal();

        try {
            const response = await fetch(`/api/conversations/${this.currentConversationId}/messages`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    conversation_id: this.currentConversationId,
                    jira_story_id: jiraStoryId,
                    jira_username: jiraUsername,
                    jira_password: jiraPassword,
                    jira_url: jiraUrl,
                    custom_prompt: customPrompt,
                    ai_model: aiModel
                })
            });

            const data = await response.json();

            if (response.ok) {
                this.renderConversation(data.conversation);
                this.showSatisfactionCheck();
                this.updateConversationTitle(data.conversation.title);
                this.loadConversations(); // Refresh the sidebar
            } else {
                this.showError(data.error || 'Failed to generate test cases');
            }

        } catch (error) {
            console.error('Error generating test cases:', error);
            this.showError('Failed to generate test cases. Please check your connection and try again.');
        } finally {
            this.isGenerating = false;
            this.hideLoadingModal();
        }
    }

    async refineTestCases() {
        const refinementPrompt = document.getElementById('refinementInput').value.trim();
        const aiModel = document.getElementById('aiModel').value;
        
        if (!refinementPrompt || !this.currentConversationId) return;

        this.isGenerating = true;
        this.showLoadingModal();

        try {
            const response = await fetch(`/api/conversations/${this.currentConversationId}/refine`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    conversation_id: this.currentConversationId,
                    refinement_prompt: refinementPrompt,
                    ai_model: aiModel
                })
            });

            const data = await response.json();

            if (response.ok) {
                this.renderConversation(data.conversation);
                this.showSatisfactionCheck();
                document.getElementById('refinementInput').value = '';
            } else {
                this.showError(data.error || 'Failed to refine test cases');
            }

        } catch (error) {
            console.error('Error refining test cases:', error);
            this.showError('Failed to refine test cases. Please try again.');
        } finally {
            this.isGenerating = false;
            this.hideLoadingModal();
        }
    }

    appendMessage(message) {
        const messagesContainer = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.type}-message`;
        
        let avatarIcon = '<i class="bi bi-person-circle"></i>';
        let avatarClass = 'user-avatar';
        
        if (message.type === 'assistant') {
            avatarIcon = '<i class="bi bi-robot"></i>';
            avatarClass = 'ai-avatar';
        } else if (message.type === 'error') {
            avatarIcon = '<i class="bi bi-exclamation-triangle"></i>';
            avatarClass = 'error-avatar';
        }

        let contentHtml = '';
        
        // Add Jira story details if available
        if (message.jira_story) {
            contentHtml += this.renderJiraStoryDetails(message.jira_story);
        }
        
        // Add custom prompt if provided
        if (message.custom_prompt) {
            contentHtml += `<div class="mb-2"><strong>Custom Focus:</strong> ${message.custom_prompt}</div>`;
        }
        
        // Add main content
        contentHtml += `<div class="test-cases-content">${this.formatContent(message.content)}</div>`;
        
        messageDiv.innerHTML = `
            <div class="message-avatar ${avatarClass}">
                ${avatarIcon}
            </div>
            <div class="message-content">
                ${contentHtml}
                <div class="message-timestamp">${this.formatDate(message.timestamp)}</div>
            </div>
        `;

        messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    renderJiraStoryDetails(story) {
        return `
            <div class="jira-story-details">
                <div class="jira-story-header">
                    <i class="bi bi-kanban"></i>
                    <span>${story.key} - ${story.issue_type}</span>
                </div>
                <div class="jira-field"><strong>Title:</strong> ${story.title}</div>
                <div class="jira-field"><strong>Status:</strong> ${story.status}</div>
                <div class="jira-field"><strong>Priority:</strong> ${story.priority}</div>
                <div class="jira-field"><strong>Assignee:</strong> ${story.assignee}</div>
                ${story.description ? `<div class="jira-field"><strong>Description:</strong> ${story.description}</div>` : ''}
                ${story.comments.length > 0 ? `
                    <div class="jira-field">
                        <strong>Comments (${story.comments.length}):</strong>
                        <div class="mt-1">
                            ${story.comments.slice(0, 3).map(comment => 
                                `<small class="d-block text-muted">${comment.author}: ${comment.body.substring(0, 100)}${comment.body.length > 100 ? '...' : ''}</small>`
                            ).join('')}
                            ${story.comments.length > 3 ? '<small class="text-muted">... and more</small>' : ''}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    formatContent(content) {
        // Basic formatting for test cases - convert line breaks and add some structure
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffTime = now - date;
        const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } else if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays < 7) {
            return `${diffDays} days ago`;
        } else {
            return date.toLocaleDateString();
        }
    }

    showInputArea() {
        document.getElementById('welcomeMessage').style.display = 'none';
        document.getElementById('inputArea').style.display = 'block';
        document.getElementById('jiraFormContainer').style.display = 'block';
        document.getElementById('refinementContainer').style.display = 'none';
        document.getElementById('satisfactionCheck').style.display = 'none';
    }

    showSatisfactionCheck() {
        document.getElementById('jiraFormContainer').style.display = 'none';
        document.getElementById('refinementContainer').style.display = 'none';
        document.getElementById('satisfactionCheck').style.display = 'block';
    }

    showRefinementInput() {
        document.getElementById('satisfactionCheck').style.display = 'none';
        document.getElementById('refinementContainer').style.display = 'block';
        document.getElementById('refinementInput').focus();
    }

    handleSatisfied() {
        this.showSuccess('Conversation saved! You can now start a new conversation or continue refining.');
        setTimeout(() => {
            this.createNewConversation();
        }, 2000);
    }

    clearChat() {
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.innerHTML = '';
        document.getElementById('welcomeMessage').style.display = 'none';
        document.getElementById('inputArea').style.display = 'none';
    }

    updateConversationTitle(title) {
        document.getElementById('conversationTitle').textContent = title;
    }

    scrollToBottom() {
        const chatContainer = document.querySelector('.chat-container');
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    showLoadingModal() {
        const modal = new bootstrap.Modal(document.getElementById('loadingModal'));
        modal.show();
    }

    hideLoadingModal() {
        const modalElement = document.getElementById('loadingModal');
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) {
            modal.hide();
        }
    }

    showError(message) {
        // Create a temporary toast or alert
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show position-fixed';
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alertDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.parentNode.removeChild(alertDiv);
            }
        }, 5000);
    }

    showSuccess(message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-success alert-dismissible fade show position-fixed';
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alertDiv);
        
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.parentNode.removeChild(alertDiv);
            }
        }, 3000);
    }
}

// Initialize the app when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new TestCaseApp();
});