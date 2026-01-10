"""Tests for Clara's LangGraph flow."""

import pytest

from mypalclara.graph import create_graph, route_after_node
from mypalclara.models.state import ClaraState


class TestRouteAfterNode:
    """Tests for the universal router."""

    def test_routes_to_ruminate(self):
        """Route to ruminate when specified."""
        state = {"next": "ruminate"}
        assert route_after_node(state) == "ruminate"

    def test_routes_to_speak(self):
        """Route to speak when specified."""
        state = {"next": "speak"}
        assert route_after_node(state) == "speak"

    def test_routes_to_command(self):
        """Route to command when specified."""
        state = {"next": "command"}
        assert route_after_node(state) == "command"

    def test_routes_to_finalize(self):
        """Route to finalize when specified."""
        state = {"next": "finalize"}
        assert route_after_node(state) == "finalize"

    def test_routes_to_end_when_missing(self):
        """Route to end when next is not specified."""
        state = {}
        assert route_after_node(state) == "end"


class TestCreateGraph:
    """Tests for graph creation."""

    def test_graph_creates_successfully(self):
        """Graph should compile without errors."""
        graph = create_graph()
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        """Graph should have all expected nodes."""
        graph = create_graph()
        # The compiled graph has a nodes property
        node_names = list(graph.nodes.keys())
        expected = ["evaluate", "ruminate", "command", "speak", "finalize"]
        for name in expected:
            assert name in node_names, f"Missing node: {name}"
