"""Email adapter for Clara Gateway.

Provides email monitoring and alert routing through the gateway event system.
"""

from adapters.email.monitor import EmailInfo, EmailMonitor
from adapters.email.provider import EmailProvider
from adapters.email.tools import (
    EMAIL_TOOLS,
    email_check_loop,
    execute_email_tool,
    handle_email_tool,
)

__all__ = [
    "EmailProvider",
    "EmailMonitor",
    "EmailInfo",
    "EMAIL_TOOLS",
    "handle_email_tool",
    "execute_email_tool",
    "email_check_loop",
]
