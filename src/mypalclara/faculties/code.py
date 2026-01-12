"""
Code Faculty - Code execution and autonomous coding.

Combines Docker sandbox execution with Claude Code agent delegation
for comprehensive code execution and development capabilities.
"""

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Optional

from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult

logger = logging.getLogger(__name__)

# Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DEFAULT_WORKDIR = os.getenv("CLAUDE_CODE_WORKDIR", "")
MAX_TURNS = int(os.getenv("CLAUDE_CODE_MAX_TURNS", "10"))


class CodeFaculty(Faculty):
    """Code execution and autonomous coding faculty."""

    name = "code"
    description = "Execute Python code in sandbox, run shell commands, or delegate complex coding tasks to Claude Code"

    available_actions = [
        # Docker Sandbox
        "execute_python",
        "install_package",
        "run_shell",
        "read_file",
        "write_file",
        "list_files",
        "unzip_file",
        # Claude Code
        "claude_code",
        "claude_code_status",
        "set_workdir",
        "get_workdir",
    ]

    def __init__(self):
        self._sandbox_manager = None
        self._user_workdirs: dict[str, str] = {}
        self._claude_auth_status: Optional[dict] = None

    async def execute(
        self,
        intent: str,
        constraints: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> FacultyResult:
        """Execute code-related intent."""
        logger.info(f"[code] Intent: {intent}")

        try:
            # Parse intent to determine action
            action, params = self._parse_intent(intent)
            # Inject user context into params
            params["user_id"] = user_id or params.get("user_id", "default")
            params["channel_id"] = channel_id or params.get("channel_id")
            logger.info(f"[code] Action: {action}, Params: {list(params.keys())}")

            # Execute the action
            if action == "execute_python":
                result = await self._execute_python(params)
            elif action == "install_package":
                result = await self._install_package(params)
            elif action == "run_shell":
                result = await self._run_shell(params)
            elif action == "read_file":
                result = await self._read_file(params)
            elif action == "write_file":
                result = await self._write_file(params)
            elif action == "list_files":
                result = await self._list_files(params)
            elif action == "unzip_file":
                result = await self._unzip_file(params)
            elif action == "claude_code":
                result = await self._claude_code(params)
            elif action == "claude_code_status":
                result = await self._claude_code_status()
            elif action == "set_workdir":
                result = self._set_workdir(params)
            elif action == "get_workdir":
                result = self._get_workdir(params)
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Unknown code action: {action}",
                    error=f"Action '{action}' not recognized",
                )

            return result

        except Exception as e:
            logger.exception(f"[code] Error: {e}")
            return FacultyResult(
                success=False,
                summary=f"Code execution error: {str(e)}",
                error=str(e),
            )

    def _parse_intent(self, intent: str) -> tuple[str, dict]:
        """Parse natural language intent into action and parameters."""
        intent_lower = intent.lower()

        # Claude Code delegation patterns
        if any(phrase in intent_lower for phrase in [
            "use claude code", "delegate to claude", "claude code",
            "autonomous", "refactor", "add feature", "fix bug",
            "write tests", "implement"
        ]):
            return "claude_code", {"prompt": intent}

        # Claude Code status
        if "claude code status" in intent_lower or "check claude" in intent_lower:
            return "claude_code_status", {}

        # Working directory
        if "set workdir" in intent_lower or "set working dir" in intent_lower:
            path = self._extract_path(intent)
            return "set_workdir", {"path": path}

        if "get workdir" in intent_lower or "current workdir" in intent_lower:
            return "get_workdir", {}

        # Python execution patterns
        if any(phrase in intent_lower for phrase in [
            "run python", "execute python", "python code",
            "calculate", "compute", "print("
        ]):
            code = self._extract_code(intent)
            logger.debug(f"[code] Extracted code: {code[:100]}..." if len(code) > 100 else f"[code] Extracted code: {code}")
            return "execute_python", {"code": code}

        # Package installation
        if any(phrase in intent_lower for phrase in ["install package", "pip install", "install"]):
            package = self._extract_package(intent)
            return "install_package", {"package": package}

        # Shell commands - check BEFORE file operations (shell commands may contain ls, cat, etc.)
        # Look for explicit shell indicators or commands in backticks that look like shell
        shell_patterns = [
            "shell command", "run shell", "run command", "execute command",
            "shell:", "bash:", "run:", "$", "echo ", "&&", "||", "|",
        ]
        if any(phrase in intent_lower for phrase in shell_patterns):
            command = self._extract_command(intent)
            logger.debug(f"[code] Extracted shell command: {command}")
            return "run_shell", {"command": command}

        # Also check if backtick content looks like a shell command (not Python)
        import re
        backtick_match = re.search(r'`([^`]+)`', intent)
        if backtick_match:
            backtick_content = backtick_match.group(1)
            # Shell indicators: starts with command, has pipes, redirects, etc.
            if any(ind in backtick_content for ind in ['echo ', 'ls ', 'cd ', 'pwd', 'cat ', 'grep ', 'mkdir ', 'rm ', '&&', '||', '|', '>', '<']):
                logger.debug(f"[code] Detected shell in backticks: {backtick_content}")
                return "run_shell", {"command": backtick_content}

        # File operations
        if any(phrase in intent_lower for phrase in ["read file", "cat ", "show file"]):
            path = self._extract_path(intent)
            return "read_file", {"path": path}

        if any(phrase in intent_lower for phrase in ["write file", "save to", "create file"]):
            path = self._extract_path(intent)
            content = self._extract_content(intent)
            return "write_file", {"path": path, "content": content}

        if any(phrase in intent_lower for phrase in ["list files", "ls ", "list dir"]):
            path = self._extract_path(intent) or "/home/user"
            return "list_files", {"path": path}

        if any(phrase in intent_lower for phrase in ["unzip", "extract", "decompress"]):
            path = self._extract_path(intent)
            return "unzip_file", {"path": path}

        # Default: try to execute as Python if it looks like code
        if "=" in intent or "(" in intent or "import " in intent:
            return "execute_python", {"code": intent}

        # Otherwise, delegate to Claude Code for complex tasks
        return "claude_code", {"prompt": intent}

    def _extract_code(self, text: str) -> str:
        """Extract Python code from text."""
        import re

        # Look for code blocks (highest priority)
        match = re.search(r'```(?:python)?\s*(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Look for inline code in backticks
        match = re.search(r'`(.+?)`', text)
        if match:
            return match.group(1)

        # Look for Python function calls like print(...), func(...)
        # This catches embedded code in natural language
        match = re.search(r'((?:print|input|len|range|sum|max|min|sorted|list|dict|set|open|int|str|float)\s*\([^)]+\))', text)
        if match:
            # Found a function call - try to get more context
            start = match.start()
            # Look for multiple statements or expressions
            code_section = text[start:]
            # Stop at sentence end or "and" if followed by non-code
            end_match = re.search(r'(?:\.\s+[A-Z]|\s+and\s+(?:then|also|maybe))', code_section)
            if end_match:
                code_section = code_section[:end_match.start()]
            return code_section.strip()

        # Look for assignment statements (x = ..., result = ...)
        match = re.search(r'([a-z_][a-z0-9_]*\s*=\s*[^,;]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Extract everything after "run" or "execute" as last resort
        for keyword in ["run python", "execute python", "run", "execute"]:
            if keyword in text.lower():
                idx = text.lower().find(keyword) + len(keyword)
                remaining = text[idx:].strip()
                # Skip common filler words
                remaining = re.sub(r'^(this|the|a|some|following|code)[\s:]+', '', remaining, flags=re.IGNORECASE)
                if remaining:
                    return remaining

        return text

    def _extract_package(self, text: str) -> str:
        """Extract package name from text."""
        import re
        # Look for "install X" pattern
        match = re.search(r'install\s+(\S+)', text.lower())
        if match:
            return match.group(1)
        return text.split()[-1] if text.split() else ""

    def _extract_command(self, text: str) -> str:
        """Extract shell command from text."""
        import re

        # Prioritize backtick-enclosed commands (most reliable)
        match = re.search(r'`([^`]+)`', text)
        if match:
            return match.group(1)

        # Look for command after keywords
        for keyword in ["shell command:", "shell command", "run shell", "run command", "execute command", "shell:", "bash:", "run:", "$"]:
            if keyword in text.lower():
                idx = text.lower().find(keyword) + len(keyword)
                remaining = text[idx:].strip()
                # Strip leading colons or spaces
                remaining = remaining.lstrip(': ')
                if remaining:
                    return remaining

        return text

    def _extract_path(self, text: str) -> str:
        """Extract file path from text."""
        import re
        # Look for paths starting with / or ~
        match = re.search(r'[~/][\w./\-_]+', text)
        if match:
            return match.group(0)

        # Look for quoted paths
        match = re.search(r'["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)

        return ""

    def _extract_content(self, text: str) -> str:
        """Extract file content from text."""
        import re
        # Look for content in quotes or code blocks
        match = re.search(r'```\s*(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        match = re.search(r'content[:\s]+["\'](.+?)["\']', text, re.DOTALL)
        if match:
            return match.group(1)

        return ""

    # ==========================================================================
    # Sandbox Manager
    # ==========================================================================

    def _get_sandbox_manager(self):
        """Get the sandbox manager (lazy initialization)."""
        if self._sandbox_manager is None:
            try:
                from sandbox.manager import get_sandbox_manager
                self._sandbox_manager = get_sandbox_manager()
            except ImportError:
                raise RuntimeError("Sandbox manager not available")
        return self._sandbox_manager

    # ==========================================================================
    # Docker Sandbox Operations
    # ==========================================================================

    async def _execute_python(self, params: dict) -> FacultyResult:
        """Execute Python code in the sandbox."""
        code = params.get("code", "")
        if not code:
            return FacultyResult(success=False, summary="No code provided", error="Missing code")

        logger.info(f"[code] Executing Python: {code[:200]}..." if len(code) > 200 else f"[code] Executing Python: {code}")
        user_id = params.get("user_id", "default")

        try:
            manager = self._get_sandbox_manager()
            result = await manager.execute_code(user_id, code, "Python execution")

            if result.success:
                output = result.output or "(no output)"
                return FacultyResult(
                    success=True,
                    summary=f"Code executed successfully:\n```\n{output[:1000]}\n```",
                    data={"output": output},
                )
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Execution error: {result.error}",
                    error=result.error,
                    data={"output": result.output},
                )
        except RuntimeError as e:
            return FacultyResult(
                success=False,
                summary="Docker sandbox not available",
                error=str(e),
            )

    async def _install_package(self, params: dict) -> FacultyResult:
        """Install a pip package in the sandbox."""
        package = params.get("package", "")
        if not package:
            return FacultyResult(success=False, summary="No package specified", error="Missing package")

        user_id = params.get("user_id", "default")

        try:
            manager = self._get_sandbox_manager()
            result = await manager.install_package(user_id, package)

            if result.success:
                return FacultyResult(
                    success=True,
                    summary=f"Installed {package} successfully",
                    data={"package": package, "output": result.output},
                )
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Failed to install {package}: {result.error}",
                    error=result.error,
                )
        except RuntimeError as e:
            return FacultyResult(success=False, summary="Docker sandbox not available", error=str(e))

    async def _run_shell(self, params: dict) -> FacultyResult:
        """Run a shell command in the sandbox."""
        command = params.get("command", "")
        if not command:
            return FacultyResult(success=False, summary="No command provided", error="Missing command")

        user_id = params.get("user_id", "default")

        try:
            manager = self._get_sandbox_manager()
            result = await manager.run_shell(user_id, command)

            if result.success:
                output = result.output or "(no output)"
                return FacultyResult(
                    success=True,
                    summary=f"Command executed:\n```\n{output[:1000]}\n```",
                    data={"output": output},
                )
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Command failed: {result.error}",
                    error=result.error,
                    data={"output": result.output},
                )
        except RuntimeError as e:
            return FacultyResult(success=False, summary="Docker sandbox not available", error=str(e))

    async def _read_file(self, params: dict) -> FacultyResult:
        """Read a file from the sandbox."""
        path = params.get("path", "")
        if not path:
            return FacultyResult(success=False, summary="No path provided", error="Missing path")

        user_id = params.get("user_id", "default")

        try:
            manager = self._get_sandbox_manager()
            result = await manager.read_file(user_id, path)

            if result.success:
                content = result.output or "(empty file)"
                return FacultyResult(
                    success=True,
                    summary=f"File {path}:\n```\n{content[:2000]}\n```",
                    data={"path": path, "content": content},
                )
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Failed to read {path}: {result.error}",
                    error=result.error,
                )
        except RuntimeError as e:
            return FacultyResult(success=False, summary="Docker sandbox not available", error=str(e))

    async def _write_file(self, params: dict) -> FacultyResult:
        """Write content to a file in the sandbox."""
        path = params.get("path", "")
        content = params.get("content", "")

        if not path:
            return FacultyResult(success=False, summary="No path provided", error="Missing path")

        user_id = params.get("user_id", "default")

        try:
            manager = self._get_sandbox_manager()
            result = await manager.write_file(user_id, path, content)

            if result.success:
                return FacultyResult(
                    success=True,
                    summary=f"Wrote {len(content)} bytes to {path}",
                    data={"path": path, "size": len(content)},
                )
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Failed to write {path}: {result.error}",
                    error=result.error,
                )
        except RuntimeError as e:
            return FacultyResult(success=False, summary="Docker sandbox not available", error=str(e))

    async def _list_files(self, params: dict) -> FacultyResult:
        """List files in a directory in the sandbox."""
        path = params.get("path", "/home/user")
        user_id = params.get("user_id", "default")

        try:
            manager = self._get_sandbox_manager()
            result = await manager.list_files(user_id, path)

            if result.success:
                output = result.output or "(empty directory)"
                return FacultyResult(
                    success=True,
                    summary=f"Files in {path}:\n{output}",
                    data={"path": path, "listing": output},
                )
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Failed to list {path}: {result.error}",
                    error=result.error,
                )
        except RuntimeError as e:
            return FacultyResult(success=False, summary="Docker sandbox not available", error=str(e))

    async def _unzip_file(self, params: dict) -> FacultyResult:
        """Extract an archive in the sandbox."""
        path = params.get("path", "")
        destination = params.get("destination")

        if not path:
            return FacultyResult(success=False, summary="No archive path provided", error="Missing path")

        user_id = params.get("user_id", "default")

        try:
            manager = self._get_sandbox_manager()
            result = await manager.unzip_file(user_id, path, destination)

            if result.success:
                return FacultyResult(
                    success=True,
                    summary=f"Extracted {path}",
                    data={"path": path, "output": result.output},
                )
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Failed to extract {path}: {result.error}",
                    error=result.error,
                )
        except RuntimeError as e:
            return FacultyResult(success=False, summary="Docker sandbox not available", error=str(e))

    # ==========================================================================
    # Claude Code Operations
    # ==========================================================================

    def _find_claude_cli(self) -> Optional[str]:
        """Find the Claude Code CLI executable."""
        claude_path = shutil.which("claude")
        if claude_path:
            return claude_path

        home = Path.home()
        common_paths = [
            home / ".claude" / "bin" / "claude",
            home / ".local" / "bin" / "claude",
            Path("/usr/local/bin/claude"),
        ]
        for path in common_paths:
            if path.exists() and path.is_file():
                return str(path)

        return None

    async def _check_claude_auth(self) -> dict:
        """Check Claude Code authentication status."""
        if self._claude_auth_status is not None:
            return self._claude_auth_status

        result = {
            "cli_installed": False,
            "cli_path": None,
            "authenticated": False,
            "auth_method": None,
            "error": None,
        }

        # Check for API key first
        if ANTHROPIC_API_KEY:
            result["authenticated"] = True
            result["auth_method"] = "api_key"
            cli_path = self._find_claude_cli()
            result["cli_installed"] = cli_path is not None
            result["cli_path"] = cli_path
            self._claude_auth_status = result
            return result

        # Check for CLI
        cli_path = self._find_claude_cli()
        if not cli_path:
            result["error"] = "Claude CLI not found"
            self._claude_auth_status = result
            return result

        result["cli_installed"] = True
        result["cli_path"] = cli_path

        # Check CLI auth status
        try:
            proc = await asyncio.create_subprocess_exec(
                cli_path,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

            if proc.returncode == 0:
                result["authenticated"] = True
                result["auth_method"] = "subscription"
            else:
                result["error"] = f"CLI error: {stderr.decode()[:100]}"
        except asyncio.TimeoutError:
            result["error"] = "CLI timeout"
        except Exception as e:
            result["error"] = f"CLI check failed: {str(e)}"

        self._claude_auth_status = result
        return result

    async def _claude_code(self, params: dict) -> FacultyResult:
        """Execute a coding task using Claude Code agent."""
        try:
            from claude_agent_sdk import ClaudeAgentOptions, query
            from claude_agent_sdk.types import (
                AssistantMessage,
                ResultMessage,
                TextBlock,
                ToolResultBlock,
                ToolUseBlock,
            )
        except ImportError:
            return FacultyResult(
                success=False,
                summary="claude-agent-sdk not installed",
                error="Run: pip install claude-agent-sdk",
            )

        prompt = params.get("prompt", "").strip()
        if not prompt:
            return FacultyResult(success=False, summary="No prompt provided", error="Missing prompt")

        # Get working directory
        user_id = params.get("user_id", "default")
        working_dir = params.get("working_dir") or self._user_workdirs.get(user_id) or DEFAULT_WORKDIR

        if not working_dir:
            return FacultyResult(
                success=False,
                summary="No working directory configured",
                error="Set CLAUDE_CODE_WORKDIR or use set_workdir action",
            )

        workdir_path = Path(working_dir).resolve()
        if not workdir_path.exists():
            return FacultyResult(
                success=False,
                summary=f"Working directory does not exist: {workdir_path}",
                error="Directory not found",
            )

        # Store for future calls
        self._user_workdirs[user_id] = str(workdir_path)

        max_turns = params.get("max_turns", MAX_TURNS)

        options = ClaudeAgentOptions(
            cwd=str(workdir_path),
            max_turns=max_turns,
            permission_mode="acceptEdits",
        )

        results: list[str] = []
        tool_calls: list[str] = []

        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            results.append(block.text)
                        elif isinstance(block, ToolUseBlock):
                            tool_calls.append(f"[{block.name}]")
                elif isinstance(message, ResultMessage):
                    if hasattr(message, "content"):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                results.append(block.text)
                            elif isinstance(block, ToolResultBlock):
                                if block.is_error:
                                    results.append(f"[Error: {block.content[:200]}...]")

        except Exception as e:
            return FacultyResult(
                success=False,
                summary=f"Claude Code error: {str(e)}",
                error=str(e),
            )

        # Format output
        output_parts = []
        if tool_calls:
            output_parts.append(f"**Tools used:** {', '.join(tool_calls[:10])}")

        if results:
            combined = "\n".join(results)
            if len(combined) > 3000:
                combined = combined[:3000] + "\n\n[Output truncated]"
            output_parts.append(combined)
        else:
            output_parts.append("Task completed (no output text).")

        return FacultyResult(
            success=True,
            summary="\n".join(output_parts),
            data={"results": results, "tools_used": tool_calls},
        )

    async def _claude_code_status(self) -> FacultyResult:
        """Check Claude Code availability and authentication status."""
        status = await self._check_claude_auth()

        lines = ["**Claude Code Status**\n"]

        if status["cli_installed"]:
            lines.append(f"CLI installed: Yes ({status['cli_path']})")
        else:
            lines.append("CLI installed: No")

        if status["authenticated"]:
            method = status["auth_method"]
            if method == "api_key":
                lines.append("Authentication: API key (ANTHROPIC_API_KEY)")
            else:
                lines.append("Authentication: Max/Pro subscription")
            lines.append("Status: Ready")
        else:
            lines.append("Authentication: Not configured")
            if status["error"]:
                lines.append(f"Error: {status['error']}")

        if DEFAULT_WORKDIR:
            lines.append(f"\nDefault workdir: {DEFAULT_WORKDIR}")

        return FacultyResult(
            success=True,
            summary="\n".join(lines),
            data=status,
        )

    def _set_workdir(self, params: dict) -> FacultyResult:
        """Set the working directory for Claude Code."""
        path = params.get("path", "")
        user_id = params.get("user_id", "default")

        if not path:
            return FacultyResult(success=False, summary="No path provided", error="Missing path")

        workdir_path = Path(path).resolve()
        if not workdir_path.exists():
            return FacultyResult(
                success=False,
                summary=f"Directory does not exist: {workdir_path}",
                error="Directory not found",
            )

        self._user_workdirs[user_id] = str(workdir_path)

        return FacultyResult(
            success=True,
            summary=f"Working directory set to: {workdir_path}",
            data={"path": str(workdir_path)},
        )

    def _get_workdir(self, params: dict) -> FacultyResult:
        """Get the current working directory."""
        user_id = params.get("user_id", "default")
        workdir = self._user_workdirs.get(user_id) or DEFAULT_WORKDIR

        if workdir:
            return FacultyResult(
                success=True,
                summary=f"Current working directory: {workdir}",
                data={"path": workdir},
            )

        return FacultyResult(
            success=True,
            summary="No working directory configured",
            data={"path": None},
        )
