# Web Interface

Clara's web interface provides a browser-based UI for managing memories, chatting, exploring the knowledge graph, and linking platform identities.

## Overview

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend | FastAPI (Python) | REST API, OAuth2, JWT auth, WebSocket chat |
| Frontend | React 19 + Vite + TypeScript | Single-page app with dark theme |
| Styling | Tailwind CSS v4 | Utility-first CSS with custom design tokens |
| State | Zustand + TanStack Query | Client state + server cache |
| Editor | Tiptap (ProseMirror) | Block-based memory editing |
| Graph | React Flow (@xyflow/react) | Entity relationship visualization |

## Architecture

```
┌─────────────────────────────────────────────┐
│               Browser (React SPA)            │
│  ┌───────┐ ┌──────┐ ┌───────┐ ┌──────────┐ │
│  │  KB   │ │ Chat │ │ Graph │ │ Settings │ │
│  └───┬───┘ └──┬───┘ └───┬───┘ └────┬─────┘ │
│      │   REST  │  WS    │  REST    │        │
└──────┼─────────┼────────┼──────────┼────────┘
       │         │        │          │
┌──────┼─────────┼────────┼──────────┼────────┐
│      ▼         ▼        ▼          ▼        │
│           FastAPI (mypalclara/web/)          │
│  ┌──────┐ ┌────────┐ ┌──────┐ ┌──────────┐ │
│  │ API  │ │  Chat  │ │ Auth │ │Middleware│ │
│  │Routes│ │  WS    │ │OAuth │ │Rate Limit│ │
│  └──┬───┘ └───┬────┘ └──┬───┘ └──────────┘ │
│     │         │         │                   │
│     ▼         ▼         ▼                   │
│  ┌──────┐ ┌────────┐ ┌──────────────────┐  │
│  │ Rook │ │Gateway │ │  PostgreSQL      │  │
│  │Memory│ │  WS    │ │  (CanonicalUser, │  │
│  └──────┘ └────────┘ │   PlatformLink)  │  │
│                      └──────────────────┘  │
└─────────────────────────────────────────────┘
```

## Pages

### Knowledge Base (`/`)

Anytype-inspired memory browser with:
- **Grid view** — Cards with content preview, category badge, key indicator, FSRS stability gauge
- **List view** — Compact table with sortable columns
- **Semantic search** — Full-text + vector search across all memories
- **Category filter chips** — Filter by category, key-only toggle
- **Saved Sets** — Save and load filter presets (persisted in localStorage)
- **Memory editor** — Tiptap block editor with properties panel (category, key toggle, FSRS state, history)
- **Export/Import** — Download all memories as JSON, upload from JSON file
- **Tags** — Tag memories with custom labels

### Chat (`/chat`)

Streaming chat interface connected to the Clara Gateway:
- Real-time streaming via WebSocket
- Tool call display (collapsible cards with status, output preview)
- Markdown rendering with syntax highlighting (Prism + oneDark theme)
- File upload (images, text, PDF — up to 10MB per file)
- Stop generation button

### Graph Explorer (`/graph`)

React Flow visualization of the FalkorDB entity graph:
- Force-directed layout with type-coded node colors
- Click node to see entity details and linked memories
- Search overlay for finding entities
- Subgraph queries with configurable depth

### Intentions (`/intentions`)

Management UI for Clara's standing instructions:
- List/filter intentions (all, active, fired)
- Create with trigger conditions (keyword, channel, DM)
- Priority and fire-once controls
- Delete intentions

### Settings (`/settings`)

User profile and adapter linking:
- View canonical user profile
- Link/unlink platform accounts (Discord, Google)
- OAuth2 flow for connecting additional platforms

## Authentication

### OAuth2 Flow

1. User clicks "Sign in with Discord/Google" on `/login`
2. Redirect to OAuth provider's authorization URL
3. Callback exchanges code for tokens, fetches user profile
4. Creates or finds `CanonicalUser` + `PlatformLink` in database
5. Issues JWT in httpOnly cookie
6. Redirects to app

### JWT Sessions

- JWT stored in httpOnly cookie (HTTPS) or query param (WebSocket)
- Default expiry: 24 hours (configurable via `WEB_JWT_EXPIRE_MINUTES`)
- Token contains `sub` (canonical user ID) and standard claims

