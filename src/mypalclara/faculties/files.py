"""
Files Faculty - File storage management.

Provides managed storage for Clara to save and retrieve files
that persist across sessions. Supports both local filesystem
and S3-compatible storage (Wasabi, AWS, etc.).
"""

import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult

logger = logging.getLogger(__name__)

# Configuration
CLARA_FILES_DIR = Path(os.getenv("CLARA_FILES_DIR", "./clara_files"))
CLARA_MAX_FILE_SIZE = int(os.getenv("CLARA_MAX_FILE_SIZE", str(50 * 1024 * 1024)))  # 50MB

# S3 Configuration
S3_ENABLED = os.getenv("S3_ENABLED", "false").lower() == "true"
S3_BUCKET = os.getenv("S3_BUCKET", "clara-files")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "https://s3.wasabisys.com")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_REGION = os.getenv("S3_REGION", "us-east-1")


class FilesFaculty(Faculty):
    """File storage faculty with local and S3 support."""

    name = "files"
    description = "Save, read, list, and manage files that persist across sessions"

    available_actions = [
        "save_file",
        "read_file",
        "list_files",
        "delete_file",
        "file_info",
        "download_from_sandbox",
        "upload_to_sandbox",
    ]

    def __init__(self):
        self._use_s3 = bool(S3_ENABLED and S3_ACCESS_KEY and S3_SECRET_KEY)
        self._s3_client = None
        self._temp_dir = Path(tempfile.gettempdir()) / "clara_s3_cache"

        if self._use_s3:
            self._init_s3()
            logger.info(f"[files] Using S3 storage: {S3_ENDPOINT_URL} / {S3_BUCKET}")
        else:
            self._base_dir = CLARA_FILES_DIR
            self._base_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[files] Using local storage: {CLARA_FILES_DIR}")

    def _init_s3(self):
        """Initialize S3 client."""
        try:
            import boto3

            self._s3_client = boto3.client(
                "s3",
                endpoint_url=S3_ENDPOINT_URL,
                aws_access_key_id=S3_ACCESS_KEY,
                aws_secret_access_key=S3_SECRET_KEY,
                region_name=S3_REGION,
            )
            self._temp_dir.mkdir(parents=True, exist_ok=True)

            # Verify bucket access
            try:
                self._s3_client.head_bucket(Bucket=S3_BUCKET)
                logger.info(f"[files] S3 bucket verified: {S3_BUCKET}")
            except Exception as e:
                logger.warning(f"[files] S3 bucket check failed: {e}")
                # Try to create bucket
                try:
                    self._s3_client.create_bucket(Bucket=S3_BUCKET)
                    logger.info(f"[files] Created S3 bucket: {S3_BUCKET}")
                except Exception as e2:
                    logger.error(f"[files] Could not create bucket: {e2}")

        except ImportError:
            logger.warning("[files] boto3 not installed, falling back to local storage")
            self._use_s3 = False
            self._base_dir = CLARA_FILES_DIR
            self._base_dir.mkdir(parents=True, exist_ok=True)

    async def execute(
        self,
        intent: str,
        constraints: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> FacultyResult:
        """Execute file-related intent."""
        logger.info(f"[files] Intent: {intent}")

        try:
            action, params = self._parse_intent(intent)
            # Inject user context into params
            params["user_id"] = user_id or params.get("user_id", "default")
            params["channel_id"] = channel_id or params.get("channel_id")
            logger.info(f"[files] Action: {action}, Params: {params}")

            if action == "save_file":
                result = await self._save_file(params)
            elif action == "read_file":
                result = await self._read_file(params)
            elif action == "list_files":
                result = await self._list_files(params)
            elif action == "delete_file":
                result = await self._delete_file(params)
            elif action == "file_info":
                result = await self._file_info(params)
            elif action == "download_from_sandbox":
                result = await self._download_from_sandbox(params)
            elif action == "upload_to_sandbox":
                result = await self._upload_to_sandbox(params)
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Unknown files action: {action}",
                    error=f"Action '{action}' not recognized",
                )

            return result

        except Exception as e:
            logger.exception(f"[files] Error: {e}")
            return FacultyResult(
                success=False,
                summary=f"File operation error: {str(e)}",
                error=str(e),
            )

    def _parse_intent(self, intent: str) -> tuple[str, dict]:
        """Parse natural language intent into action and parameters."""
        intent_lower = intent.lower()

        # Save file patterns
        if any(phrase in intent_lower for phrase in ["save", "write", "create file", "store"]):
            filename = self._extract_filename(intent)
            content = self._extract_content(intent)
            return "save_file", {"filename": filename, "content": content}

        # Read file patterns
        if any(phrase in intent_lower for phrase in ["read", "open", "show file", "get file", "cat"]):
            filename = self._extract_filename(intent)
            return "read_file", {"filename": filename}

        # List files patterns
        if any(phrase in intent_lower for phrase in ["list files", "show files", "ls", "what files"]):
            return "list_files", {}

        # Delete file patterns
        if any(phrase in intent_lower for phrase in ["delete", "remove", "rm"]):
            filename = self._extract_filename(intent)
            return "delete_file", {"filename": filename}

        # File info patterns
        if any(phrase in intent_lower for phrase in ["file info", "file details", "stat"]):
            filename = self._extract_filename(intent)
            return "file_info", {"filename": filename}

        # Download from sandbox
        if any(phrase in intent_lower for phrase in ["download from sandbox", "copy from sandbox"]):
            sandbox_path = self._extract_path(intent)
            local_filename = self._extract_filename(intent)
            return "download_from_sandbox", {"sandbox_path": sandbox_path, "local_filename": local_filename}

        # Upload to sandbox
        if any(phrase in intent_lower for phrase in ["upload to sandbox", "copy to sandbox"]):
            local_filename = self._extract_filename(intent)
            sandbox_path = self._extract_path(intent)
            return "upload_to_sandbox", {"local_filename": local_filename, "sandbox_path": sandbox_path}

        # Default to list files
        return "list_files", {}

    def _extract_filename(self, text: str) -> str:
        """Extract filename from text."""
        import re

        # Look for quoted filenames
        match = re.search(r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']', text)
        if match:
            return match.group(1)

        # Look for filename patterns
        match = re.search(r'\b([\w\-]+\.[\w]+)\b', text)
        if match:
            return match.group(1)

        return ""

    def _extract_content(self, text: str) -> str:
        """Extract file content from text."""
        import re

        # Look for content in code blocks
        match = re.search(r'```\s*(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Look for content after "content:" or "with content"
        match = re.search(r'(?:content:|with content)\s*["\']?(.+?)["\']?$', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        return ""

    def _extract_path(self, text: str) -> str:
        """Extract file path from text."""
        import re

        # Look for paths starting with /
        match = re.search(r'(/[\w./\-_]+)', text)
        if match:
            return match.group(1)

        return ""

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage."""
        safe = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
        safe = safe.lstrip(".")
        return safe or "unnamed_file"

    def _sanitize_id(self, id_str: str) -> str:
        """Sanitize an ID for filesystem/S3 key use."""
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in id_str)

    # ==========================================================================
    # Storage path helpers
    # ==========================================================================

    def _local_storage_dir(self, user_id: str, channel_id: Optional[str] = None) -> Path:
        """Get the local storage directory for a user/channel."""
        safe_user = self._sanitize_id(user_id)
        if channel_id:
            safe_channel = self._sanitize_id(channel_id)
            path = self._base_dir / safe_user / safe_channel
        else:
            path = self._base_dir / safe_user
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _s3_key(self, user_id: str, filename: str, channel_id: Optional[str] = None) -> str:
        """Generate S3 object key for a file."""
        safe_user = self._sanitize_id(user_id)
        safe_name = self._sanitize_filename(filename)
        if channel_id:
            safe_channel = self._sanitize_id(channel_id)
            return f"{safe_user}/{safe_channel}/{safe_name}"
        return f"{safe_user}/{safe_name}"

    # ==========================================================================
    # File Operations
    # ==========================================================================

    async def _save_file(self, params: dict) -> FacultyResult:
        """Save content to a file."""
        filename = params.get("filename", "")
        content = params.get("content", "")
        user_id = params.get("user_id", "default")
        channel_id = params.get("channel_id")

        if not filename:
            return FacultyResult(success=False, summary="No filename provided", error="Missing filename")

        safe_name = self._sanitize_filename(filename)

        # Convert to bytes for size check
        content_bytes = content.encode("utf-8") if isinstance(content, str) else content
        if len(content_bytes) > CLARA_MAX_FILE_SIZE:
            return FacultyResult(
                success=False,
                summary=f"File too large (max {CLARA_MAX_FILE_SIZE / 1024 / 1024:.1f}MB)",
                error="File size exceeds limit",
            )

        if self._use_s3:
            return await self._s3_save(user_id, safe_name, content_bytes, channel_id)
        else:
            return await self._local_save(user_id, safe_name, content, channel_id)

    async def _local_save(self, user_id: str, filename: str, content: str | bytes, channel_id: Optional[str]) -> FacultyResult:
        """Save file to local storage."""
        storage_path = self._local_storage_dir(user_id, channel_id)
        file_path = storage_path / filename

        mode = "w" if isinstance(content, str) else "wb"
        with open(file_path, mode) as f:
            f.write(content)

        content_bytes = content.encode("utf-8") if isinstance(content, str) else content
        size_kb = len(content_bytes) / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb >= 1 else f"{len(content_bytes)} bytes"

        return FacultyResult(
            success=True,
            summary=f"Saved '{filename}' to local storage ({size_str})",
            data={"filename": filename, "path": str(file_path), "size": len(content_bytes), "storage": "local"},
        )

    async def _s3_save(self, user_id: str, filename: str, content: bytes, channel_id: Optional[str]) -> FacultyResult:
        """Save file to S3 storage."""
        key = self._s3_key(user_id, filename, channel_id)

        try:
            self._s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=content,
            )

            size_kb = len(content) / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb >= 1 else f"{len(content)} bytes"

            return FacultyResult(
                success=True,
                summary=f"Saved '{filename}' to cloud storage ({size_str})",
                data={"filename": filename, "key": key, "size": len(content), "storage": "s3", "bucket": S3_BUCKET},
            )

        except Exception as e:
            logger.exception(f"[files] S3 save failed: {e}")
            return FacultyResult(
                success=False,
                summary=f"Failed to save to cloud storage: {str(e)}",
                error=str(e),
            )

    async def _read_file(self, params: dict) -> FacultyResult:
        """Read content from a file."""
        filename = params.get("filename", "")
        user_id = params.get("user_id", "default")
        channel_id = params.get("channel_id")

        if not filename:
            return FacultyResult(success=False, summary="No filename provided", error="Missing filename")

        safe_name = self._sanitize_filename(filename)

        if self._use_s3:
            return await self._s3_read(user_id, safe_name, channel_id)
        else:
            return await self._local_read(user_id, safe_name, channel_id)

    async def _local_read(self, user_id: str, filename: str, channel_id: Optional[str]) -> FacultyResult:
        """Read file from local storage."""
        storage_path = self._local_storage_dir(user_id, channel_id)
        file_path = storage_path / filename

        if not file_path.exists():
            return FacultyResult(
                success=False,
                summary=f"File '{filename}' not found",
                error="File not found",
            )

        try:
            with open(file_path, "r") as f:
                content = f.read()
        except UnicodeDecodeError:
            content = f"(Binary file, {file_path.stat().st_size} bytes)"

        return FacultyResult(
            success=True,
            summary=f"Contents of '{filename}':\n```\n{content[:2000]}\n```",
            data={"filename": filename, "content": content, "storage": "local"},
        )

    async def _s3_read(self, user_id: str, filename: str, channel_id: Optional[str]) -> FacultyResult:
        """Read file from S3 storage."""
        key = self._s3_key(user_id, filename, channel_id)

        try:
            response = self._s3_client.get_object(Bucket=S3_BUCKET, Key=key)
            content_bytes = response["Body"].read()

            try:
                content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = f"(Binary file, {len(content_bytes)} bytes)"

            return FacultyResult(
                success=True,
                summary=f"Contents of '{filename}':\n```\n{content[:2000]}\n```",
                data={"filename": filename, "content": content, "storage": "s3"},
            )

        except self._s3_client.exceptions.NoSuchKey:
            return FacultyResult(
                success=False,
                summary=f"File '{filename}' not found in cloud storage",
                error="File not found",
            )
        except Exception as e:
            logger.exception(f"[files] S3 read failed: {e}")
            return FacultyResult(
                success=False,
                summary=f"Failed to read from cloud storage: {str(e)}",
                error=str(e),
            )

    async def _list_files(self, params: dict) -> FacultyResult:
        """List files in storage."""
        user_id = params.get("user_id", "default")
        channel_id = params.get("channel_id")

        if self._use_s3:
            return await self._s3_list(user_id, channel_id)
        else:
            return await self._local_list(user_id, channel_id)

    async def _local_list(self, user_id: str, channel_id: Optional[str]) -> FacultyResult:
        """List files in local storage."""
        storage_path = self._local_storage_dir(user_id, channel_id)

        files = []
        for file_path in storage_path.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                size_kb = stat.st_size / 1024
                if size_kb < 1:
                    size_str = f"{stat.st_size} bytes"
                elif size_kb < 1024:
                    size_str = f"{size_kb:.1f} KB"
                else:
                    size_str = f"{size_kb / 1024:.1f} MB"

                files.append({
                    "name": file_path.name,
                    "size": stat.st_size,
                    "size_str": size_str,
                    "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                })

        if not files:
            return FacultyResult(
                success=True,
                summary="No files saved yet",
                data={"files": [], "storage": "local"},
            )

        file_list = "\n".join(f"- `{f['name']}` ({f['size_str']})" for f in files)

        return FacultyResult(
            success=True,
            summary=f"**Saved Files (local):**\n{file_list}",
            data={"files": files, "storage": "local"},
        )

    async def _s3_list(self, user_id: str, channel_id: Optional[str]) -> FacultyResult:
        """List files in S3 storage."""
        safe_user = self._sanitize_id(user_id)
        if channel_id:
            safe_channel = self._sanitize_id(channel_id)
            prefix = f"{safe_user}/{safe_channel}/"
        else:
            prefix = f"{safe_user}/"

        try:
            response = self._s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)

            files = []
            for obj in response.get("Contents", []):
                key = obj["Key"]
                filename = key.split("/")[-1]

                size_kb = obj["Size"] / 1024
                if size_kb < 1:
                    size_str = f"{obj['Size']} bytes"
                elif size_kb < 1024:
                    size_str = f"{size_kb:.1f} KB"
                else:
                    size_str = f"{size_kb / 1024:.1f} MB"

                files.append({
                    "name": filename,
                    "size": obj["Size"],
                    "size_str": size_str,
                    "modified": obj["LastModified"].isoformat(),
                })

            if not files:
                return FacultyResult(
                    success=True,
                    summary="No files saved yet",
                    data={"files": [], "storage": "s3"},
                )

            file_list = "\n".join(f"- `{f['name']}` ({f['size_str']})" for f in files)

            return FacultyResult(
                success=True,
                summary=f"**Saved Files (cloud):**\n{file_list}",
                data={"files": files, "storage": "s3", "bucket": S3_BUCKET},
            )

        except Exception as e:
            logger.exception(f"[files] S3 list failed: {e}")
            return FacultyResult(
                success=False,
                summary=f"Failed to list files: {str(e)}",
                error=str(e),
            )

    async def _delete_file(self, params: dict) -> FacultyResult:
        """Delete a file."""
        filename = params.get("filename", "")
        user_id = params.get("user_id", "default")
        channel_id = params.get("channel_id")

        if not filename:
            return FacultyResult(success=False, summary="No filename provided", error="Missing filename")

        safe_name = self._sanitize_filename(filename)

        if self._use_s3:
            return await self._s3_delete(user_id, safe_name, channel_id)
        else:
            return await self._local_delete(user_id, safe_name, channel_id)

    async def _local_delete(self, user_id: str, filename: str, channel_id: Optional[str]) -> FacultyResult:
        """Delete file from local storage."""
        storage_path = self._local_storage_dir(user_id, channel_id)
        file_path = storage_path / filename

        if not file_path.exists():
            return FacultyResult(
                success=False,
                summary=f"File '{filename}' not found",
                error="File not found",
            )

        file_path.unlink()

        return FacultyResult(
            success=True,
            summary=f"Deleted '{filename}'",
            data={"filename": filename, "storage": "local"},
        )

    async def _s3_delete(self, user_id: str, filename: str, channel_id: Optional[str]) -> FacultyResult:
        """Delete file from S3 storage."""
        key = self._s3_key(user_id, filename, channel_id)

        try:
            # Check if exists first
            self._s3_client.head_object(Bucket=S3_BUCKET, Key=key)
        except Exception:
            return FacultyResult(
                success=False,
                summary=f"File '{filename}' not found in cloud storage",
                error="File not found",
            )

        try:
            self._s3_client.delete_object(Bucket=S3_BUCKET, Key=key)
            return FacultyResult(
                success=True,
                summary=f"Deleted '{filename}' from cloud storage",
                data={"filename": filename, "storage": "s3"},
            )
        except Exception as e:
            logger.exception(f"[files] S3 delete failed: {e}")
            return FacultyResult(
                success=False,
                summary=f"Failed to delete from cloud storage: {str(e)}",
                error=str(e),
            )

    async def _file_info(self, params: dict) -> FacultyResult:
        """Get information about a file."""
        filename = params.get("filename", "")
        user_id = params.get("user_id", "default")
        channel_id = params.get("channel_id")

        if not filename:
            return FacultyResult(success=False, summary="No filename provided", error="Missing filename")

        safe_name = self._sanitize_filename(filename)

        if self._use_s3:
            return await self._s3_info(user_id, safe_name, channel_id)
        else:
            return await self._local_info(user_id, safe_name, channel_id)

    async def _local_info(self, user_id: str, filename: str, channel_id: Optional[str]) -> FacultyResult:
        """Get file info from local storage."""
        storage_path = self._local_storage_dir(user_id, channel_id)
        file_path = storage_path / filename

        if not file_path.exists():
            return FacultyResult(
                success=False,
                summary=f"File '{filename}' not found",
                error="File not found",
            )

        stat = file_path.stat()

        info = {
            "name": filename,
            "path": str(file_path),
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime, UTC).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            "storage": "local",
        }

        size_kb = stat.st_size / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb >= 1 else f"{stat.st_size} bytes"

        return FacultyResult(
            success=True,
            summary=f"**{filename}**\n- Size: {size_str}\n- Modified: {info['modified']}\n- Storage: local",
            data=info,
        )

    async def _s3_info(self, user_id: str, filename: str, channel_id: Optional[str]) -> FacultyResult:
        """Get file info from S3 storage."""
        key = self._s3_key(user_id, filename, channel_id)

        try:
            response = self._s3_client.head_object(Bucket=S3_BUCKET, Key=key)

            size = response["ContentLength"]
            size_kb = size / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb >= 1 else f"{size} bytes"

            info = {
                "name": filename,
                "key": key,
                "size": size,
                "modified": response["LastModified"].isoformat(),
                "storage": "s3",
                "bucket": S3_BUCKET,
            }

            return FacultyResult(
                success=True,
                summary=f"**{filename}**\n- Size: {size_str}\n- Modified: {info['modified']}\n- Storage: cloud ({S3_BUCKET})",
                data=info,
            )

        except Exception as e:
            if "404" in str(e) or "NoSuchKey" in str(e):
                return FacultyResult(
                    success=False,
                    summary=f"File '{filename}' not found in cloud storage",
                    error="File not found",
                )
            logger.exception(f"[files] S3 info failed: {e}")
            return FacultyResult(
                success=False,
                summary=f"Failed to get file info: {str(e)}",
                error=str(e),
            )

    async def _download_from_sandbox(self, params: dict) -> FacultyResult:
        """Download a file from Docker sandbox to storage."""
        sandbox_path = params.get("sandbox_path", "")
        local_filename = params.get("local_filename", "")
        user_id = params.get("user_id", "default")
        channel_id = params.get("channel_id")

        if not sandbox_path:
            return FacultyResult(success=False, summary="No sandbox path provided", error="Missing sandbox_path")

        try:
            from sandbox.manager import get_sandbox_manager
            sandbox_manager = get_sandbox_manager()
        except ImportError:
            return FacultyResult(success=False, summary="Sandbox not available", error="Sandbox manager not found")

        # Read from sandbox
        result = await sandbox_manager.read_file(user_id, sandbox_path)
        if not result.success:
            return FacultyResult(
                success=False,
                summary=f"Failed to read from sandbox: {result.error}",
                error=result.error,
            )

        # Determine filename
        if not local_filename:
            local_filename = sandbox_path.split("/")[-1]

        # Save to storage
        save_result = await self._save_file({
            "filename": local_filename,
            "content": result.output,
            "user_id": user_id,
            "channel_id": channel_id,
        })

        if save_result.success:
            storage_type = "cloud" if self._use_s3 else "local"
            return FacultyResult(
                success=True,
                summary=f"Downloaded '{local_filename}' from sandbox to {storage_type} storage",
                data={"filename": local_filename, "sandbox_path": sandbox_path, **save_result.data},
            )
        return save_result

    async def _upload_to_sandbox(self, params: dict) -> FacultyResult:
        """Upload a file from storage to Docker sandbox."""
        local_filename = params.get("local_filename", "")
        sandbox_path = params.get("sandbox_path", "")
        user_id = params.get("user_id", "default")
        channel_id = params.get("channel_id")

        if not local_filename:
            return FacultyResult(success=False, summary="No filename provided", error="Missing local_filename")

        # Read from storage
        read_result = await self._read_file({
            "filename": local_filename,
            "user_id": user_id,
            "channel_id": channel_id,
        })

        if not read_result.success:
            return read_result

        content = read_result.data.get("content", "")

        try:
            from sandbox.manager import get_sandbox_manager
            sandbox_manager = get_sandbox_manager()
        except ImportError:
            return FacultyResult(success=False, summary="Sandbox not available", error="Sandbox manager not found")

        # Determine sandbox path
        if not sandbox_path:
            sandbox_path = f"/home/user/{local_filename}"

        # Write to sandbox
        result = await sandbox_manager.write_file(user_id, sandbox_path, content)
        if not result.success:
            return FacultyResult(
                success=False,
                summary=f"Failed to upload to sandbox: {result.error}",
                error=result.error,
            )

        return FacultyResult(
            success=True,
            summary=f"Uploaded '{local_filename}' to sandbox at {sandbox_path}",
            data={"filename": local_filename, "sandbox_path": sandbox_path},
        )

    # ==========================================================================
    # Public helpers for Discord adapter
    # ==========================================================================

    def get_file_path(self, user_id: str, filename: str, channel_id: Optional[str] = None) -> Path | None:
        """Get file path for Discord file sending.

        For local storage, returns the file path directly.
        For S3 storage, downloads to temp and returns temp path.
        """
        safe_name = self._sanitize_filename(filename)

        if self._use_s3:
            return self._s3_get_file_path(user_id, safe_name, channel_id)
        else:
            storage_path = self._local_storage_dir(user_id, channel_id)
            file_path = storage_path / safe_name
            return file_path if file_path.exists() else None

    def _s3_get_file_path(self, user_id: str, filename: str, channel_id: Optional[str]) -> Path | None:
        """Download S3 file to temp and return path."""
        key = self._s3_key(user_id, filename, channel_id)

        try:
            # Create temp directory structure
            safe_user = self._sanitize_id(user_id)
            if channel_id:
                safe_channel = self._sanitize_id(channel_id)
                temp_dir = self._temp_dir / safe_user / safe_channel
            else:
                temp_dir = self._temp_dir / safe_user
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / filename

            self._s3_client.download_file(S3_BUCKET, key, str(temp_path))
            logger.info(f"[files] Downloaded S3 file to temp: {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"[files] Failed to download S3 file: {e}")
            return None

    def save_from_bytes(self, user_id: str, filename: str, data: bytes, channel_id: Optional[str] = None) -> FacultyResult:
        """Synchronous save for Discord attachment handling."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self._save_file({
                "filename": filename,
                "content": data,
                "user_id": user_id,
                "channel_id": channel_id,
            })
        )
