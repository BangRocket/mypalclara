"""Tools for the GitHub Agent.

GitHub API operations using PyGithub.
"""

import os
from typing import Union

from mindflow.tools import tool


def _get_github_client():
    """Get authenticated GitHub client."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN not configured")

    try:
        from github import Github
        return Github(token)
    except ImportError:
        raise ImportError("PyGithub not installed. Run: pip install PyGithub")


@tool("github_get_user")
def github_get_user(username: Union[str, None] = None) -> str:
    """Get information about a GitHub user.

    If no username is provided, returns info about the authenticated user.

    Args:
        username: GitHub username (omit for authenticated user)

    Returns:
        User profile information
    """
    try:
        gh = _get_github_client()

        if username:
            user = gh.get_user(username)
        else:
            user = gh.get_user()

        return f"""**{user.name or user.login}** (@{user.login})

Bio: {user.bio or "No bio"}
Location: {user.location or "Not specified"}
Company: {user.company or "Not specified"}
Public repos: {user.public_repos}
Followers: {user.followers}
Following: {user.following}
URL: {user.html_url}
"""
    except Exception as e:
        return f"Error getting user: {e}"


@tool("github_search_repos")
def github_search_repos(query: str, max_results: int = 5) -> str:
    """Search for GitHub repositories.

    Args:
        query: Search query (supports GitHub search syntax)
        max_results: Maximum number of results (default: 5)

    Returns:
        List of matching repositories
    """
    try:
        gh = _get_github_client()
        repos = gh.search_repositories(query=query)

        results = []
        for i, repo in enumerate(repos[:max_results], 1):
            results.append(
                f"{i}. **{repo.full_name}** ({repo.stargazers_count}⭐)\n"
                f"   {repo.description or 'No description'}\n"
                f"   URL: {repo.html_url}"
            )

        if not results:
            return f"No repositories found for: {query}"

        return "\n\n".join(results)

    except Exception as e:
        return f"Error searching repos: {e}"


@tool("github_get_repo")
def github_get_repo(repo_name: str) -> str:
    """Get detailed information about a repository.

    Args:
        repo_name: Repository name in format "owner/repo"

    Returns:
        Repository details
    """
    try:
        gh = _get_github_client()
        repo = gh.get_repo(repo_name)

        return f"""**{repo.full_name}**

Description: {repo.description or "No description"}
Language: {repo.language or "Not specified"}
Stars: {repo.stargazers_count}
Forks: {repo.forks_count}
Open Issues: {repo.open_issues_count}
Default Branch: {repo.default_branch}
Created: {repo.created_at.strftime("%Y-%m-%d")}
Updated: {repo.updated_at.strftime("%Y-%m-%d")}
URL: {repo.html_url}
Clone: {repo.clone_url}
"""
    except Exception as e:
        return f"Error getting repo: {e}"


@tool("github_list_issues")
def github_list_issues(repo_name: str, state: str = "open", max_results: int = 10) -> str:
    """List issues in a repository.

    Args:
        repo_name: Repository name in format "owner/repo"
        state: Issue state - "open", "closed", or "all" (default: "open")
        max_results: Maximum number of results (default: 10)

    Returns:
        List of issues
    """
    try:
        gh = _get_github_client()
        repo = gh.get_repo(repo_name)
        issues = repo.get_issues(state=state)

        results = []
        count = 0
        for issue in issues:
            if issue.pull_request:  # Skip PRs
                continue
            count += 1
            if count > max_results:
                break

            labels = ", ".join([l.name for l in issue.labels]) or "No labels"
            results.append(
                f"#{issue.number}: **{issue.title}**\n"
                f"   State: {issue.state} | Labels: {labels}\n"
                f"   Created: {issue.created_at.strftime('%Y-%m-%d')} by @{issue.user.login}"
            )

        if not results:
            return f"No {state} issues found in {repo_name}"

        return "\n\n".join(results)

    except Exception as e:
        return f"Error listing issues: {e}"


@tool("github_get_issue")
def github_get_issue(repo_name: str, issue_number: int) -> str:
    """Get details of a specific issue.

    Args:
        repo_name: Repository name in format "owner/repo"
        issue_number: Issue number

    Returns:
        Issue details including comments
    """
    try:
        gh = _get_github_client()
        repo = gh.get_repo(repo_name)
        issue = repo.get_issue(issue_number)

        labels = ", ".join([l.name for l in issue.labels]) or "No labels"
        assignees = ", ".join([a.login for a in issue.assignees]) or "Unassigned"

        result = f"""**#{issue.number}: {issue.title}**

State: {issue.state}
Labels: {labels}
Assignees: {assignees}
Created: {issue.created_at.strftime('%Y-%m-%d')} by @{issue.user.login}
URL: {issue.html_url}

