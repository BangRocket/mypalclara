"""Live-updating console formatter for CrewAI flows.

Replaces CrewAI's default ConsoleFormatter with one that uses rich.live.Live
to update the flow tree in place rather than reprinting it each time.
"""

from __future__ import annotations

import threading
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.tree import Tree

from mindflow.events.utils.console_formatter import ConsoleFormatter


class LiveFlowFormatter(ConsoleFormatter):
    """Console formatter that updates flow trees in place.

    Uses rich's Live display to update the tree in place rather than
    reprinting the entire tree on each step update.
    """

    def __init__(self, verbose: bool = False):
        super().__init__(verbose=verbose)
        self._live: Optional[Live] = None
        self._live_lock = threading.Lock()
        self._flow_active = False
        self._method_branches: dict[str, Tree] = {}  # Track branches by method name
        self._current_agent_branch: Optional[Tree] = None

    def _start_live(self, initial_content) -> None:
        """Start the live display context."""
        with self._live_lock:
            if self._live is None:
                self._live = Live(
                    initial_content,
                    console=self.console,
                    refresh_per_second=10,
                    transient=False,  # Keep final output
                )
                self._live.start()
                self._flow_active = True

    def _stop_live(self) -> None:
        """Stop the live display context."""
        with self._live_lock:
            if self._live is not None:
                self._live.stop()
                self._live = None
                self._flow_active = False

    def _update_live(self, content) -> None:
        """Update the live display content."""
        with self._live_lock:
            if self._live is not None:
                self._live.update(content)

    def start_flow(self, flow_name: str, flow_id: str) -> Optional[Tree]:
        """Initialize a flow execution tree with live display."""
        flow_tree = Tree("")
        flow_label = Text()
        flow_label.append("🌊 Flow: ", style="blue bold")
        flow_label.append(flow_name, style="blue")
        flow_label.append("\n    ID: ", style="white")
        flow_label.append(flow_id, style="blue")
        flow_tree.label = flow_label

        self.add_tree_node(flow_tree, "🧠 Starting Flow...", "yellow")

        # Start live display instead of printing
        self._start_live(flow_tree)

        self.current_flow_tree = flow_tree
        return flow_tree

    def update_flow_status(
        self,
        flow_tree: Optional[Tree],
        flow_name: str,
        flow_id: str,
        status: str = "completed",
    ) -> None:
        """Update flow status and stop live display."""
        if flow_tree is None:
            return

        # Update main flow label
        self.update_tree_label(
            flow_tree,
            "✅ Flow Finished:" if status == "completed" else "❌ Flow Failed:",
            flow_name,
            "green" if status == "completed" else "red",
        )

        # Update initialization node status
        for child in flow_tree.children:
            if "Starting Flow" in str(child.label):
                child.label = Text(
                    (
                        "✅ Flow Completed"
                        if status == "completed"
                        else "❌ Flow Failed"
                    ),
                    style="green" if status == "completed" else "red",
                )
                break

        # Final update before stopping
        self._update_live(flow_tree)

        # Stop live display
        self._stop_live()

        # Print final status panel
        content = self.create_status_content(
            (
                "Flow Execution Completed"
                if status == "completed"
                else "Flow Execution Failed"
            ),
            flow_name,
            "green" if status == "completed" else "red",
            ID=flow_id,
        )
        self.print_panel(
            content, "Flow Completion", "green" if status == "completed" else "red"
        )

    def update_method_status(
        self,
        method_branch: Optional[Tree],
        flow_tree: Optional[Tree],
        method_name: str,
        status: str = "running",
        error: str | None = None,
    ) -> Optional[Tree]:
        """Update method status in the flow tree with live update."""
        if not flow_tree:
            return None

        if status == "running":
            prefix, style = "🔄 Running:", "yellow"
        elif status == "completed":
            prefix, style = "✅ Completed:", "green"
            # Update initialization node when a method completes successfully
            for child in flow_tree.children:
                if "Starting Flow" in str(child.label):
                    child.label = Text("Flow Method Step", style="white")
                    break
        else:
            prefix, style = "❌ Failed:", "red"
            # Update initialization node on failure
            for child in flow_tree.children:
                if "Starting Flow" in str(child.label):
                    child.label = Text("❌ Flow Step Failed", style="red")
                    break

        if not method_branch:
            # Find or create method branch
            for branch in flow_tree.children:
                if method_name in str(branch.label):
                    method_branch = branch
                    break
            if not method_branch:
                method_branch = flow_tree.add("")

        label = Text(prefix, style=f"{style} bold") + Text(
            f" {method_name}", style=style
        )

        # Add error message if failed
        if status == "failed" and error:
            error_msg = str(error)[:80]
            if len(str(error)) > 80:
                error_msg += "..."
            label.append(f" ({error_msg})", style="red dim")

        method_branch.label = label

        # Track the branch by method name for agent additions
        self._method_branches[method_name] = method_branch

        # Update live display instead of reprinting
        self._update_live(flow_tree)

        return method_branch

    def add_agent_execution(
        self,
        method_name: str,
        agent_name: str,
        status: str = "running",
        error: str | None = None,
    ) -> Optional[Tree]:
        """Add an agent execution branch under a method.

        Args:
            method_name: The flow method this agent is running under
            agent_name: Name of the agent being invoked
            status: "running", "completed", or "failed"
            error: Error message if status is "failed"

        Returns:
            The agent branch node
        """
        if not self.current_flow_tree:
            return None

        # Find the method branch
        method_branch = self._method_branches.get(method_name)
        if not method_branch:
            return None

        if status == "running":
            prefix, style = "🤖", "cyan"
            label = Text(f"{prefix} {agent_name}", style=style)
            label.append(" (running...)", style="cyan dim")
        elif status == "completed":
            prefix, style = "🤖", "green"
            label = Text(f"{prefix} {agent_name}", style=style)
            label.append(" ✓", style="green bold")
        else:
            prefix, style = "🤖", "red"
            label = Text(f"{prefix} {agent_name}", style=style)
            label.append(" ✗ ", style="red bold")
            if error:
                # Truncate error message
                error_msg = str(error)[:80]
                if len(str(error)) > 80:
                    error_msg += "..."
                label.append(f"({error_msg})", style="red dim")

        # Find existing agent branch or create new one
        agent_branch = None
        for child in method_branch.children:
            if agent_name in str(child.label):
                agent_branch = child
                break

        if not agent_branch:
            agent_branch = method_branch.add(label)
        else:
            agent_branch.label = label

        self._current_agent_branch = agent_branch
        self._update_live(self.current_flow_tree)
        return agent_branch

    def add_tool_execution(
        self,
        tool_name: str,
        status: str = "running",
        error: str | None = None,
    ) -> None:
        """Add a tool execution under the current agent.

        Args:
            tool_name: Name of the tool being used
            status: "running", "completed", or "failed"
            error: Error message if status is "failed"
        """
        if not self._current_agent_branch or not self.current_flow_tree:
            return

        if status == "running":
            style = "yellow"
            label = Text(f"  🔧 {tool_name}", style=style)
            label.append(" ...", style="yellow dim")
        elif status == "completed":
            style = "green"
            label = Text(f"  🔧 {tool_name}", style=style)
        else:
            style = "red"
            label = Text(f"  🔧 {tool_name}", style=style)
            label.append(" ✗ ", style="red bold")
            if error:
                # Truncate error message to keep tree readable
                error_msg = str(error)[:60]
                if len(str(error)) > 60:
                    error_msg += "..."
                label.append(f"({error_msg})", style="red dim")
            else:
                label.append("(failed)", style="red dim")

        # Find existing tool branch or create new one
        tool_branch = None
        for child in self._current_agent_branch.children:
            if tool_name in str(child.label):
                tool_branch = child
                break

        if not tool_branch:
            self._current_agent_branch.add(label)
        else:
            tool_branch.label = label

        self._update_live(self.current_flow_tree)

    # Override ConsoleFormatter tool methods to work with flow-based agent tracking

    def handle_tool_usage_started(
        self,
        agent_branch: Optional[Tree],
        tool_name: str,
        crew_tree: Optional[Tree],
    ) -> Optional[Tree]:
        """Handle tool usage started - override for flow context."""
        # Use our flow-based tracking instead of crew-based
        if self._current_agent_branch and self.current_flow_tree:
            self.add_tool_execution(tool_name, "running")
            # Return a dummy branch for compatibility
            return self._current_agent_branch
        # Fall back to parent implementation for crew context
        return super().handle_tool_usage_started(agent_branch, tool_name, crew_tree)

    def handle_tool_usage_finished(
        self,
        tool_branch: Optional[Tree],
        tool_name: str,
        crew_tree: Optional[Tree],
    ) -> None:
        """Handle tool usage finished - override for flow context."""
        # Use our flow-based tracking instead of crew-based
        if self._current_agent_branch and self.current_flow_tree:
            self.add_tool_execution(tool_name, "completed")
            return
        # Fall back to parent implementation for crew context
        super().handle_tool_usage_finished(tool_branch, tool_name, crew_tree)

    def handle_tool_usage_error(
        self,
        tool_branch: Optional[Tree],
        tool_name: str,
        error: str,
        crew_tree: Optional[Tree],
    ) -> None:
        """Handle tool usage error - override for flow context."""
        # Use our flow-based tracking instead of crew-based
        if self._current_agent_branch and self.current_flow_tree:
            self.add_tool_execution(tool_name, "failed", error=error)
            return
        # Fall back to parent implementation for crew context
        super().handle_tool_usage_error(tool_branch, tool_name, error, crew_tree)

    def print(self, *args, **kwargs) -> None:
        """Print to console, skipping if live display is active for flows."""
        # During active flow, don't print trees - use live update instead
        if self._flow_active and args and isinstance(args[0], Tree):
            self._update_live(args[0])
            return

        # For everything else, use normal printing
        self.console.print(*args, **kwargs)


_live_formatter: Optional[LiveFlowFormatter] = None


def install_live_formatter() -> LiveFlowFormatter:
    """Install the live formatter as the global event listener's formatter.

    Call this at startup before any flows are executed.

    Returns:
        The installed LiveFlowFormatter instance
    """
    global _live_formatter
    from mindflow.events.event_listener import event_listener

    # Replace the default formatter with our live formatter
    _live_formatter = LiveFlowFormatter(verbose=False)
    event_listener.formatter = _live_formatter
    return _live_formatter


def get_live_formatter() -> Optional[LiveFlowFormatter]:
    """Get the installed live formatter instance.

    Returns:
        The LiveFlowFormatter if installed, None otherwise
    """
    return _live_formatter
