"""
Email Faculty - Email monitoring and alerts.

Provides tools for users to configure email monitoring accounts and rules.
Supports Gmail (via Google OAuth) and IMAP (app-specific passwords).
"""

import logging
import os
from typing import Any, Optional

from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult

logger = logging.getLogger(__name__)

# Configuration
EMAIL_ENCRYPTION_KEY = os.getenv("EMAIL_ENCRYPTION_KEY", "")
EMAIL_DEFAULT_POLL_INTERVAL = int(os.getenv("EMAIL_DEFAULT_POLL_INTERVAL", "5"))


class EmailFaculty(Faculty):
    """Email monitoring and alerts faculty."""

    name = "email"
    description = "Monitor email accounts for important messages and configure alert rules"

    available_actions = [
        # Account Management
        "connect_gmail",
        "connect_imap",
        "list_accounts",
        "disconnect",
        # Configuration
        "set_alert_channel",
        "set_quiet_hours",
        "toggle_ping",
        # Rules
        "apply_preset",
        "list_presets",
        "add_rule",
        "list_rules",
        "remove_rule",
        # Inbox
        "list_folders",
        "list_inbox",
        "search",
        "read_email",
        # Status
        "status",
        "recent_alerts",
    ]

    async def execute(
        self,
        intent: str,
        constraints: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> FacultyResult:
        """Execute email-related intent."""
        logger.info(f"[email] Intent: {intent}")

        try:
            action, params = self._parse_intent(intent)
            logger.info(f"[email] Action: {action}")

            # Account Management
            if action == "connect_gmail":
                result = await self._connect_gmail(params)
            elif action == "connect_imap":
                result = await self._connect_imap(params)
            elif action == "list_accounts":
                result = await self._list_accounts(params)
            elif action == "disconnect":
                result = await self._disconnect(params)
            # Configuration
            elif action == "set_alert_channel":
                result = await self._set_alert_channel(params)
            elif action == "set_quiet_hours":
                result = await self._set_quiet_hours(params)
            elif action == "toggle_ping":
                result = await self._toggle_ping(params)
            # Rules
            elif action == "apply_preset":
                result = await self._apply_preset(params)
            elif action == "list_presets":
                result = await self._list_presets(params)
            elif action == "add_rule":
                result = await self._add_rule(params)
            elif action == "list_rules":
                result = await self._list_rules(params)
            elif action == "remove_rule":
                result = await self._remove_rule(params)
            # Inbox
            elif action == "list_folders":
                result = await self._list_folders(params)
            elif action == "list_inbox":
                result = await self._list_inbox(params)
            elif action == "search":
                result = await self._search_emails(params)
            elif action == "read_email":
                result = await self._read_email(params)
            # Status
            elif action == "status":
                result = await self._status(params)
            elif action == "recent_alerts":
                result = await self._recent_alerts(params)
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Unknown email action: {action}",
                    error=f"Action '{action}' not recognized",
                )

            return result

        except Exception as e:
            logger.exception(f"[email] Error: {e}")
            return FacultyResult(
                success=False,
                summary=f"Email error: {str(e)}",
                error=str(e),
            )

    def _parse_intent(self, intent: str) -> tuple[str, dict]:
        """Parse natural language intent into action and parameters."""
        intent_lower = intent.lower()

        # Account Management
        if "connect gmail" in intent_lower:
            return "connect_gmail", {}
        if "connect imap" in intent_lower or "connect email" in intent_lower:
            email = self._extract_email(intent)
            password = self._extract_password(intent)
            server = self._extract_server(intent)
            return "connect_imap", {"email_address": email, "password": password, "imap_server": server}
        if "list account" in intent_lower or "email account" in intent_lower:
            return "list_accounts", {}
        if "disconnect" in intent_lower:
            email = self._extract_email(intent)
            return "disconnect", {"email_address": email}

        # Configuration
        if "alert channel" in intent_lower or "set channel" in intent_lower:
            channel_id = self._extract_channel_id(intent)
            return "set_alert_channel", {"channel_id": channel_id}
        if "quiet hours" in intent_lower:
            return "set_quiet_hours", self._parse_quiet_hours(intent)
        if "toggle ping" in intent_lower or "enable ping" in intent_lower or "disable ping" in intent_lower:
            return "toggle_ping", {"enabled": "enable" in intent_lower}

        # Rules
        if "apply preset" in intent_lower or "use preset" in intent_lower:
            preset = self._extract_preset(intent)
            return "apply_preset", {"preset": preset}
        if "list preset" in intent_lower or "available preset" in intent_lower:
            return "list_presets", {}
        if "add rule" in intent_lower or "create rule" in intent_lower:
            return "add_rule", self._parse_rule(intent)
        if "list rule" in intent_lower or "my rules" in intent_lower:
            return "list_rules", {}
        if "remove rule" in intent_lower or "delete rule" in intent_lower:
            rule_id = self._extract_id(intent)
            return "remove_rule", {"rule_id": rule_id}

        # Inbox
        if "list folder" in intent_lower or "email folder" in intent_lower:
            return "list_folders", {}
        if "list inbox" in intent_lower or "check inbox" in intent_lower or "recent email" in intent_lower:
            folder = self._extract_folder(intent)
            return "list_inbox", {"folder": folder}
        if "search email" in intent_lower or "find email" in intent_lower:
            return "search", self._parse_search(intent)
        if "read email" in intent_lower or "show email" in intent_lower:
            email_id = self._extract_id(intent)
            return "read_email", {"email_id": email_id}

        # Status
        if "status" in intent_lower or "monitoring status" in intent_lower:
            return "status", {}
        if "recent alert" in intent_lower or "alert history" in intent_lower:
            return "recent_alerts", {}

        # Default
        return "status", {}

    def _extract_email(self, text: str) -> str:
        """Extract email address from text."""
        import re
        match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        return match.group(0) if match else ""

    def _extract_password(self, text: str) -> str:
        """Extract password from text."""
        import re
        match = re.search(r'password[:\s]+["\']([^"\']+)["\']', text, re.IGNORECASE)
        return match.group(1) if match else ""

    def _extract_server(self, text: str) -> str:
        """Extract IMAP server from text."""
        import re
        match = re.search(r'server[:\s]+["\']?([a-zA-Z0-9.-]+)["\']?', text, re.IGNORECASE)
        return match.group(1) if match else ""

    def _extract_channel_id(self, text: str) -> str:
        """Extract Discord channel ID from text."""
        import re
        match = re.search(r'\b(\d{17,19})\b', text)
        return match.group(1) if match else ""

    def _extract_preset(self, text: str) -> str:
        """Extract preset name from text."""
        presets = ["job_hunting", "urgent", "security", "financial", "shipping"]
        for preset in presets:
            if preset in text.lower():
                return preset
        return ""

    def _extract_folder(self, text: str) -> str:
        """Extract folder name from text."""
        import re
        match = re.search(r'folder[:\s]+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        return match.group(1) if match else "INBOX"

    def _extract_id(self, text: str) -> str:
        """Extract ID from text."""
        import re
        match = re.search(r'\b(\d+)\b', text)
        return match.group(1) if match else ""

    def _parse_quiet_hours(self, text: str) -> dict:
        """Parse quiet hours from text."""
        import re
        result: dict[str, Any] = {}
        match = re.search(r'(\d{1,2}):?(\d{2})?\s*-\s*(\d{1,2}):?(\d{2})?', text)
        if match:
            result["start_hour"] = int(match.group(1))
            result["end_hour"] = int(match.group(3))
        return result

    def _parse_rule(self, text: str) -> dict:
        """Parse rule parameters from text."""
        import re
        result: dict[str, Any] = {}

        # Extract from pattern
        match = re.search(r'from[:\s]+["\']([^"\']+)["\']', text, re.IGNORECASE)
        if match:
            result["from_pattern"] = match.group(1)

        # Extract subject pattern
        match = re.search(r'subject[:\s]+["\']([^"\']+)["\']', text, re.IGNORECASE)
        if match:
            result["subject_pattern"] = match.group(1)

        return result

    def _parse_search(self, text: str) -> dict:
        """Parse search parameters from text."""
        import re
        result: dict[str, Any] = {}

        match = re.search(r'from[:\s]+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if match:
            result["from_addr"] = match.group(1)

        match = re.search(r'subject[:\s]+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if match:
            result["subject"] = match.group(1)

        if "unread" in text.lower():
            result["unread_only"] = True

        return result

    # ==========================================================================
    # Account Management
    # ==========================================================================

    async def _connect_gmail(self, params: dict) -> FacultyResult:
        """Connect Gmail for monitoring using existing Google OAuth."""
        user_id = params.get("user_id", "default")

        try:
            from tools.google_oauth import is_user_connected
            if not is_user_connected(user_id):
                return FacultyResult(
                    success=False,
                    summary="You need to connect your Google account first. Use the Google faculty to connect.",
                    error="Google not connected",
                )
        except ImportError:
            return FacultyResult(
                success=False,
                summary="Google OAuth module not available",
                error="Module not found",
            )

        try:
            from db.connection import SessionLocal
            from db.models import EmailAccount

            with SessionLocal() as session:
                existing = (
                    session.query(EmailAccount)
                    .filter(
                        EmailAccount.user_id == user_id,
                        EmailAccount.provider_type == "gmail",
                    )
                    .first()
                )

                if existing:
                    return FacultyResult(
                        success=True,
                        summary=f"Gmail is already connected: {existing.email_address}",
                        data={"email": existing.email_address},
                    )

                # Create new account
                account = EmailAccount(
                    user_id=user_id,
                    email_address="(pending verification)",
                    provider_type="gmail",
                    enabled="true",
                    poll_interval_minutes=EMAIL_DEFAULT_POLL_INTERVAL,
                    status="active",
                )
                session.add(account)
                session.commit()

            return FacultyResult(
                success=True,
                summary="Gmail connected successfully!\n\nNext steps:\n1. Use 'set alert channel' to choose where to receive alerts\n2. Use 'apply preset' to add rules (job_hunting, urgent, etc.)",
                data={"connected": True},
            )
        except ImportError:
            return FacultyResult(
                success=False,
                summary="Database module not available",
                error="Module not found",
            )

    async def _connect_imap(self, params: dict) -> FacultyResult:
        """Connect an IMAP email account."""
        user_id = params.get("user_id", "default")
        email_address = params.get("email_address", "")
        password = params.get("password", "")
        imap_server = params.get("imap_server", "")

        if not email_address or not password:
            return FacultyResult(
                success=False,
                summary="Both email_address and password are required",
                error="Missing credentials",
            )

        if not EMAIL_ENCRYPTION_KEY:
            return FacultyResult(
                success=False,
                summary="Email encryption not configured. Please set EMAIL_ENCRYPTION_KEY.",
                error="Encryption not configured",
            )

        # Auto-detect IMAP server
        if not imap_server:
            domain = email_address.split("@")[-1].lower()
            imap_servers = {
                "icloud.com": "imap.mail.me.com",
                "me.com": "imap.mail.me.com",
                "mac.com": "imap.mail.me.com",
                "outlook.com": "outlook.office365.com",
                "hotmail.com": "outlook.office365.com",
                "live.com": "outlook.office365.com",
                "yahoo.com": "imap.mail.yahoo.com",
                "gmail.com": "imap.gmail.com",
            }
            imap_server = imap_servers.get(domain, f"imap.{domain}")

        try:
            from db.connection import SessionLocal
            from db.models import EmailAccount
            from email_service.credentials import encrypt_credential

            with SessionLocal() as session:
                existing = (
                    session.query(EmailAccount)
                    .filter(
                        EmailAccount.user_id == user_id,
                        EmailAccount.email_address == email_address,
                    )
                    .first()
                )

                if existing:
                    return FacultyResult(
                        success=True,
                        summary=f"Account already connected: {email_address}",
                        data={"email": email_address},
                    )

                account = EmailAccount(
                    user_id=user_id,
                    email_address=email_address,
                    provider_type="imap",
                    imap_server=imap_server,
                    imap_port=993,
                    imap_username=email_address,
                    imap_password=encrypt_credential(password),
                    enabled="true",
                    poll_interval_minutes=EMAIL_DEFAULT_POLL_INTERVAL,
                    status="active",
                )
                session.add(account)
                session.commit()

            return FacultyResult(
                success=True,
                summary=f"Email account connected: {email_address}\n\nNext steps:\n1. Use 'set alert channel' to choose where to receive alerts\n2. Use 'apply preset' to add rules",
                data={"email": email_address, "server": imap_server},
            )
        except ImportError:
            return FacultyResult(
                success=False,
                summary="Database or email module not available",
                error="Module not found",
            )

    async def _list_accounts(self, params: dict) -> FacultyResult:
        """List connected email accounts."""
        user_id = params.get("user_id", "default")

        try:
            from db.connection import SessionLocal
            from db.models import EmailAccount

            with SessionLocal() as session:
                accounts = (
                    session.query(EmailAccount)
                    .filter(EmailAccount.user_id == user_id)
                    .all()
                )

                if not accounts:
                    return FacultyResult(
                        success=True,
                        summary="No email accounts connected. Use 'connect gmail' or 'connect imap' to add one.",
                        data={"accounts": []},
                    )

                lines = ["**Connected Email Accounts:**\n"]
                for acc in accounts:
                    status_emoji = "✅" if acc.status == "active" else "⚠️" if acc.status == "error" else "🔴"
                    channel = f"<#{acc.alert_channel_id}>" if acc.alert_channel_id else "Not set"
                    lines.append(f"{status_emoji} **{acc.email_address}** ({acc.provider_type})")
                    lines.append(f"   Status: {acc.status} | Alerts: {channel}")

                return FacultyResult(
                    success=True,
                    summary="\n".join(lines),
                    data={"accounts": [{"email": a.email_address, "status": a.status} for a in accounts]},
                )
        except ImportError:
            return FacultyResult(
                success=False,
                summary="Database module not available",
                error="Module not found",
            )

    async def _disconnect(self, params: dict) -> FacultyResult:
        """Disconnect an email account."""
        user_id = params.get("user_id", "default")
        email_address = params.get("email_address", "")

        if not email_address:
            return FacultyResult(
                success=False,
                summary="Please specify the email_address to disconnect",
                error="Missing email_address",
            )

        try:
            from db.connection import SessionLocal
            from db.models import EmailAccount

            with SessionLocal() as session:
                account = (
                    session.query(EmailAccount)
                    .filter(
                        EmailAccount.user_id == user_id,
                        EmailAccount.email_address == email_address,
                    )
                    .first()
                )

                if not account:
                    return FacultyResult(
                        success=False,
                        summary=f"Account not found: {email_address}",
                        error="Account not found",
                    )

                session.delete(account)
                session.commit()

            return FacultyResult(
                success=True,
                summary=f"Disconnected {email_address}",
                data={"email": email_address},
            )
        except ImportError:
            return FacultyResult(
                success=False,
                summary="Database module not available",
                error="Module not found",
            )

    # ==========================================================================
    # Configuration
    # ==========================================================================

    async def _set_alert_channel(self, params: dict) -> FacultyResult:
        """Set Discord channel for email alerts."""
        user_id = params.get("user_id", "default")
        channel_id = params.get("channel_id", "")
        email_address = params.get("email_address")

        if not channel_id:
            return FacultyResult(
                success=False,
                summary="Please provide a channel ID",
                error="Missing channel_id",
            )

        try:
            from db.connection import SessionLocal
            from db.models import EmailAccount

            with SessionLocal() as session:
                query = session.query(EmailAccount).filter(EmailAccount.user_id == user_id)
                if email_address:
                    query = query.filter(EmailAccount.email_address == email_address)

                accounts = query.all()
                if not accounts:
                    return FacultyResult(
                        success=False,
                        summary="No email accounts found. Connect one first.",
                        error="No accounts",
                    )

                for acc in accounts:
                    acc.alert_channel_id = channel_id
                session.commit()

            return FacultyResult(
                success=True,
                summary=f"Alert channel set to <#{channel_id}> for {len(accounts)} account(s)",
                data={"channel_id": channel_id},
            )
        except ImportError:
            return FacultyResult(success=False, summary="Database module not available", error="Module not found")

    async def _set_quiet_hours(self, params: dict) -> FacultyResult:
        """Configure quiet hours (no alerts during this time)."""
        user_id = params.get("user_id", "default")
        start_hour = params.get("start_hour", 22)
        end_hour = params.get("end_hour", 8)

        try:
            from db.connection import SessionLocal
            from db.models import EmailAccount

            with SessionLocal() as session:
                accounts = session.query(EmailAccount).filter(EmailAccount.user_id == user_id).all()
                for acc in accounts:
                    acc.quiet_start = start_hour
                    acc.quiet_end = end_hour
                session.commit()

            return FacultyResult(
                success=True,
                summary=f"Quiet hours set: {start_hour}:00 - {end_hour}:00",
                data={"start": start_hour, "end": end_hour},
            )
        except ImportError:
            return FacultyResult(success=False, summary="Database module not available", error="Module not found")

    async def _toggle_ping(self, params: dict) -> FacultyResult:
        """Toggle @mentions on alerts."""
        user_id = params.get("user_id", "default")
        enabled = params.get("enabled", True)

        try:
            from db.connection import SessionLocal
            from db.models import EmailAccount

            with SessionLocal() as session:
                accounts = session.query(EmailAccount).filter(EmailAccount.user_id == user_id).all()
                for acc in accounts:
                    acc.ping_enabled = enabled
                session.commit()

            status = "enabled" if enabled else "disabled"
            return FacultyResult(
                success=True,
                summary=f"@mentions {status} for email alerts",
                data={"ping_enabled": enabled},
            )
        except ImportError:
            return FacultyResult(success=False, summary="Database module not available", error="Module not found")

    # ==========================================================================
    # Rules
    # ==========================================================================

    async def _apply_preset(self, params: dict) -> FacultyResult:
        """Apply a built-in rule preset."""
        user_id = params.get("user_id", "default")
        preset = params.get("preset", "")

        if not preset:
            return FacultyResult(
                success=False,
                summary="Please specify a preset: job_hunting, urgent, security, financial, shipping",
                error="Missing preset",
            )

        presets_info = {
            "job_hunting": "Recruiter emails, ATS platforms (Greenhouse, Lever, Workday), job keywords",
            "urgent": "Emails with urgent/ASAP keywords",
            "security": "Password resets, 2FA codes, security alerts",
            "financial": "Banking, payment notifications",
            "shipping": "Package tracking, delivery updates",
        }

        if preset not in presets_info:
            return FacultyResult(
                success=False,
                summary=f"Unknown preset: {preset}. Available: {', '.join(presets_info.keys())}",
                error="Invalid preset",
            )

        try:
            from email_service.presets import apply_preset

            result = apply_preset(user_id, preset)

            return FacultyResult(
                success=True,
                summary=f"Applied preset: **{preset}**\n{presets_info[preset]}",
                data={"preset": preset},
            )
        except ImportError:
            return FacultyResult(success=False, summary="Presets module not available", error="Module not found")

    async def _list_presets(self, params: dict) -> FacultyResult:
        """List available rule presets."""
        presets = {
            "job_hunting": "Recruiter emails, ATS platforms (Greenhouse, Lever, Workday), job keywords",
            "urgent": "Emails with urgent/ASAP keywords",
            "security": "Password resets, 2FA codes, security alerts",
            "financial": "Banking, payment notifications",
            "shipping": "Package tracking, delivery updates",
        }

        lines = ["**Available Presets:**\n"]
        for name, desc in presets.items():
            lines.append(f"- **{name}**: {desc}")

        return FacultyResult(
            success=True,
            summary="\n".join(lines),
            data={"presets": list(presets.keys())},
        )

    async def _add_rule(self, params: dict) -> FacultyResult:
        """Add a custom email rule."""
        user_id = params.get("user_id", "default")
        from_pattern = params.get("from_pattern")
        subject_pattern = params.get("subject_pattern")

        if not from_pattern and not subject_pattern:
            return FacultyResult(
                success=False,
                summary="Please provide from_pattern or subject_pattern",
                error="Missing pattern",
            )

        try:
            from db.connection import SessionLocal
            from db.models import EmailRule

            with SessionLocal() as session:
                rule = EmailRule(
                    user_id=user_id,
                    from_pattern=from_pattern,
                    subject_pattern=subject_pattern,
                    enabled=True,
                )
                session.add(rule)
                session.commit()

                rule_id = rule.id

            patterns = []
            if from_pattern:
                patterns.append(f"from: '{from_pattern}'")
            if subject_pattern:
                patterns.append(f"subject: '{subject_pattern}'")

            return FacultyResult(
                success=True,
                summary=f"Added rule #{rule_id}: {', '.join(patterns)}",
                data={"rule_id": rule_id},
            )
        except ImportError:
            return FacultyResult(success=False, summary="Database module not available", error="Module not found")

    async def _list_rules(self, params: dict) -> FacultyResult:
        """List configured email rules."""
        user_id = params.get("user_id", "default")

        try:
            from db.connection import SessionLocal
            from db.models import EmailRule

            with SessionLocal() as session:
                rules = session.query(EmailRule).filter(EmailRule.user_id == user_id).all()

                if not rules:
                    return FacultyResult(
                        success=True,
                        summary="No rules configured. Use 'apply preset' or 'add rule' to create one.",
                        data={"rules": []},
                    )

                lines = ["**Email Rules:**\n"]
                for rule in rules:
                    status = "✅" if rule.enabled else "🔴"
                    patterns = []
                    if rule.from_pattern:
                        patterns.append(f"from: '{rule.from_pattern}'")
                    if rule.subject_pattern:
                        patterns.append(f"subject: '{rule.subject_pattern}'")
                    lines.append(f"{status} #{rule.id}: {', '.join(patterns)}")

                return FacultyResult(
                    success=True,
                    summary="\n".join(lines),
                    data={"rules": [{"id": r.id, "enabled": r.enabled} for r in rules]},
                )
        except ImportError:
            return FacultyResult(success=False, summary="Database module not available", error="Module not found")

    async def _remove_rule(self, params: dict) -> FacultyResult:
        """Remove an email rule."""
        user_id = params.get("user_id", "default")
        rule_id = params.get("rule_id", "")

        if not rule_id:
            return FacultyResult(success=False, summary="Please specify rule_id", error="Missing rule_id")

        try:
            from db.connection import SessionLocal
            from db.models import EmailRule

            with SessionLocal() as session:
                rule = (
                    session.query(EmailRule)
                    .filter(EmailRule.user_id == user_id, EmailRule.id == int(rule_id))
                    .first()
                )

                if not rule:
                    return FacultyResult(success=False, summary=f"Rule #{rule_id} not found", error="Not found")

                session.delete(rule)
                session.commit()

            return FacultyResult(
                success=True,
                summary=f"Removed rule #{rule_id}",
                data={"rule_id": rule_id},
            )
        except ImportError:
            return FacultyResult(success=False, summary="Database module not available", error="Module not found")

    # ==========================================================================
    # Inbox Operations
    # ==========================================================================

    async def _list_folders(self, params: dict) -> FacultyResult:
        """List available email folders/labels."""
        return FacultyResult(
            success=True,
            summary="Common folders: INBOX, Sent, Drafts, Trash, Spam\n(Gmail labels vary by account)",
            data={"folders": ["INBOX", "Sent", "Drafts", "Trash", "Spam"]},
        )

    async def _list_inbox(self, params: dict) -> FacultyResult:
        """List recent emails from inbox."""
        user_id = params.get("user_id", "default")
        folder = params.get("folder", "INBOX")
        limit = params.get("limit", 10)

        return FacultyResult(
            success=False,
            summary="Inbox listing requires email provider connection. This feature will be available when connected.",
            error="Not implemented in faculty - use email monitor",
        )

    async def _search_emails(self, params: dict) -> FacultyResult:
        """Search emails with filters."""
        return FacultyResult(
            success=False,
            summary="Email search requires email provider connection. This feature will be available when connected.",
            error="Not implemented in faculty - use email monitor",
        )

    async def _read_email(self, params: dict) -> FacultyResult:
        """Read full email content."""
        return FacultyResult(
            success=False,
            summary="Reading emails requires email provider connection. This feature will be available when connected.",
            error="Not implemented in faculty - use email monitor",
        )

    # ==========================================================================
    # Status
    # ==========================================================================

    async def _status(self, params: dict) -> FacultyResult:
        """Check email monitoring status."""
        user_id = params.get("user_id", "default")

        try:
            from db.connection import SessionLocal
            from db.models import EmailAccount

            with SessionLocal() as session:
                accounts = session.query(EmailAccount).filter(EmailAccount.user_id == user_id).all()

                if not accounts:
                    return FacultyResult(
                        success=True,
                        summary="No email accounts configured. Use 'connect gmail' or 'connect imap' to start.",
                        data={"accounts": 0},
                    )

                active = sum(1 for a in accounts if a.status == "active")

                lines = [f"**Email Monitoring Status**\n{active}/{len(accounts)} accounts active\n"]
                for acc in accounts:
                    status_emoji = "✅" if acc.status == "active" else "⚠️"
                    lines.append(f"{status_emoji} {acc.email_address}")

                return FacultyResult(
                    success=True,
                    summary="\n".join(lines),
                    data={"accounts": len(accounts), "active": active},
                )
        except ImportError:
            return FacultyResult(success=False, summary="Database module not available", error="Module not found")

    async def _recent_alerts(self, params: dict) -> FacultyResult:
        """View recent email alerts."""
        user_id = params.get("user_id", "default")
        limit = params.get("limit", 10)

        try:
            from db.connection import SessionLocal
            from db.models import EmailAlert

            with SessionLocal() as session:
                alerts = (
                    session.query(EmailAlert)
                    .filter(EmailAlert.user_id == user_id)
                    .order_by(EmailAlert.created_at.desc())
                    .limit(limit)
                    .all()
                )

                if not alerts:
                    return FacultyResult(
                        success=True,
                        summary="No recent alerts",
                        data={"alerts": []},
                    )

                lines = ["**Recent Alerts:**\n"]
                for alert in alerts:
                    lines.append(f"- {alert.subject[:50]} from {alert.from_addr}")

                return FacultyResult(
                    success=True,
                    summary="\n".join(lines),
                    data={"alerts": [{"subject": a.subject, "from": a.from_addr} for a in alerts]},
                )
        except ImportError:
            return FacultyResult(success=False, summary="Database module not available", error="Module not found")
