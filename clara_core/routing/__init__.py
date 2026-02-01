"""Clara Routing System.

Provides message routing with binding priorities following OpenClaw's pattern:
1. peer - Direct match to user/group ID
2. guild - Discord guild ID / Slack workspace
3. team - Teams team ID
4. account - Specific bot account
5. channel - Wildcard account
6. default - Fallback agent

Also provides session scoping options:
- main - Shared session across all peers
- per-peer - Isolated session per contact
- per-channel-peer - Per contact per channel
- per-account-channel-peer - Full isolation
"""

from clara_core.routing.resolve import (
    AgentBinding,
    AgentRoute,
    BindingPriority,
    SessionScope,
    resolve_route,
)
from clara_core.routing.session_key import (
    SessionKey,
    generate_session_key,
)

__all__ = [
    # Routing
    "BindingPriority",
    "SessionScope",
    "AgentBinding",
    "AgentRoute",
    "resolve_route",
    # Session
    "SessionKey",
    "generate_session_key",
]
