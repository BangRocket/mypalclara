"""Tests for the simplified FalkorDB graph memory."""

from unittest.mock import MagicMock, patch

import pytest


class FakeQueryResult:
    """Mimics FalkorDB QueryResult for testing."""

    def __init__(self, header=None, result_set=None):
        self.header = header or []
        self.result_set = result_set or []


@pytest.fixture
def mock_falkordb():
    """Mock FalkorDB client and graph."""
    with patch("clara_core.memory.graph.falkordb.falkordb") as mock_module:
        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_module.FalkorDB.return_value = mock_client
        mock_client.select_graph.return_value = mock_graph
        # Default: index creation succeeds silently
        mock_graph.query.return_value = FakeQueryResult()
        yield mock_graph


@pytest.fixture
def mock_embedding():
    """Mock OpenAI embedding model."""
    with patch("clara_core.memory.graph.falkordb.OpenAIEmbedding") as mock_cls:
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [0.1] * 1536
        mock_cls.return_value = mock_embedder
        yield mock_embedder


@pytest.fixture
def mock_llm():
    """Mock UnifiedLLM."""
    with patch("clara_core.memory.graph.falkordb.UnifiedLLM") as mock_cls:
        mock_llm = MagicMock()
        mock_cls.return_value = mock_llm
        yield mock_llm


@pytest.fixture
def graph_config():
    """Build a ClaraMemoryConfig-like object for testing."""
    from unittest.mock import MagicMock

    config = MagicMock()
    config.graph_store.config = {
        "host": "localhost",
        "port": 6379,
        "password": None,
        "graph_name": "test_graph",
    }
    config.graph_store.provider = "falkordb"
    config.graph_store.llm = None
    config.graph_store.threshold = 0.7
    config.embedder.config = {"model": "text-embedding-3-small", "api_key": "test"}
    config.llm.provider = "openrouter"
    config.llm.config = {"provider": "openrouter", "model": "gpt-4o-mini", "api_key": "test"}
    return config


@pytest.fixture
def memory_graph(mock_falkordb, mock_embedding, mock_llm, graph_config):
    """Create a MemoryGraph instance with all mocks."""
    from clara_core.memory.graph.falkordb import MemoryGraph

    graph = MemoryGraph(graph_config)
    return graph


class TestMemoryGraphInit:
    """Tests for MemoryGraph initialization."""

    def test_creates_vector_index(self, mock_falkordb, mock_embedding, mock_llm, graph_config):
        """Index creation should be attempted on init."""
        from clara_core.memory.graph.falkordb import MemoryGraph

        MemoryGraph(graph_config)
        # Should have called query for index creation
        calls = [str(c) for c in mock_falkordb.query.call_args_list]
        assert any("VECTOR INDEX" in c for c in calls)

    def test_index_creation_failure_is_silent(self, mock_falkordb, mock_embedding, mock_llm, graph_config):
        """If index already exists, exception should be swallowed."""
        mock_falkordb.query.side_effect = Exception("Index already exists")
        from clara_core.memory.graph.falkordb import MemoryGraph

        # Should not raise
        MemoryGraph(graph_config)


class TestMemoryGraphAdd:
    """Tests for the write path."""

    def test_add_calls_llm_with_extract_triples_tool(self, memory_graph, mock_llm):
        """Write path should make exactly 1 LLM call with extract_triples tool."""
        mock_llm.generate_response.return_value = {
            "tool_calls": [
                {
                    "name": "extract_triples",
                    "arguments": {
                        "triples": [
                            {"subject": "Josh", "predicate": "likes", "object": "pizza"},
                        ]
                    },
                }
            ]
        }
        result = memory_graph.add("Josh likes pizza", {"user_id": "user-1"})

        # Exactly 1 LLM call
        assert mock_llm.generate_response.call_count == 1
        call_kwargs = mock_llm.generate_response.call_args
        # Should have tools and tool_choice
        assert call_kwargs.kwargs.get("tools") is not None or (
            len(call_kwargs.args) > 1 and call_kwargs.args[1] is not None
        )

    def test_add_merges_nodes_and_relationship(self, memory_graph, mock_llm, mock_falkordb):
        """Add should MERGE source, destination, and relationship."""
        mock_llm.generate_response.return_value = {
            "tool_calls": [
                {
                    "name": "extract_triples",
                    "arguments": {
                        "triples": [
                            {"subject": "Josh", "predicate": "lives_in", "object": "NYC"},
                        ]
                    },
                }
            ]
        }
        memory_graph.add("Josh lives in NYC", {"user_id": "user-1"})

        # Check that Cypher MERGE was called (beyond index creation)
        cypher_calls = [str(c) for c in mock_falkordb.query.call_args_list if "MERGE" in str(c)]
        assert len(cypher_calls) >= 1

    def test_add_handles_string_llm_response(self, memory_graph, mock_llm):
        """If LLM returns string instead of tool call, add should return empty gracefully."""
        mock_llm.generate_response.return_value = "I found some entities"
        result = memory_graph.add("Josh likes pizza", {"user_id": "user-1"})
        assert result["added_entities"] == []

    def test_add_handles_empty_llm_response(self, memory_graph, mock_llm):
        """If LLM returns empty/None, add should return empty gracefully."""
        mock_llm.generate_response.return_value = ""
        result = memory_graph.add("Josh likes pizza", {"user_id": "user-1"})
        assert result["added_entities"] == []

    def test_add_normalizes_entity_names(self, memory_graph, mock_llm, mock_falkordb):
        """Entity names should be lowercased with spaces replaced by underscores."""
        mock_llm.generate_response.return_value = {
            "tool_calls": [
                {
                    "name": "extract_triples",
                    "arguments": {
                        "triples": [
                            {"subject": "Joshua Heidorn", "predicate": "Works At", "object": "Acme Corp"},
                        ]
                    },
                }
            ]
        }
        memory_graph.add("Joshua Heidorn works at Acme Corp", {"user_id": "user-1"})

        # Check that normalized names appear in Cypher
        cypher_calls = " ".join(str(c) for c in mock_falkordb.query.call_args_list)
        assert "joshua_heidorn" in cypher_calls.lower() or "$source_name" in cypher_calls

    def test_add_returns_correct_structure(self, memory_graph, mock_llm):
        """Add should return dict with deleted_entities and added_entities."""
        mock_llm.generate_response.return_value = {
            "tool_calls": [
                {
                    "name": "extract_triples",
                    "arguments": {
                        "triples": [
                            {"subject": "Josh", "predicate": "likes", "object": "pizza"},
                        ]
                    },
                }
            ]
        }
        result = memory_graph.add("Josh likes pizza", {"user_id": "user-1"})
        assert "deleted_entities" in result
        assert "added_entities" in result
        assert isinstance(result["deleted_entities"], list)
        assert isinstance(result["added_entities"], list)


