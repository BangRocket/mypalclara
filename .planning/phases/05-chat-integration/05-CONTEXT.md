# Phase 5: Chat Integration - Context

**Gathered:** 2026-01-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Connect to Clara backend for AI conversations via desktop UI. Delivers a chat panel for sending messages, viewing history, and streaming responses. Clara can read and edit notes in Phase 6 - this phase focuses on the chat interface and backend connection.

</domain>

<decisions>
## Implementation Decisions

### Chat Panel Layout
- Dedicated tab/view, not sidebar or split - switch between notes and chat modes
- Sidebar icons for navigation (like VS Code activity bar) - icons to switch between Notes and Chat
- Clara always has context of the active note when chatting (automatic, not manual attachment)
- Persistent conversation history - all chats saved, can scroll back through time

### Message Display
- Chat bubbles style - user messages on right, Clara on left (iMessage-like)
- Timestamps + avatars - Clara has an icon/avatar, user has theirs
- Full markdown support - headers, lists, code blocks, links (like Discord)
- Syntax highlighted code blocks with copy button

### Input Behavior
- Multi-line with Shift+Enter - Enter sends, Shift+Enter for new line
- File and image attachments supported - drag-and-drop or button
- Slash commands supported - /help, /clear, /model etc. (like Discord)
- No character/token limit indicator - let users type freely

### Streaming UX
- Word by word streaming - text appears as generated, cursor at end
- Typing indicator before streaming starts - "Clara is thinking..." or animated dots
- Stop button visible during streaming to cancel response
- On connection drop: keep partial response, show error indicator (don't clear)
- Markdown renders on complete, not progressively (prevents visual jumping)
- Smart auto-scroll - follows bottom unless user scrolled up to read history
- Floating "scroll to bottom" button when viewing history

### Claude's Discretion
- Tool execution status display (inline status, just indicator, or detailed - based on Clara's existing patterns)
- Exact avatar design for Clara
- Loading states and skeleton designs
- Error message wording

</decisions>

<specifics>
## Specific Ideas

- Navigation feels like VS Code activity bar - icons on left sidebar to switch modes
- Chat bubbles should feel modern and clean, similar to iMessage
- Code blocks need proper syntax highlighting - this is important for Clara's code-heavy responses
- Smart scroll behavior is critical - don't lose your place when reading history

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope

</deferred>

---

*Phase: 05-chat-integration*
*Context gathered: 2026-01-24*
