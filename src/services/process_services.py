import logging
from typing import Any, Dict, List

import psutil

from src.models.process_model import (
    ProcessInfo,
    check_high_resource_usage,
    create_process,
    get_processes,
    terminate_process,
)
from src.services.process_validation import (
    get_safe_to_terminate_processes,
    is_process_safe_to_terminate,
)

logger = logging.getLogger(__name__)


def list_processes(limit: int) -> Dict[str, Any]:
    logger.info(f"Fetching first {limit} processes")

    process_list: List[ProcessInfo] = get_processes(limit)
    response_data: Dict[str, Any] = {
        "count": len(process_list),
        "processes": [p.to_dict() for p in process_list],
    }

    logger.debug(f"Returned {response_data['count']} processes")
    return response_data


def get_high_resource_usage_processes() -> List[Dict[str, Any]]:
    logger.info("Checking high resource usage processes")

    high_usage: List[ProcessInfo] = check_high_resource_usage()
    logger.debug(f"Found {len(high_usage)} high usage processes")

    safe_processes: List[ProcessInfo] = get_safe_to_terminate_processes(high_usage)
    logger.info(f"{len(safe_processes)} processes are safe to terminate")

    return [p.to_dict() for p in safe_processes]


def terminate_process_safe(pid: int) -> Dict[str, Any]:
    logger.info(f"Termination requested for PID {pid}")

    try:
        process_info: ProcessInfo = create_process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
        logger.warning(f"Cannot inspect PID {pid}: {exc}")
        return {"success": False, "pid": pid, "message": str(exc)}

    is_safe, reason = is_process_safe_to_terminate(process_info)

    if not is_safe:
        logger.warning(f"Termination blocked for PID {pid}. Reason: {reason}")
        return {"success": False, "pid": pid, "message": reason}

    success: bool = terminate_process(pid)

    if success:
        logger.info(f"Process {pid} terminated successfully")
    else:
        logger.error(f"Failed to terminate process {pid}")

    return {
        "success": success,
        "pid": pid,
        "message": "Process terminated" if success else "Failed to terminate process",
    }
