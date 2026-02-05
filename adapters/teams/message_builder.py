"""Adaptive Card builder for Microsoft Teams.

Provides rich card formatting for Clara's responses, tool status,
and error messages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedMarkers:
    """Parsed markers from response text."""

    text: str
    buttons: list[dict[str, str]] | None = None
    card_title: str | None = None
    card_style: str | None = None


def parse_markers(text: str) -> ParsedMarkers:
    """Parse special markers from response text.

    Supported markers:
    - __BUTTONS__[{"title": "...", "action": "..."}]__BUTTONS__
    - __CARD_TITLE__Title Text__CARD_TITLE__
    - __CARD_STYLE__emphasis|accent|good|warning|attention__CARD_STYLE__

    Args:
        text: Response text potentially containing markers

    Returns:
        ParsedMarkers with extracted data
    """
    result = ParsedMarkers(text=text)

    # Extract buttons
    button_pattern = r"__BUTTONS__(\[.*?\])__BUTTONS__"
    button_match = re.search(button_pattern, text, re.DOTALL)
    if button_match:
        try:
            import json

            result.buttons = json.loads(button_match.group(1))
            result.text = text[: button_match.start()] + text[button_match.end() :]
        except (json.JSONDecodeError, ValueError):
            pass

    # Extract card title
    title_pattern = r"__CARD_TITLE__(.+?)__CARD_TITLE__"
    title_match = re.search(title_pattern, result.text)
    if title_match:
        result.card_title = title_match.group(1).strip()
        result.text = result.text[: title_match.start()] + result.text[title_match.end() :]

    # Extract card style
    style_pattern = r"__CARD_STYLE__(\w+)__CARD_STYLE__"
    style_match = re.search(style_pattern, result.text)
    if style_match:
        result.card_style = style_match.group(1)
        result.text = result.text[: style_match.start()] + result.text[style_match.end() :]

    result.text = result.text.strip()
    return result


class AdaptiveCardBuilder:
    """Builds Adaptive Cards for Teams messages.

    Adaptive Cards are a platform-agnostic way to create rich,
    interactive content in Teams, Outlook, and other Microsoft apps.
    """

    # Adaptive Card schema version
    SCHEMA_VERSION = "1.4"

    def build_response_card(
        self,
        text: str,
        tool_count: int = 0,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Build an Adaptive Card for a response.

        Args:
            text: Response text content
            tool_count: Number of tools used (for footer)
            title: Optional title for the card

        Returns:
            Adaptive Card JSON structure
        """
        body = []

        # Optional title
        if title:
            body.append(
                {
                    "type": "TextBlock",
                    "text": title,
                    "weight": "Bolder",
                    "size": "Medium",
                    "wrap": True,
                }
            )

        # Main content - split into blocks if very long
        text_blocks = self._split_text(text, max_length=3000)
        for block in text_blocks:
            body.append(
                {
                    "type": "TextBlock",
                    "text": block,
                    "wrap": True,
                }
            )

        # Tool count footer
        if tool_count > 0:
            body.append(
                {
                    "type": "TextBlock",
                    "text": f"_Used {tool_count} tool{'s' if tool_count > 1 else ''}_",
                    "size": "Small",
                    "isSubtle": True,
                    "wrap": True,
                }
            )

        return {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": self.SCHEMA_VERSION,
            "body": body,
        }

    def build_tool_status_card(
        self,
        tool_name: str,
        step: int,
        emoji: str = "🔧",
        description: str | None = None,
    ) -> dict[str, Any]:
        """Build an Adaptive Card for tool execution status.

        Args:
            tool_name: Name of the tool being executed
            step: Step number in the workflow
            emoji: Emoji to display
            description: Optional description of what the tool is doing

        Returns:
            Adaptive Card JSON structure
        """
        body = [
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": emoji,
                                "size": "Medium",
                            }
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": f"**{tool_name}** (step {step})",
                                "wrap": True,
                            }
                        ],
                    },
                ],
            }
        ]

        if description:
            body.append(
                {
                    "type": "TextBlock",
                    "text": f"_{description}_",
                    "size": "Small",
                    "isSubtle": True,
                    "wrap": True,
                }
            )

        return {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": self.SCHEMA_VERSION,
            "body": body,
        }

    def build_error_card(
        self,
        error_message: str,
        title: str = "Error",
    ) -> dict[str, Any]:
        """Build an Adaptive Card for error display.

        Args:
            error_message: The error message to display
            title: Card title

        Returns:
            Adaptive Card JSON structure
        """
        return {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": self.SCHEMA_VERSION,
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"⚠️ {title}",
                    "weight": "Bolder",
                    "color": "Attention",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": error_message,
                    "wrap": True,
                },
            ],
        }

    def build_welcome_card(
        self,
        user_name: str | None = None,
    ) -> dict[str, Any]:
        """Build a welcome card for new conversations.

        Args:
            user_name: Optional user name for personalization

        Returns:
            Adaptive Card JSON structure
        """
        greeting = f"Hello{', ' + user_name if user_name else ''}!"

        return {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": self.SCHEMA_VERSION,
            "body": [
                {
                    "type": "TextBlock",
                    "text": greeting,
                    "weight": "Bolder",
                    "size": "Large",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": (
                        "I'm Clara, your AI assistant. I can help you with "
                        "questions, tasks, and creative work. Just send me a message!"
                    ),
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": "**Tip:** Use `!high` for complex tasks or `!fast` for quick questions.",
                    "size": "Small",
                    "isSubtle": True,
                    "wrap": True,
                },
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "👋 Say Hello",
                    "data": {"action": "greet"},
                },
            ],
        }

    def build_code_card(
        self,
        code: str,
        language: str = "",
        title: str | None = None,
    ) -> dict[str, Any]:
        """Build an Adaptive Card for code display.

        Args:
            code: The code content
            language: Programming language for syntax hints
            title: Optional title

        Returns:
            Adaptive Card JSON structure
        """
        body = []

        if title:
            body.append(
                {
                    "type": "TextBlock",
                    "text": title,
                    "weight": "Bolder",
                    "wrap": True,
                }
            )

        # Code in monospace container
        body.append(
            {
                "type": "Container",
                "style": "emphasis",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": f"```{language}\n{code}\n```",
                        "fontType": "Monospace",
                        "wrap": True,
                    }
                ],
            }
        )

        return {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": self.SCHEMA_VERSION,
            "body": body,
        }

    def build_file_card(
        self,
        filename: str,
        file_size: int | None = None,
        download_url: str | None = None,
    ) -> dict[str, Any]:
        """Build an Adaptive Card for file display.

        Args:
            filename: Name of the file
            file_size: Size in bytes
            download_url: Optional download URL

        Returns:
            Adaptive Card JSON structure
        """
        size_str = self._format_size(file_size) if file_size else ""

        body = [
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "📄",
                                "size": "Large",
                            }
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": filename,
                                "weight": "Bolder",
                                "wrap": True,
                            },
                            {
                                "type": "TextBlock",
                                "text": size_str,
                                "size": "Small",
                                "isSubtle": True,
                            },
                        ],
                    },
                ],
            }
        ]

        card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": self.SCHEMA_VERSION,
            "body": body,
        }

        if download_url:
            card["actions"] = [
                {
                    "type": "Action.OpenUrl",
                    "title": "Download",
                    "url": download_url,
                }
            ]

        return card

    def _split_text(self, text: str, max_length: int = 3000) -> list[str]:
        """Split text into chunks for Adaptive Card blocks.

        Args:
            text: Text to split
            max_length: Maximum characters per block

        Returns:
            List of text chunks
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        current = ""

        for line in text.split("\n"):
            if len(current) + len(line) + 1 > max_length:
                if current:
                    chunks.append(current.strip())
                current = line + "\n"
            else:
                current += line + "\n"

        if current.strip():
            chunks.append(current.strip())

        return chunks if chunks else [text[:max_length]]

    def _format_size(self, size_bytes: int) -> str:
        """Format file size for display.

        Args:
            size_bytes: Size in bytes

        Returns:
            Human-readable size string
        """
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def build_button_card(
        self,
        text: str,
        buttons: list[dict[str, str]],
        title: str | None = None,
        style: str | None = None,
    ) -> dict[str, Any]:
        """Build an Adaptive Card with action buttons.

        Args:
            text: Card body text
            buttons: List of button dicts with "title" and "action" or "url"
            title: Optional card title
            style: Optional container style (emphasis, accent, good, warning, attention)

        Returns:
            Adaptive Card JSON structure
        """
        body = []

        if title:
            body.append(
                {
                    "type": "TextBlock",
                    "text": title,
                    "weight": "Bolder",
                    "size": "Medium",
                    "wrap": True,
                }
            )

        container_items = [
            {
                "type": "TextBlock",
                "text": text,
                "wrap": True,
            }
        ]

        if style:
            body.append(
                {
                    "type": "Container",
                    "style": style,
                    "items": container_items,
                }
            )
        else:
            body.extend(container_items)

        # Build actions
        actions = []
        for btn in buttons[:5]:  # Max 5 buttons
            if "url" in btn:
                actions.append(
                    {
                        "type": "Action.OpenUrl",
                        "title": btn.get("title", "Link"),
                        "url": btn["url"],
                    }
                )
            else:
                actions.append(
                    {
                        "type": "Action.Submit",
                        "title": btn.get("title", "Action"),
                        "data": {"action": btn.get("action", "")},
                    }
                )

        return {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": self.SCHEMA_VERSION,
            "body": body,
            "actions": actions,
        }

    def build_from_parsed(
        self,
        parsed: ParsedMarkers,
        tool_count: int = 0,
    ) -> dict[str, Any]:
        """Build an Adaptive Card from parsed markers.

        Args:
            parsed: ParsedMarkers from parse_markers()
            tool_count: Number of tools used

        Returns:
            Adaptive Card JSON structure
        """
        if parsed.buttons:
            return self.build_button_card(
                text=parsed.text,
                buttons=parsed.buttons,
                title=parsed.card_title,
                style=parsed.card_style,
            )
        else:
            return self.build_response_card(
                text=parsed.text,
                tool_count=tool_count,
                title=parsed.card_title,
            )
