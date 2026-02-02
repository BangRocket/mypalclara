# API Service

Standalone FastAPI service for OAuth callbacks and external API endpoints.

## Overview

The API service provides:
- OAuth callback handling (Google Workspace)
- Token storage and refresh
- Health check endpoints
- Separation from Discord bot process

## Location

```
api_service/
├── main.py           # FastAPI application
├── Dockerfile        # Container image
└── requirements.txt
```

## Configuration

```bash
# Database (same as Discord bot)
DATABASE_URL=postgresql://user:pass@host:5432/clara_main

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://your-api.example.com/oauth/google/callback
```

## Endpoints

### Health Check

```
GET /health
```

Returns: `{"status": "healthy"}`

### Google OAuth

#### Get Authorization URL

```
GET /oauth/google/authorize/{user_id}
```

Returns JSON with authorization URL for the user to visit.

#### Start OAuth (Redirect)

```
GET /oauth/google/start/{user_id}
```

Redirects user directly to Google OAuth consent screen.

#### OAuth Callback

```
GET /oauth/google/callback
```

Handles OAuth callback from Google, exchanges code for tokens, stores in database.

#### Check Connection Status

```
GET /oauth/google/status/{user_id}
```

Returns connection status for the user.

#### Disconnect

```
POST /oauth/google/disconnect/{user_id}
```

Removes stored tokens for the user.

## Running

### Local Development

```bash
cd api_service
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Docker

```bash
cd api_service
docker build -t clara-api .
docker run -p 8000:8000 --env-file ../.env clara-api
```

## Railway Deployment

### Setup

1. Create new service in Railway
2. Set root directory to `api_service`
3. Railway auto-detects Python/FastAPI
4. Enable public networking
5. Note the generated domain

### Environment Variables

Set in Railway dashboard:

```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://your-api.up.railway.app/oauth/google/callback
```

### Update Discord Bot

Set `CLARA_API_URL` on Discord bot service:

```bash
CLARA_API_URL=https://your-api.up.railway.app
```

## Google Cloud Setup

### Create OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create or select a project
3. Enable APIs:
   - Google Sheets API
   - Google Drive API
   - Google Docs API
   - Google Calendar API
   - Gmail API (for email monitoring)
4. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
5. Application type: **Web application**
6. Add authorized redirect URI:
   - `https://your-api.example.com/oauth/google/callback`
7. Copy Client ID and Client Secret

### OAuth Consent Screen

1. Go to **OAuth consent screen**
2. User type: **External** (or Internal for Workspace)
3. Fill in app information
4. Add scopes:
   - `https://www.googleapis.com/auth/spreadsheets`
   - `https://www.googleapis.com/auth/drive`
   - `https://www.googleapis.com/auth/documents`
   - `https://www.googleapis.com/auth/calendar`
   - `https://www.googleapis.com/auth/gmail.readonly`
5. Add test users if in testing mode

## OAuth Flow

```
User: @Clara connect Google

Clara: Click here to connect: [OAuth URL]
         │
         ▼
┌─────────────────────┐
│  Google OAuth       │
│  Consent Screen     │
└──────────┬──────────┘
           │ User approves
           ▼
┌─────────────────────┐
│  API Service        │
│  /oauth/callback    │
└──────────┬──────────┘
           │ Exchange code for tokens
           ▼
┌─────────────────────┐
│  Database           │
│  Store tokens       │
└──────────┬──────────┘
           │
           ▼
Clara: Google account connected!
```

## Token Management

### Storage

Tokens are stored in the `google_tokens` table:
- `user_id` - Discord user ID
- `access_token` - Short-lived access token
- `refresh_token` - Long-lived refresh token
- `token_expiry` - When access token expires
- `scopes` - Granted permission scopes

### Refresh

Tokens are automatically refreshed when:
1. Access token is expired
2. API call returns 401
3. User explicitly reconnects

## Architecture

```
┌─────────────────┐
│  Discord Bot    │
│  (clara tools)  │
└────────┬────────┘
         │ CLARA_API_URL
         ▼
┌─────────────────┐     ┌─────────────────┐
│   API Service   │────▶│   PostgreSQL    │
│   (FastAPI)     │     │   (tokens)      │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│  Google APIs    │
└─────────────────┘
```

## Security

### Recommendations

1. Use HTTPS for all endpoints
2. Validate `state` parameter in OAuth callback
3. Store tokens encrypted at rest
4. Implement rate limiting
5. Log OAuth events for auditing

### CORS

Configure CORS if calling from browser:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-app.com"],
    allow_methods=["GET", "POST"],
)
```

## Troubleshooting

### Redirect URI Mismatch

Error: `redirect_uri_mismatch`

1. Check `GOOGLE_REDIRECT_URI` matches exactly
2. Include protocol (`https://`)
3. No trailing slash
4. Must be in authorized redirect URIs in Google Console

### Token Refresh Failed

1. User may have revoked access
2. Refresh token may be expired (6 months inactive)
3. Have user reconnect: `/google disconnect` then `/google connect`

### Database Connection Error

1. Check `DATABASE_URL` format
2. Verify network connectivity
3. Check SSL requirements

## See Also

- [[Configuration]] - Google OAuth configuration
- [[Discord-Features]] - Google Workspace tools
- [[Deployment]] - Production deployment
