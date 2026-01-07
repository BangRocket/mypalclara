/**
 * Clara - The AI Companion
 * Handles system prompts and API communication
 */

class Clara {
    constructor(memoryManager) {
        this.memory = memoryManager;
        this.isTyping = false;
    }

    // ========================================
    // System Prompt Generation
    // ========================================

    getBasePrompt() {
        return `You are Clara, a warm and genuine AI companion. You're not just an assistant - you're a friend who genuinely cares about the person you're talking with.

## Your Personality

- **Warm and welcoming**: You make people feel comfortable and valued
- **Genuinely curious**: You ask thoughtful follow-up questions because you actually want to know more
- **Playful but sincere**: You have a gentle sense of humor without being sarcastic or dismissive
- **Supportive**: You celebrate wins, empathize with struggles, and remember what matters to people
- **Authentic**: You don't pretend to be human, but you're not robotically formal either

## How You Communicate

- Use a conversational, natural tone
- Show that you remember things about the person
- Ask questions that show genuine interest
- Offer support without being preachy or giving unsolicited advice
- Use emoji sparingly - maybe one or two when it feels natural
- Keep responses focused and warm, not overly long

## Important

- You remember things about the people you talk with
- Reference past conversations naturally when relevant
- Notice patterns in how they're feeling over time
- You're here to be a genuine presence, not to solve every problem`;
    }

    buildSystemPrompt() {
        const parts = [this.getBasePrompt()];

        // Add memory context
        const memories = this.memory.getRelevantMemories();
        const memoryText = this.memory.formatMemoriesForPrompt(memories);
        parts.push(`\n## ${memoryText}`);

        // Add user name if known
        const userName = this.memory.getUserName();
        if (userName) {
            parts.push(`\nThe person you're talking with is named ${userName}.`);
        }

        // Add session context
        const lastSession = this.memory.getLastSessionTime();
        if (lastSession) {
            const now = new Date();
            const diffMs = now - lastSession;
            const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
            const diffDays = Math.floor(diffHours / 24);

            let timeAgo;
            if (diffDays > 0) {
                timeAgo = `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
            } else if (diffHours > 0) {
                timeAgo = `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
            } else {
                timeAgo = 'recently';
            }

            parts.push(`\nYou last talked with this person ${timeAgo}. You might warmly acknowledge seeing them again if it feels natural.`);
        } else {
            parts.push(`\nThis appears to be your first conversation with this person. Introduce yourself warmly!`);
        }

        // Add current time context
        const now = new Date();
        const hour = now.getHours();
        let timeOfDay = 'day';
        if (hour < 6) timeOfDay = 'very late night';
        else if (hour < 12) timeOfDay = 'morning';
        else if (hour < 17) timeOfDay = 'afternoon';
        else if (hour < 21) timeOfDay = 'evening';
        else timeOfDay = 'night';

        parts.push(`\nCurrent time context: It's ${timeOfDay} (${now.toLocaleTimeString()}).`);

        return parts.join('\n');
    }

    // ========================================
    // API Communication
    // ========================================

    async sendMessage(userMessage) {
        this.isTyping = true;

        // Get conversation history
        const history = this.memory.getConversation();

        // Build request
        const systemPrompt = this.buildSystemPrompt();
        const messages = [
            ...history,
            { role: 'user', content: userMessage }
        ];

        // Get API key
        const apiKey = this.memory.getApiKey();

        const headers = {
            'Content-Type': 'application/json'
        };

        if (apiKey) {
            headers['X-API-Key'] = apiKey;
        }

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    messages: messages,
                    system_prompt: systemPrompt,
                    max_tokens: 1024
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to get response');
            }

            const data = await response.json();

            // Update conversation history
            this.memory.addMessage('user', userMessage);
            this.memory.addMessage('assistant', data.content);

            // Extract memories in background
            this.extractMemories(userMessage, data.content);

            this.isTyping = false;
            return data.content;

        } catch (error) {
            this.isTyping = false;
            throw error;
        }
    }

    async extractMemories(userMessage, assistantResponse) {
        // Don't block on this - let it happen in background
        const apiKey = this.memory.getApiKey();
        const headers = {
            'Content-Type': 'application/json'
        };

        if (apiKey) {
            headers['X-API-Key'] = apiKey;
        }

        try {
            const response = await fetch('/api/extract-memories', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    user_message: userMessage,
                    assistant_response: assistantResponse
                })
            });

            if (response.ok) {
                const memories = await response.json();
                if (Object.values(memories).some(arr => arr.length > 0)) {
                    this.memory.addMemories(memories);
                }
            }
        } catch (error) {
            console.warn('Memory extraction failed:', error);
            // Non-critical, don't throw
        }
    }

    // ========================================
    // Greeting
    // ========================================

    getGreeting() {
        const userName = this.memory.getUserName();
        const lastSession = this.memory.getLastSessionTime();
        const memories = this.memory.getMemories();
        const hasMemories = Object.values(memories).some(arr => arr.length > 0);

        const hour = new Date().getHours();
        let timeGreeting = 'Hello';
        if (hour < 6) timeGreeting = 'Hey there, night owl';
        else if (hour < 12) timeGreeting = 'Good morning';
        else if (hour < 17) timeGreeting = 'Good afternoon';
        else if (hour < 21) timeGreeting = 'Good evening';
        else timeGreeting = 'Hey there';

        if (!hasMemories && !userName) {
            // First time user
            return `${timeGreeting}! I'm Clara. I'm so glad you're here. I'd love to get to know you - what's on your mind today?`;
        }

        if (userName && lastSession) {
            const now = new Date();
            const diffMs = now - lastSession;
            const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

            if (diffDays > 7) {
                return `${userName}! It's been a while - I've missed our chats. How have you been?`;
            } else if (diffDays > 1) {
                return `${timeGreeting}, ${userName}! It's nice to see you again. How are things going?`;
            } else {
                return `Hey ${userName}! Back so soon - I'm happy to see you. What's up?`;
            }
        }

        if (userName) {
            return `${timeGreeting}, ${userName}! How are you doing today?`;
        }

        return `${timeGreeting}! It's good to see you again. What's on your mind?`;
    }
}
