# Google Workspace Integration

Clara integrates with Google Workspace (Sheets, Drive, Docs, Calendar) using per-user OAuth.

## Overview

The integration provides:
- OAuth callback handling for Google Workspace
- Per-user token storage and refresh
- Google Sheets, Drive, Docs, and Calendar access
- Gmail integration for email monitoring

## Configuration

```bash
# Google OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://your-domain.example.com/oauth/google/callback
CLARA_API_URL=https://your-domain.example.com
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
4. Go to **Credentials** > **Create Credentials** > **OAuth client ID**
5. Application type: **Web application**
6. Add authorized redirect URI:
   - `https://your-domain.example.com/oauth/google/callback`
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
│  OAuth Callback     │
│  Exchange code      │
└──────────┬──────────┘
           │ Store tokens
           ▼
Clara: Google account connected!
```

### Connecting (Discord)

Users connect via Discord commands:
```
@Clara connect my Google account
/google connect
```

### Check Status

```
/google status
```

### Disconnect

```
/google disconnect
```

## Token Management

### Storage

Tokens are stored in the database:
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

## Security

### Recommendations

1. Use HTTPS for all endpoints
2. Validate `state` parameter in OAuth callback
3. Store tokens encrypted at rest
4. Implement rate limiting
5. Log OAuth events for auditing

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
