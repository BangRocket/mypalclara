"""Email tools for Clara.

Provides EMAIL_TOOLS definitions and handlers for email operations.
Migrated from email_monitor.py to enable gateway integration.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from adapters.email.monitor import EmailInfo, EmailMonitor

if TYPE_CHECKING:
    import discord

# Email configuration - loaded from environment
EMAIL_ADDRESS = os.environ.get("CLARA_EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("CLARA_EMAIL_PASSWORD")

# Discord user ID to notify (default: None if not set)
_notify_user_env = os.getenv("CLARA_EMAIL_NOTIFY_USER", "").strip()
NOTIFY_USER_ID = int(_notify_user_env) if _notify_user_env else None

# Whether to send Discord notifications (default: off)
NOTIFY_ENABLED = os.getenv("CLARA_EMAIL_NOTIFY", "false").lower() == "true"

# Check interval in seconds
CHECK_INTERVAL = int(os.getenv("CLARA_EMAIL_CHECK_INTERVAL", "60"))

# SMTP timeout in seconds
SMTP_TIMEOUT = int(os.getenv("CLARA_SMTP_TIMEOUT", "30"))


# Global monitor instance
_email_monitor: EmailMonitor | None = None


def get_email_monitor() -> EmailMonitor:
    """Get or create the email monitor instance."""
    global _email_monitor
    if _email_monitor is None:
        _email_monitor = EmailMonitor()
    return _email_monitor


# Tool definitions for check_email and send_email
EMAIL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_email",
            "description": "Check Clara's email inbox (clara@jorsh.net). Returns recent emails with sender, subject, and date. Use this when asked about email or to check for new messages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "unread_only": {
                        "type": "boolean",
                        "description": "If true, only show unread emails. Default is false (show all recent).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of emails to return (default: 10, max: 25)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email from Clara's email address (clara@jorsh.net).",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Email body text"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
]


async def handle_email_tool(tool_name: str, arguments: dict) -> str:
    """Handle email tool calls."""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return "Error: Email not configured. CLARA_EMAIL_ADDRESS and CLARA_EMAIL_PASSWORD must be set."

    monitor = get_email_monitor()

    if tool_name == "check_email":
        unread_only = arguments.get("unread_only", False)
        limit = min(arguments.get("limit", 10), 25)

        if unread_only:
            emails, error = monitor.check_emails(unseen_only=True)
        else:
            emails, error = monitor.get_all_emails(limit=limit)

        if error:
            return f"Error checking email: {error}"

        if not emails:
            return "No emails found." if not unread_only else "No unread emails."

        # Format results
        lines = [f"Found {len(emails)} email(s):\n"]
        for i, e in enumerate(emails, 1):
            status = " [UNREAD]" if not e.is_read else ""
            lines.append(f"{i}. **From:** {e.from_addr}")
            lines.append(f"   **Subject:** {e.subject}{status}")
            lines.append(f"   **Date:** {e.date}")
            if e.preview:
                lines.append(f"   **Preview:** {e.preview}")
            lines.append("")

        return "\n".join(lines)

    elif tool_name == "send_email":
        to_addr = arguments.get("to", "")
        subject = arguments.get("subject", "")
        body = arguments.get("body", "")

        if not to_addr or not subject or not body:
            return "Error: to, subject, and body are all required"

        try:
            # SMTP settings for Titan
            smtp_server = os.getenv("CLARA_SMTP_SERVER", "smtp.titan.email")
            smtp_port = int(os.getenv("CLARA_SMTP_PORT", "465"))

            msg = MIMEMultipart()
            msg["From"] = EMAIL_ADDRESS
            msg["To"] = to_addr
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)

            return f"Email sent successfully to {to_addr}"

        except Exception as e:
            return f"Error sending email: {str(e)}"

    return f"Unknown email tool: {tool_name}"


# Alias for backward compatibility
execute_email_tool = handle_email_tool


def _send_email_sync(
    to_addr: str, subject: str, body: str, is_reply: bool = False
) -> tuple[bool, str]:
    """Synchronous email sending (runs in thread executor).

    Args:
        to_addr: Recipient email address
        subject: Email subject
        body: Email body
        is_reply: If True, adds "Re:" prefix to subject

    Returns:
        Tuple of (success, message)
    """
    try:
        smtp_server = os.getenv("CLARA_SMTP_SERVER", "smtp.titan.email")
        smtp_port = int(os.getenv("CLARA_SMTP_PORT", "465"))

        # Add Re: prefix if not already there and this is a reply
        if is_reply and not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # Use timeout for SMTP connection
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=SMTP_TIMEOUT) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)

        return True, "Email sent successfully"

    except TimeoutError:
        return False, f"SMTP connection timed out after {SMTP_TIMEOUT}s"
    except Exception as e:
        return False, str(e)


def send_email_response(to_addr: str, subject: str, body: str) -> tuple[bool, str]:
    """Send an email response (synchronous, for backwards compatibility)."""
    return _send_email_sync(to_addr, subject, body, is_reply=True)


# LLM for email evaluation - lazy initialized
_email_llm = None


def _get_email_llm():
    """Get LLM for email evaluation (lazy init)."""
    global _email_llm
    if _email_llm is None:
        from clara_core import make_llm

        _email_llm = make_llm()
    return _email_llm


def evaluate_and_respond(email_info: EmailInfo) -> dict:
    """Use LLM to evaluate an email and decide whether to respond.

    Returns dict with:
        - should_respond: bool
        - reason: str (why or why not to respond)
        - response: str (the response to send, if should_respond)
    """
    from config.bot import BOT_NAME

    llm = _get_email_llm()

    # Build prompt for evaluation
    prompt = f"""You are {BOT_NAME}, a helpful AI assistant. You've received an email and need to decide if you should respond.

