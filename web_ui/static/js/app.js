/**
 * MyPalClara - Main Application
 * Handles UI interactions and ties everything together
 */

// Initialize Clara
const clara = new Clara(memoryManager);

// DOM Elements
const messagesContainer = document.getElementById('messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const settingsModal = document.getElementById('settings-modal');
const apiKeyInput = document.getElementById('api-key');
const userNameInput = document.getElementById('user-name');

// ========================================
// Initialization
// ========================================

document.addEventListener('DOMContentLoaded', () => {
    // Load settings into form
    const settings = memoryManager.getSettings();
    apiKeyInput.value = settings.apiKey || '';
    userNameInput.value = settings.userName || '';

    // Start session
    memoryManager.startSession();

    // Show greeting
    showGreeting();

    // Auto-resize textarea
    messageInput.addEventListener('input', autoResizeTextarea);

    // Check for server API key
    checkServerConfig();
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    const conversation = memoryManager.getConversation();
    memoryManager.endSession(conversation.length);
});

async function checkServerConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();

        if (config.has_server_key) {
            // Server has API key, user doesn't need to provide one
            const hint = document.querySelector('.setting-group .hint');
            if (hint) {
                hint.textContent = 'Server has a default key. You can optionally use your own.';
            }
        }
    } catch (error) {
        console.warn('Could not fetch server config:', error);
    }
}

function showGreeting() {
    const greeting = clara.getGreeting();
    addMessageToUI('clara', greeting);
}

// ========================================
// Message Handling
// ========================================

async function sendMessage(event) {
    event.preventDefault();

    const message = messageInput.value.trim();
    if (!message || clara.isTyping) return;

    // Check for API key
    if (!memoryManager.getApiKey()) {
        try {
            const config = await fetch('/api/config').then(r => r.json());
            if (!config.has_server_key) {
                showError('Please add your API key in settings first!');
                toggleSettings();
                return;
            }
        } catch (e) {
            showError('Please add your API key in settings first!');
            toggleSettings();
            return;
        }
    }

    // Clear input
    messageInput.value = '';
    autoResizeTextarea();

    // Add user message to UI
    addMessageToUI('user', message);

    // Show typing indicator
    const typingEl = showTypingIndicator();

    try {
        const response = await clara.sendMessage(message);

        // Remove typing indicator
        typingEl.remove();

        // Add Clara's response
        addMessageToUI('clara', response);

    } catch (error) {
        typingEl.remove();
        showError(error.message);
    }
}

function addMessageToUI(role, content) {
    const messageEl = document.createElement('div');
    messageEl.className = `message ${role}`;

    const avatar = role === 'clara' ? '🌸' : '👤';

    messageEl.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-bubble">
            <div class="message-content">${formatMessage(content)}</div>
        </div>
    `;

    messagesContainer.appendChild(messageEl);
    scrollToBottom();
}

function formatMessage(content) {
    // Basic formatting: escape HTML, convert newlines
    return content
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>')
        // Basic markdown-like formatting
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>');
}

function showTypingIndicator() {
    const typingEl = document.createElement('div');
    typingEl.className = 'message clara typing';
    typingEl.innerHTML = `
        <div class="message-avatar">🌸</div>
        <div class="message-bubble">
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    messagesContainer.appendChild(typingEl);
    scrollToBottom();
    return typingEl;
}

function showError(message) {
    const errorEl = document.createElement('div');
    errorEl.className = 'message clara';
    errorEl.innerHTML = `
        <div class="message-avatar">⚠️</div>
        <div class="message-bubble">
            <div class="message-content" style="color: #d45d5d;">
                Oops! ${message}
            </div>
        </div>
    `;
    messagesContainer.appendChild(errorEl);
    scrollToBottom();
}

function scrollToBottom() {
    messagesContainer.parentElement.scrollTop = messagesContainer.parentElement.scrollHeight;
}

// ========================================
// Input Handling
// ========================================

function handleKeyDown(event) {
    // Send on Enter (without Shift)
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        document.getElementById('chat-form').dispatchEvent(new Event('submit'));
    }
}

function autoResizeTextarea() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
}

// ========================================
// Settings Modal
// ========================================

function toggleSettings() {
    settingsModal.classList.toggle('hidden');

    if (!settingsModal.classList.contains('hidden')) {
        // Refresh values when opening
        const settings = memoryManager.getSettings();
        apiKeyInput.value = settings.apiKey || '';
        userNameInput.value = settings.userName || '';
    }
}

function saveSettings() {
    const apiKey = apiKeyInput.value.trim();
    const userName = userNameInput.value.trim();

    memoryManager.saveSettings({
        apiKey: apiKey,
        userName: userName
    });

    // If userName was just set and we have memories, add it as a fact
    if (userName && !memoryManager.getUserName()) {
        memoryManager.addMemories({
            facts: [`Their name is ${userName}`]
        });
    }

    toggleSettings();

    // Show confirmation
    showConfirmation('Settings saved!');
}

function showConfirmation(message) {
    // Simple toast-like notification
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 100px;
        left: 50%;
        transform: translateX(-50%);
        background: var(--text-primary);
        color: var(--bg-primary);
        padding: 12px 24px;
        border-radius: 8px;
        font-size: 14px;
        z-index: 1000;
        animation: fadeIn 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

// ========================================
// Memory Management
// ========================================

function exportMemories() {
    const data = memoryManager.exportAll();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `clara-memories-${new Date().toISOString().split('T')[0]}.json`;
    a.click();

    URL.revokeObjectURL(url);
    showConfirmation('Memories exported!');
}

function importMemories(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const data = JSON.parse(e.target.result);
            memoryManager.importAll(data);
            showConfirmation('Memories imported!');

            // Refresh the page to show new greeting
            setTimeout(() => location.reload(), 1500);
        } catch (error) {
            showError('Invalid file format');
        }
    };
    reader.readAsText(file);

    // Reset input
    event.target.value = '';
}

function clearMemories() {
    if (confirm('Are you sure you want to clear all memories? Clara will forget everything about you. This cannot be undone.')) {
        memoryManager.clearMemories();
        memoryManager.clearConversation();
        showConfirmation('Memories cleared');

        // Refresh to start fresh
        setTimeout(() => location.reload(), 1500);
    }
}

// ========================================
// Keyboard Shortcuts
// ========================================

document.addEventListener('keydown', (event) => {
    // Escape closes modal
    if (event.key === 'Escape' && !settingsModal.classList.contains('hidden')) {
        toggleSettings();
    }

    // Focus input with /
    if (event.key === '/' && document.activeElement !== messageInput) {
        event.preventDefault();
        messageInput.focus();
    }
});

// Close modal when clicking outside
settingsModal.addEventListener('click', (event) => {
    if (event.target === settingsModal) {
        toggleSettings();
    }
});
