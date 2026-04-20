from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import psutil

BYTES_TO_MB = 1024 ** 2
THRESHOLD_MEMORY_MB = 500
TERMINATION_TIMEOUT_SEC = 3
IGNORED_EXCEPTIONS = (psutil.NoSuchProcess, psutil.AccessDenied)
UNKNOWN_STATUS = "unknown"
DEFAULT_CPU_USAGE = 0.0
DEFAULT_MEMORY_USAGE = 0.0

@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str
    status: str
    cpu_usage: float
    memory_usage: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_process_by_pid(pid: int) -> Optional[psutil.Process]:
    """Get a psutil Process object by PID"""
    try:
        return psutil.Process(pid)
    except IGNORED_EXCEPTIONS:
        return None


def get_process_memory_usage(process: psutil.Process) -> float:
    """Get memory usage in MB"""
    try:
        return process.memory_info().rss / BYTES_TO_MB
    except IGNORED_EXCEPTIONS:
        return DEFAULT_MEMORY_USAGE


def get_process_cpu_usage(process: psutil.Process) -> float:
    """Get CPU usage percentage"""
    try:
        return process.cpu_percent(interval=0)
    except IGNORED_EXCEPTIONS:
        return DEFAULT_CPU_USAGE


def get_process_status(process: psutil.Process) -> str:
    """Get process status string"""
    try:
        return process.status()
    except IGNORED_EXCEPTIONS:
        return UNKNOWN_STATUS


def get_process_name(process: psutil.Process) -> str:
    """Get process name"""
    try:
        return process.name()
    except IGNORED_EXCEPTIONS:
        return UNKNOWN_STATUS


def create_process_info(proc: psutil.Process) -> ProcessInfo:
    """Create a ProcessInfo object from a process"""
    return ProcessInfo(
        pid=proc.pid,
        name=get_process_name(proc),
        status=get_process_status(proc),
        cpu_usage=get_process_cpu_usage(proc),
        memory_usage=get_process_memory_usage(proc),
    )


def create_process(pid: int) -> ProcessInfo:
    """Create a ProcessInfo object from a pid"""
    proc = psutil.Process(pid)
    return create_process_info(proc)


def collect_process_info(proc: psutil.Process) -> Optional[ProcessInfo]:
    """Safely collect process information"""
    try:
        return create_process_info(proc)
    except IGNORED_EXCEPTIONS:
        return None


def process_iter_safe() -> List[psutil.Process]:
    """Safely iterate through processes"""
    return list(psutil.process_iter(["pid"]))


def get_processes(limit: int) -> List[ProcessInfo]:
    """Get list of processes up to limit"""
    result: List[ProcessInfo] = []
    
    for proc in process_iter_safe():
        process_info = collect_process_info(proc)
        if process_info:
            result.append(process_info)
            if len(result) >= limit:
                break
                
    return result


def collect_high_memory_process(process: psutil.Process, threshold_mb: float) -> Optional[ProcessInfo]:
    """Check and collect high memory process information"""
    try:
        memory_mb = get_process_memory_usage(process)
        
        if memory_mb > threshold_mb:
            return collect_process_info(process)
        return None
    except IGNORED_EXCEPTIONS:
        return None


def check_high_resource_usage(memory_threshold_mb: float = THRESHOLD_MEMORY_MB) -> List[ProcessInfo]:
    """Find processes with high memory usage"""
    high_usage: List[ProcessInfo] = []
    
    for proc in process_iter_safe():
        try:
            process = psutil.Process(proc.info["pid"])
            process_info = collect_high_memory_process(process, memory_threshold_mb)
            
            if process_info:
                high_usage.append(process_info)
                    
        except IGNORED_EXCEPTIONS:
            continue
            
    return high_usage


def get_parent_process(process: psutil.Process) -> Optional[psutil.Process]:
    """Get parent process"""
    try:
        return process.parent()
    except IGNORED_EXCEPTIONS:
        return None


def check_end_of_parent_chain(parent: Optional[psutil.Process], current: psutil.Process, name: str) -> bool:
    """Check if we reached end of parent chain"""
    if parent is None:
        return True
        
    try:
        return get_process_name(parent) != name
    except IGNORED_EXCEPTIONS:
        return True


def get_root_parent(pid: int) -> Optional[psutil.Process]:
    """Find root parent with same name in process tree"""
    proc = get_process_by_pid(pid)
    if proc is None:
        return None
        
    name = get_process_name(proc)
    current = proc
    
    while True:
        parent = get_parent_process(current)
        if check_end_of_parent_chain(parent, current, name):
            return current
            
        current = parent


def get_process_children(process: psutil.Process, recursive: bool = True) -> List[psutil.Process]:
    """Get child processes"""
    try:
        return process.children(recursive=recursive)
    except IGNORED_EXCEPTIONS:
        return []


def terminate_single_process(process: psutil.Process) -> bool:
    """Terminate a single process"""
    try:
        process.terminate()
        return True
    except IGNORED_EXCEPTIONS:
        return False


def kill_process(process: psutil.Process) -> bool:
    """Kill a process forcefully"""
    try:
        process.kill()
        return True
    except IGNORED_EXCEPTIONS:
        return False


def wait_for_processes(processes: List[psutil.Process], timeout: int) -> List[psutil.Process]:
    """Wait for processes to terminate and return survivors"""
    try:
        _, alive = psutil.wait_procs(processes, timeout=timeout)
        return alive
    except Exception:
        return []


def terminate_process_tree(processes_to_stop: List[psutil.Process]) -> None:
    """Terminate a list of processes gracefully first, then forcefully"""
    # First try graceful termination
    for process in processes_to_stop:
        terminate_single_process(process)
    
    # Wait for processes to terminate
    alive_processes = wait_for_processes(processes_to_stop, timeout=TERMINATION_TIMEOUT_SEC)
    
    # Force kill survivors
    for process in alive_processes:
        kill_process(process)


def terminate_process(pid: int) -> bool:
    """Terminate a process and its children"""
    # Get the root process
    root_proc = get_root_parent(pid)
    if root_proc is None:
        return False
    
    # Collect all processes to stop
    processes_to_stop = get_process_children(root_proc, recursive=True)
    processes_to_stop.append(root_proc)
    
    # Terminate the process tree
    terminate_process_tree(processes_to_stop)
    
    # Check if termination was successful
    return not psutil.pid_exists(pid)