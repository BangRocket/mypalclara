"""Obsidian vault tools — Clara can read, search, and edit the user's vault.

Each handler looks up the caller's ObsidianAccountConfig via ToolContext.user_id,
so the same tool definitions serve any user who has configured an account.
Users without a configured+verified account won't see these tools in the
first place (registry-level gating), but handlers also refuse gracefully
in case a stale schema leaks through.
"""

from __future__ import annotations

import logging
from typing import Any

from mypalclara.core.obsidian import (
    ObsidianClient,
    ObsidianError,
    get_account,
    set_last_error,
)
from mypalclara.tools._base import ToolContext, ToolDef

MODULE_NAME = "obsidian"
MODULE_VERSION = "1.0.0"

logger = logging.getLogger("clara.tools.obsidian")


def _client_for(ctx: ToolContext) -> ObsidianClient | None:
    """Load the caller's ObsidianAccountConfig into a ready client, or None."""
    cfg = get_account(ctx.user_id)
    if not cfg or not cfg.enabled:
        return None
    return ObsidianClient(cfg)


def _error(user_id: str, action: str, e: Exception) -> str:
    msg = str(e)
    logger.warning(f"Obsidian {action} failed for {user_id}: {msg}")
    try:
        set_last_error(user_id, f"{action}: {msg}")
    except Exception:
        pass
    return f"Obsidian {action} failed: {msg}"


def _no_account(action: str) -> str:
    return (
        f"Can't {action}: no Obsidian account is configured for this user. "
        "The user can set one up on their Settings page."
    )


# -- search --------------------------------------------------------------


async def _handle_search(args: dict[str, Any], ctx: ToolContext) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return "Error: 'query' is required."
    context_length = int(args.get("context_length") or 100)

    client = _client_for(ctx)
    if not client:
        return _no_account("search the vault")

    try:
        results = await client.search_simple(query, context_length=context_length)
    except ObsidianError as e:
        return _error(ctx.user_id, "search", e)

    if not results:
        return f"No results for '{query}'."

    limit = 20
    lines = [f"Found {len(results)} result(s) for '{query}' (showing up to {limit}):"]
    for r in results[:limit]:
        filename = r.get("filename") or r.get("path") or "(unknown)"
        score = r.get("score")
        matches = r.get("matches") or []
        lines.append(f"\n- **{filename}**" + (f" (score: {score})" if score is not None else ""))
        for m in matches[:3]:
            ctx_text = (m.get("context") or "").strip().replace("\n", " ")
            if ctx_text:
                if len(ctx_text) > 200:
                    ctx_text = ctx_text[:197] + "..."
                lines.append(f"  > {ctx_text}")
    return "\n".join(lines)


# -- read ----------------------------------------------------------------


async def _handle_read(args: dict[str, Any], ctx: ToolContext) -> str:
    path = (args.get("path") or "").strip()
    if not path:
        return "Error: 'path' is required."

    client = _client_for(ctx)
    if not client:
        return _no_account("read notes")

    try:
        content = await client.read_note(path)
    except ObsidianError as e:
        return _error(ctx.user_id, "read", e)

    if len(content) > 40_000:
        content = content[:40_000] + "\n\n[... truncated, note is larger ...]"
    return f"**{path}**\n\n{content}"


# -- create --------------------------------------------------------------


async def _handle_create(args: dict[str, Any], ctx: ToolContext) -> str:
    path = (args.get("path") or "").strip()
    content = args.get("content") or ""
    overwrite = bool(args.get("overwrite"))
    if not path:
        return "Error: 'path' is required."

    client = _client_for(ctx)
    if not client:
        return _no_account("create notes")

    try:
        await client.create_note(path, content, overwrite=overwrite)
    except ObsidianError as e:
        return _error(ctx.user_id, "create", e)

    action = "Overwrote" if overwrite else "Created"
    return f"{action} note at `{path}` ({len(content)} chars)."


# -- update --------------------------------------------------------------


async def _handle_update(args: dict[str, Any], ctx: ToolContext) -> str:
    path = (args.get("path") or "").strip()
    content = args.get("content") or ""
    operation = (args.get("operation") or "append").lower()
    target_type = (args.get("target_type") or "heading").lower()
    target = args.get("target")
    if not path:
        return "Error: 'path' is required."
    if not content:
        return "Error: 'content' is required."

    client = _client_for(ctx)
    if not client:
        return _no_account("update notes")

    try:
        await client.update_note(
            path,
            content,
            operation=operation,
            target_type=target_type,
            target=target,
        )
    except ObsidianError as e:
        return _error(ctx.user_id, "update", e)

    if target:
        return f"Applied {operation} at {target_type} '{target}' in `{path}`."
    return f"Appended {len(content)} chars to `{path}`."


# -- delete --------------------------------------------------------------


async def _handle_delete(args: dict[str, Any], ctx: ToolContext) -> str:
    path = (args.get("path") or "").strip()
    if not path:
        return "Error: 'path' is required."

    client = _client_for(ctx)
    if not client:
        return _no_account("delete notes")

    try:
        await client.delete_note(path)
    except ObsidianError as e:
        return _error(ctx.user_id, "delete", e)

    return f"Deleted `{path}`."


# -- list ----------------------------------------------------------------


async def _handle_list(args: dict[str, Any], ctx: ToolContext) -> str:
    path = (args.get("path") or "").strip()

    client = _client_for(ctx)
    if not client:
        return _no_account("list the vault")

    try:
        entries = await client.list_directory(path)
    except ObsidianError as e:
        return _error(ctx.user_id, "list", e)

    if not entries:
        loc = f"`{path}`" if path else "the vault root"
        return f"No entries under {loc}."

    loc = f"`{path}`" if path else "vault root"
    limit = 200
    listed = entries[:limit]
    lines = [f"{len(entries)} entries under {loc}:"]
    lines.extend(f"- {name}" for name in listed)
    if len(entries) > limit:
        lines.append(f"... and {len(entries) - limit} more")
    return "\n".join(lines)


