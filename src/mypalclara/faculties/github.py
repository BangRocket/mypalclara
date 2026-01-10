"""
GitHub Faculty - Clara's GitHub capability.

This faculty translates Clara's high-level intents into GitHub API calls.
It uses pattern matching for common operations and can plan more complex
multi-step workflows when needed.
"""

import logging
import os
import re
from typing import Optional

import httpx

from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult

logger = logging.getLogger(__name__)

# GitHub API configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_URL = "https://api.github.com"


def _get_headers() -> dict[str, str]:
    """Get headers for GitHub API requests."""
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def _github_request(
    method: str,
    endpoint: str,
    params: dict | None = None,
    json_data: dict | None = None,
) -> dict | list | str:
    """Make a GitHub API request."""
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN not configured")

    url = f"{GITHUB_API_URL}{endpoint}"

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            url,
            headers=_get_headers(),
            params=params,
            json=json_data,
            timeout=30.0,
        )
        response.raise_for_status()

        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return response.text


class GitHubFaculty(Faculty):
    """Clara's GitHub capability."""

    name = "github"
    description = "Interact with GitHub repositories, issues, PRs, and code"
    available_tools = [
        "list_repos",
        "get_repo",
        "list_issues",
        "get_issue",
        "create_issue",
        "list_pulls",
        "get_pull",
        "search_code",
        "get_file_contents",
    ]

    def __init__(self):
        self._configured = bool(GITHUB_TOKEN)

    async def execute(
        self,
        intent: str,
        constraints: Optional[list[str]] = None,
    ) -> FacultyResult:
        """
        Translate Clara's intent into GitHub API calls.
        """
        if not self._configured:
            return FacultyResult(
                success=False,
                summary="GitHub is not configured. Please set GITHUB_TOKEN.",
                error="GITHUB_TOKEN not set",
            )

        logger.info(f"[faculty:github] Planning for intent: {intent}")

        try:
            # Determine what API calls are needed
            plan = self._plan_execution(intent, constraints)
            logger.info(f"[faculty:github] Plan: {plan}")

            # Execute the plan
            results = []
            for step in plan["steps"]:
                logger.info(f"[faculty:github] Executing: {step['action']}")
                result = await self._execute_step(step)
                results.append(result)

            # Synthesize results
            summary = self._summarize_results(results, intent)

            return FacultyResult(
                success=True,
                data={"results": results},
                summary=summary,
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"GitHub API error: {e.response.status_code}"
            logger.error(f"[faculty:github] {error_msg}")
            return FacultyResult(
                success=False,
                error=error_msg,
                summary=f"GitHub returned an error: {e.response.status_code}",
            )
        except Exception as e:
            logger.exception(f"[faculty:github] Error: {e}")
            return FacultyResult(
                success=False,
                error=str(e),
                summary=f"GitHub operation failed: {str(e)}",
            )

    def _plan_execution(self, intent: str, constraints: Optional[list[str]]) -> dict:
        """
        Figure out what API calls to make based on intent.

        Uses pattern matching for common operations.
        """
        intent_lower = intent.lower()

        # List issues
        if "list" in intent_lower and "issue" in intent_lower:
            repo = self._extract_repo(intent)
            state = "open" if "open" in intent_lower else ("closed" if "closed" in intent_lower else "all")
            return {
                "steps": [
                    {"action": "list_issues", "repo": repo, "state": state},
                ]
            }

        # Get specific issue
        if ("get" in intent_lower or "show" in intent_lower) and "issue" in intent_lower:
            repo = self._extract_repo(intent)
            issue_number = self._extract_number(intent)
            if issue_number:
                return {
                    "steps": [
                        {"action": "get_issue", "repo": repo, "number": issue_number},
                    ]
                }

        # List PRs
        if "list" in intent_lower and ("pr" in intent_lower or "pull" in intent_lower):
            repo = self._extract_repo(intent)
            state = "open" if "open" in intent_lower else ("closed" if "closed" in intent_lower else "all")
            return {
                "steps": [
                    {"action": "list_pulls", "repo": repo, "state": state},
                ]
            }

        # Get specific PR
        if ("get" in intent_lower or "show" in intent_lower) and ("pr" in intent_lower or "pull" in intent_lower):
            repo = self._extract_repo(intent)
            pr_number = self._extract_number(intent)
            if pr_number:
                return {
                    "steps": [
                        {"action": "get_pull", "repo": repo, "number": pr_number},
                    ]
                }

        # List repos
        if "list" in intent_lower and "repo" in intent_lower:
            return {
                "steps": [
                    {"action": "list_repos"},
                ]
            }

        # Get repo info
        if ("get" in intent_lower or "show" in intent_lower or "info" in intent_lower) and "repo" in intent_lower:
            repo = self._extract_repo(intent)
            return {
                "steps": [
                    {"action": "get_repo", "repo": repo},
                ]
            }

        # Search code
        if "search" in intent_lower and "code" in intent_lower:
            query = self._extract_search_query(intent)
            repo = self._extract_repo(intent)
            return {
                "steps": [
                    {"action": "search_code", "query": query, "repo": repo},
                ]
            }

        # Get file contents
        if ("get" in intent_lower or "read" in intent_lower or "show" in intent_lower) and "file" in intent_lower:
            repo = self._extract_repo(intent)
            path = self._extract_path(intent)
            return {
                "steps": [
                    {"action": "get_file", "repo": repo, "path": path},
                ]
            }

        # Default: try to infer from intent
        logger.warning("[faculty:github] No pattern matched, returning help")
        return {
            "steps": [
                {"action": "help", "message": f"I'm not sure how to handle: {intent}"},
            ]
        }

    async def _execute_step(self, step: dict) -> dict:
        """Execute a single step of the plan."""
        action = step["action"]

        if action == "list_issues":
            repo = step.get("repo", "")
            state = step.get("state", "open")
            if "/" not in repo:
                return {"action": action, "error": "Invalid repo format (expected owner/repo)"}
            data = await _github_request("GET", f"/repos/{repo}/issues", params={"state": state, "per_page": 10})
            return {"action": action, "data": data, "count": len(data) if isinstance(data, list) else 0}

        elif action == "get_issue":
            repo = step.get("repo", "")
            number = step.get("number")
            data = await _github_request("GET", f"/repos/{repo}/issues/{number}")
            return {"action": action, "data": data}

        elif action == "list_pulls":
            repo = step.get("repo", "")
            state = step.get("state", "open")
            if "/" not in repo:
                return {"action": action, "error": "Invalid repo format (expected owner/repo)"}
            data = await _github_request("GET", f"/repos/{repo}/pulls", params={"state": state, "per_page": 10})
            return {"action": action, "data": data, "count": len(data) if isinstance(data, list) else 0}

        elif action == "get_pull":
            repo = step.get("repo", "")
            number = step.get("number")
            data = await _github_request("GET", f"/repos/{repo}/pulls/{number}")
            return {"action": action, "data": data}

        elif action == "list_repos":
            data = await _github_request("GET", "/user/repos", params={"per_page": 20, "sort": "updated"})
            return {"action": action, "data": data, "count": len(data) if isinstance(data, list) else 0}

        elif action == "get_repo":
            repo = step.get("repo", "")
            if "/" not in repo:
                return {"action": action, "error": "Invalid repo format (expected owner/repo)"}
            data = await _github_request("GET", f"/repos/{repo}")
            return {"action": action, "data": data}

        elif action == "search_code":
            query = step.get("query", "")
            repo = step.get("repo")
            search_query = f"{query} repo:{repo}" if repo else query
            data = await _github_request("GET", "/search/code", params={"q": search_query, "per_page": 10})
            return {"action": action, "data": data}

        elif action == "get_file":
            repo = step.get("repo", "")
            path = step.get("path", "")
            data = await _github_request("GET", f"/repos/{repo}/contents/{path}")
            return {"action": action, "data": data}

        elif action == "help":
            return {"action": action, "message": step.get("message", "Unknown action")}

        else:
            return {"action": action, "error": f"Unknown action: {action}"}

    def _extract_repo(self, intent: str) -> str:
        """Extract repository name from intent."""
        # Look for owner/repo pattern
        match = re.search(r"(\w[\w-]*/[\w.-]+)", intent)
        if match:
            return match.group(1)
        # Default to mypalclara repo
        return "BangRocket/mypalclara"

    def _extract_number(self, intent: str) -> int | None:
        """Extract issue/PR number from intent."""
        # Look for #123 or just 123
        match = re.search(r"#?(\d+)", intent)
        if match:
            return int(match.group(1))
        return None

    def _extract_search_query(self, intent: str) -> str:
        """Extract search query from intent."""
        # Look for quoted strings first
        match = re.search(r'"([^"]+)"', intent)
        if match:
            return match.group(1)
        # Otherwise take everything after "search for" or "find"
        match = re.search(r"(?:search for|find|search)\s+(.+)", intent, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return intent

    def _extract_path(self, intent: str) -> str:
        """Extract file path from intent."""
        # Look for path-like strings
        match = re.search(r"([\w/.-]+\.\w+)", intent)
        if match:
            return match.group(1)
        return ""

    def _summarize_results(self, results: list[dict], intent: str) -> str:
        """Create human-readable summary for Clara."""
        if not results:
            return "No results found."

        summaries = []
        for r in results:
            action = r.get("action", "unknown")

            if "error" in r:
                summaries.append(f"{action}: Error - {r['error']}")
            elif action == "help":
                summaries.append(r.get("message", ""))
            elif action in ("list_issues", "list_pulls", "list_repos"):
                count = r.get("count", 0)
                data = r.get("data", [])
                if isinstance(data, list) and data:
                    items = []
                    for item in data[:5]:  # Show top 5
                        if "title" in item:
                            items.append(f"- #{item.get('number', '?')}: {item['title']}")
                        elif "full_name" in item:
                            items.append(f"- {item['full_name']}")
                    summaries.append(f"Found {count} items:\n" + "\n".join(items))
                else:
                    summaries.append(f"Found {count} items")
            elif action in ("get_issue", "get_pull"):
                data = r.get("data", {})
                title = data.get("title", "Unknown")
                state = data.get("state", "unknown")
                body = data.get("body", "")[:200]
                summaries.append(f"**{title}** ({state})\n{body}...")
            elif action == "get_repo":
                data = r.get("data", {})
                name = data.get("full_name", "Unknown")
                desc = data.get("description", "No description")
                stars = data.get("stargazers_count", 0)
                summaries.append(f"**{name}** - {desc} ({stars} stars)")
            else:
                summaries.append(f"{action}: completed")

        return "\n\n".join(summaries)
