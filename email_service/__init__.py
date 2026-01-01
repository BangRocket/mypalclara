"""Email Monitoring Service for Clara.

Background service that monitors user email accounts and sends
Discord alerts for important messages based on configurable rules.
"""

from email_service.credentials import decrypt_credential, encrypt_credential
from email_service.providers.base import EmailMessage, EmailProvider
from email_service.rules_engine import RuleMatch, evaluate_email

__all__ = [
    "EmailMessage",
    "EmailProvider",
    "RuleMatch",
    "decrypt_credential",
    "encrypt_credential",
    "evaluate_email",
]
