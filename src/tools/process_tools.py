from src.app import mcp
from src.services import process_services


@mcp.tool(description="Terminate a process after validation and user confirmation")
def terminate_process_tool(pid: int, confirmed: bool):
    if not confirmed:
        return {"success": False, "message": "User confirmation required", "pid": pid}
    return process_services.terminate_process_safe(pid)


@mcp.tool(description="Return the first running processes in the system")
def list_processes_tool(number: int = 30):
    return process_services.list_processes(number)


@mcp.tool(
    description="Check for processes consuming excessive resources."
)
def high_resource_processes_tool():
    return process_services.get_high_resource_usage_processes()