# -- tags ----------------------------------------------------------------


async def _handle_tags(args: dict[str, Any], ctx: ToolContext) -> str:
    client = _client_for(ctx)
    if not client:
        return _no_account("list tags")

    try:
        tags = await client.list_tags()
    except ObsidianError as e:
        return _error(ctx.user_id, "tags", e)

    if not tags:
        return "No tags found in the vault."

    lines = [f"{len(tags)} tag(s) in the vault:"]
    for t in tags[:200]:
        if isinstance(t, dict):
            name = t.get("name") or t.get("tag") or ""
            count = t.get("count") or t.get("usage") or t.get("relevance")
            if count is not None:
                lines.append(f"- #{name} ({count})")
            else:
                lines.append(f"- #{name}")
        else:
            lines.append(f"- #{t}")
    return "\n".join(lines)


SYSTEM_PROMPT = """
## Obsidian Vault
You have read/write access to the user's Obsidian vault via the Local REST API.
Use these tools when the user asks about their notes, wants to capture something
to their vault, or needs to update an existing note.

- `obsidian_search`: Full-text fuzzy search across the vault.
- `obsidian_read`: Read a specific note by path.
- `obsidian_list`: List files/folders under a vault path (or root).
- `obsidian_tags`: See all tags and how often they're used.
- `obsidian_create`: Create a new note. Use `overwrite=true` to replace.
- `obsidian_update`: Append/prepend/replace at a heading, block, or end of file.
- `obsidian_delete`: Delete a note (destructive — confirm before using).

Paths are vault-relative (e.g., `Journal/2026-04-19.md`). For quick captures with
no target, `obsidian_update` with operation=append and no target appends to end of file.
""".strip()


TOOLS = [
    ToolDef(
        name="obsidian_search",
        description="Full-text fuzzy search across the user's Obsidian vault.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "context_length": {
                    "type": "integer",
                    "description": "Characters of context around each match (default 100).",
                },
            },
            "required": ["query"],
        },
        handler=_handle_search,
        emoji="\U0001f50d",
        label="Search Vault",
        detail_keys=["query"],
        risk_level="safe",
        intent="read",
    ),
    ToolDef(
        name="obsidian_read",
        description="Read the full markdown contents of a note by vault-relative path.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Vault-relative path (e.g., 'Ideas/project.md')."},
            },
            "required": ["path"],
        },
        handler=_handle_read,
        emoji="\U0001f4d6",
        label="Read Note",
        detail_keys=["path"],
        risk_level="safe",
        intent="read",
    ),
    ToolDef(
        name="obsidian_list",
        description="List files and folders under a vault-relative path (blank for root).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Vault path to list. Omit for root."},
            },
        },
        handler=_handle_list,
        emoji="\U0001f4c1",
        label="List Vault",
        detail_keys=["path"],
        risk_level="safe",
        intent="read",
    ),
    ToolDef(
        name="obsidian_tags",
        description="List all tags in the vault with usage counts.",
        parameters={"type": "object", "properties": {}},
        handler=_handle_tags,
        emoji="\U0001f3f7\ufe0f",
        label="Vault Tags",
        risk_level="safe",
        intent="read",
    ),
    ToolDef(
        name="obsidian_create",
        description=(
            "Create a new note in the vault. If the file exists and overwrite=false, "
            "content is appended; with overwrite=true the note is replaced."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Vault-relative path (must end in .md for markdown)."},
                "content": {"type": "string", "description": "Markdown body of the note."},
                "overwrite": {
                    "type": "boolean",
                    "description": "Replace existing note instead of appending. Default false.",
                },
            },
            "required": ["path"],
        },
        handler=_handle_create,
        emoji="\U0001f4dd",
        label="Create Note",
        detail_keys=["path", "overwrite"],
        risk_level="moderate",
        intent="write",
    ),
    ToolDef(
        name="obsidian_update",
        description=(
            "Update an existing note. Without a target, appends to end of file. "
            "With target_type+target, performs append/prepend/replace at a specific "
            "heading, block reference, or frontmatter field."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Vault-relative path."},
                "content": {"type": "string", "description": "Markdown to insert."},
                "operation": {
                    "type": "string",
                    "enum": ["append", "prepend", "replace"],
                    "description": "How to apply the content. Default: append.",
                },
                "target_type": {
                    "type": "string",
                    "enum": ["heading", "block", "frontmatter"],
                    "description": "What the target identifies. Default: heading.",
                },
                "target": {
                    "type": "string",
                    "description": (
                        "Heading path (e.g., 'Notes::Sub'), block id, or frontmatter key. "
                        "Omit to append to end of file."
                    ),
                },
            },
            "required": ["path", "content"],
        },
        handler=_handle_update,
        emoji="\u270f\ufe0f",
        label="Update Note",
        detail_keys=["path", "operation", "target"],
        risk_level="moderate",
        intent="write",
    ),
    ToolDef(
        name="obsidian_delete",
        description="Delete a note from the vault. Destructive — confirm intent first.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Vault-relative path to delete."},
            },
            "required": ["path"],
        },
        handler=_handle_delete,
        emoji="\U0001f5d1\ufe0f",
        label="Delete Note",
        detail_keys=["path"],
        risk_level="dangerous",
        intent="write",
    ),
]


async def initialize() -> None:
    """No-op: DB-backed config is read lazily per request."""
    return None


async def cleanup() -> None:
    """No-op."""
    return None
