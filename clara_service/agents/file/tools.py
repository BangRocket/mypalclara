"""Tools for the File Agent.

Local file storage operations for persistent user files.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from mindflow.tools import tool


def _get_files_dir(user_id: str = "default") -> Path:
    """Get the files directory for a user."""
    base_dir = os.getenv("CLARA_FILES_DIR", "./clara_files")
    user_dir = Path(base_dir) / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _get_max_file_size() -> int:
    """Get max file size from env (default 50MB)."""
    return int(os.getenv("CLARA_MAX_FILE_SIZE", 50 * 1024 * 1024))


@tool("save_file")
def save_file(filename: str, content: str, user_id: str = "default") -> str:
    """Save content to a file in local storage.

    Args:
        filename: Name of the file to save
        content: Content to write to the file
        user_id: User ID for file isolation (default: "default")

    Returns:
        Confirmation message with file path
    """
    try:
        # Sanitize filename
        filename = Path(filename).name  # Remove any path components
        if not filename:
            return "Error: Invalid filename"

        files_dir = _get_files_dir(user_id)
        file_path = files_dir / filename

        # Check size
        if len(content.encode("utf-8")) > _get_max_file_size():
            return f"Error: Content exceeds max file size ({_get_max_file_size() // 1024 // 1024}MB)"

        # Write file
        file_path.write_text(content, encoding="utf-8")

        return f"File saved successfully: {file_path}"

    except Exception as e:
        return f"Error saving file: {e}"


@tool("read_file")
def read_file(filename: str, user_id: str = "default") -> str:
    """Read a file from local storage.

    Args:
        filename: Name of the file to read
        user_id: User ID for file isolation (default: "default")

    Returns:
        File contents
    """
    try:
        files_dir = _get_files_dir(user_id)
        file_path = files_dir / Path(filename).name

        if not file_path.exists():
            return f"Error: File not found: {filename}"

        content = file_path.read_text(encoding="utf-8")

        # Truncate if too long
        if len(content) > 10000:
            content = content[:10000] + "\n\n... [truncated - file too long]"

        return f"""**{filename}**

```
{content}
```
"""
    except Exception as e:
        return f"Error reading file: {e}"


@tool("list_files")
def list_files(user_id: str = "default") -> str:
    """List all files in local storage for a user.

    Args:
        user_id: User ID for file isolation (default: "default")

    Returns:
        List of files with sizes and dates
    """
    try:
        files_dir = _get_files_dir(user_id)

        files = []
        for file_path in files_dir.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                size = stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

                # Format size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size // 1024} KB"
                else:
                    size_str = f"{size // 1024 // 1024} MB"

                files.append(f"- **{file_path.name}** ({size_str}) - {mtime}")

        if not files:
            return "No files found in storage."

        return f"""**Files in storage ({len(files)} files):**

{chr(10).join(files)}
"""
    except Exception as e:
        return f"Error listing files: {e}"


@tool("delete_file")
def delete_file(filename: str, user_id: str = "default") -> str:
    """Delete a file from local storage.

    Args:
        filename: Name of the file to delete
        user_id: User ID for file isolation (default: "default")

    Returns:
        Confirmation message
    """
    try:
        files_dir = _get_files_dir(user_id)
        file_path = files_dir / Path(filename).name

        if not file_path.exists():
            return f"Error: File not found: {filename}"

        file_path.unlink()
        return f"File deleted: {filename}"

    except Exception as e:
        return f"Error deleting file: {e}"


@tool("file_info")
def file_info(filename: str, user_id: str = "default") -> str:
    """Get detailed information about a file.

    Args:
        filename: Name of the file
        user_id: User ID for file isolation (default: "default")

    Returns:
        File metadata
    """
    try:
        files_dir = _get_files_dir(user_id)
        file_path = files_dir / Path(filename).name

        if not file_path.exists():
            return f"Error: File not found: {filename}"

        stat = file_path.stat()
        size = stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        ctime = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")

        # Detect file type from extension
        suffix = file_path.suffix.lower()
        type_map = {
            ".txt": "Text",
            ".md": "Markdown",
            ".py": "Python",
            ".js": "JavaScript",
            ".json": "JSON",
            ".csv": "CSV",
            ".html": "HTML",
            ".css": "CSS",
            ".yaml": "YAML",
            ".yml": "YAML",
        }
        file_type = type_map.get(suffix, f"Unknown ({suffix})" if suffix else "Unknown")

        # Format size
        if size < 1024:
            size_str = f"{size} bytes"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / 1024 / 1024:.1f} MB"

        return f"""**{filename}**

Type: {file_type}
Size: {size_str}
Modified: {mtime}
Created: {ctime}
Path: {file_path}
"""
    except Exception as e:
        return f"Error getting file info: {e}"


@tool("copy_file")
def copy_file(source: str, destination: str, user_id: str = "default") -> str:
    """Copy a file within local storage.

    Args:
        source: Source filename
        destination: Destination filename
        user_id: User ID for file isolation (default: "default")

    Returns:
        Confirmation message
    """
    try:
        files_dir = _get_files_dir(user_id)
        src_path = files_dir / Path(source).name
        dst_path = files_dir / Path(destination).name

        if not src_path.exists():
            return f"Error: Source file not found: {source}"

        if dst_path.exists():
            return f"Error: Destination file already exists: {destination}"

        import shutil
        shutil.copy2(src_path, dst_path)

        return f"File copied: {source} → {destination}"

    except Exception as e:
        return f"Error copying file: {e}"


# Export all tools
FILE_TOOLS = [
    save_file,
    read_file,
    list_files,
    delete_file,
    file_info,
    copy_file,
]
