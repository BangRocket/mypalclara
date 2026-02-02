"""Tests for the Microsoft Teams adapter."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTeamsBot:
    """Tests for TeamsBot class."""

    @pytest.fixture
    def mock_gateway_client(self):
        """Create a mock gateway client."""
        client = MagicMock()
        client.is_connected = True
        client.send_teams_message = AsyncMock(return_value="req-123")
        return client

    @pytest.fixture
    def teams_bot(self, mock_gateway_client):
        """Create a TeamsBot instance."""
        from adapters.teams.bot import TeamsBot

        return TeamsBot(gateway_client=mock_gateway_client)

    @pytest.fixture
    def mock_turn_context(self):
        """Create a mock turn context."""
        context = MagicMock()
        context.activity = MagicMock()
        context.activity.from_property = MagicMock()
        context.activity.from_property.id = "user-123"
        context.activity.from_property.name = "Test User"
        context.activity.text = "Hello Clara"
        context.activity.recipient = MagicMock()
        context.activity.recipient.id = "bot-123"
        context.send_activity = AsyncMock()
        return context

    def test_detect_tier_high(self, teams_bot):
        """Should detect high tier prefix."""
        assert teams_bot._detect_tier("!high What is AI?") == "high"
        assert teams_bot._detect_tier("!opus Explain quantum physics") == "high"

    def test_detect_tier_mid(self, teams_bot):
        """Should detect mid tier prefix."""
        assert teams_bot._detect_tier("!mid Summarize this") == "mid"
        assert teams_bot._detect_tier("!sonnet Write a poem") == "mid"

    def test_detect_tier_low(self, teams_bot):
        """Should detect low tier prefix."""
        assert teams_bot._detect_tier("!low What time is it?") == "low"
        assert teams_bot._detect_tier("!haiku Quick question") == "low"
        assert teams_bot._detect_tier("!fast Hello") == "low"

    def test_detect_tier_none(self, teams_bot):
        """Should return None for no prefix."""
        assert teams_bot._detect_tier("Hello world") is None
        assert teams_bot._detect_tier("What is !high used for?") is None

    @pytest.mark.asyncio
    async def test_on_message_sends_to_gateway(
        self, teams_bot, mock_turn_context, mock_gateway_client
    ):
        """Should send message to gateway."""
        await teams_bot.on_message_activity(mock_turn_context)

        mock_gateway_client.send_teams_message.assert_called_once()
        call_kwargs = mock_gateway_client.send_teams_message.call_args
        assert call_kwargs.kwargs["turn_context"] == mock_turn_context
        assert call_kwargs.kwargs["tier_override"] is None

    @pytest.mark.asyncio
    async def test_on_message_with_tier(
        self, teams_bot, mock_turn_context, mock_gateway_client
    ):
        """Should pass tier override to gateway."""
        mock_turn_context.activity.text = "!high Complex question"

        await teams_bot.on_message_activity(mock_turn_context)

        call_kwargs = mock_gateway_client.send_teams_message.call_args
        assert call_kwargs.kwargs["tier_override"] == "high"

    @pytest.mark.asyncio
    async def test_on_message_gateway_disconnected(
        self, teams_bot, mock_turn_context, mock_gateway_client
    ):
        """Should send error when gateway disconnected."""
        mock_gateway_client.is_connected = False

        await teams_bot.on_message_activity(mock_turn_context)

        mock_turn_context.send_activity.assert_called()
        call_args = mock_turn_context.send_activity.call_args[0][0]
        assert "trouble connecting" in call_args


class TestTeamsGatewayClient:
    """Tests for TeamsGatewayClient class."""

    @pytest.fixture
    def mock_graph_client(self):
        """Create a mock Graph client."""
        client = MagicMock()
        client.get_chat_messages = AsyncMock(return_value=[])
        client.get_channel_messages = AsyncMock(return_value=[])
        client.upload_file_to_onedrive = AsyncMock(
            return_value={"id": "file-1", "name": "test.txt", "webUrl": "https://..."}
        )
        client.create_sharing_link = AsyncMock(return_value="https://share.link")
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def gateway_client(self, mock_graph_client):
        """Create a TeamsGatewayClient instance."""
        from adapters.teams.gateway_client import TeamsGatewayClient

        client = TeamsGatewayClient(
            gateway_url="ws://localhost:18789",
            graph_client=mock_graph_client,
        )
        return client

    def test_clean_content_removes_mentions(self, gateway_client):
        """Should remove bot mentions from content."""
        from botbuilder.schema import Activity, Entity

        activity = Activity()
        activity.entities = [
            MagicMock(
                type="mention",
                additional_properties={
                    "mentioned": {"id": "bot-123"},
                    "text": "<at>Clara</at>",
                },
            )
        ]

        result = gateway_client._clean_content("<at>Clara</at> Hello there", activity)
        assert result == "Hello there"

    def test_clean_content_no_mentions(self, gateway_client):
        """Should preserve content with no mentions."""
        from botbuilder.schema import Activity

        activity = Activity()
        activity.entities = []

        result = gateway_client._clean_content("Hello there", activity)
        assert result == "Hello there"

    @pytest.mark.asyncio
    async def test_build_reply_chain_chat(self, gateway_client, mock_graph_client):
        """Should fetch chat messages for personal conversations."""
        mock_graph_client.get_chat_messages.return_value = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"},
        ]

        mock_turn_context = MagicMock()
        mock_turn_context.activity = MagicMock()
        mock_turn_context.activity.conversation = MagicMock()
        mock_turn_context.activity.conversation.id = "chat-123"
        mock_turn_context.activity.conversation.conversation_type = "personal"
        mock_turn_context.activity.text = "Current message"

        result = await gateway_client._build_reply_chain(mock_turn_context)

        mock_graph_client.get_chat_messages.assert_called_once()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_build_reply_chain_channel(self, gateway_client, mock_graph_client):
        """Should fetch channel messages for group conversations."""
        mock_graph_client.get_channel_messages.return_value = [
            {"role": "user", "content": "Channel message"},
        ]

        mock_turn_context = MagicMock()
        mock_turn_context.activity = MagicMock()
        mock_turn_context.activity.conversation = MagicMock()
        mock_turn_context.activity.conversation.id = "19:xxx@thread.tacv2"
        mock_turn_context.activity.conversation.conversation_type = "channel"
        mock_turn_context.activity.channel_data = {"team": {"id": "team-123"}}
        mock_turn_context.activity.text = "Current message"

        result = await gateway_client._build_reply_chain(mock_turn_context)

        mock_graph_client.get_channel_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_files_uploads_to_onedrive(
        self, gateway_client, mock_graph_client, tmp_path
    ):
        """Should upload files to OneDrive and send cards."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        mock_turn_context = MagicMock()
        mock_turn_context.send_activity = AsyncMock()

        await gateway_client._send_files(mock_turn_context, [str(test_file)])

        mock_graph_client.upload_file_to_onedrive.assert_called_once()
        mock_graph_client.create_sharing_link.assert_called_once()
        mock_turn_context.send_activity.assert_called_once()


