"""Email adapter for Clara Gateway.

Provides email monitoring and alert routing through the gateway event system.
"""

from adapters.email.monitor import EmailInfo, EmailMonitor
from adapters.email.provider import EmailProvider

__all__ = ["EmailProvider", "EmailMonitor", "EmailInfo"]
