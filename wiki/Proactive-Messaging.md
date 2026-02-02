# Proactive Messaging

Clara's organic response system for initiating conversations naturally.

## Philosophy

> "Reach out when there's genuine reason - not on a schedule. Be like a thoughtful friend."

The proactive messaging system allows Clara to initiate conversations when appropriate, rather than only responding to direct messages.

## Overview

The system consists of two components:

1. **Organic Response System (ORS)** - State machine for deciding when to speak
2. **Proactive Engine** - Background process for monitoring and initiating

## How It Works

### State Machine

```
     ┌──────────────────────────────────────┐
     │                                      │
     ▼                                      │
┌─────────┐     ┌─────────┐     ┌─────────┐ │
│  WAIT   │────▶│  THINK  │────▶│  SPEAK  │─┘
└─────────┘     └─────────┘     └─────────┘
     ▲               │
     └───────────────┘
```

1. **WAIT** - Observe conversation, accumulate context
2. **THINK** - Evaluate if there's genuine reason to speak
3. **SPEAK** - Deliver proactive message (returns to WAIT)

### Decision Factors

Clara considers:
- **Notes** - Accumulated observations and follow-up items
- **Emotional context** - Recent conversation patterns
- **User interaction patterns** - Activity history
- **Time since last message** - Avoid being intrusive
- **Topic connections** - Relevant insights to share

## Configuration

```bash
# Enable proactive messaging
ORS_ENABLED=true

# Check interval (minutes between assessments)
ORS_BASE_INTERVAL_MINUTES=15

# Minimum hours between proactive messages
ORS_MIN_SPEAK_GAP_HOURS=2

# Days of activity history to consider
ORS_ACTIVE_DAYS=7

# Days before note relevance decays
ORS_NOTE_DECAY_DAYS=7

# Time before extracting conversation summary (minutes)
ORS_IDLE_TIMEOUT_MINUTES=30
```

## Notes System

Clara accumulates "notes" - observations and follow-up items:

### Note Types

| Type | Description |
|------|-------------|
| `follow_up` | Something to check back on |
| `insight` | Interesting observation |
| `reminder` | Time-sensitive item |
| `connection` | Link between topics |

### Note Lifecycle

1. **Creation** - Extracted from conversations
2. **Validation** - Checked against recent context
3. **Decay** - Relevance decreases over time
4. **Delivery** - Used in proactive message
5. **Expiration** - Removed after `ORS_NOTE_DECAY_DAYS`

### Example Notes

```
- Josh mentioned a job interview next Tuesday (follow_up)
- User seems stressed about the deadline (insight)
- Asked to remind about the meeting at 3pm (reminder)
- The API issue might be related to the caching problem (connection)
```

## Proactive Message Types

### Follow-ups

```
Hey! How did that interview go on Tuesday?
```

### Insights

```
I noticed you've been working on the auth system a lot lately.
Would you like me to summarize the changes we've discussed?
```

### Connections

```
That error you saw earlier might be related to the caching
issue we debugged last week. Want me to check?
```

## Emotional Context

The system tracks conversation patterns:

| Factor | Description |
|--------|-------------|
| Emotional arc | Stable, improving, or declining |
| Energy level | Stressed, focused, casual |
| Conversation endings | How sessions typically end |
| Interaction frequency | How often user engages |

This affects:
- **Timing** - Don't interrupt when stressed
- **Tone** - Match energy level
- **Content** - Prioritize relevant topics

## Database Models

| Model | Purpose |
|-------|---------|
| `ProactiveNote` | Accumulated observations |
| `ProactiveMessage` | Sent proactive messages |
| `ProactiveAssessment` | Decision history |
| `UserInteractionPattern` | Activity patterns |

## Best Practices

### Do

- Enable gradually (start with longer intervals)
- Monitor for user feedback
- Adjust timing based on user activity patterns
- Use for genuine follow-ups and insights

### Don't

- Set intervals too short (feels intrusive)
- Enable for all channels (start with specific ones)
- Ignore negative feedback
- Use for marketing or announcements

## Tuning Parameters

### Conservative (Less Proactive)

```bash
ORS_BASE_INTERVAL_MINUTES=60
ORS_MIN_SPEAK_GAP_HOURS=8
ORS_NOTE_DECAY_DAYS=3
```

### Moderate (Default)

```bash
ORS_BASE_INTERVAL_MINUTES=15
ORS_MIN_SPEAK_GAP_HOURS=2
ORS_NOTE_DECAY_DAYS=7
```

### Active (More Proactive)

```bash
ORS_BASE_INTERVAL_MINUTES=5
ORS_MIN_SPEAK_GAP_HOURS=1
ORS_NOTE_DECAY_DAYS=14
```

## Monitoring

### Check Status

```
@Clara proactive messaging status
```

### View Pending Notes

```
@Clara what notes do you have about me?
```

### Clear Notes

```
@Clara clear your proactive notes
```

## Disabling

### Per-User

```
@Clara disable proactive messages for me
```

### Global

```bash
ORS_ENABLED=false
```

## Architecture

```
┌─────────────────────────┐
│    Proactive Engine     │
│   proactive_engine.py   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Organic Response Sys   │
│ organic_response_sys.py │
└───────────┬─────────────┘
            │
     ┌──────┴──────┐
     ▼             ▼
┌─────────┐  ┌──────────┐
│  Notes  │  │ Patterns │
│   DB    │  │    DB    │
└─────────┘  └──────────┘
            │
            ▼
┌─────────────────────────┐
│   Discord/Platform      │
└─────────────────────────┘
```

## Example Scenario

1. **Monday 2pm** - User mentions interview on Thursday
2. **Monday 2pm** - Clara creates follow_up note
3. **Thursday 10am** - ORS check, note is relevant
4. **Thursday 10am** - Clara assesses: genuine reason to reach out
5. **Thursday 10am** - Clara sends: "Good luck with your interview today!"
6. **Thursday 6pm** - Clara sends: "How did the interview go?"

## See Also

- [[Memory-System]] - How Clara remembers context
- [[Configuration]] - All configuration options
- [[Discord-Features]] - Platform integration