---
{issue.body or "No description"}
"""

        # Get recent comments
        comments = list(issue.get_comments())
        if comments:
            result += "\n\n**Recent Comments:**\n"
            for comment in comments[-3:]:  # Last 3 comments
                result += f"\n@{comment.user.login} ({comment.created_at.strftime('%Y-%m-%d')}):\n{comment.body[:200]}...\n"

        return result

    except Exception as e:
        return f"Error getting issue: {e}"


@tool("github_create_issue")
def github_create_issue(repo_name: str, title: str, body: Union[str, None] = None, labels: Union[str, None] = None) -> str:
    """Create a new issue in a repository.

    Args:
        repo_name: Repository name in format "owner/repo"
        title: Issue title
        body: Issue body/description (optional)
        labels: Comma-separated labels (optional)

    Returns:
        Created issue details
    """
    try:
        gh = _get_github_client()
        repo = gh.get_repo(repo_name)

        label_list = [l.strip() for l in labels.split(",") if l.strip()] if labels else []

        issue = repo.create_issue(
            title=title,
            body=body,
            labels=label_list if label_list else None,
        )

        return f"""Issue created successfully!

**#{issue.number}: {issue.title}**
URL: {issue.html_url}
"""
    except Exception as e:
        return f"Error creating issue: {e}"


@tool("github_list_prs")
def github_list_prs(repo_name: str, state: str = "open", max_results: int = 10) -> str:
    """List pull requests in a repository.

    Args:
        repo_name: Repository name in format "owner/repo"
        state: PR state - "open", "closed", or "all" (default: "open")
        max_results: Maximum number of results (default: 10)

    Returns:
        List of pull requests
    """
    try:
        gh = _get_github_client()
        repo = gh.get_repo(repo_name)
        prs = repo.get_pulls(state=state)

        results = []
        for i, pr in enumerate(prs[:max_results], 1):
            labels = ", ".join([l.name for l in pr.labels]) or "No labels"
            results.append(
                f"#{pr.number}: **{pr.title}**\n"
                f"   {pr.head.ref} → {pr.base.ref} | {pr.state}\n"
                f"   Labels: {labels} | By @{pr.user.login}"
            )

        if not results:
            return f"No {state} pull requests found in {repo_name}"

        return "\n\n".join(results)

    except Exception as e:
        return f"Error listing PRs: {e}"


@tool("github_get_pr")
def github_get_pr(repo_name: str, pr_number: int) -> str:
    """Get details of a specific pull request.

    Args:
        repo_name: Repository name in format "owner/repo"
        pr_number: Pull request number

    Returns:
        Pull request details
    """
    try:
        gh = _get_github_client()
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        labels = ", ".join([l.name for l in pr.labels]) or "No labels"
        reviewers = ", ".join([r.login for r in pr.requested_reviewers]) or "None requested"

        return f"""**#{pr.number}: {pr.title}**

State: {pr.state} | Merged: {pr.merged}
Branch: {pr.head.ref} → {pr.base.ref}
Labels: {labels}
Reviewers: {reviewers}
Created: {pr.created_at.strftime('%Y-%m-%d')} by @{pr.user.login}
Commits: {pr.commits} | Additions: +{pr.additions} | Deletions: -{pr.deletions}
URL: {pr.html_url}

---
{pr.body or "No description"}
"""
    except Exception as e:
        return f"Error getting PR: {e}"


@tool("github_get_file")
def github_get_file(repo_name: str, file_path: str, branch: Union[str, None] = None) -> str:
    """Get contents of a file from a repository.

    Args:
        repo_name: Repository name in format "owner/repo"
        file_path: Path to the file in the repository
        branch: Branch name (default: repository's default branch)

    Returns:
        File contents (truncated if too long)
    """
    try:
        gh = _get_github_client()
        repo = gh.get_repo(repo_name)

        if branch:
            content = repo.get_contents(file_path, ref=branch)
        else:
            content = repo.get_contents(file_path)

        if isinstance(content, list):
            return f"Error: {file_path} is a directory, not a file"

        decoded = content.decoded_content.decode("utf-8")

        # Truncate if too long
        if len(decoded) > 5000:
            decoded = decoded[:5000] + "\n\n... [truncated - file too long]"

        return f"""**{file_path}** ({content.size} bytes)

```
{decoded}
```
"""
    except Exception as e:
        return f"Error getting file: {e}"


# Export all tools
GITHUB_TOOLS = [
    github_get_user,
    github_search_repos,
    github_get_repo,
    github_list_issues,
    github_get_issue,
    github_create_issue,
    github_list_prs,
    github_get_pr,
    github_get_file,
]