### Cross-Platform Identity

The `CanonicalUser` model unifies identities across platforms:

```
CanonicalUser (id, display_name, email, avatar)
  └── PlatformLink (platform, platform_user_id, prefixed_user_id)
       ├── discord-123456
       ├── teams-abc-def
       └── web-{canonical_id}
```

When a user links multiple platforms, their memories from all platforms appear in the Knowledge Base. The gateway processor resolves canonical users for cross-platform memory queries.

## API Endpoints

### Auth (`/auth`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/login/{provider}` | Get OAuth authorization URL |
| GET | `/auth/callback/{provider}` | OAuth callback (exchanges code) |
| POST | `/auth/logout` | Revoke session |
| GET | `/auth/me` | Current user info |
| POST | `/auth/link/{provider}` | Link additional platform |
| DELETE | `/auth/link/{provider}` | Unlink platform |

### Memories (`/api/v1/memories`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/memories` | List with pagination + filters |
| GET | `/memories/stats` | Count by category, key, etc. |
| GET | `/memories/export` | Export all as JSON |
| GET | `/memories/tags/all` | List all unique tags |
| GET | `/memories/{id}` | Single memory with metadata |
| POST | `/memories` | Create memory |
| POST | `/memories/search` | Semantic search |
| POST | `/memories/import` | Import from JSON |
| PUT | `/memories/{id}` | Update content/metadata |
| PUT | `/memories/{id}/tags` | Update tags |
| DELETE | `/memories/{id}` | Delete memory |
| GET | `/memories/{id}/history` | Change history |
| GET | `/memories/{id}/dynamics` | FSRS state |

### Graph (`/api/v1/graph`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/graph/entities` | List entities |
| GET | `/graph/entities/{name}` | Entity with relationships |
| GET | `/graph/search` | Search entities |
| GET | `/graph/subgraph` | Filtered subgraph for visualization |

### Intentions (`/api/v1/intentions`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/intentions` | List with filters |
| POST | `/intentions` | Create intention |
| PUT | `/intentions/{id}` | Update intention |
| DELETE | `/intentions/{id}` | Delete intention |

### Sessions (`/api/v1/sessions`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sessions` | List chat sessions |
| GET | `/sessions/{id}` | Session with messages |

### Users (`/api/v1/users`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/users/me` | Canonical user + links |
| PUT | `/users/me` | Update profile |
| GET | `/users/me/links` | List platform links |

### Chat WebSocket (`/ws/chat`)

Authentication via JWT query parameter: `/ws/chat?token=<jwt>`

**Client sends:**
```json
{"type": "message", "content": "Hello Clara", "tier": "mid"}
{"type": "cancel", "request_id": "..."}
{"type": "ping"}
```

**Server sends:**
```json
{"type": "response_start", "request_id": "..."}
{"type": "chunk", "text": "...", "accumulated": "..."}
{"type": "tool_start", "tool_name": "...", "step": 1}
{"type": "tool_result", "tool_name": "...", "success": true}
{"type": "response_end", "full_text": "...", "tool_count": 0}
{"type": "error", "message": "..."}
```

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `WEB_SECRET_KEY` | JWT signing key (change in production!) |
| `DISCORD_OAUTH_CLIENT_ID` | Discord OAuth2 application client ID |
| `DISCORD_OAUTH_CLIENT_SECRET` | Discord OAuth2 application client secret |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_HOST` | `0.0.0.0` | Server bind address |
| `WEB_PORT` | `8000` | Server port |
| `WEB_JWT_EXPIRE_MINUTES` | `1440` | JWT token expiry (24h) |
| `WEB_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated CORS origins |
| `WEB_STATIC_DIR` | (empty) | Path to built frontend for production serving |
| `WEB_FRONTEND_URL` | `http://localhost:5173` | Frontend URL for OAuth redirects |
| `GOOGLE_OAUTH_CLIENT_ID` | (empty) | Google OAuth2 client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | (empty) | Google OAuth2 client secret |

## Development

### Running Locally

```bash
# Terminal 1: FastAPI backend (auto-reload)
poetry run uvicorn mypalclara.web.app:create_app --factory --reload --port 8000

# Terminal 2: Vite dev server (proxies API/WS to :8000)
cd web-ui && pnpm dev

# Terminal 3: Gateway (required for chat)
poetry run python -m mypalclara.gateway start
```