EMAIL DETAILS:
From: {email_info.from_addr}
Subject: {email_info.subject}
Date: {email_info.date}

BODY:
{email_info.body[:3000]}

INSTRUCTIONS:
1. Evaluate if this email requires or warrants a response from you
2. DO NOT respond to:
   - Automated notifications (order confirmations, shipping updates, etc.)
   - Marketing/promotional emails
   - Newsletters
   - No-reply addresses
   - Spam
3. DO respond to:
   - Personal emails addressed to you/{BOT_NAME}
   - Questions that need answers
   - Requests for help or information
   - Emails that seem to expect a reply

Respond with a JSON object (no markdown, just raw JSON):
{{
    "should_respond": true/false,
    "reason": "brief explanation of your decision",
    "response": "your email response if should_respond is true, otherwise empty string"
}}

If you do respond, write as {BOT_NAME} - be helpful, friendly, and concise. Sign off naturally."""

    try:
        result = llm([{"role": "user", "content": prompt}])

        # Parse JSON from response
        # Try to extract JSON if wrapped in markdown
        json_str = result.strip()
        if json_str.startswith("```"):
            json_str = re.sub(r"^```(?:json)?\n?", "", json_str)
            json_str = re.sub(r"\n?```$", "", json_str)

        parsed = json.loads(json_str)
        return {
            "should_respond": parsed.get("should_respond", False),
            "reason": parsed.get("reason", ""),
            "response": parsed.get("response", ""),
        }

    except Exception as e:
        print(f"[email] Error evaluating email: {e}")
        return {
            "should_respond": False,
            "reason": f"Error evaluating: {e}",
            "response": "",
        }


async def email_check_loop(bot: "discord.Client") -> None:
    """Background task that checks for new emails periodically.

    For each new email:
    1. Fetches the full email content
    2. Uses LLM to decide if Clara should respond
    3. Sends a response if appropriate
    4. Notifies the user via Discord DM

    Should be started from on_ready() in the Discord bot.
    """
    await bot.wait_until_ready()

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print(
            "[email] Email monitoring DISABLED - CLARA_EMAIL_ADDRESS or CLARA_EMAIL_PASSWORD not set"
        )
        return

    monitor = get_email_monitor()
    print(f"[email] Starting email monitor for {EMAIL_ADDRESS}")
    print("[email] Auto-respond enabled - Clara will evaluate and respond to emails")
    if NOTIFY_ENABLED:
        print(f"[email] Discord notifications ON - will notify user ID {NOTIFY_USER_ID}")
    else:
        print("[email] Discord notifications OFF (set CLARA_EMAIL_NOTIFY=true to enable)")

    while not bot.is_closed():
        try:
            new_emails, error = monitor.get_new_emails()

            if error:
                print(f"[email] Error: {error}")
            elif new_emails:
                print(f"[email] {len(new_emails)} new email(s) detected!")

                # Get the user to notify (only if notifications enabled)
                user = None
                if NOTIFY_ENABLED:
                    try:
                        user = await bot.fetch_user(NOTIFY_USER_ID)
                    except Exception as e:
                        print(f"[email] Failed to fetch user for notifications: {e}")

                for email_header in new_emails:
                    # Fetch full email with body
                    full_email, fetch_error = monitor.get_full_email(email_header.uid)

                    if fetch_error or not full_email:
                        print(f"[email] Failed to fetch full email: {fetch_error}")
                        # Still notify about the email
                        if user:
                            await user.send(
                                f"**New Email!**\n"
                                f"**From:** {email_header.from_addr}\n"
                                f"**Subject:** {email_header.subject}\n"
                                f"**Date:** {email_header.date}\n"
                                f"*(Could not fetch body for auto-response)*"
                            )
                        continue

                    print(
                        f"[email] Evaluating email from {full_email.from_addr}: {full_email.subject}"
                    )

                    # Use LLM to decide whether to respond
                    evaluation = evaluate_and_respond(full_email)

                    if evaluation["should_respond"]:
                        print(f"[email] Clara decided to respond: {evaluation['reason']}")

                        # Extract reply-to address (use From if no Reply-To)
                        reply_to = full_email.from_addr
                        # Handle "Name <email>" format
                        email_match = re.search(r"<([^>]+)>", reply_to)
                        if email_match:
                            reply_to = email_match.group(1)

                        # Send the response
                        success, send_result = send_email_response(
                            to_addr=reply_to,
                            subject=full_email.subject,
                            body=evaluation["response"],
                        )

                        if success:
                            print(f"[email] Response sent to {reply_to}")
                            if user:
                                await user.send(
                                    f"**New Email - Clara Responded!**\n"
                                    f"**From:** {full_email.from_addr}\n"
                                    f"**Subject:** {full_email.subject}\n\n"
                                    f"**Clara's Response:**\n{evaluation['response'][:1500]}"
                                )
                        else:
                            print(f"[email] Failed to send response: {send_result}")
                            if user:
                                await user.send(
                                    f"**New Email - Response Failed!**\n"
                                    f"**From:** {full_email.from_addr}\n"
                                    f"**Subject:** {full_email.subject}\n"
                                    f"**Error:** {send_result}\n\n"
                                    f"**Clara wanted to say:**\n{evaluation['response'][:1000]}"
                                )
                    else:
                        print(
                            f"[email] Clara decided not to respond: {evaluation['reason']}"
                        )
                        if user:
                            # Truncate body preview
                            body_preview = (
                                full_email.body[:500] + "..."
                                if len(full_email.body) > 500
                                else full_email.body
                            )
                            await user.send(
                                f"**New Email** *(no response needed)*\n"
                                f"**From:** {full_email.from_addr}\n"
                                f"**Subject:** {full_email.subject}\n"
                                f"**Reason:** {evaluation['reason']}\n\n"
                                f"**Preview:**\n{body_preview}"
                            )

        except Exception as e:
            print(f"[email] Loop error: {e}")

        await asyncio.sleep(CHECK_INTERVAL)
