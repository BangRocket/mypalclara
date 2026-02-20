# Email Monitoring

Monitor email accounts and receive Discord alerts for important messages.

## Overview

The email monitoring service provides:
- Gmail OAuth integration
- IMAP support (iCloud, Outlook, etc.)
- Rule-based importance scoring
- Built-in presets for common use cases
- Per-account quiet hours
- Alert deduplication

## Configuration

```bash
# Enable the service
EMAIL_MONITORING_ENABLED=true

# Encryption key for IMAP passwords (generate with Fernet)
EMAIL_ENCRYPTION_KEY=your-fernet-key

# Polling interval
EMAIL_DEFAULT_POLL_INTERVAL=5    # Minutes between checks
```

### Generate Encryption Key

```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

## Connecting Accounts

### Gmail (OAuth)

Uses your existing Google OAuth connection:

```
@Clara connect my Gmail for email monitoring
```

Or use the tool directly:
```
email_connect_gmail
```

### IMAP (iCloud, Outlook, etc.)

```
@Clara connect my iCloud email
Server: imap.mail.me.com
Email: user@icloud.com
Password: your-app-specific-password
```

**Important**: Use app-specific passwords, not your main password.

#### Common IMAP Servers

| Provider | Server | Port |
|----------|--------|------|
| iCloud | imap.mail.me.com | 993 |
| Outlook | outlook.office365.com | 993 |
| Yahoo | imap.mail.yahoo.com | 993 |
| Gmail | imap.gmail.com | 993 |

## Alert Channel Setup

Set the Discord channel for email alerts:

```
@Clara set email alerts to this channel
```

Or specify a channel:
```
email_set_alert_channel(channel_id="123456789")
```

## Rule Presets

Built-in presets for common monitoring needs:

### Available Presets

| Preset | Description |
|--------|-------------|
| `job_hunting` | Recruiter emails, ATS platforms, job keywords |
| `urgent` | Emails with urgent/ASAP keywords |
| `security` | Password resets, 2FA codes, security alerts |
| `financial` | Banking, payment notifications |
| `shipping` | Package tracking, delivery updates |

### Apply Preset

```
@Clara apply the job_hunting email preset
```

Or:
```
email_apply_preset(preset_name="job_hunting")
```

### Preset Details

**job_hunting:**
- From: `*@greenhouse.io`, `*@lever.co`, `*@workday.com`, `*recruiter*`
- Subject: `interview`, `opportunity`, `position`, `application`

**urgent:**
- Subject: `urgent`, `asap`, `immediate`, `critical`, `emergency`

**security:**
- Subject: `password reset`, `verification code`, `2fa`, `security alert`
- From: `*@security.*`, `*noreply*`

**financial:**
- From: `*@bank*`, `*@paypal.com`, `*@venmo.com`
- Subject: `payment`, `transaction`, `deposit`, `withdrawal`

**shipping:**
- From: `*@ups.com`, `*@fedex.com`, `*@usps.com`, `*@amazon.com`
- Subject: `tracking`, `delivery`, `shipped`, `out for delivery`

## Custom Rules

Create custom rules for specific needs:

```
@Clara add an email rule for messages from my boss
```

Or use the tool:
```python
email_add_rule(
    name="boss_emails",
    from_pattern="*@company.com",
    subject_pattern="*",
    priority=10
)
```

### Rule Parameters

| Parameter | Description |
|-----------|-------------|
| `name` | Unique rule identifier |
| `from_pattern` | Sender pattern (supports wildcards) |
| `subject_pattern` | Subject pattern (supports wildcards) |
| `priority` | Importance score (1-10, higher = more important) |

### List Rules

```
@Clara list my email rules
```

### Remove Rule

```
@Clara remove the boss_emails rule
```

## Quiet Hours

Prevent alerts during specific times:

```
@Clara set quiet hours from 10pm to 7am
```

Or:
```python
email_set_quiet_hours(
    start_hour=22,
    end_hour=7,
    timezone="America/New_York"
)
```

## Alert Format

Email alerts appear in Discord like this:

```
📧 New Important Email

From: recruiter@company.com
Subject: Interview Opportunity at TechCorp
Received: 2 minutes ago

Preview: Hi, I came across your profile and wanted to reach out about...

Rule matched: job_hunting (priority: 8)
```

## Managing Accounts

### List Accounts

```
@Clara list my connected email accounts
```

### Check Status

```
@Clara email monitoring status
```

### Disconnect Account

```
@Clara disconnect my Gmail from email monitoring
```

## Tools Reference

| Tool | Description |
|------|-------------|
| `email_connect_gmail` | Connect Gmail via OAuth |
| `email_connect_imap` | Connect IMAP account |
| `email_list_accounts` | List connected accounts |
| `email_disconnect` | Remove an account |
| `email_set_alert_channel` | Set Discord alert channel |
| `email_set_quiet_hours` | Configure quiet hours |
| `email_toggle_ping` | Enable/disable @mentions |
| `email_apply_preset` | Apply rule preset |
| `email_list_presets` | List available presets |
| `email_add_rule` | Create custom rule |
| `email_list_rules` | List configured rules |
| `email_remove_rule` | Remove a rule |
| `email_status` | Check monitoring status |
| `email_recent_alerts` | View recent alerts |

## Database Tables

| Table | Purpose |
|-------|---------|
| `email_accounts` | User connections (Gmail OAuth or encrypted IMAP) |
| `email_rules` | Per-user importance rules |
| `email_alerts` | Alert history for deduplication |

## Architecture

```
┌─────────────────┐
│  Email Monitor  │  (mypalclara/services/email/)
│   monitor.py    │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────┐
│ Gmail │ │ IMAP  │
│ OAuth │ │ Login │
└───────┘ └───────┘
         │
         ▼
┌─────────────────┐
│  Rules Engine   │
│ rules_engine.py │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Discord Alert   │
└─────────────────┘
```

## Troubleshooting

### Gmail Not Connecting

1. Ensure Google OAuth is set up (see [[Configuration]])
2. Check `google_status` shows connected
3. Verify Gmail API is enabled in Google Cloud Console

### IMAP Authentication Failed

1. Use app-specific password, not main password
2. Enable "Less secure apps" or generate app password
3. Check server/port settings

### Alerts Not Arriving

1. Verify alert channel is set: `email_status`
2. Check bot has permission to post in channel
3. Review quiet hours settings
4. Check if emails match any rules

### Duplicate Alerts

Alert deduplication uses message ID. If seeing duplicates:
1. Check `email_recent_alerts` for patterns
2. May indicate rule overlap

## See Also

- [[Configuration]] - Google OAuth setup
- [[Discord-Features]] - Discord integration
- [[Troubleshooting]] - Common issues
