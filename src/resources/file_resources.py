from src.app import mcp


@mcp.resource("file://cleanup-report")
def cleanup_report() -> str:
    """Return a static summary hinting users to scan directories for cleanup candidates."""
    return "Cleanup report: Scan the directory to see candidates for deletion."
