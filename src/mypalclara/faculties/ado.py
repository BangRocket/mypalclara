"""
Azure DevOps Faculty - Azure DevOps API integration.

Provides comprehensive Azure DevOps integration using the official
Microsoft Azure DevOps Python SDK.

https://github.com/microsoft/azure-devops-python-api
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Optional

from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult

logger = logging.getLogger(__name__)

# Configuration
AZURE_DEVOPS_ORG = os.getenv("AZURE_DEVOPS_ORG", "")
AZURE_DEVOPS_PAT = os.getenv("AZURE_DEVOPS_PAT", "")

# Thread pool for running sync SDK calls
_executor = ThreadPoolExecutor(max_workers=4)


def is_configured() -> bool:
    """Check if Azure DevOps is configured."""
    return bool(AZURE_DEVOPS_ORG and AZURE_DEVOPS_PAT)


def _get_org_url() -> str:
    """Get the Azure DevOps organization URL."""
    org = AZURE_DEVOPS_ORG
    if org.startswith("http"):
        return org.rstrip("/")
    return f"https://dev.azure.com/{org}"


class AdoFaculty(Faculty):
    """Azure DevOps faculty using the official Microsoft SDK."""

    name = "ado"
    description = "Azure DevOps projects, repos, work items, pipelines, and wiki"

    available_actions = [
        # Projects & Teams
        "list_projects",
        "list_teams",
        # Repositories
        "list_repos",
        "get_repo",
        "list_branches",
        "create_branch",
        "list_commits",
        "get_file",
        # Pull Requests
        "list_prs",
        "get_pr",
        "create_pr",
        "list_pr_threads",
        "add_pr_comment",
        # Work Items
        "get_work_item",
        "create_work_item",
        "update_work_item",
        "search_work_items",
        "my_work_items",
        "list_work_item_types",
        # Pipelines
        "list_pipelines",
        "list_builds",
        "run_pipeline",
        "get_build_logs",
        # Wiki
        "list_wikis",
        "get_wiki_page",
        "create_wiki_page",
        # Search
        "search_code",
        # Iterations
        "list_iterations",
    ]

    def __init__(self):
        self._connection = None
        self._last_project: Optional[str] = None

    def _get_connection(self):
        """Get or create the Azure DevOps connection."""
        if self._connection is None:
            from azure.devops.connection import Connection
            from msrest.authentication import BasicAuthentication

            credentials = BasicAuthentication("", AZURE_DEVOPS_PAT)
            self._connection = Connection(base_url=_get_org_url(), creds=credentials)

        return self._connection

    def _get_core_client(self):
        """Get the Core client for projects and teams."""
        return self._get_connection().clients.get_core_client()

    def _get_git_client(self):
        """Get the Git client for repos and PRs."""
        return self._get_connection().clients.get_git_client()

    def _get_work_item_client(self):
        """Get the Work Item Tracking client."""
        return self._get_connection().clients.get_work_item_tracking_client()

    def _get_build_client(self):
        """Get the Build client for pipelines."""
        return self._get_connection().clients.get_build_client()

    def _get_wiki_client(self):
        """Get the Wiki client."""
        return self._get_connection().clients.get_wiki_client()

    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in the thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, partial(func, *args, **kwargs))

    async def execute(
        self,
        intent: str,
        constraints: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> FacultyResult:
        """Execute Azure DevOps intent."""
        logger.info(f"[ado] Intent: {intent}")

        if not is_configured():
            return FacultyResult(
                success=False,
                summary="Azure DevOps not configured. Set AZURE_DEVOPS_ORG and AZURE_DEVOPS_PAT.",
                error="Not configured",
            )

        try:
            action, params = self._parse_intent(intent)
            logger.info(f"[ado] Action: {action}")

            # Projects & Teams
            if action == "list_projects":
                result = await self._list_projects(params)
            elif action == "list_teams":
                result = await self._list_teams(params)
            # Repositories
            elif action == "list_repos":
                result = await self._list_repos(params)
            elif action == "get_repo":
                result = await self._get_repo(params)
            elif action == "list_branches":
                result = await self._list_branches(params)
            elif action == "create_branch":
                result = await self._create_branch(params)
            elif action == "list_commits":
                result = await self._list_commits(params)
            elif action == "get_file":
                result = await self._get_file(params)
            # Pull Requests
            elif action == "list_prs":
                result = await self._list_prs(params)
            elif action == "get_pr":
                result = await self._get_pr(params)
            elif action == "create_pr":
                result = await self._create_pr(params)
            elif action == "list_pr_threads":
                result = await self._list_pr_threads(params)
            elif action == "add_pr_comment":
                result = await self._add_pr_comment(params)
            # Work Items
            elif action == "get_work_item":
                result = await self._get_work_item(params)
            elif action == "create_work_item":
                result = await self._create_work_item(params)
            elif action == "update_work_item":
                result = await self._update_work_item(params)
            elif action == "search_work_items":
                result = await self._search_work_items(params)
            elif action == "my_work_items":
                result = await self._my_work_items(params)
            elif action == "list_work_item_types":
                result = await self._list_work_item_types(params)
            # Pipelines
            elif action == "list_pipelines":
                result = await self._list_pipelines(params)
            elif action == "list_builds":
                result = await self._list_builds(params)
            elif action == "run_pipeline":
                result = await self._run_pipeline(params)
            elif action == "get_build_logs":
                result = await self._get_build_logs(params)
            # Wiki
            elif action == "list_wikis":
                result = await self._list_wikis(params)
            elif action == "get_wiki_page":
                result = await self._get_wiki_page(params)
            elif action == "create_wiki_page":
                result = await self._create_wiki_page(params)
            # Search
            elif action == "search_code":
                result = await self._search_code(params)
            # Iterations
            elif action == "list_iterations":
                result = await self._list_iterations(params)
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Unknown ADO action: {action}",
                    error=f"Action '{action}' not recognized",
                )

            return result

        except Exception as e:
            logger.exception(f"[ado] Error: {e}")
            return FacultyResult(
                success=False,
                summary=f"Azure DevOps error: {str(e)}",
                error=str(e),
            )

    def _parse_intent(self, intent: str) -> tuple[str, dict]:
        """Parse natural language intent into action and parameters."""
        intent_lower = intent.lower()

        # Extract project from intent
        project = self._extract_project(intent)
        if project:
            self._last_project = project
        elif self._last_project:
            project = self._last_project

        # Projects & Teams
        if "list project" in intent_lower or "projects" in intent_lower:
            return "list_projects", {}
        if "list team" in intent_lower or "teams in" in intent_lower:
            return "list_teams", {"project": project}

        # Repositories
        if "list repo" in intent_lower or "repositories" in intent_lower:
            return "list_repos", {"project": project}
        if "get repo" in intent_lower or "repo detail" in intent_lower:
            repo = self._extract_repo(intent)
            return "get_repo", {"project": project, "repository": repo}
        if "list branch" in intent_lower or "branches" in intent_lower:
            repo = self._extract_repo(intent)
            return "list_branches", {"project": project, "repository": repo}
        if "create branch" in intent_lower:
            repo = self._extract_repo(intent)
            branch_name = self._extract_branch_name(intent)
            return "create_branch", {"project": project, "repository": repo, "branch_name": branch_name}
        if "list commit" in intent_lower or "commits" in intent_lower:
            repo = self._extract_repo(intent)
            return "list_commits", {"project": project, "repository": repo}
        if "get file" in intent_lower or "file content" in intent_lower:
            repo = self._extract_repo(intent)
            path = self._extract_path(intent)
            return "get_file", {"project": project, "repository": repo, "path": path}

        # Pull Requests
        if "list pr" in intent_lower or "pull request" in intent_lower and "list" in intent_lower:
            repo = self._extract_repo(intent)
            return "list_prs", {"project": project, "repository": repo}
        if "get pr" in intent_lower or "pr detail" in intent_lower or "pr #" in intent_lower:
            repo = self._extract_repo(intent)
            pr_id = self._extract_id(intent)
            return "get_pr", {"project": project, "repository": repo, "pr_id": pr_id}
        if "create pr" in intent_lower or "new pull request" in intent_lower:
            repo = self._extract_repo(intent)
            return "create_pr", {"project": project, "repository": repo, **self._parse_pr_params(intent)}
        if "pr thread" in intent_lower or "pr comment" in intent_lower and "list" in intent_lower:
            repo = self._extract_repo(intent)
            pr_id = self._extract_id(intent)
            return "list_pr_threads", {"project": project, "repository": repo, "pr_id": pr_id}
        if "add comment" in intent_lower and "pr" in intent_lower:
            repo = self._extract_repo(intent)
            pr_id = self._extract_id(intent)
            content = self._extract_content(intent)
            return "add_pr_comment", {"project": project, "repository": repo, "pr_id": pr_id, "content": content}

        # Work Items
        if "get work item" in intent_lower or "work item #" in intent_lower:
            work_item_id = self._extract_id(intent)
            return "get_work_item", {"work_item_id": work_item_id}
        if "create work item" in intent_lower or "new work item" in intent_lower:
            return "create_work_item", {"project": project, **self._parse_work_item_params(intent)}
        if "update work item" in intent_lower:
            work_item_id = self._extract_id(intent)
            return "update_work_item", {"work_item_id": work_item_id, **self._parse_work_item_params(intent)}
        if "search work item" in intent_lower or "find work item" in intent_lower:
            query = self._extract_query(intent)
            return "search_work_items", {"project": project, "query": query}
        if "my work item" in intent_lower or "assigned to me" in intent_lower:
            return "my_work_items", {"project": project}
        if "work item type" in intent_lower:
            return "list_work_item_types", {"project": project}

        # Pipelines
        if "list pipeline" in intent_lower or "pipelines" in intent_lower:
            return "list_pipelines", {"project": project}
        if "list build" in intent_lower or "builds" in intent_lower:
            return "list_builds", {"project": project}
        if "run pipeline" in intent_lower or "trigger pipeline" in intent_lower:
            pipeline_id = self._extract_id(intent)
            return "run_pipeline", {"project": project, "pipeline_id": pipeline_id}
        if "build log" in intent_lower:
            build_id = self._extract_id(intent)
            return "get_build_logs", {"project": project, "build_id": build_id}

        # Wiki
        if "list wiki" in intent_lower or "wikis" in intent_lower:
            return "list_wikis", {"project": project}
        if "wiki page" in intent_lower and "get" in intent_lower:
            page = self._extract_wiki_page(intent)
            return "get_wiki_page", {"project": project, "page": page}
        if "wiki page" in intent_lower and ("create" in intent_lower or "update" in intent_lower):
            page = self._extract_wiki_page(intent)
            content = self._extract_content(intent)
            return "create_wiki_page", {"project": project, "page": page, "content": content}

        # Search
        if "search code" in intent_lower:
            query = self._extract_query(intent)
            return "search_code", {"project": project, "query": query}

        # Iterations
        if "iteration" in intent_lower or "sprint" in intent_lower:
            return "list_iterations", {"project": project}

        # Default
        return "list_projects", {}

    def _extract_project(self, text: str) -> str:
        """Extract project name from text."""
        import re
        match = re.search(r'project[:\s]+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r'in\s+["\']?([A-Za-z0-9_-]+)["\']?', text)
        if match:
            return match.group(1)
        return ""

    def _extract_repo(self, text: str) -> str:
        """Extract repository name from text."""
        import re
        match = re.search(r'repo(?:sitory)?[:\s]+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_id(self, text: str) -> str:
        """Extract ID from text."""
        import re
        match = re.search(r'#(\d+)', text)
        if match:
            return match.group(1)
        match = re.search(r'\b(\d+)\b', text)
        return match.group(1) if match else ""

    def _extract_branch_name(self, text: str) -> str:
        """Extract branch name from text."""
        import re
        match = re.search(r'branch[:\s]+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_path(self, text: str) -> str:
        """Extract file path from text."""
        import re
        match = re.search(r'path[:\s]+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r'/[\w./\-_]+', text)
        return match.group(0) if match else "/"

    def _extract_content(self, text: str) -> str:
        """Extract content from text."""
        import re
        match = re.search(r'```\s*(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r'content[:\s]+["\'](.+?)["\']', text, re.DOTALL)
        return match.group(1) if match else ""

    def _extract_query(self, text: str) -> str:
        """Extract search query from text."""
        import re
        match = re.search(r'(?:search|find|query)[:\s]+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_wiki_page(self, text: str) -> str:
        """Extract wiki page name from text."""
        import re
        match = re.search(r'page[:\s]+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _parse_pr_params(self, text: str) -> dict:
        """Parse pull request parameters from text."""
        import re
        params: dict[str, Any] = {}
        match = re.search(r'title[:\s]+["\']([^"\']+)["\']', text, re.IGNORECASE)
        if match:
            params["title"] = match.group(1)
        match = re.search(r'source[:\s]+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if match:
            params["source_branch"] = match.group(1)
        match = re.search(r'target[:\s]+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if match:
            params["target_branch"] = match.group(1)
        return params

    def _parse_work_item_params(self, text: str) -> dict:
        """Parse work item parameters from text."""
        import re
        params: dict[str, Any] = {}
        match = re.search(r'title[:\s]+["\']([^"\']+)["\']', text, re.IGNORECASE)
        if match:
            params["title"] = match.group(1)
        match = re.search(r'type[:\s]+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if match:
            params["work_item_type"] = match.group(1)
        match = re.search(r'description[:\s]+["\']([^"\']+)["\']', text, re.IGNORECASE)
        if match:
            params["description"] = match.group(1)
        return params

    # ==========================================================================
    # Projects & Teams
    # ==========================================================================

    async def _list_projects(self, params: dict) -> FacultyResult:
        """List all projects in the organization."""
        def _fetch():
            client = self._get_core_client()
            return client.get_projects()

        response = await self._run_sync(_fetch)
        projects = [
            {"name": p.name, "state": p.state, "visibility": getattr(p, "visibility", None)}
            for p in response
        ]

        formatted = "\n".join([f"- **{p['name']}** ({p.get('state', 'N/A')})" for p in projects[:20]])

        return FacultyResult(
            success=True,
            summary=f"**Projects ({len(projects)}):**\n{formatted}",
            data={"projects": projects},
        )

    async def _list_teams(self, params: dict) -> FacultyResult:
        """List teams within a project."""
        project = params.get("project", "")
        if not project:
            return FacultyResult(success=False, summary="Project required", error="Missing project")

        def _fetch():
            client = self._get_core_client()
            return client.get_teams(project)

        teams = await self._run_sync(_fetch)
        team_list = [{"name": t.name, "id": t.id} for t in teams]
        formatted = "\n".join([f"- {t['name']}" for t in team_list])

        return FacultyResult(
            success=True,
            summary=f"**Teams in {project}:**\n{formatted}",
            data={"teams": team_list},
        )

    # ==========================================================================
    # Repositories
    # ==========================================================================

    async def _list_repos(self, params: dict) -> FacultyResult:
        """List all repositories in a project."""
        project = params.get("project", "")
        if not project:
            return FacultyResult(success=False, summary="Project required", error="Missing project")

        def _fetch():
            client = self._get_git_client()
            return client.get_repositories(project=project)

        repos = await self._run_sync(_fetch)
        repo_list = [
            {
                "name": r.name,
                "id": r.id,
                "defaultBranch": (r.default_branch or "").replace("refs/heads/", ""),
                "webUrl": r.web_url,
            }
            for r in repos
        ]

        formatted = "\n".join([f"- **{r['name']}** (default: {r.get('defaultBranch', 'N/A')})" for r in repo_list])

        return FacultyResult(
            success=True,
            summary=f"**Repositories in {project}:**\n{formatted}",
            data={"repos": repo_list},
        )

    async def _get_repo(self, params: dict) -> FacultyResult:
        """Get repository details."""
        project = params.get("project", "")
        repo = params.get("repository", "")
        if not project or not repo:
            return FacultyResult(success=False, summary="Project and repository required", error="Missing params")

        def _fetch():
            client = self._get_git_client()
            return client.get_repository(repository_id=repo, project=project)

        result = await self._run_sync(_fetch)
        default_branch = (result.default_branch or "").replace("refs/heads/", "")

        return FacultyResult(
            success=True,
            summary=f"**{result.name}**\nDefault branch: {default_branch}\nURL: {result.web_url}",
            data={
                "name": result.name,
                "id": result.id,
                "defaultBranch": default_branch,
                "webUrl": result.web_url,
            },
        )

    async def _list_branches(self, params: dict) -> FacultyResult:
        """List branches in a repository."""
        project = params.get("project", "")
        repo = params.get("repository", "")
        if not project or not repo:
            return FacultyResult(success=False, summary="Project and repository required", error="Missing params")

        def _fetch():
            client = self._get_git_client()
            return client.get_refs(repository_id=repo, project=project, filter="heads")

        refs = await self._run_sync(_fetch)
        branches = [
            {"name": r.name.replace("refs/heads/", ""), "objectId": r.object_id[:7]}
            for r in refs
        ]

        formatted = "\n".join([f"- {b['name']}" for b in branches[:20]])

        return FacultyResult(
            success=True,
            summary=f"**Branches:**\n{formatted}",
            data={"branches": branches},
        )

    async def _create_branch(self, params: dict) -> FacultyResult:
        """Create a new branch."""
        project = params.get("project", "")
        repo = params.get("repository", "")
        branch_name = params.get("branch_name", "")
        source_branch = params.get("source_branch", "main")

        if not all([project, repo, branch_name]):
            return FacultyResult(success=False, summary="Project, repository, and branch_name required", error="Missing params")

        def _fetch():
            from azure.devops.v7_1.git.models import GitRefUpdate

            client = self._get_git_client()

            # Get source branch ref
            refs = client.get_refs(repository_id=repo, project=project, filter=f"heads/{source_branch}")
            if not refs:
                raise ValueError(f"Source branch '{source_branch}' not found")

            source_sha = refs[0].object_id

            # Create new branch
            ref_update = GitRefUpdate(
                name=f"refs/heads/{branch_name}",
                old_object_id="0000000000000000000000000000000000000000",
                new_object_id=source_sha,
            )
            return client.update_refs(ref_updates=[ref_update], repository_id=repo, project=project)

        await self._run_sync(_fetch)

        return FacultyResult(
            success=True,
            summary=f"Created branch '{branch_name}' from '{source_branch}'",
            data={"branch": branch_name},
        )

    async def _list_commits(self, params: dict) -> FacultyResult:
        """List commits in a repository."""
        project = params.get("project", "")
        repo = params.get("repository", "")
        if not project or not repo:
            return FacultyResult(success=False, summary="Project and repository required", error="Missing params")

        def _fetch():
            from azure.devops.v7_1.git.models import GitQueryCommitsCriteria

            client = self._get_git_client()
            criteria = GitQueryCommitsCriteria(top=params.get("top", 20))
            if params.get("branch"):
                criteria.item_version = {"version": params["branch"]}
            return client.get_commits(repository_id=repo, search_criteria=criteria, project=project)

        commits = await self._run_sync(_fetch)
        commit_list = [
            {
                "id": c.commit_id[:7],
                "message": c.comment.split("\n")[0][:60] if c.comment else "",
                "author": c.author.name if c.author else "Unknown",
            }
            for c in commits
        ]

        formatted = "\n".join([f"- `{c['id']}` {c['message']} ({c['author']})" for c in commit_list[:15]])

        return FacultyResult(
            success=True,
            summary=f"**Recent commits:**\n{formatted}",
            data={"commits": commit_list},
        )

    async def _get_file(self, params: dict) -> FacultyResult:
        """Get file contents from a repository."""
        project = params.get("project", "")
        repo = params.get("repository", "")
        path = params.get("path", "/")

        if not project or not repo:
            return FacultyResult(success=False, summary="Project and repository required", error="Missing params")

        def _fetch():
            client = self._get_git_client()
            version_descriptor = None
            if params.get("branch"):
                from azure.devops.v7_1.git.models import GitVersionDescriptor
                version_descriptor = GitVersionDescriptor(version=params["branch"], version_type="branch")

            return client.get_item(
                repository_id=repo,
                path=path,
                project=project,
                include_content=True,
                version_descriptor=version_descriptor,
            )

        result = await self._run_sync(_fetch)

        if result.is_folder:
            def _list_items():
                client = self._get_git_client()
                return client.get_items(repository_id=repo, project=project, scope_path=path, recursion_level="OneLevel")

            items = await self._run_sync(_list_items)
            item_list = [i.path for i in items]
            return FacultyResult(
                success=True,
                summary=f"**Directory {path}:**\n" + "\n".join([f"- {i}" for i in item_list[:20]]),
                data={"type": "directory", "items": item_list},
            )
        else:
            content = result.content or ""
            return FacultyResult(
                success=True,
                summary=f"**{path}:**\n```\n{content[:2000]}\n```",
                data={"type": "file", "path": path, "content": content},
            )

    # ==========================================================================
    # Pull Requests
    # ==========================================================================

    async def _list_prs(self, params: dict) -> FacultyResult:
        """List pull requests."""
        project = params.get("project", "")
        repo = params.get("repository")

        if not project:
            return FacultyResult(success=False, summary="Project required", error="Missing project")

        def _fetch():
            client = self._get_git_client()
            if repo:
                return client.get_pull_requests(repository_id=repo, project=project, status=params.get("status"))
            else:
                return client.get_pull_requests_by_project(project=project, status=params.get("status"))

        prs = await self._run_sync(_fetch)
        pr_list = [
            {
                "id": pr.pull_request_id,
                "title": pr.title[:50] if pr.title else "",
                "status": pr.status,
                "createdBy": pr.created_by.display_name if pr.created_by else "Unknown",
            }
            for pr in prs
        ]

        formatted = "\n".join([f"- **#{p['id']}** {p['title']} ({p['status']}) by {p['createdBy']}" for p in pr_list[:15]])

        return FacultyResult(
            success=True,
            summary=f"**Pull Requests:**\n{formatted}",
            data={"prs": pr_list},
        )

    async def _get_pr(self, params: dict) -> FacultyResult:
        """Get details of a specific pull request."""
        project = params.get("project", "")
        repo = params.get("repository", "")
        pr_id = params.get("pr_id", "")

        if not all([project, repo, pr_id]):
            return FacultyResult(success=False, summary="Project, repository, and pr_id required", error="Missing params")

        def _fetch():
            client = self._get_git_client()
            return client.get_pull_request(repository_id=repo, pull_request_id=int(pr_id), project=project)

        pr = await self._run_sync(_fetch)
        source = (pr.source_ref_name or "").replace("refs/heads/", "")
        target = (pr.target_ref_name or "").replace("refs/heads/", "")
        creator = pr.created_by.display_name if pr.created_by else "Unknown"

        return FacultyResult(
            success=True,
            summary=f"**PR #{pr.pull_request_id}: {pr.title}**\nStatus: {pr.status}\nSource: {source} → {target}\nCreated by: {creator}",
            data={
                "id": pr.pull_request_id,
                "title": pr.title,
                "status": pr.status,
                "source": source,
                "target": target,
                "createdBy": creator,
            },
        )

    async def _create_pr(self, params: dict) -> FacultyResult:
        """Create a pull request."""
        project = params.get("project", "")
        repo = params.get("repository", "")
        title = params.get("title", "")
        source_branch = params.get("source_branch", "")
        target_branch = params.get("target_branch", "main")

        if not all([project, repo, title, source_branch]):
            return FacultyResult(success=False, summary="Project, repository, title, and source_branch required", error="Missing params")

        def _fetch():
            from azure.devops.v7_1.git.models import GitPullRequest

            client = self._get_git_client()
            pr = GitPullRequest(
                title=title,
                source_ref_name=f"refs/heads/{source_branch}",
                target_ref_name=f"refs/heads/{target_branch}",
            )
            return client.create_pull_request(git_pull_request_to_create=pr, repository_id=repo, project=project)

        result = await self._run_sync(_fetch)

        return FacultyResult(
            success=True,
            summary=f"Created PR #{result.pull_request_id}: {title}",
            data={"id": result.pull_request_id, "title": title},
        )

    async def _list_pr_threads(self, params: dict) -> FacultyResult:
        """List threads/comments on a PR."""
        project = params.get("project", "")
        repo = params.get("repository", "")
        pr_id = params.get("pr_id", "")

        if not all([project, repo, pr_id]):
            return FacultyResult(success=False, summary="Project, repository, and pr_id required", error="Missing params")

        def _fetch():
            client = self._get_git_client()
            return client.get_threads(repository_id=repo, pull_request_id=int(pr_id), project=project)

        threads = await self._run_sync(_fetch)
        formatted_threads = []
        for t in threads[:10]:
            if t.comments:
                first_comment = t.comments[0]
                author = first_comment.author.display_name if first_comment.author else "Unknown"
                content = (first_comment.content or "")[:100]
                formatted_threads.append(f"- {author}: {content}")

        return FacultyResult(
            success=True,
            summary=f"**PR #{pr_id} Threads:**\n" + "\n".join(formatted_threads) if formatted_threads else "No comments",
            data={"threads": [{"id": t.id, "status": t.status} for t in threads]},
        )

    async def _add_pr_comment(self, params: dict) -> FacultyResult:
        """Add a comment to a PR."""
        project = params.get("project", "")
        repo = params.get("repository", "")
        pr_id = params.get("pr_id", "")
        content = params.get("content", "")

        if not all([project, repo, pr_id, content]):
            return FacultyResult(success=False, summary="Project, repository, pr_id, and content required", error="Missing params")

        def _fetch():
            from azure.devops.v7_1.git.models import Comment, GitPullRequestCommentThread

            client = self._get_git_client()
            comment = Comment(content=content, comment_type=1)
            thread = GitPullRequestCommentThread(comments=[comment], status=1)
            return client.create_thread(comment_thread=thread, repository_id=repo, pull_request_id=int(pr_id), project=project)

        result = await self._run_sync(_fetch)

        return FacultyResult(
            success=True,
            summary=f"Added comment to PR #{pr_id}",
            data={"thread_id": result.id},
        )

    # ==========================================================================
    # Work Items
    # ==========================================================================

    async def _get_work_item(self, params: dict) -> FacultyResult:
        """Get work item details."""
        work_item_id = params.get("work_item_id", "")
        if not work_item_id:
            return FacultyResult(success=False, summary="work_item_id required", error="Missing params")

        def _fetch():
            client = self._get_work_item_client()
            return client.get_work_item(id=int(work_item_id), expand="All")

        wi = await self._run_sync(_fetch)
        fields = wi.fields or {}
        title = fields.get("System.Title", "N/A")
        wi_type = fields.get("System.WorkItemType", "N/A")
        state = fields.get("System.State", "N/A")
        assigned = fields.get("System.AssignedTo", {})
        assigned_name = assigned.get("displayName", "Unassigned") if isinstance(assigned, dict) else "Unassigned"

        return FacultyResult(
            success=True,
            summary=f"**#{work_item_id}: {title}**\nType: {wi_type}\nState: {state}\nAssigned: {assigned_name}",
            data={"id": wi.id, "title": title, "type": wi_type, "state": state, "assigned": assigned_name},
        )

    async def _create_work_item(self, params: dict) -> FacultyResult:
        """Create a work item."""
        project = params.get("project", "")
        work_item_type = params.get("work_item_type", "Task")
        title = params.get("title", "")

        if not project or not title:
            return FacultyResult(success=False, summary="Project and title required", error="Missing params")

        def _fetch():
            from azure.devops.v7_1.work_item_tracking.models import JsonPatchOperation

            client = self._get_work_item_client()
            operations = [
                JsonPatchOperation(op="add", path="/fields/System.Title", value=title),
            ]
            if params.get("description"):
                operations.append(JsonPatchOperation(op="add", path="/fields/System.Description", value=params["description"]))

            return client.create_work_item(document=operations, project=project, type=work_item_type)

        wi = await self._run_sync(_fetch)

        return FacultyResult(
            success=True,
            summary=f"Created {work_item_type} #{wi.id}: {title}",
            data={"id": wi.id, "type": work_item_type, "title": title},
        )

    async def _update_work_item(self, params: dict) -> FacultyResult:
        """Update a work item."""
        work_item_id = params.get("work_item_id", "")
        if not work_item_id:
            return FacultyResult(success=False, summary="work_item_id required", error="Missing params")

        def _fetch():
            from azure.devops.v7_1.work_item_tracking.models import JsonPatchOperation

            client = self._get_work_item_client()
            operations = []
            if params.get("title"):
                operations.append(JsonPatchOperation(op="add", path="/fields/System.Title", value=params["title"]))
            if params.get("state"):
                operations.append(JsonPatchOperation(op="add", path="/fields/System.State", value=params["state"]))

            if not operations:
                raise ValueError("No updates specified")

            return client.update_work_item(document=operations, id=int(work_item_id))

        wi = await self._run_sync(_fetch)

        return FacultyResult(
            success=True,
            summary=f"Updated work item #{work_item_id}",
            data={"id": wi.id},
        )

    async def _search_work_items(self, params: dict) -> FacultyResult:
        """Search work items with WIQL."""
        project = params.get("project", "")
        query = params.get("query", "")

        if not project:
            return FacultyResult(success=False, summary="Project required", error="Missing project")

        def _fetch():
            from azure.devops.v7_1.work_item_tracking.models import Wiql

            client = self._get_work_item_client()

            # Build WIQL query
            wiql_str = f"SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.TeamProject] = '{project}'"
            if query:
                wiql_str += f" AND [System.Title] CONTAINS '{query}'"
            wiql_str += " ORDER BY [System.ChangedDate] DESC"

            wiql = Wiql(query=wiql_str)
            result = client.query_by_wiql(wiql=wiql, top=20)

            if not result.work_items:
                return []

            # Get work item details
            ids = [wi.id for wi in result.work_items]
            return client.get_work_items(ids=ids, fields=["System.Id", "System.Title", "System.State"])

        work_items = await self._run_sync(_fetch)

        if not work_items:
            return FacultyResult(success=True, summary="No work items found", data={"work_items": []})

        items = [
            {
                "id": wi.id,
                "title": (wi.fields or {}).get("System.Title", "N/A")[:50],
                "state": (wi.fields or {}).get("System.State"),
            }
            for wi in work_items
        ]

        formatted = "\n".join([f"- **#{i['id']}** {i['title']} ({i['state']})" for i in items])

        return FacultyResult(
            success=True,
            summary=f"**Work Items:**\n{formatted}",
            data={"work_items": items},
        )

    async def _my_work_items(self, params: dict) -> FacultyResult:
        """Get work items assigned to current user."""
        project = params.get("project", "")
        if not project:
            return FacultyResult(success=False, summary="Project required", error="Missing project")

        def _fetch():
            from azure.devops.v7_1.work_item_tracking.models import Wiql

            client = self._get_work_item_client()

            wiql_str = f"SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.TeamProject] = '{project}' AND [System.AssignedTo] = @Me ORDER BY [System.ChangedDate] DESC"

            wiql = Wiql(query=wiql_str)
            result = client.query_by_wiql(wiql=wiql, top=20)

            if not result.work_items:
                return []

            ids = [wi.id for wi in result.work_items]
            return client.get_work_items(ids=ids, fields=["System.Id", "System.Title", "System.State"])

        work_items = await self._run_sync(_fetch)

        if not work_items:
            return FacultyResult(success=True, summary="No work items assigned to you", data={"work_items": []})

        items = [
            {
                "id": wi.id,
                "title": (wi.fields or {}).get("System.Title", "N/A")[:50],
                "state": (wi.fields or {}).get("System.State"),
            }
            for wi in work_items
        ]

        formatted = "\n".join([f"- **#{i['id']}** {i['title']} ({i['state']})" for i in items])

        return FacultyResult(
            success=True,
            summary=f"**Your Work Items:**\n{formatted}",
            data={"work_items": items},
        )

    async def _list_work_item_types(self, params: dict) -> FacultyResult:
        """List available work item types."""
        project = params.get("project", "")
        if not project:
            return FacultyResult(success=False, summary="Project required", error="Missing project")

        def _fetch():
            client = self._get_work_item_client()
            return client.get_work_item_types(project=project)

        types = await self._run_sync(_fetch)
        type_names = [t.name for t in types]
        formatted = "\n".join([f"- {t}" for t in type_names])

        return FacultyResult(
            success=True,
            summary=f"**Work Item Types:**\n{formatted}",
            data={"types": type_names},
        )

    # ==========================================================================
    # Pipelines
    # ==========================================================================

    async def _list_pipelines(self, params: dict) -> FacultyResult:
        """List pipelines."""
        project = params.get("project", "")
        if not project:
            return FacultyResult(success=False, summary="Project required", error="Missing project")

        def _fetch():
            client = self._get_build_client()
            return client.get_definitions(project=project)

        pipelines = await self._run_sync(_fetch)
        pipeline_list = [{"id": p.id, "name": p.name} for p in pipelines]
        formatted = "\n".join([f"- **{p['name']}** (ID: {p['id']})" for p in pipeline_list])

        return FacultyResult(
            success=True,
            summary=f"**Pipelines:**\n{formatted}",
            data={"pipelines": pipeline_list},
        )

    async def _list_builds(self, params: dict) -> FacultyResult:
        """List builds."""
        project = params.get("project", "")
        if not project:
            return FacultyResult(success=False, summary="Project required", error="Missing project")

        def _fetch():
            client = self._get_build_client()
            return client.get_builds(project=project, top=20)

        builds = await self._run_sync(_fetch)
        build_list = [
            {
                "id": b.id,
                "number": b.build_number,
                "status": b.status,
                "result": b.result,
            }
            for b in builds
        ]

        formatted = "\n".join([f"- **#{b['id']}** {b['number']} - {b['status']} ({b.get('result', 'N/A')})" for b in build_list])

        return FacultyResult(
            success=True,
            summary=f"**Recent Builds:**\n{formatted}",
            data={"builds": build_list},
        )

    async def _run_pipeline(self, params: dict) -> FacultyResult:
        """Run a pipeline."""
        project = params.get("project", "")
        pipeline_id = params.get("pipeline_id", "")

        if not project or not pipeline_id:
            return FacultyResult(success=False, summary="Project and pipeline_id required", error="Missing params")

        def _fetch():
            client = self._get_build_client()
            from azure.devops.v7_1.build.models import Build

            build = Build(definition={"id": int(pipeline_id)})
            return client.queue_build(build=build, project=project)

        result = await self._run_sync(_fetch)

        return FacultyResult(
            success=True,
            summary=f"Started build #{result.id}",
            data={"build_id": result.id},
        )

    async def _get_build_logs(self, params: dict) -> FacultyResult:
        """Get build logs."""
        project = params.get("project", "")
        build_id = params.get("build_id", "")

        if not project or not build_id:
            return FacultyResult(success=False, summary="Project and build_id required", error="Missing params")

        def _fetch():
            client = self._get_build_client()
            return client.get_build_logs(project=project, build_id=int(build_id))

        logs = await self._run_sync(_fetch)

        return FacultyResult(
            success=True,
            summary=f"Build #{build_id} has {len(logs)} log entries",
            data={"logs": [{"id": l.id, "type": l.type} for l in logs]},
        )

    # ==========================================================================
    # Wiki
    # ==========================================================================

    async def _list_wikis(self, params: dict) -> FacultyResult:
        """List wikis in a project."""
        project = params.get("project", "")
        if not project:
            return FacultyResult(success=False, summary="Project required", error="Missing project")

        def _fetch():
            client = self._get_wiki_client()
            return client.get_all_wikis(project=project)

        wikis = await self._run_sync(_fetch)
        wiki_list = [{"name": w.name, "id": w.id} for w in wikis]
        formatted = "\n".join([f"- {w['name']}" for w in wiki_list])

        return FacultyResult(
            success=True,
            summary=f"**Wikis:**\n{formatted}",
            data={"wikis": wiki_list},
        )

    async def _get_wiki_page(self, params: dict) -> FacultyResult:
        """Get wiki page content."""
        project = params.get("project", "")
        page = params.get("page", "")

        if not project or not page:
            return FacultyResult(success=False, summary="Project and page required", error="Missing params")

        def _fetch():
            client = self._get_wiki_client()

            # Get first wiki
            wikis = client.get_all_wikis(project=project)
            if not wikis:
                raise ValueError("No wikis found")

            wiki_id = wikis[0].id
            return client.get_page(project=project, wiki_identifier=wiki_id, path=page, include_content=True)

        result = await self._run_sync(_fetch)
        content = result.content or ""

        return FacultyResult(
            success=True,
            summary=f"**{page}:**\n{content[:2000]}",
            data={"page": page, "content": content},
        )

    async def _create_wiki_page(self, params: dict) -> FacultyResult:
        """Create or update wiki page."""
        project = params.get("project", "")
        page = params.get("page", "")
        content = params.get("content", "")

        if not all([project, page, content]):
            return FacultyResult(success=False, summary="Project, page, and content required", error="Missing params")

        def _fetch():
            from azure.devops.v7_1.wiki.models import WikiPageCreateOrUpdateParameters

            client = self._get_wiki_client()

            # Get first wiki
            wikis = client.get_all_wikis(project=project)
            if not wikis:
                raise ValueError("No wikis found")

            wiki_id = wikis[0].id
            params_obj = WikiPageCreateOrUpdateParameters(content=content)
            return client.create_or_update_page(
                parameters=params_obj,
                project=project,
                wiki_identifier=wiki_id,
                path=page,
                version=None,  # Create or update
            )

        await self._run_sync(_fetch)

        return FacultyResult(
            success=True,
            summary=f"Created/updated wiki page: {page}",
            data={"page": page},
        )

    # ==========================================================================
    # Search
    # ==========================================================================

    async def _search_code(self, params: dict) -> FacultyResult:
        """Search code across repos."""
        project = params.get("project", "")
        query = params.get("query", "")

        if not project or not query:
            return FacultyResult(success=False, summary="Project and query required", error="Missing params")

        # Code search uses a different API endpoint that's not in the SDK
        # Fall back to REST API for this one
        import httpx
        import base64

        def _fetch():
            org_url = _get_org_url()
            url = f"{org_url}/{project}/_apis/search/codesearchresults"
            auth = base64.b64encode(f":{AZURE_DEVOPS_PAT}".encode()).decode()
            headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

            with httpx.Client() as client:
                response = client.post(
                    url,
                    headers=headers,
                    params={"api-version": "7.1"},
                    json={"searchText": query, "$top": 20},
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()

        result = await self._run_sync(_fetch)
        results = result.get("results", [])
        formatted = "\n".join([f"- {r.get('path', 'N/A')} in {r.get('repository', {}).get('name', 'N/A')}" for r in results[:15]])

        return FacultyResult(
            success=True,
            summary=f"**Code search results for '{query}':**\n{formatted}" if formatted else "No results found",
            data={"results": results},
        )

    # ==========================================================================
    # Iterations
    # ==========================================================================

    async def _list_iterations(self, params: dict) -> FacultyResult:
        """List iterations/sprints."""
        project = params.get("project", "")
        if not project:
            return FacultyResult(success=False, summary="Project required", error="Missing project")

        # Work client for iterations
        def _fetch():
            connection = self._get_connection()
            work_client = connection.clients.get_work_client()
            # Get default team context
            team_context = {"project": project}
            return work_client.get_team_iterations(team_context=team_context)

        iterations = await self._run_sync(_fetch)
        iteration_list = [
            {
                "name": i.name,
                "path": i.path,
                "startDate": str(i.attributes.start_date) if i.attributes and i.attributes.start_date else None,
                "finishDate": str(i.attributes.finish_date) if i.attributes and i.attributes.finish_date else None,
            }
            for i in iterations
        ]

        formatted = "\n".join([f"- **{i['name']}** ({i.get('startDate', 'N/A')} - {i.get('finishDate', 'N/A')})" for i in iteration_list])

        return FacultyResult(
            success=True,
            summary=f"**Iterations/Sprints:**\n{formatted}",
            data={"iterations": iteration_list},
        )
