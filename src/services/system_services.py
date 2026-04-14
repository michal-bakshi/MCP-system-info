import logging
import os
import platform
from typing import Any, Dict

import psutil

from src.models.system_model import SystemInfo

logger = logging.getLogger(__name__)

_BYTES_PER_GB = 1024**3
_BYTES_PER_MB = 1024**2


def get_system_info() -> Dict[str, Any]:
    # logger.info("Fetching system information")

    net_io = psutil.net_io_counters()
    virtual_memory = psutil.virtual_memory()

    system_info = SystemInfo(
        system=platform.system(),
        node_name=platform.node(),
        release=platform.release(),
        version=platform.version(),
        machine=platform.machine(),
        processor=platform.processor(),
        cpu_cores=psutil.cpu_count(logical=False),
        logical_cpus=psutil.cpu_count(logical=True),
        ram=virtual_memory.total / _BYTES_PER_GB,
        disk_usage=psutil.disk_usage(os.path.abspath(os.sep)).percent,
        cpu_usage=psutil.cpu_percent(interval=0.1),
        memory_usage=virtual_memory.percent,
        network_sent=net_io.bytes_sent / _BYTES_PER_MB,
        network_recv=net_io.bytes_recv / _BYTES_PER_MB,
        uptime=psutil.boot_time(),
    )

    return system_info.to_dict()