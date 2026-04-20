from typing import Optional

from src.app import mcp
from src.services import file_services


@mcp.tool(description="Scan a directory for duplicate, large, or old files")
def search_cleanup_candidates(
    directory: str,
    min_size_mb: int = 50,
    max_files: Optional[int] = None,
    max_depth: Optional[int] = None,
    mode: str = "balanced",
):
    return file_services.scan_for_cleanup(
        directory,
        min_size_mb,
        max_files=max_files,
        max_depth=max_depth,
        mode=mode,
    )


@mcp.tool(description="Delete a file from the system")
def delete_file(path: str, confirmed: bool):
    return file_services.delete_file(path, confirmed)
