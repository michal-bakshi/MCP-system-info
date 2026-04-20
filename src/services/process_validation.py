import os
from enum import Enum
from typing import Tuple, List

import psutil

from src.models.process_model import ProcessInfo


class ValidationReason(str, Enum):
    SAFE = "Safe to terminate"
    ZOMBIE = "Zombie process"
    CRITICAL_PID = "Critical system PID"
    CURRENT_PROCESS = "Cannot terminate current process"
    CRITICAL_WINDOWS = "Critical Windows process"
    CRITICAL_LINUX = "Critical Linux process"
    INVALID_INFO = "Invalid process information"
    NO_SUCH_PROCESS = "Process no longer exists"
    ACCESS_DENIED = "Access denied"


CRITICAL_WINDOWS_NAMES = {
    "system",
    "svchost.exe",
    "wininit.exe",
    "winlogon.exe",
    "csrss.exe",
    "services.exe",
}


#  TODO think on another cases 
def is_process_safe_to_terminate(
    process_info: ProcessInfo,
) -> Tuple[bool, ValidationReason]:
    try:
        if process_info.status == psutil.STATUS_ZOMBIE:
            return True, ValidationReason.ZOMBIE

        name = (process_info.name or "").lower()

        if process_info.pid in (0, 1):
            return False, ValidationReason.CRITICAL_PID

        if process_info.pid == os.getpid():
            return False, ValidationReason.CURRENT_PROCESS

        if name in CRITICAL_WINDOWS_NAMES:
            return False, ValidationReason.CRITICAL_WINDOWS

        return True, ValidationReason.SAFE

    except AttributeError:
        return False, ValidationReason.INVALID_INFO

    except psutil.NoSuchProcess:
        return False, ValidationReason.NO_SUCH_PROCESS

    except psutil.AccessDenied:
        return False, ValidationReason.ACCESS_DENIED


def get_safe_to_terminate_processes(processes: List[ProcessInfo]) -> List[ProcessInfo]:
    safe_processes: List[ProcessInfo] = []

    for proc in processes:
        is_safe, _ = is_process_safe_to_terminate(proc)

        if is_safe:
            safe_processes.append(proc)

    return safe_processes


def user_confirmed(action: str, confirmed: bool) -> bool:
    if not confirmed:
        raise ValueError(f"User confirmation required before performing: {action}")
    return True