class TestGraphClient:
    """Tests for GraphClient class."""

    @pytest.fixture
    def graph_client(self):
        """Create a GraphClient instance."""
        from adapters.teams.graph_client import GraphClient

        return GraphClient(
            app_id="test-app-id",
            app_password="test-password",
            tenant_id="test-tenant",
        )

    def test_strip_html(self, graph_client):
        """Should strip HTML tags from content."""
        html = "<p>Hello <b>World</b></p>"
        result = graph_client._strip_html(html)
        assert result == "Hello World"

    def test_strip_html_entities(self, graph_client):
        """Should decode HTML entities."""
        html = "Hello&nbsp;World &amp; Friends &lt;3"
        result = graph_client._strip_html(html)
        assert result == "Hello World & Friends <3"

    @pytest.mark.asyncio
    async def test_get_token_caches(self, graph_client):
        """Should cache tokens."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            mock_session.closed = False

            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={
                    "access_token": "test-token",
                    "expires_in": 3600,
                }
            )
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock()

            mock_session.post = MagicMock(return_value=mock_response)

            # First call should request token
            token1 = await graph_client._get_token()

            # Second call should use cache
            token2 = await graph_client._get_token()

            assert token1 == "test-token"
            assert token2 == "test-token"
            # Should only have called post once
            assert mock_session.post.call_count == 1


class TestAdaptiveCardBuilder:
    """Tests for AdaptiveCardBuilder class."""

    @pytest.fixture
    def card_builder(self):
        """Create an AdaptiveCardBuilder instance."""
        from adapters.teams.message_builder import AdaptiveCardBuilder

        return AdaptiveCardBuilder()

    def test_build_response_card(self, card_builder):
        """Should build a valid response card."""
        card = card_builder.build_response_card(
            text="Hello world",
            tool_count=2,
        )

        assert card["type"] == "AdaptiveCard"
        assert card["version"] == "1.4"
        assert len(card["body"]) == 2  # Text + tool count

    def test_build_response_card_long_text(self, card_builder):
        """Should split long text into blocks when it has newlines."""
        # Create text with newlines that exceeds max_length
        long_text = "\n".join(["A" * 100] * 50)  # 50 lines of 100 chars
        card = card_builder.build_response_card(text=long_text)

        # Should have multiple text blocks when split on newlines
        text_blocks = [b for b in card["body"] if b["type"] == "TextBlock"]
        assert len(text_blocks) >= 2

    def test_build_tool_status_card(self, card_builder):
        """Should build a valid tool status card."""
        card = card_builder.build_tool_status_card(
            tool_name="python_execute",
            step=1,
            emoji="🐍",
        )

        assert card["type"] == "AdaptiveCard"
        # Should have column set with emoji and name
        assert card["body"][0]["type"] == "ColumnSet"

    def test_build_error_card(self, card_builder):
        """Should build a valid error card."""
        card = card_builder.build_error_card(
            error_message="Something went wrong",
        )

        assert card["type"] == "AdaptiveCard"
        assert card["body"][0]["color"] == "Attention"

    def test_build_welcome_card(self, card_builder):
        """Should build a welcome card with action."""
        card = card_builder.build_welcome_card(user_name="Alice")

        assert card["type"] == "AdaptiveCard"
        assert "actions" in card
        assert card["actions"][0]["type"] == "Action.Submit"

    def test_build_file_card(self, card_builder):
        """Should build a file card with download link."""
        card = card_builder.build_file_card(
            filename="report.pdf",
            file_size=1024 * 1024,  # 1MB
            download_url="https://example.com/download",
        )

        assert card["type"] == "AdaptiveCard"
        assert "actions" in card
        assert card["actions"][0]["type"] == "Action.OpenUrl"

    def test_format_size(self, card_builder):
        """Should format file sizes correctly."""
        assert "1.0 KB" in card_builder._format_size(1024)
        assert "1.0 MB" in card_builder._format_size(1024 * 1024)
        assert "1.0 GB" in card_builder._format_size(1024 * 1024 * 1024)
