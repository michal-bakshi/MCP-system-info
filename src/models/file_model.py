from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict

from os import stat_result

BYTES_PER_MB = 1024 * 1024
ONE_YEAR_SECONDS = 365 * 24 * 60 * 60


class ScanMode(str, Enum):
    """How aggressively duplicate detection hashes file contents."""

    FAST = "fast"
    BALANCED = "balanced"
    DEEP = "deep"


def is_large_file(size_mb: float, min_size_mb: int) -> bool:
    """Return True if ``size_mb`` exceeds the large-file threshold."""
    return size_mb > min_size_mb


def is_old_file(last_accessed: float) -> bool:
    """Return True if ``last_accessed`` is older than one year."""
    one_year_ago = time.time() - ONE_YEAR_SECONDS
    return last_accessed < one_year_ago


@dataclass(frozen=True)
class FileInfo:
    """Snapshot of file fields used for cleanup reporting."""

    path: str
    name: str
    size_mb: float
    last_accessed: float  # Timestamp
    is_duplicate: bool = False

    @classmethod
    def from_stat(cls, path: str, name: str, stat_result_value: stat_result) -> FileInfo:
        """Build a ``FileInfo`` from a path segment and ``os.stat`` result."""
        size_mb = stat_result_value.st_size / BYTES_PER_MB
        return cls(
            path=path,
            name=name,
            size_mb=round(size_mb, 2),
            last_accessed=stat_result_value.st_atime,
        )

    def is_cleanup_candidate(self, min_size_mb: int, is_duplicate: bool) -> bool:
        """True if this file belongs in cleanup results (large, old, or duplicate)."""
        return (
            is_large_file(self.size_mb, min_size_mb)
            or is_old_file(self.last_accessed)
            or is_duplicate
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
