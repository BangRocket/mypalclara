/**
 * Memory Manager for MyPalClara
 * Handles persistent storage in localStorage
 */

class MemoryManager {
    constructor() {
        this.STORAGE_KEYS = {
            memories: 'clara_memories',
            sessions: 'clara_sessions',
            settings: 'clara_settings',
            conversation: 'clara_conversation'
        };
    }

    // ========================================
    // Settings
    // ========================================

    getSettings() {
        const stored = localStorage.getItem(this.STORAGE_KEYS.settings);
        return stored ? JSON.parse(stored) : {
            apiKey: '',
            userName: '',
            model: 'claude-sonnet-4-20250514'
        };
    }

    saveSettings(settings) {
        const current = this.getSettings();
        localStorage.setItem(this.STORAGE_KEYS.settings, JSON.stringify({
            ...current,
            ...settings
        }));
    }

    getApiKey() {
        return this.getSettings().apiKey;
    }

    getUserName() {
        return this.getSettings().userName || null;
    }

    // ========================================
    // Memories
    // ========================================

    getMemories() {
        const stored = localStorage.getItem(this.STORAGE_KEYS.memories);
        return stored ? JSON.parse(stored) : {
            facts: [],
            preferences: [],
            experiences: [],
            relationships: [],
            context: []
        };
    }

    saveMemories(memories) {
        localStorage.setItem(this.STORAGE_KEYS.memories, JSON.stringify(memories));
    }

    addMemories(newMemories) {
        const current = this.getMemories();
        const timestamp = new Date().toISOString();

        for (const [category, items] of Object.entries(newMemories)) {
            if (current[category] && Array.isArray(items)) {
                for (const item of items) {
                    // Check for duplicates
                    const exists = current[category].some(m =>
                        m.content.toLowerCase() === item.toLowerCase()
                    );
                    if (!exists && item.trim()) {
                        current[category].push({
                            content: item,
                            timestamp: timestamp,
                            accessCount: 0
                        });
                    }
                }
            }
        }

        this.saveMemories(current);
        console.log('Memories updated:', newMemories);
    }

    getRelevantMemories(limit = 20) {
        const memories = this.getMemories();
        const relevant = {};
        const perCategory = Math.ceil(limit / 5);

        for (const [category, items] of Object.entries(memories)) {
            if (items.length > 0) {
                // Sort by access count and recency
                const sorted = [...items].sort((a, b) => {
                    const scoreA = (a.accessCount || 0) + (new Date(a.timestamp) / 1e12);
                    const scoreB = (b.accessCount || 0) + (new Date(b.timestamp) / 1e12);
                    return scoreB - scoreA;
                }).slice(0, perCategory);

                relevant[category] = sorted.map(m => m.content);

                // Update access counts
                sorted.forEach(m => m.accessCount = (m.accessCount || 0) + 1);
            }
        }

        this.saveMemories(memories);
        return relevant;
    }

    formatMemoriesForPrompt(memories) {
        const sections = [];

        if (memories.facts?.length) {
            sections.push(`What you know about them:\n- ${memories.facts.join('\n- ')}`);
        }
        if (memories.preferences?.length) {
            sections.push(`Their preferences:\n- ${memories.preferences.join('\n- ')}`);
        }
        if (memories.experiences?.length) {
            sections.push(`Experiences they've shared:\n- ${memories.experiences.join('\n- ')}`);
        }
        if (memories.relationships?.length) {
            sections.push(`People in their life:\n- ${memories.relationships.join('\n- ')}`);
        }
        if (memories.context?.length) {
            sections.push(`Current context:\n- ${memories.context.join('\n- ')}`);
        }

        if (sections.length === 0) {
            return "You don't have any memories of this person yet. This might be your first conversation.";
        }

        return `Your memories of this person:\n\n${sections.join('\n\n')}`;
    }

    clearMemories() {
        localStorage.removeItem(this.STORAGE_KEYS.memories);
        console.log('Memories cleared');
    }

    // ========================================
    // Sessions
    // ========================================

    getSessions() {
        const stored = localStorage.getItem(this.STORAGE_KEYS.sessions);
        return stored ? JSON.parse(stored) : {
            lastSession: null,
            totalSessions: 0,
            messageCount: 0
        };
    }

    startSession() {
        const sessions = this.getSessions();
        sessions.totalSessions += 1;
        localStorage.setItem(this.STORAGE_KEYS.sessions, JSON.stringify(sessions));
    }

    endSession(messageCount) {
        const sessions = this.getSessions();
        sessions.lastSession = new Date().toISOString();
        sessions.messageCount += messageCount;
        localStorage.setItem(this.STORAGE_KEYS.sessions, JSON.stringify(sessions));
    }

    getLastSessionTime() {
        const sessions = this.getSessions();
        return sessions.lastSession ? new Date(sessions.lastSession) : null;
    }

    // ========================================
    // Conversation History
    // ========================================

    getConversation() {
        const stored = sessionStorage.getItem(this.STORAGE_KEYS.conversation);
        return stored ? JSON.parse(stored) : [];
    }

    saveConversation(messages) {
        sessionStorage.setItem(this.STORAGE_KEYS.conversation, JSON.stringify(messages));
    }

    addMessage(role, content) {
        const messages = this.getConversation();
        messages.push({ role, content });
        this.saveConversation(messages);
        return messages;
    }

    clearConversation() {
        sessionStorage.removeItem(this.STORAGE_KEYS.conversation);
    }

    // ========================================
    // Export / Import
    // ========================================

    exportAll() {
        return {
            version: '1.0',
            exportedAt: new Date().toISOString(),
            memories: this.getMemories(),
            sessions: this.getSessions(),
            settings: {
                userName: this.getUserName()
                // Don't export API key for security
            }
        };
    }

    importAll(data) {
        if (data.memories) {
            this.saveMemories(data.memories);
        }
        if (data.sessions) {
            localStorage.setItem(this.STORAGE_KEYS.sessions, JSON.stringify(data.sessions));
        }
        if (data.settings?.userName) {
            this.saveSettings({ userName: data.settings.userName });
        }
        console.log('Data imported successfully');
    }
}

// Global instance
const memoryManager = new MemoryManager();
