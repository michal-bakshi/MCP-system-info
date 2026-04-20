from dataclasses import dataclass, asdict
from typing import Any, Dict, List

import psutil

_MB = 1024**2
THRESHOLD_MEMORY_MB = 500  

@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str
    status: str
    cpu_usage: float
    memory_usage: float

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the ProcessInfo object to a dictionary for further usage or embedding.
        """
        return asdict(self)


def create_process(pid: int) -> ProcessInfo:
    proc = psutil.Process(pid)
    return ProcessInfo(
        pid=proc.pid,
        name=proc.name(),
        status=proc.status(),
        cpu_usage=proc.cpu_percent(interval=0),
        memory_usage=proc.memory_info().rss / _MB,
    )

def get_processes(limit: int) -> List[ProcessInfo]:
    result: List[ProcessInfo] = []

    for proc in psutil.process_iter(["pid"]):
        try:
            result.append(create_process(proc.pid))
            if len(result) >= limit:
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return result

def check_high_resource_usage(memory_threshold_mb: float = THRESHOLD_MEMORY_MB) -> List[ProcessInfo]:
    high_usage: List[ProcessInfo] = []

    for proc in psutil.process_iter(["pid"]):
        try:
            proc_obj = psutil.Process(proc.info["pid"])
            memory_mb = proc_obj.memory_info().rss / _MB
            if memory_mb > memory_threshold_mb:
                high_usage.append(create_process(proc_obj.pid))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return high_usage


def get_root_parent(pid: int) -> psutil.Process | None:
    """
    Walk up the parent chain while parent has the same executable name.
    This helps map worker PIDs (e.g., Code.exe child) to app-root PID.
    """
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        current = proc

        while True:
            parent = current.parent()
            if parent is None:
                return current

            try:
                if parent.name() != name:
                    return current
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return current

            current = parent
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error):
        return None


def terminate_process(pid: int) -> bool:
    try:
        root_proc = get_root_parent(pid)
        if root_proc is None:
            return False

        proc = root_proc
        processes_to_stop = proc.children(recursive=True)
        processes_to_stop.append(proc)

        for process in processes_to_stop:
            try:
                process.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        _, alive = psutil.wait_procs(processes_to_stop, timeout=3)

        for process in alive:
            try:
                process.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Only report success if target PID actually disappeared.
        return not psutil.pid_exists(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error):
        return False