The Vite dev server runs on port 5173 and proxies `/api`, `/auth`, and `/ws` requests to the backend on port 8000.

### Production (Docker)

```bash
docker-compose --profile web up
```

Uses a multi-stage Dockerfile (`Dockerfile.web`):
1. **Stage 1**: Node.js builds the React frontend to `web-ui/dist/`
2. **Stage 2**: Python serves the built frontend via FastAPI's StaticFiles

### Running Tests

```bash
poetry run pytest tests/web/ -v
```

Tests cover JWT auth, rate limiting middleware, and configuration.

## Database Models

Four new models support the web identity system:

### CanonicalUser
Unified user identity across platforms.
- `id` (UUID PK), `display_name`, `primary_email` (unique), `avatar_url`, `created_at`, `updated_at`

### PlatformLink
Maps a platform-specific user to a canonical user.
- `id` (UUID PK), `canonical_user_id` (FK), `platform`, `platform_user_id`, `prefixed_user_id` (unique)
- Unique index on `(platform, platform_user_id)`

### OAuthToken
Stores OAuth2 tokens for linked providers.
- `id` (UUID PK), `canonical_user_id` (FK), `provider`, `access_token`, `refresh_token`, `expires_at`

### WebSession
Active web login sessions.
- `id` (UUID PK), `canonical_user_id` (FK), `session_token_hash` (unique), `created_at`, `expires_at`, `revoked`

### Migration

```bash
# Run the Alembic migration
poetry run python scripts/migrate.py

# Backfill existing users
poetry run python scripts/backfill_users.py --dry-run  # Preview
poetry run python scripts/backfill_users.py             # Execute
```

The backfill script scans all existing `user_id` values across Sessions, Messages, MemoryDynamics, and Intentions tables and creates `CanonicalUser` + `PlatformLink` records for each.

## Rate Limiting

The web API includes per-IP rate limiting:
- **120 requests/minute** sustained rate
- **30 requests/second** burst limit
- Only applies to `/api/` and `/auth/` endpoints
- Static files and WebSocket connections are not rate-limited
- Returns `429 Too Many Requests` with `Retry-After` header

## Frontend Structure

```
web-ui/src/
├── main.tsx                          # Entry point (QueryClient, Router, Auth)
├── App.tsx                           # Route definitions
├── index.css                         # Tailwind v4 theme + custom styles
├── api/client.ts                     # Typed API client
├── auth/
│   ├── AuthProvider.tsx              # Auth context (user, login, logout)
│   └── OAuthCallback.tsx             # OAuth redirect handler
├── stores/
│   ├── chatStore.ts                  # WebSocket chat state (Zustand)
│   └── savedSets.ts                  # Saved filter presets (localStorage)
├── hooks/useWebSocket.ts             # Auto-connect chat WebSocket
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx              # Sidebar + main content (responsive)
│   │   └── Sidebar.tsx               # Navigation sidebar
│   ├── knowledge/
│   │   ├── SearchBar.tsx             # Search input
│   │   ├── MemoryCard.tsx            # Grid card component
│   │   ├── MemoryGrid.tsx            # Responsive card grid
│   │   ├── MemoryList.tsx            # Table view
│   │   └── MemoryEditor.tsx          # Tiptap editor slide-over
│   ├── chat/
│   │   ├── ChatView.tsx              # Full chat UI
│   │   ├── MessageBubble.tsx         # Message with markdown + syntax highlighting
│   │   ├── ToolCallDisplay.tsx       # Collapsible tool call card
│   │   └── FileUpload.tsx            # File picker with base64 encoding
│   ├── graph/GraphCanvas.tsx         # React Flow wrapper
│   └── settings/AdapterLinking.tsx   # Platform link/unlink UI
└── pages/
    ├── Login.tsx                     # OAuth sign-in page
    ├── KnowledgeBase.tsx             # Memory browser
    ├── Chat.tsx                      # Chat page
    ├── GraphExplorer.tsx             # Graph visualization
    ├── Intentions.tsx                # Intentions management
    └── Settings.tsx                  # User settings
```
