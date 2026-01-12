"""
GitHub Faculty - Clara's comprehensive GitHub capability using PyGithub.

Supports the full GitHub REST API (to the extent PyGithub supports it).
"""

import asyncio
import base64
import logging
import os
import re
from datetime import datetime
from typing import Any, Optional

from github import Auth, Github, GithubException
from github.GithubException import UnknownObjectException

from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


def _get_client() -> Github:
    """Get authenticated GitHub client."""
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN not configured")
    auth = Auth.Token(GITHUB_TOKEN)
    return Github(auth=auth)


class GitHubFaculty(Faculty):
    """Clara's comprehensive GitHub capability."""

    name = "github"
    description = "Full GitHub API access - repos, issues, PRs, actions, releases, and more"

    # All supported actions
    available_actions = [
        # User & Auth
        "get_user", "get_authenticated_user", "search_users",
        # Repositories
        "list_repos", "get_repo", "create_repo", "search_repos",
        "list_branches", "get_branch", "list_tags",
        "list_contributors", "list_languages", "list_topics",
        # Contents
        "get_readme", "get_file", "list_contents", "create_file", "update_file", "delete_file",
        # Issues
        "list_issues", "get_issue", "create_issue", "update_issue", "close_issue",
        "list_issue_comments", "create_issue_comment",
        "list_labels", "create_label",
        "list_milestones", "create_milestone",
        # Pull Requests
        "list_pulls", "get_pull", "create_pull", "update_pull", "merge_pull",
        "list_pull_commits", "list_pull_files", "list_pull_comments",
        "create_pull_comment", "list_pull_reviews", "create_pull_review",
        # Commits
        "list_commits", "get_commit", "compare_commits",
        # Branches & Refs
        "create_branch", "delete_branch", "get_branch_protection",
        # Releases
        "list_releases", "get_release", "get_latest_release", "create_release",
        # Actions & Workflows
        "list_workflows", "get_workflow", "list_workflow_runs", "get_workflow_run",
        "list_artifacts", "trigger_workflow",
        # Organizations
        "get_org", "list_org_repos", "list_org_members", "list_org_teams",
        # Gists
        "list_gists", "get_gist", "create_gist",
        # Stars & Watching
        "list_stargazers", "list_watchers", "star_repo", "unstar_repo",
        # Forks
        "list_forks", "create_fork",
        # Notifications
        "list_notifications", "mark_notifications_read",
        # Search
        "search_code", "search_issues", "search_commits",
    ]

    def __init__(self):
        self._configured = bool(GITHUB_TOKEN)
        self._last_repo: str = ""

    async def execute(
        self,
        intent: str,
        constraints: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> FacultyResult:
        """Translate Clara's intent into GitHub API calls."""
        if not self._configured:
            return FacultyResult(
                success=False,
                summary="GitHub is not configured. Please set GITHUB_TOKEN.",
                error="GITHUB_TOKEN not set",
            )

        logger.info(f"[faculty:github] Planning for intent: {intent}")

        try:
            plan = self._plan_execution(intent, constraints)
            logger.info(f"[faculty:github] Plan: {plan}")

            results = []
            for step in plan["steps"]:
                logger.info(f"[faculty:github] Executing: {step['action']}")
                result = await asyncio.to_thread(self._execute_step, step)
                results.append(result)

            summary = self._summarize_results(results, intent)

            return FacultyResult(
                success=all("error" not in r for r in results),
                data={"results": results},
                summary=summary,
            )

        except GithubException as e:
            error_msg = f"GitHub API error: {e.status} - {e.data.get('message', str(e))}"
            logger.error(f"[faculty:github] {error_msg}")
            return FacultyResult(success=False, error=error_msg, summary=f"GitHub error: {e.status}")
        except Exception as e:
            logger.exception(f"[faculty:github] Error: {e}")
            return FacultyResult(success=False, error=str(e), summary=f"GitHub operation failed: {str(e)}")

    def _plan_execution(self, intent: str, constraints: Optional[list[str]]) -> dict:
        """Parse intent into API calls."""
        intent_lower = intent.lower()
        repo = self._extract_repo(intent)

        # === USER & AUTH ===
        if any(x in intent_lower for x in ["my profile", "my account", "who am i", "authenticated user"]):
            return {"steps": [{"action": "get_authenticated_user"}]}

        if "search" in intent_lower and "user" in intent_lower:
            query = self._extract_query(intent)
            return {"steps": [{"action": "search_users", "query": query}]}

        if ("get" in intent_lower or "show" in intent_lower) and "user" in intent_lower:
            username = self._extract_username(intent)
            return {"steps": [{"action": "get_user", "username": username}]}

        # === REPOSITORIES ===
        if "search" in intent_lower and "repo" in intent_lower:
            query = self._extract_query(intent)
            return {"steps": [{"action": "search_repos", "query": query}]}

        if "create" in intent_lower and "repo" in intent_lower:
            name = self._extract_repo_name(intent)
            desc = self._extract_description(intent)
            private = "private" in intent_lower
            return {"steps": [{"action": "create_repo", "name": name, "description": desc, "private": private}]}

        if "fork" in intent_lower:
            return {"steps": [{"action": "create_fork", "repo": repo}]}

        if "list" in intent_lower and "fork" in intent_lower:
            return {"steps": [{"action": "list_forks", "repo": repo}]}

        if "list" in intent_lower and "repo" in intent_lower:
            if "org" in intent_lower:
                org = self._extract_org(intent)
                return {"steps": [{"action": "list_org_repos", "org": org}]}
            return {"steps": [{"action": "list_repos"}]}

        # === BRANCHES ===
        if "list" in intent_lower and "branch" in intent_lower:
            return {"steps": [{"action": "list_branches", "repo": repo}]}

        if "create" in intent_lower and "branch" in intent_lower:
            branch_name = self._extract_branch_name(intent)
            source = self._extract_source_branch(intent)
            return {"steps": [{"action": "create_branch", "repo": repo, "branch": branch_name, "source": source}]}

        if "delete" in intent_lower and "branch" in intent_lower:
            branch_name = self._extract_branch_name(intent)
            return {"steps": [{"action": "delete_branch", "repo": repo, "branch": branch_name}]}

        if ("get" in intent_lower or "show" in intent_lower) and "branch" in intent_lower:
            branch_name = self._extract_branch_name(intent)
            return {"steps": [{"action": "get_branch", "repo": repo, "branch": branch_name}]}

        if "protection" in intent_lower and "branch" in intent_lower:
            branch_name = self._extract_branch_name(intent)
            return {"steps": [{"action": "get_branch_protection", "repo": repo, "branch": branch_name}]}

        # === TAGS ===
        if "list" in intent_lower and "tag" in intent_lower:
            return {"steps": [{"action": "list_tags", "repo": repo}]}

        # === CONTRIBUTORS & LANGUAGES ===
        if "contributor" in intent_lower:
            return {"steps": [{"action": "list_contributors", "repo": repo}]}

        if "language" in intent_lower:
            return {"steps": [{"action": "list_languages", "repo": repo}]}

        if "topic" in intent_lower and "list" in intent_lower:
            return {"steps": [{"action": "list_topics", "repo": repo}]}

        # === CONTENTS ===
        if "readme" in intent_lower:
            return {"steps": [{"action": "get_readme", "repo": repo}]}

        if "create" in intent_lower and "file" in intent_lower:
            path = self._extract_path(intent)
            content = self._extract_content(intent)
            message = self._extract_commit_message(intent) or f"Create {path}"
            return {"steps": [{"action": "create_file", "repo": repo, "path": path, "content": content, "message": message}]}

        if "update" in intent_lower and "file" in intent_lower:
            path = self._extract_path(intent)
            content = self._extract_content(intent)
            message = self._extract_commit_message(intent) or f"Update {path}"
            return {"steps": [{"action": "update_file", "repo": repo, "path": path, "content": content, "message": message}]}

        if "delete" in intent_lower and "file" in intent_lower:
            path = self._extract_path(intent)
            message = self._extract_commit_message(intent) or f"Delete {path}"
            return {"steps": [{"action": "delete_file", "repo": repo, "path": path, "message": message}]}

        if "list" in intent_lower and ("content" in intent_lower or "file" in intent_lower or "dir" in intent_lower):
            path = self._extract_path(intent)
            return {"steps": [{"action": "list_contents", "repo": repo, "path": path}]}

        if ("get" in intent_lower or "read" in intent_lower or "show" in intent_lower) and "file" in intent_lower:
            path = self._extract_path(intent)
            return {"steps": [{"action": "get_file", "repo": repo, "path": path}]}

        # === ISSUES ===
        if "create" in intent_lower and "issue" in intent_lower:
            title = self._extract_title(intent)
            body = self._extract_body(intent)
            return {"steps": [{"action": "create_issue", "repo": repo, "title": title, "body": body}]}

        if "close" in intent_lower and "issue" in intent_lower:
            number = self._extract_number(intent)
            return {"steps": [{"action": "close_issue", "repo": repo, "number": number}]}

        if "update" in intent_lower and "issue" in intent_lower:
            number = self._extract_number(intent)
            title = self._extract_title(intent)
            body = self._extract_body(intent)
            return {"steps": [{"action": "update_issue", "repo": repo, "number": number, "title": title, "body": body}]}

        if "comment" in intent_lower and "issue" in intent_lower:
            number = self._extract_number(intent)
            if "list" in intent_lower:
                return {"steps": [{"action": "list_issue_comments", "repo": repo, "number": number}]}
            body = self._extract_body(intent) or self._extract_comment(intent)
            return {"steps": [{"action": "create_issue_comment", "repo": repo, "number": number, "body": body}]}

        if "list" in intent_lower and "issue" in intent_lower:
            state = "open" if "open" in intent_lower else ("closed" if "closed" in intent_lower else "all")
            return {"steps": [{"action": "list_issues", "repo": repo, "state": state}]}

        if ("get" in intent_lower or "show" in intent_lower) and "issue" in intent_lower:
            number = self._extract_number(intent)
            return {"steps": [{"action": "get_issue", "repo": repo, "number": number}]}

        # === LABELS ===
        if "list" in intent_lower and "label" in intent_lower:
            return {"steps": [{"action": "list_labels", "repo": repo}]}

        if "create" in intent_lower and "label" in intent_lower:
            name = self._extract_label_name(intent)
            color = self._extract_color(intent)
            return {"steps": [{"action": "create_label", "repo": repo, "name": name, "color": color}]}

        # === MILESTONES ===
        if "list" in intent_lower and "milestone" in intent_lower:
            return {"steps": [{"action": "list_milestones", "repo": repo}]}

        if "create" in intent_lower and "milestone" in intent_lower:
            title = self._extract_title(intent)
            return {"steps": [{"action": "create_milestone", "repo": repo, "title": title}]}

        # === PULL REQUESTS ===
        if "create" in intent_lower and ("pr" in intent_lower or "pull" in intent_lower):
            title = self._extract_title(intent)
            body = self._extract_body(intent)
            head = self._extract_head_branch(intent)
            base = self._extract_base_branch(intent)
            return {"steps": [{"action": "create_pull", "repo": repo, "title": title, "body": body, "head": head, "base": base}]}

        if "merge" in intent_lower and ("pr" in intent_lower or "pull" in intent_lower):
            number = self._extract_number(intent)
            return {"steps": [{"action": "merge_pull", "repo": repo, "number": number}]}

        if "update" in intent_lower and ("pr" in intent_lower or "pull" in intent_lower):
            number = self._extract_number(intent)
            title = self._extract_title(intent)
            body = self._extract_body(intent)
            return {"steps": [{"action": "update_pull", "repo": repo, "number": number, "title": title, "body": body}]}

        if "commit" in intent_lower and ("pr" in intent_lower or "pull" in intent_lower):
            number = self._extract_number(intent)
            return {"steps": [{"action": "list_pull_commits", "repo": repo, "number": number}]}

        if ("file" in intent_lower or "change" in intent_lower) and ("pr" in intent_lower or "pull" in intent_lower):
            number = self._extract_number(intent)
            return {"steps": [{"action": "list_pull_files", "repo": repo, "number": number}]}

        if "comment" in intent_lower and ("pr" in intent_lower or "pull" in intent_lower):
            number = self._extract_number(intent)
            if "list" in intent_lower:
                return {"steps": [{"action": "list_pull_comments", "repo": repo, "number": number}]}
            body = self._extract_body(intent) or self._extract_comment(intent)
            return {"steps": [{"action": "create_pull_comment", "repo": repo, "number": number, "body": body}]}

        if "review" in intent_lower and ("pr" in intent_lower or "pull" in intent_lower):
            number = self._extract_number(intent)
            if "list" in intent_lower:
                return {"steps": [{"action": "list_pull_reviews", "repo": repo, "number": number}]}
            body = self._extract_body(intent)
            event = "APPROVE" if "approve" in intent_lower else ("REQUEST_CHANGES" if "request change" in intent_lower else "COMMENT")
            return {"steps": [{"action": "create_pull_review", "repo": repo, "number": number, "body": body, "event": event}]}

        if "list" in intent_lower and ("pr" in intent_lower or "pull" in intent_lower):
            state = "open" if "open" in intent_lower else ("closed" if "closed" in intent_lower else "all")
            return {"steps": [{"action": "list_pulls", "repo": repo, "state": state}]}

        if ("get" in intent_lower or "show" in intent_lower) and ("pr" in intent_lower or "pull" in intent_lower):
            number = self._extract_number(intent)
            return {"steps": [{"action": "get_pull", "repo": repo, "number": number}]}

        # === COMMITS ===
        if "compare" in intent_lower and "commit" in intent_lower:
            base = self._extract_base_branch(intent) or "main"
            head = self._extract_head_branch(intent)
            return {"steps": [{"action": "compare_commits", "repo": repo, "base": base, "head": head}]}

        if "list" in intent_lower and "commit" in intent_lower:
            branch = self._extract_branch_name(intent)
            return {"steps": [{"action": "list_commits", "repo": repo, "branch": branch}]}

        if ("get" in intent_lower or "show" in intent_lower) and "commit" in intent_lower:
            sha = self._extract_sha(intent)
            return {"steps": [{"action": "get_commit", "repo": repo, "sha": sha}]}

        if "search" in intent_lower and "commit" in intent_lower:
            query = self._extract_query(intent)
            return {"steps": [{"action": "search_commits", "query": query, "repo": repo}]}

        # === RELEASES ===
        if "latest" in intent_lower and "release" in intent_lower:
            return {"steps": [{"action": "get_latest_release", "repo": repo}]}

        if "create" in intent_lower and "release" in intent_lower:
            tag = self._extract_tag(intent)
            name = self._extract_title(intent) or tag
            body = self._extract_body(intent)
            prerelease = "prerelease" in intent_lower or "pre-release" in intent_lower
            return {"steps": [{"action": "create_release", "repo": repo, "tag": tag, "name": name, "body": body, "prerelease": prerelease}]}

        if "list" in intent_lower and "release" in intent_lower:
            return {"steps": [{"action": "list_releases", "repo": repo}]}

        if ("get" in intent_lower or "show" in intent_lower) and "release" in intent_lower:
            tag = self._extract_tag(intent)
            return {"steps": [{"action": "get_release", "repo": repo, "tag": tag}]}

        # === ACTIONS & WORKFLOWS ===
        if "trigger" in intent_lower and "workflow" in intent_lower:
            workflow = self._extract_workflow(intent)
            branch = self._extract_branch_name(intent) or "main"
            return {"steps": [{"action": "trigger_workflow", "repo": repo, "workflow": workflow, "branch": branch}]}

        if "list" in intent_lower and "artifact" in intent_lower:
            return {"steps": [{"action": "list_artifacts", "repo": repo}]}

        if ("run" in intent_lower or "execution" in intent_lower) and "workflow" in intent_lower:
            workflow = self._extract_workflow(intent)
            if "list" in intent_lower:
                return {"steps": [{"action": "list_workflow_runs", "repo": repo, "workflow": workflow}]}
            run_id = self._extract_number(intent)
            return {"steps": [{"action": "get_workflow_run", "repo": repo, "run_id": run_id}]}

        if "list" in intent_lower and "workflow" in intent_lower:
            return {"steps": [{"action": "list_workflows", "repo": repo}]}

        if ("get" in intent_lower or "show" in intent_lower) and "workflow" in intent_lower:
            workflow = self._extract_workflow(intent)
            return {"steps": [{"action": "get_workflow", "repo": repo, "workflow": workflow}]}

        # === ORGANIZATIONS ===
        if ("get" in intent_lower or "show" in intent_lower) and "org" in intent_lower:
            org = self._extract_org(intent)
            return {"steps": [{"action": "get_org", "org": org}]}

        if "member" in intent_lower and "org" in intent_lower:
            org = self._extract_org(intent)
            return {"steps": [{"action": "list_org_members", "org": org}]}

        if "team" in intent_lower and "org" in intent_lower:
            org = self._extract_org(intent)
            return {"steps": [{"action": "list_org_teams", "org": org}]}

        # === GISTS ===
        if "create" in intent_lower and "gist" in intent_lower:
            filename = self._extract_filename(intent)
            content = self._extract_content(intent)
            desc = self._extract_description(intent)
            public = "public" in intent_lower
            return {"steps": [{"action": "create_gist", "filename": filename, "content": content, "description": desc, "public": public}]}

        if "list" in intent_lower and "gist" in intent_lower:
            return {"steps": [{"action": "list_gists"}]}

        if ("get" in intent_lower or "show" in intent_lower) and "gist" in intent_lower:
            gist_id = self._extract_gist_id(intent)
            return {"steps": [{"action": "get_gist", "gist_id": gist_id}]}

        # === STARS & WATCHING ===
        if "star" in intent_lower:
            if "unstar" in intent_lower:
                return {"steps": [{"action": "unstar_repo", "repo": repo}]}
            if "list" in intent_lower or "who" in intent_lower:
                return {"steps": [{"action": "list_stargazers", "repo": repo}]}
            return {"steps": [{"action": "star_repo", "repo": repo}]}

        if "watch" in intent_lower and "list" in intent_lower:
            return {"steps": [{"action": "list_watchers", "repo": repo}]}

        # === NOTIFICATIONS ===
        if "notification" in intent_lower:
            if "mark" in intent_lower and "read" in intent_lower:
                return {"steps": [{"action": "mark_notifications_read"}]}
            return {"steps": [{"action": "list_notifications"}]}

        # === SEARCH ===
        if "search" in intent_lower and "code" in intent_lower:
            query = self._extract_query(intent)
            return {"steps": [{"action": "search_code", "query": query, "repo": repo}]}

        if "search" in intent_lower and "issue" in intent_lower:
            query = self._extract_query(intent)
            return {"steps": [{"action": "search_issues", "query": query}]}

        # === REPO INFO (default for repo mentions) ===
        if repo and ("get" in intent_lower or "show" in intent_lower or "info" in intent_lower or "about" in intent_lower):
            return {"steps": [{"action": "get_repo", "repo": repo}]}

        if repo:
            # Default: get repo info if a repo is mentioned
            return {"steps": [{"action": "get_repo", "repo": repo}]}

        # === HELP ===
        return {"steps": [{"action": "help", "message": self._get_help_message(intent)}]}

    def _execute_step(self, step: dict) -> dict:
        """Execute a single API call."""
        action = step["action"]
        g = _get_client()

        try:
            # === USER & AUTH ===
            if action == "get_authenticated_user":
                user = g.get_user()
                return {"action": action, "data": self._user_to_dict(user)}

            if action == "get_user":
                user = g.get_user(step["username"])
                return {"action": action, "data": self._user_to_dict(user)}

            if action == "search_users":
                users = list(g.search_users(step["query"])[:10])
                return {"action": action, "data": [self._user_to_dict(u) for u in users], "count": len(users)}

            # === REPOSITORIES ===
            if action == "list_repos":
                user = g.get_user()
                repos = list(user.get_repos(sort="updated")[:20])
                return {"action": action, "data": [self._repo_summary(r) for r in repos], "count": len(repos)}

            if action == "get_repo":
                repo_name = step.get("repo", "")
                if not self._validate_repo(repo_name):
                    return {"action": action, "error": "No repository specified. Use owner/repo format."}
                repo = g.get_repo(repo_name)
                return {"action": action, "data": self._repo_to_dict(repo)}

            if action == "create_repo":
                user = g.get_user()
                repo = user.create_repo(
                    name=step["name"],
                    description=step.get("description", ""),
                    private=step.get("private", False),
                )
                return {"action": action, "data": self._repo_summary(repo), "message": f"Created repository {repo.full_name}"}

            if action == "search_repos":
                repos = list(g.search_repositories(step["query"])[:10])
                return {"action": action, "data": [self._repo_summary(r) for r in repos], "count": len(repos)}

            if action == "list_forks":
                repo = g.get_repo(step["repo"])
                forks = list(repo.get_forks()[:20])
                return {"action": action, "data": [self._repo_summary(f) for f in forks], "count": len(forks)}

            if action == "create_fork":
                repo = g.get_repo(step["repo"])
                fork = g.get_user().create_fork(repo)
                return {"action": action, "data": self._repo_summary(fork), "message": f"Forked to {fork.full_name}"}

            # === BRANCHES ===
            if action == "list_branches":
                repo = g.get_repo(step["repo"])
                branches = list(repo.get_branches()[:30])
                return {"action": action, "data": [{"name": b.name, "protected": b.protected} for b in branches]}

            if action == "get_branch":
                repo = g.get_repo(step["repo"])
                branch = repo.get_branch(step["branch"])
                return {"action": action, "data": {"name": branch.name, "protected": branch.protected, "sha": branch.commit.sha}}

            if action == "create_branch":
                repo = g.get_repo(step["repo"])
                source = step.get("source") or repo.default_branch
                source_branch = repo.get_branch(source)
                repo.create_git_ref(f"refs/heads/{step['branch']}", source_branch.commit.sha)
                return {"action": action, "message": f"Created branch {step['branch']} from {source}"}

            if action == "delete_branch":
                repo = g.get_repo(step["repo"])
                ref = repo.get_git_ref(f"heads/{step['branch']}")
                ref.delete()
                return {"action": action, "message": f"Deleted branch {step['branch']}"}

            if action == "get_branch_protection":
                repo = g.get_repo(step["repo"])
                branch = repo.get_branch(step["branch"])
                try:
                    prot = branch.get_protection()
                    return {"action": action, "data": {"required_reviews": prot.required_pull_request_reviews is not None}}
                except GithubException:
                    return {"action": action, "data": {"protected": False}}

            # === TAGS ===
            if action == "list_tags":
                repo = g.get_repo(step["repo"])
                tags = list(repo.get_tags()[:20])
                return {"action": action, "data": [{"name": t.name, "sha": t.commit.sha} for t in tags]}

            # === CONTRIBUTORS & LANGUAGES ===
            if action == "list_contributors":
                repo = g.get_repo(step["repo"])
                contribs = list(repo.get_contributors()[:20])
                return {"action": action, "data": [{"login": c.login, "contributions": c.contributions} for c in contribs]}

            if action == "list_languages":
                repo = g.get_repo(step["repo"])
                return {"action": action, "data": repo.get_languages()}

            if action == "list_topics":
                repo = g.get_repo(step["repo"])
                return {"action": action, "data": repo.get_topics()}

            # === CONTENTS ===
            if action == "get_readme":
                repo_name = step.get("repo", "")
                if not self._validate_repo(repo_name):
                    return {"action": action, "error": "No repository specified."}
                repo = g.get_repo(repo_name)
                try:
                    readme = repo.get_readme()
                    content = self._decode_content(readme.content, readme.encoding)
                    return {"action": action, "data": {"name": readme.name, "content": content}, "repo": repo_name}
                except UnknownObjectException:
                    return {"action": action, "error": f"No README found in {repo_name}"}

            if action == "get_file":
                repo_name = step.get("repo", "")
                if not self._validate_repo(repo_name):
                    return {"action": action, "error": "No repository specified."}
                repo = g.get_repo(repo_name)
                path = step.get("path", "")
                try:
                    contents = repo.get_contents(path)
                    if isinstance(contents, list):
                        return {"action": action, "data": [{"name": c.name, "type": c.type, "path": c.path} for c in contents], "is_dir": True}
                    content = self._decode_content(contents.content, contents.encoding)
                    return {"action": action, "data": {"name": contents.name, "path": contents.path, "content": content, "size": contents.size, "sha": contents.sha}, "repo": repo_name}
                except UnknownObjectException:
                    return {"action": action, "error": f"File not found: {path}"}

            if action == "list_contents":
                repo = g.get_repo(step["repo"])
                path = step.get("path", "")
                contents = repo.get_contents(path)
                if not isinstance(contents, list):
                    contents = [contents]
                return {"action": action, "data": [{"name": c.name, "type": c.type, "path": c.path, "size": c.size} for c in contents]}

            if action == "create_file":
                repo = g.get_repo(step["repo"])
                result = repo.create_file(step["path"], step["message"], step["content"])
                return {"action": action, "message": f"Created {step['path']}", "sha": result["commit"].sha}

            if action == "update_file":
                repo = g.get_repo(step["repo"])
                contents = repo.get_contents(step["path"])
                result = repo.update_file(step["path"], step["message"], step["content"], contents.sha)
                return {"action": action, "message": f"Updated {step['path']}", "sha": result["commit"].sha}

            if action == "delete_file":
                repo = g.get_repo(step["repo"])
                contents = repo.get_contents(step["path"])
                repo.delete_file(step["path"], step["message"], contents.sha)
                return {"action": action, "message": f"Deleted {step['path']}"}

            # === ISSUES ===
            if action == "list_issues":
                repo_name = step.get("repo", "")
                if not self._validate_repo(repo_name):
                    return {"action": action, "error": "No repository specified."}
                repo = g.get_repo(repo_name)
                issues = list(repo.get_issues(state=step.get("state", "open"))[:15])
                return {"action": action, "data": [self._issue_summary(i) for i in issues], "count": len(issues), "repo": repo_name}

            if action == "get_issue":
                repo = g.get_repo(step["repo"])
                issue = repo.get_issue(step["number"])
                return {"action": action, "data": self._issue_to_dict(issue)}

            if action == "create_issue":
                repo = g.get_repo(step["repo"])
                issue = repo.create_issue(title=step["title"], body=step.get("body", ""))
                return {"action": action, "data": self._issue_summary(issue), "message": f"Created issue #{issue.number}"}

            if action == "update_issue":
                repo = g.get_repo(step["repo"])
                issue = repo.get_issue(step["number"])
                issue.edit(title=step.get("title"), body=step.get("body"))
                return {"action": action, "message": f"Updated issue #{step['number']}"}

            if action == "close_issue":
                repo = g.get_repo(step["repo"])
                issue = repo.get_issue(step["number"])
                issue.edit(state="closed")
                return {"action": action, "message": f"Closed issue #{step['number']}"}

            if action == "list_issue_comments":
                repo = g.get_repo(step["repo"])
                issue = repo.get_issue(step["number"])
                comments = list(issue.get_comments()[:20])
                return {"action": action, "data": [{"user": c.user.login, "body": c.body[:200], "created": c.created_at.isoformat()} for c in comments]}

            if action == "create_issue_comment":
                repo = g.get_repo(step["repo"])
                issue = repo.get_issue(step["number"])
                comment = issue.create_comment(step["body"])
                return {"action": action, "message": f"Added comment to issue #{step['number']}"}

            # === LABELS ===
            if action == "list_labels":
                repo = g.get_repo(step["repo"])
                labels = list(repo.get_labels())
                return {"action": action, "data": [{"name": l.name, "color": l.color} for l in labels]}

            if action == "create_label":
                repo = g.get_repo(step["repo"])
                label = repo.create_label(name=step["name"], color=step.get("color", "ededed"))
                return {"action": action, "message": f"Created label '{label.name}'"}

            # === MILESTONES ===
            if action == "list_milestones":
                repo = g.get_repo(step["repo"])
                milestones = list(repo.get_milestones())
                return {"action": action, "data": [{"title": m.title, "state": m.state, "open_issues": m.open_issues} for m in milestones]}

            if action == "create_milestone":
                repo = g.get_repo(step["repo"])
                milestone = repo.create_milestone(title=step["title"])
                return {"action": action, "message": f"Created milestone '{milestone.title}'"}

            # === PULL REQUESTS ===
            if action == "list_pulls":
                repo_name = step.get("repo", "")
                if not self._validate_repo(repo_name):
                    return {"action": action, "error": "No repository specified."}
                repo = g.get_repo(repo_name)
                pulls = list(repo.get_pulls(state=step.get("state", "open"))[:15])
                return {"action": action, "data": [self._pr_summary(p) for p in pulls], "count": len(pulls), "repo": repo_name}

            if action == "get_pull":
                repo = g.get_repo(step["repo"])
                pr = repo.get_pull(step["number"])
                return {"action": action, "data": self._pr_to_dict(pr)}

            if action == "create_pull":
                repo = g.get_repo(step["repo"])
                pr = repo.create_pull(title=step["title"], body=step.get("body", ""), head=step["head"], base=step.get("base", "main"))
                return {"action": action, "data": self._pr_summary(pr), "message": f"Created PR #{pr.number}"}

            if action == "update_pull":
                repo = g.get_repo(step["repo"])
                pr = repo.get_pull(step["number"])
                pr.edit(title=step.get("title"), body=step.get("body"))
                return {"action": action, "message": f"Updated PR #{step['number']}"}

            if action == "merge_pull":
                repo = g.get_repo(step["repo"])
                pr = repo.get_pull(step["number"])
                pr.merge()
                return {"action": action, "message": f"Merged PR #{step['number']}"}

            if action == "list_pull_commits":
                repo = g.get_repo(step["repo"])
                pr = repo.get_pull(step["number"])
                commits = list(pr.get_commits())
                return {"action": action, "data": [{"sha": c.sha[:7], "message": c.commit.message.split("\n")[0], "author": c.commit.author.name} for c in commits]}

            if action == "list_pull_files":
                repo = g.get_repo(step["repo"])
                pr = repo.get_pull(step["number"])
                files = list(pr.get_files())
                return {"action": action, "data": [{"filename": f.filename, "status": f.status, "additions": f.additions, "deletions": f.deletions} for f in files]}

            if action == "list_pull_comments":
                repo = g.get_repo(step["repo"])
                pr = repo.get_pull(step["number"])
                comments = list(pr.get_comments()[:20])
                return {"action": action, "data": [{"user": c.user.login, "body": c.body[:200]} for c in comments]}

            if action == "create_pull_comment":
                repo = g.get_repo(step["repo"])
                pr = repo.get_pull(step["number"])
                pr.create_issue_comment(step["body"])
                return {"action": action, "message": f"Added comment to PR #{step['number']}"}

            if action == "list_pull_reviews":
                repo = g.get_repo(step["repo"])
                pr = repo.get_pull(step["number"])
                reviews = list(pr.get_reviews())
                return {"action": action, "data": [{"user": r.user.login, "state": r.state, "body": (r.body or "")[:200]} for r in reviews]}

            if action == "create_pull_review":
                repo = g.get_repo(step["repo"])
                pr = repo.get_pull(step["number"])
                pr.create_review(body=step.get("body", ""), event=step.get("event", "COMMENT"))
                return {"action": action, "message": f"Added review to PR #{step['number']}"}

            # === COMMITS ===
            if action == "list_commits":
                repo = g.get_repo(step["repo"])
                branch = step.get("branch") or repo.default_branch
                commits = list(repo.get_commits(sha=branch)[:20])
                return {"action": action, "data": [{"sha": c.sha[:7], "message": c.commit.message.split("\n")[0], "author": c.commit.author.name, "date": c.commit.author.date.isoformat()} for c in commits]}

            if action == "get_commit":
                repo = g.get_repo(step["repo"])
                commit = repo.get_commit(step["sha"])
                return {"action": action, "data": {"sha": commit.sha, "message": commit.commit.message, "author": commit.commit.author.name, "date": commit.commit.author.date.isoformat(), "files": [f.filename for f in commit.files[:20]]}}

            if action == "compare_commits":
                repo = g.get_repo(step["repo"])
                comp = repo.compare(step["base"], step["head"])
                return {"action": action, "data": {"ahead_by": comp.ahead_by, "behind_by": comp.behind_by, "commits": len(comp.commits), "files": [f.filename for f in comp.files[:20]]}}

            if action == "search_commits":
                query = step["query"]
                if step.get("repo"):
                    query += f" repo:{step['repo']}"
                commits = list(g.search_commits(query)[:10])
                return {"action": action, "data": [{"sha": c.sha[:7], "message": c.commit.message.split("\n")[0], "repo": c.repository.full_name} for c in commits]}

            # === RELEASES ===
            if action == "list_releases":
                repo = g.get_repo(step["repo"])
                releases = list(repo.get_releases()[:10])
                return {"action": action, "data": [{"tag": r.tag_name, "name": r.title, "prerelease": r.prerelease, "published": r.published_at.isoformat() if r.published_at else None} for r in releases]}

            if action == "get_release":
                repo = g.get_repo(step["repo"])
                release = repo.get_release(step["tag"])
                return {"action": action, "data": {"tag": release.tag_name, "name": release.title, "body": release.body, "prerelease": release.prerelease}}

            if action == "get_latest_release":
                repo = g.get_repo(step["repo"])
                release = repo.get_latest_release()
                return {"action": action, "data": {"tag": release.tag_name, "name": release.title, "body": release.body, "published": release.published_at.isoformat() if release.published_at else None}}

            if action == "create_release":
                repo = g.get_repo(step["repo"])
                release = repo.create_git_release(tag=step["tag"], name=step.get("name", step["tag"]), message=step.get("body", ""), prerelease=step.get("prerelease", False))
                return {"action": action, "message": f"Created release {release.tag_name}"}

            # === ACTIONS & WORKFLOWS ===
            if action == "list_workflows":
                repo = g.get_repo(step["repo"])
                workflows = list(repo.get_workflows()[:20])
                return {"action": action, "data": [{"id": w.id, "name": w.name, "state": w.state, "path": w.path} for w in workflows]}

            if action == "get_workflow":
                repo = g.get_repo(step["repo"])
                workflow = repo.get_workflow(step["workflow"])
                return {"action": action, "data": {"id": workflow.id, "name": workflow.name, "state": workflow.state, "path": workflow.path}}

            if action == "list_workflow_runs":
                repo = g.get_repo(step["repo"])
                if step.get("workflow"):
                    workflow = repo.get_workflow(step["workflow"])
                    runs = list(workflow.get_runs()[:10])
                else:
                    runs = list(repo.get_workflow_runs()[:10])
                return {"action": action, "data": [{"id": r.id, "name": r.name, "status": r.status, "conclusion": r.conclusion, "branch": r.head_branch} for r in runs]}

            if action == "get_workflow_run":
                repo = g.get_repo(step["repo"])
                run = repo.get_workflow_run(step["run_id"])
                return {"action": action, "data": {"id": run.id, "name": run.name, "status": run.status, "conclusion": run.conclusion, "branch": run.head_branch, "url": run.html_url}}

            if action == "trigger_workflow":
                repo = g.get_repo(step["repo"])
                workflow = repo.get_workflow(step["workflow"])
                workflow.create_dispatch(ref=step.get("branch", "main"))
                return {"action": action, "message": f"Triggered workflow {step['workflow']}"}

            if action == "list_artifacts":
                repo = g.get_repo(step["repo"])
                artifacts = list(repo.get_artifacts()[:20])
                return {"action": action, "data": [{"id": a.id, "name": a.name, "size": a.size_in_bytes} for a in artifacts]}

            # === ORGANIZATIONS ===
            if action == "get_org":
                org = g.get_organization(step["org"])
                return {"action": action, "data": {"login": org.login, "name": org.name, "description": org.description, "public_repos": org.public_repos, "members": org.get_members().totalCount}}

            if action == "list_org_repos":
                org = g.get_organization(step["org"])
                repos = list(org.get_repos()[:20])
                return {"action": action, "data": [self._repo_summary(r) for r in repos], "count": len(repos)}

            if action == "list_org_members":
                org = g.get_organization(step["org"])
                members = list(org.get_members()[:30])
                return {"action": action, "data": [{"login": m.login, "name": m.name} for m in members]}

            if action == "list_org_teams":
                org = g.get_organization(step["org"])
                teams = list(org.get_teams())
                return {"action": action, "data": [{"name": t.name, "slug": t.slug, "members": t.members_count} for t in teams]}

            # === GISTS ===
            if action == "list_gists":
                user = g.get_user()
                gists = list(user.get_gists()[:20])
                return {"action": action, "data": [{"id": gist.id, "description": gist.description, "files": list(gist.files.keys())} for gist in gists]}

            if action == "get_gist":
                gist = g.get_gist(step["gist_id"])
                files = {name: {"content": f.content[:2000]} for name, f in gist.files.items()}
                return {"action": action, "data": {"id": gist.id, "description": gist.description, "files": files}}

            if action == "create_gist":
                user = g.get_user()
                gist = user.create_gist(public=step.get("public", False), files={step["filename"]: {"content": step["content"]}}, description=step.get("description", ""))
                return {"action": action, "data": {"id": gist.id, "url": gist.html_url}, "message": f"Created gist {gist.id}"}

            # === STARS & WATCHING ===
            if action == "star_repo":
                user = g.get_user()
                repo = g.get_repo(step["repo"])
                user.add_to_starred(repo)
                return {"action": action, "message": f"Starred {step['repo']}"}

            if action == "unstar_repo":
                user = g.get_user()
                repo = g.get_repo(step["repo"])
                user.remove_from_starred(repo)
                return {"action": action, "message": f"Unstarred {step['repo']}"}

            if action == "list_stargazers":
                repo = g.get_repo(step["repo"])
                stargazers = list(repo.get_stargazers()[:30])
                return {"action": action, "data": [u.login for u in stargazers], "count": repo.stargazers_count}

            if action == "list_watchers":
                repo = g.get_repo(step["repo"])
                watchers = list(repo.get_watchers()[:30])
                return {"action": action, "data": [u.login for u in watchers], "count": repo.watchers_count}

            # === NOTIFICATIONS ===
            if action == "list_notifications":
                user = g.get_user()
                notifs = list(user.get_notifications()[:20])
                return {"action": action, "data": [{"id": n.id, "reason": n.reason, "subject": n.subject.title, "type": n.subject.type} for n in notifs]}

            if action == "mark_notifications_read":
                user = g.get_user()
                user.mark_notifications_as_read()
                return {"action": action, "message": "Marked all notifications as read"}

            # === SEARCH ===
            if action == "search_code":
                query = step["query"]
                if step.get("repo"):
                    query += f" repo:{step['repo']}"
                results = list(g.search_code(query)[:10])
                return {"action": action, "data": [{"path": r.path, "repo": r.repository.full_name, "url": r.html_url} for r in results], "count": len(results)}

            if action == "search_issues":
                results = list(g.search_issues(step["query"])[:10])
                return {"action": action, "data": [{"number": i.number, "title": i.title, "repo": i.repository.full_name, "state": i.state} for i in results], "count": len(results)}

            # === HELP ===
            if action == "help":
                return {"action": action, "message": step.get("message", "")}

            return {"action": action, "error": f"Unknown action: {action}"}

        except UnknownObjectException as e:
            return {"action": action, "error": f"Not found: {e.data.get('message', str(e))}"}
        except GithubException as e:
            return {"action": action, "error": f"GitHub error: {e.status} - {e.data.get('message', str(e))}"}
        finally:
            g.close()

    # === HELPER METHODS ===

    def _validate_repo(self, repo: str) -> bool:
        return bool(repo and "/" in repo)

    def _decode_content(self, content: str, encoding: str) -> str:
        if encoding == "base64":
            decoded = base64.b64decode(content).decode("utf-8")
            if len(decoded) > 8000:
                return decoded[:8000] + "\n\n... (truncated)"
            return decoded
        return content

    def _user_to_dict(self, user) -> dict:
        return {"login": user.login, "name": user.name, "bio": user.bio, "public_repos": user.public_repos, "followers": user.followers, "following": user.following, "url": user.html_url}

    def _repo_summary(self, repo) -> dict:
        return {"full_name": repo.full_name, "description": repo.description, "language": repo.language, "stars": repo.stargazers_count}

    def _repo_to_dict(self, repo) -> dict:
        return {
            "full_name": repo.full_name, "description": repo.description, "language": repo.language,
            "stars": repo.stargazers_count, "forks": repo.forks_count, "open_issues": repo.open_issues_count,
            "topics": repo.get_topics(), "default_branch": repo.default_branch,
            "created_at": repo.created_at.isoformat() if repo.created_at else None,
            "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
            "homepage": repo.homepage, "license": repo.license.name if repo.license else None,
            "private": repo.private, "archived": repo.archived,
        }

    def _issue_summary(self, issue) -> dict:
        return {"number": issue.number, "title": issue.title, "state": issue.state, "user": issue.user.login}

    def _issue_to_dict(self, issue) -> dict:
        return {
            "number": issue.number, "title": issue.title, "state": issue.state, "body": issue.body,
            "user": issue.user.login, "labels": [l.name for l in issue.labels], "comments": issue.comments,
            "created_at": issue.created_at.isoformat(), "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
        }

    def _pr_summary(self, pr) -> dict:
        return {"number": pr.number, "title": pr.title, "state": pr.state, "user": pr.user.login}

    def _pr_to_dict(self, pr) -> dict:
        return {
            "number": pr.number, "title": pr.title, "state": pr.state, "body": pr.body,
            "user": pr.user.login, "merged": pr.merged, "mergeable": pr.mergeable,
            "additions": pr.additions, "deletions": pr.deletions, "changed_files": pr.changed_files,
            "head": pr.head.ref, "base": pr.base.ref,
            "created_at": pr.created_at.isoformat(),
        }

    # === EXTRACTION METHODS ===

    def _extract_repo(self, intent: str) -> str:
        false_positives = {"contents/file", "owner/repo", "user/repo", "repository/contents", "file/path", "the/repo", "a/repo"}
        matches = re.findall(r"\b([A-Za-z][\w-]*/[\w.-]+)\b", intent)
        for match in matches:
            if match.lower() not in false_positives and not match.lower().startswith(("the/", "a/", "this/")):
                self._last_repo = match
                return match
        if self._last_repo:
            return self._last_repo
        return ""

    def _extract_number(self, intent: str) -> Optional[int]:
        match = re.search(r"#(\d+)|(?:number|issue|pr|pull)\s*(\d+)|(\d+)", intent)
        if match:
            return int(next(g for g in match.groups() if g))
        return None

    def _extract_query(self, intent: str) -> str:
        match = re.search(r'"([^"]+)"', intent)
        if match:
            return match.group(1)
        match = re.search(r"(?:search|find|for)\s+(.+?)(?:\s+in\s+|\s*$)", intent, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return intent

    def _extract_username(self, intent: str) -> str:
        match = re.search(r"user\s+@?(\w+)|@(\w+)", intent)
        if match:
            return match.group(1) or match.group(2)
        return ""

    def _extract_org(self, intent: str) -> str:
        match = re.search(r"(?:org|organization)\s+@?(\w+)", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_path(self, intent: str) -> str:
        match = re.search(r"(?:file|path)\s+[\"']?([^\s\"']+)[\"']?", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r"([\w/.-]+\.\w+)", intent)
        if match:
            return match.group(1)
        return ""

    def _extract_branch_name(self, intent: str) -> str:
        match = re.search(r"branch\s+[\"']?([^\s\"']+)[\"']?", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_source_branch(self, intent: str) -> str:
        match = re.search(r"from\s+[\"']?([^\s\"']+)[\"']?", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_head_branch(self, intent: str) -> str:
        match = re.search(r"head\s+[\"']?([^\s\"']+)[\"']?", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_base_branch(self, intent: str) -> str:
        match = re.search(r"(?:base|into)\s+[\"']?([^\s\"']+)[\"']?", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return "main"

    def _extract_title(self, intent: str) -> str:
        match = re.search(r"title\s+[\"']([^\"']+)[\"']", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_body(self, intent: str) -> str:
        match = re.search(r"body\s+[\"']([^\"']+)[\"']", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_comment(self, intent: str) -> str:
        match = re.search(r"comment\s+[\"']([^\"']+)[\"']", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_content(self, intent: str) -> str:
        match = re.search(r"content\s+[\"']([^\"']+)[\"']", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_description(self, intent: str) -> str:
        match = re.search(r"description\s+[\"']([^\"']+)[\"']", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_commit_message(self, intent: str) -> str:
        match = re.search(r"message\s+[\"']([^\"']+)[\"']", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_tag(self, intent: str) -> str:
        match = re.search(r"tag\s+[\"']?([^\s\"']+)[\"']?", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r"v?\d+\.\d+\.\d+[\w.-]*", intent)
        if match:
            return match.group(0)
        return ""

    def _extract_sha(self, intent: str) -> str:
        match = re.search(r"\b([a-f0-9]{7,40})\b", intent)
        if match:
            return match.group(1)
        return ""

    def _extract_workflow(self, intent: str) -> str:
        match = re.search(r"workflow\s+[\"']?([^\s\"']+)[\"']?", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_label_name(self, intent: str) -> str:
        match = re.search(r"label\s+[\"']([^\"']+)[\"']", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_color(self, intent: str) -> str:
        match = re.search(r"color\s+[\"']?([a-fA-F0-9]{6})[\"']?", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return "ededed"

    def _extract_repo_name(self, intent: str) -> str:
        match = re.search(r"(?:repo|repository)\s+[\"']?(\w[\w-]*)[\"']?", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_filename(self, intent: str) -> str:
        match = re.search(r"(?:file|filename)\s+[\"']?([^\s\"']+)[\"']?", intent, re.IGNORECASE)
        if match:
            return match.group(1)
        return "file.txt"

    def _extract_gist_id(self, intent: str) -> str:
        match = re.search(r"\b([a-f0-9]{20,})\b", intent)
        if match:
            return match.group(1)
        return ""

    def _get_help_message(self, intent: str) -> str:
        return f"""I'm not sure how to handle: "{intent}"

Here are some things I can do:
- **Repos**: get repo info, list repos, create repo, fork, search repos
- **Issues**: list/get/create/close issues, add comments
- **PRs**: list/get/create/merge PRs, list files/commits, add reviews
- **Commits**: list commits, compare branches, search commits
- **Releases**: list/get/create releases, get latest release
- **Workflows**: list workflows, trigger workflow, list runs
- **Files**: get README, get/create/update/delete files
- **Users**: get user, search users, my profile
- **Orgs**: get org info, list members/teams/repos

Try being specific, e.g.:
- "get repo info for owner/repo"
- "list open issues in owner/repo"
- "get README from owner/repo"
- "search code for 'function_name' in owner/repo"
"""

    def _summarize_results(self, results: list[dict], intent: str) -> str:
        """Create human-readable summary."""
        if not results:
            return "No results found."

        summaries = []
        for r in results:
            action = r.get("action", "unknown")

            if "error" in r:
                summaries.append(f"**Error:** {r['error']}")
                continue

            if "message" in r:
                summaries.append(r["message"])
                continue

            data = r.get("data", {})

            if action == "help":
                summaries.append(data if isinstance(data, str) else r.get("message", ""))

            elif action in ("get_authenticated_user", "get_user"):
                summaries.append(f"**{data.get('login')}** ({data.get('name') or 'No name'})\n{data.get('bio') or ''}\nRepos: {data.get('public_repos')} | Followers: {data.get('followers')}")

            elif action == "search_users":
                items = [f"- @{u['login']}: {u.get('name') or ''}" for u in data[:10]]
                summaries.append(f"Found {r.get('count', len(data))} users:\n" + "\n".join(items))

            elif action in ("list_repos", "list_org_repos", "search_repos", "list_forks"):
                items = [f"- **{repo['full_name']}**: {repo.get('description') or 'No description'}" for repo in data[:10]]
                summaries.append(f"Found {r.get('count', len(data))} repos:\n" + "\n".join(items))

            elif action == "get_repo":
                summaries.append(f"**{data['full_name']}**\n{data.get('description') or 'No description'}\nLanguage: {data.get('language')} | Stars: {data.get('stars')} | Forks: {data.get('forks')}\nTopics: {', '.join(data.get('topics', [])) or 'None'}")

            elif action == "get_readme":
                content = data.get("content", "")
                summaries.append(f"**README from {r.get('repo')}:**\n\n{content}")

            elif action == "get_file":
                if r.get("is_dir"):
                    items = [f"- {f['name']} ({f['type']})" for f in data[:20]]
                    summaries.append(f"Directory contents:\n" + "\n".join(items))
                else:
                    summaries.append(f"**{data.get('name')}:**\n```\n{data.get('content', '')}\n```")

            elif action in ("list_contents",):
                items = [f"- {f['name']} ({f['type']}, {f.get('size', 0)} bytes)" for f in data[:20]]
                summaries.append("Contents:\n" + "\n".join(items))

            elif action in ("list_issues", "search_issues"):
                items = [f"- #{i['number']}: {i['title']} ({i['state']})" for i in data[:15]]
                summaries.append(f"Issues ({r.get('count', len(data))}):\n" + "\n".join(items) if items else "No issues found")

            elif action == "get_issue":
                body = (data.get("body") or "No description")[:500]
                summaries.append(f"**#{data['number']} - {data['title']}** ({data['state']})\nBy: @{data['user']} | Comments: {data.get('comments', 0)}\nLabels: {', '.join(data.get('labels', [])) or 'None'}\n\n{body}")

            elif action == "list_pulls":
                items = [f"- #{p['number']}: {p['title']} ({p['state']})" for p in data[:15]]
                summaries.append(f"Pull Requests ({r.get('count', len(data))}):\n" + "\n".join(items) if items else "No PRs found")

            elif action == "get_pull":
                body = (data.get("body") or "No description")[:500]
                summaries.append(f"**PR #{data['number']} - {data['title']}** ({data['state']})\n{data['head']} → {data['base']} | +{data.get('additions', 0)}/-{data.get('deletions', 0)} in {data.get('changed_files', 0)} files\n\n{body}")

            elif action in ("list_branches",):
                items = [f"- {b['name']}" + (" (protected)" if b.get("protected") else "") for b in data[:20]]
                summaries.append(f"Branches:\n" + "\n".join(items))

            elif action in ("list_tags",):
                items = [f"- {t['name']}" for t in data[:20]]
                summaries.append(f"Tags:\n" + "\n".join(items))

            elif action in ("list_commits", "search_commits"):
                items = [f"- `{c['sha']}` {c['message'][:60]} ({c.get('author', 'unknown')})" for c in data[:15]]
                summaries.append(f"Commits:\n" + "\n".join(items))

            elif action == "get_commit":
                summaries.append(f"**Commit {data['sha'][:7]}**\n{data['message']}\nBy: {data['author']} on {data.get('date', '')}\nFiles: {', '.join(data.get('files', [])[:10])}")

            elif action == "compare_commits":
                summaries.append(f"Comparison: {data.get('ahead_by', 0)} commits ahead, {data.get('behind_by', 0)} behind\n{data.get('commits', 0)} commits, {len(data.get('files', []))} files changed")

            elif action in ("list_releases",):
                items = [f"- **{rel['tag']}**: {rel.get('name') or rel['tag']}" for rel in data[:10]]
                summaries.append(f"Releases:\n" + "\n".join(items))

            elif action in ("get_release", "get_latest_release"):
                summaries.append(f"**Release {data['tag']}** - {data.get('name') or ''}\n{data.get('body', '')[:500]}")

            elif action in ("list_workflows",):
                items = [f"- {w['name']} ({w['state']})" for w in data[:15]]
                summaries.append(f"Workflows:\n" + "\n".join(items))

            elif action in ("list_workflow_runs",):
                items = [f"- {run['name']}: {run['status']}/{run.get('conclusion', 'pending')} on {run.get('branch', '')}" for run in data[:10]]
                summaries.append(f"Workflow Runs:\n" + "\n".join(items))

            elif action == "search_code":
                items = [f"- {item['repo']}: {item['path']}" for item in data[:10]]
                summaries.append(f"Code matches ({r.get('count', len(data))}):\n" + "\n".join(items) if items else "No matches found")

            elif action in ("list_contributors",):
                items = [f"- @{c['login']}: {c['contributions']} contributions" for c in data[:15]]
                summaries.append(f"Contributors:\n" + "\n".join(items))

            elif action == "list_languages":
                items = [f"- {lang}: {bytes:,} bytes" for lang, bytes in data.items()]
                summaries.append(f"Languages:\n" + "\n".join(items))

            elif action == "list_topics":
                summaries.append(f"Topics: {', '.join(data) if data else 'None'}")

            elif action in ("list_labels",):
                items = [f"- {l['name']}" for l in data[:20]]
                summaries.append(f"Labels:\n" + "\n".join(items))

            elif action in ("list_milestones",):
                items = [f"- {m['title']} ({m['state']}, {m.get('open_issues', 0)} open)" for m in data[:15]]
                summaries.append(f"Milestones:\n" + "\n".join(items))

            elif action in ("list_gists",):
                items = [f"- {g['id']}: {g.get('description') or ', '.join(g.get('files', []))[:50]}" for g in data[:10]]
                summaries.append(f"Gists:\n" + "\n".join(items))

            elif action == "get_gist":
                files = data.get("files", {})
                content = "\n\n".join([f"**{name}:**\n```\n{f.get('content', '')[:1000]}\n```" for name, f in files.items()])
                summaries.append(f"**Gist {data['id']}**\n{data.get('description', '')}\n\n{content}")

            elif action == "get_org":
                summaries.append(f"**{data['login']}** ({data.get('name') or ''})\n{data.get('description') or ''}\nRepos: {data.get('public_repos')} | Members: {data.get('members')}")

            elif action in ("list_org_members",):
                items = [f"- @{m['login']}" for m in data[:20]]
                summaries.append(f"Members:\n" + "\n".join(items))

            elif action in ("list_org_teams",):
                items = [f"- {t['name']} ({t.get('members', 0)} members)" for t in data[:15]]
                summaries.append(f"Teams:\n" + "\n".join(items))

            elif action in ("list_stargazers", "list_watchers"):
                summaries.append(f"Count: {r.get('count', len(data))}\n" + ", ".join(data[:30]))

            elif action in ("list_notifications",):
                items = [f"- [{n['type']}] {n['subject']} ({n['reason']})" for n in data[:15]]
                summaries.append(f"Notifications:\n" + "\n".join(items) if items else "No notifications")

            elif action in ("list_issue_comments", "list_pull_comments"):
                items = [f"- @{c['user']}: {c['body'][:100]}..." for c in data[:10]]
                summaries.append(f"Comments:\n" + "\n".join(items) if items else "No comments")

            elif action in ("list_pull_reviews",):
                items = [f"- @{r['user']}: {r['state']}" for r in data[:10]]
                summaries.append(f"Reviews:\n" + "\n".join(items) if items else "No reviews")

            elif action in ("list_pull_commits",):
                items = [f"- `{c['sha']}` {c['message'][:50]}" for c in data[:15]]
                summaries.append(f"PR Commits:\n" + "\n".join(items))

            elif action in ("list_pull_files",):
                items = [f"- {f['filename']} ({f['status']}, +{f['additions']}/-{f['deletions']})" for f in data[:20]]
                summaries.append(f"Changed Files:\n" + "\n".join(items))

            elif action in ("list_artifacts",):
                items = [f"- {a['name']} ({a['size']:,} bytes)" for a in data[:15]]
                summaries.append(f"Artifacts:\n" + "\n".join(items))

            else:
                summaries.append(f"{action}: completed")

        return "\n\n".join(summaries)
