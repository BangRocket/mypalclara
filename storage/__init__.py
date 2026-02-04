"""Storage backends for Clara.

Provides local and cloud file storage.

NOTE: Storage classes have been moved to clara_core.core_tools.files_tool.
This module re-exports for backwards compatibility.
"""

from clara_core.core_tools.files_tool import (
    LOCAL_FILE_TOOLS,
    LOCAL_FILES_DIR,
    MAX_FILE_SIZE,
    S3_ACCESS_KEY,
    S3_BUCKET,
    S3_ENABLED,
    S3_ENDPOINT_URL,
    S3_REGION,
    S3_SECRET_KEY,
    FileInfo,
    FileManager,
    FileResult,
    LocalFileManager,
    S3FileManager,
    format_file_list,
    get_file_manager,
)

__all__ = [
    "FileInfo",
    "FileManager",
    "FileResult",
    "LOCAL_FILE_TOOLS",
    "LOCAL_FILES_DIR",
    "LocalFileManager",
    "MAX_FILE_SIZE",
    "S3_ACCESS_KEY",
    "S3_BUCKET",
    "S3_ENABLED",
    "S3_ENDPOINT_URL",
    "S3_REGION",
    "S3_SECRET_KEY",
    "S3FileManager",
    "format_file_list",
    "get_file_manager",
]