class TestMemoryGraphSearch:
    """Tests for the read path."""

    def test_search_does_not_call_llm(self, memory_graph, mock_llm, mock_falkordb):
        """Read path should NOT make any LLM calls -- only embedding + vector search."""
        mock_falkordb.query.return_value = FakeQueryResult()
        memory_graph.search("what does Josh like", {"user_id": "user-1"})
        mock_llm.generate_response.assert_not_called()

    def test_search_uses_vector_query_nodes(self, memory_graph, mock_falkordb, mock_embedding):
        """Search should use db.idx.vector.queryNodes for KNN search."""
        mock_falkordb.query.return_value = FakeQueryResult()
        memory_graph.search("what does Josh like", {"user_id": "user-1"})

        cypher_calls = " ".join(str(c) for c in mock_falkordb.query.call_args_list)
        assert "db.idx.vector.queryNodes" in cypher_calls

    def test_search_returns_correct_structure(self, memory_graph, mock_falkordb, mock_embedding):
        """Search should return list of {source, relationship, destination} dicts."""
        mock_falkordb.query.return_value = FakeQueryResult(
            header=[[1, "source"], [1, "relationship"], [1, "destination"], [1, "score"]],
            result_set=[["josh", "likes", "pizza", 0.95]],
        )
        results = memory_graph.search("what does Josh like", {"user_id": "user-1"})
        assert len(results) == 1
        assert results[0]["source"] == "josh"
        assert results[0]["relationship"] == "likes"
        assert results[0]["destination"] == "pizza"

    def test_search_returns_empty_for_no_matches(self, memory_graph, mock_falkordb):
        """Search with no matching nodes should return empty list."""
        mock_falkordb.query.return_value = FakeQueryResult()
        results = memory_graph.search("unknown topic", {"user_id": "user-1"})
        assert results == []

    def test_search_respects_limit(self, memory_graph, mock_falkordb):
        """Limit parameter should be passed to the query."""
        mock_falkordb.query.return_value = FakeQueryResult()
        memory_graph.search("query", {"user_id": "user-1"}, limit=3)
        cypher_calls = " ".join(str(c) for c in mock_falkordb.query.call_args_list)
        # The limit should appear in the query params
        assert "3" in cypher_calls or "$limit" in cypher_calls


class TestMemoryGraphGetAll:
    """Tests for get_all."""

    def test_get_all_returns_correct_structure(self, memory_graph, mock_falkordb):
        """get_all should return list of {source, relationship, target} dicts."""
        mock_falkordb.query.return_value = FakeQueryResult(
            header=[[1, "source"], [1, "relationship"], [1, "target"]],
            result_set=[["josh", "likes", "pizza"]],
        )
        results = memory_graph.get_all({"user_id": "user-1"})
        assert len(results) == 1
        assert results[0]["source"] == "josh"
        assert results[0]["relationship"] == "likes"
        assert results[0]["target"] == "pizza"


class TestMemoryGraphDeleteAll:
    """Tests for delete_all."""

    def test_delete_all_runs_detach_delete(self, memory_graph, mock_falkordb):
        """delete_all should DETACH DELETE matching nodes."""
        mock_falkordb.query.return_value = FakeQueryResult()
        memory_graph.delete_all({"user_id": "user-1"})
        cypher_calls = " ".join(str(c) for c in mock_falkordb.query.call_args_list)
        assert "DETACH DELETE" in cypher_calls


class TestQueryHelper:
    """Tests for the _query result normalizer."""

    def test_query_normalizes_result_set(self, memory_graph, mock_falkordb):
        """_query should convert result_set rows to list[dict]."""
        mock_falkordb.query.return_value = FakeQueryResult(
            header=[[1, "name"], [1, "age"]],
            result_set=[["Alice", 30], ["Bob", 25]],
        )
        results = memory_graph._query("MATCH (n) RETURN n.name AS name, n.age AS age")
        assert results == [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]

    def test_query_handles_empty_result(self, memory_graph, mock_falkordb):
        """_query should return [] for empty result_set."""
        mock_falkordb.query.return_value = FakeQueryResult()
        results = memory_graph._query("MATCH (n) RETURN n")
        assert results == []
