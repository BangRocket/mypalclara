"""Tests for subagent orchestration."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from mypalclara.core.subagent.registry import SubagentRegistry, SubagentStatus
from mypalclara.core.subagent.runner import SubagentRunner
from mypalclara.core.subagent.tools import handle_subagent_tool, make_subagent_tools


class TestSubagentRegistry:
    def test_register_and_list(self):
        registry = SubagentRegistry()
        record = registry.register("parent_1", "Write a summary", tier="mid")
        assert record.status == SubagentStatus.RUNNING
        agents = registry.list_active()
        assert len(agents) == 1
        assert agents[0].task == "Write a summary"

    def test_kill_agent(self):
        registry = SubagentRegistry()
        record = registry.register("parent_1", "Task A")
        registry.kill(record.id)
        assert registry.get(record.id).status == SubagentStatus.KILLED

    def test_kill_all(self):
        registry = SubagentRegistry()
        registry.register("parent_1", "Task A")
        registry.register("parent_1", "Task B")
        killed = registry.kill_all("parent_1")
        assert killed == 2
        assert all(r.status == SubagentStatus.KILLED for r in registry.list_all())

    def test_complete_agent(self):
        registry = SubagentRegistry()
        record = registry.register("parent_1", "Task A")
        registry.complete(record.id, "Done successfully")
        assert registry.get(record.id).status == SubagentStatus.COMPLETED
        assert registry.get(record.id).result_summary == "Done successfully"

    def test_max_subagents_per_parent(self):
        registry = SubagentRegistry(max_per_parent=3)
        for i in range(3):
            registry.register("parent_1", f"Task {i}")
        with pytest.raises(RuntimeError, match="maximum"):
            registry.register("parent_1", "Task overflow")

    def test_different_parents_independent(self):
        registry = SubagentRegistry(max_per_parent=2)
        registry.register("parent_1", "Task A")
        registry.register("parent_1", "Task B")
        registry.register("parent_2", "Task C")  # Should work - different parent
        assert len(registry.list_active("parent_1")) == 2
        assert len(registry.list_active("parent_2")) == 1

    def test_fail_agent(self):
        registry = SubagentRegistry()
        record = registry.register("parent_1", "Task A")
        registry.fail(record.id, "Something broke")
        assert registry.get(record.id).status == SubagentStatus.FAILED
        assert "Something broke" in registry.get(record.id).result_summary


class TestSubagentSteering:
    def test_steer_queues_instruction(self):
        registry = SubagentRegistry()
        record = registry.register("parent_1", "Task A")
        registry.steer(record.id, "Focus on error handling")
        instructions = registry.pop_steering(record.id)
        assert len(instructions) == 1
        assert instructions[0] == "Focus on error handling"

    def test_steer_rate_limited(self):
        registry = SubagentRegistry()
        record = registry.register("parent_1", "Task A")
        registry.steer(record.id, "Instruction 1")
        with pytest.raises(RuntimeError, match="rate"):
            registry.steer(record.id, "Instruction 2")

    def test_steer_dead_agent_raises(self):
        registry = SubagentRegistry()
        record = registry.register("parent_1", "Task A")
        registry.kill(record.id)
        with pytest.raises(RuntimeError, match="not running"):
            registry.steer(record.id, "Too late")

    def test_pop_steering_clears_queue(self):
        registry = SubagentRegistry()
        record = registry.register("parent_1", "Task A")
        registry.steer(record.id, "Instruction 1")
        registry.pop_steering(record.id)
        assert registry.pop_steering(record.id) == []

    def test_pop_steering_nonexistent(self):
        registry = SubagentRegistry()
        assert registry.pop_steering("nonexistent") == []


class TestSubagentRunner:
    @pytest.mark.asyncio
    async def test_run_completes_task(self):
        registry = SubagentRegistry()

        async def mock_generate(*args, **kwargs):
            yield {"type": "complete", "content": "Task completed successfully"}

        mock_orch = MagicMock()
        mock_orch.generate_with_tools = MagicMock(return_value=mock_generate())

        runner = SubagentRunner(registry, lambda: mock_orch)
        record = registry.register("parent_1", "Summarize the document")
        result = await runner.run(record.id, tools=[], user_id="test_user")
        assert registry.get(record.id).status == SubagentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_timeout_fails_agent(self):
        registry = SubagentRegistry()

        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(10)
            yield {"type": "complete", "content": "Never reached"}

        mock_orch = MagicMock()
        mock_orch.generate_with_tools = MagicMock(return_value=slow_generate())

        runner = SubagentRunner(registry, lambda: mock_orch, timeout_seconds=0.1)
        record = registry.register("parent_1", "Slow task")
        await runner.run(record.id, tools=[], user_id="test_user")
        assert registry.get(record.id).status == SubagentStatus.FAILED


class TestSubagentTools:
    def test_make_tools_returns_four(self):
        registry = SubagentRegistry()
        runner = SubagentRunner(registry, lambda: None)
        tools = make_subagent_tools(registry, runner)
        assert len(tools) == 4
        names = [t["name"] for t in tools]
        assert "subagent_spawn" in names
        assert "subagent_list" in names
        assert "subagent_kill" in names
        assert "subagent_steer" in names

    @pytest.mark.asyncio
    async def test_handle_list_empty(self):
        registry = SubagentRegistry()
        runner = SubagentRunner(registry, lambda: None)
        result = await handle_subagent_tool("subagent_list", {}, "parent_1", registry, runner, [], "user")
        assert "No sub-agents" in result

    @pytest.mark.asyncio
    async def test_handle_kill(self):
        registry = SubagentRegistry()
        runner = SubagentRunner(registry, lambda: None)
        record = registry.register("parent_1", "Task A")
        result = await handle_subagent_tool(
            "subagent_kill",
            {"id": record.id},
            "parent_1",
            registry,
            runner,
            [],
            "user",
        )
        assert "Killed" in result
        assert registry.get(record.id).status == SubagentStatus.KILLED

    @pytest.mark.asyncio
    async def test_handle_steer(self):
        registry = SubagentRegistry()
        runner = SubagentRunner(registry, lambda: None)
        record = registry.register("parent_1", "Task A")
        result = await handle_subagent_tool(
            "subagent_steer",
            {"id": record.id, "instruction": "Be concise"},
            "parent_1",
            registry,
            runner,
            [],
            "user",
        )
        assert "sent" in result.lower()
