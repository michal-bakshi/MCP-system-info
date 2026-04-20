import hashlib
import logging
import os
import stat
from dataclasses import replace
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from os import stat_result

from src.models.file_model import FileInfo, ScanMode

logger = logging.getLogger(__name__)

CHUNK_SIZE = 4096
PROGRESS_LOG_INTERVAL = 50


def _md5_of_file(path: str, *, read_limit: Optional[int] = None) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as f:
        if read_limit is None:
            for block in iter(lambda: f.read(CHUNK_SIZE), b""):
                digest.update(block)
        else:
            digest.update(f.read(read_limit))
    return digest.hexdigest()


def get_file_hash(file_path: str) -> str:
    """Calculate MD5 hash of a file to identify real duplicates."""
    return _md5_of_file(file_path, read_limit=None)


def _partial_file_hash(file_path: str) -> str:
    """MD5 of the first CHUNK_SIZE of a file (or entire file if smaller)."""
    return _md5_of_file(file_path, read_limit=CHUNK_SIZE)


def map_file_info(path: str, name: str, stat_result_value: stat_result) -> FileInfo:
    """Map path and stat metadata to :class:`FileInfo` (see :meth:`FileInfo.from_stat`)."""
    return FileInfo.from_stat(path, name, stat_result_value)


def _coerce_scan_mode(mode: str) -> ScanMode:
    key = (mode or "balanced").strip().lower()
    try:
        return ScanMode(key)
    except ValueError:
        logger.warning("Unknown scan mode %r; using balanced", mode)
        return ScanMode.BALANCED


def _directory_depth(root: str, base: str) -> int:
    """Depth of ``root`` under ``base`` (0 = base directory itself)."""
    rel = os.path.relpath(root, base)
    if rel in (os.curdir, ""):
        return 0
    return rel.count(os.sep) + 1


def _is_symlink_stat(st: stat_result) -> bool:
    return stat.S_ISLNK(st.st_mode)


def _emit_scan_progress(files_scanned: int, path: str) -> None:
    if files_scanned == 1 or files_scanned % PROGRESS_LOG_INTERVAL == 0:
        logger.info("Files scanned: %s, current: %s", files_scanned, path)


def _emit_walk_complete_if_needed(files_scanned: int) -> None:
    if files_scanned and files_scanned % PROGRESS_LOG_INTERVAL != 0:
        logger.info("Files scanned: %s (walk complete)", files_scanned)


def _safe_stat(path: str) -> Optional[stat_result]:
    try:
        return os.stat(path, follow_symlinks=False)
    except OSError as exc:
        logger.warning("Could not stat %s: %s", path, exc, exc_info=True)
        return None


def _prune_walk_if_at_max_depth(
    root: str, directory: str, max_depth: Optional[int], dirnames: List[str]
) -> None:
    if max_depth is not None and _directory_depth(root, directory) >= max_depth:
        dirnames.clear()


def _append_one_file(
    root: str,
    name: str,
    collected: List[Tuple[str, str, stat_result]],
    files_scanned: int,
) -> Tuple[List[Tuple[str, str, stat_result]], int]:
    path = os.path.join(root, name)
    st = _safe_stat(path)
    if st is None:
        return collected, files_scanned
    collected.append((path, name, st))
    next_count = files_scanned + 1
    _emit_scan_progress(next_count, path)
    return collected, next_count


def _collect_file_entries(
    directory: str,
    max_files: Optional[int],
    max_depth: Optional[int],
) -> List[Tuple[str, str, stat_result]]:
    """Walk ``directory`` without following symlinks; return (path, name, lstat)."""
    collected: List[Tuple[str, str, stat_result]] = []
    files_scanned = 0

    for root, dirnames, filenames in os.walk(
        directory, topdown=True, followlinks=False
    ):
        _prune_walk_if_at_max_depth(root, directory, max_depth, dirnames)
        for name in filenames:
            if max_files is not None and len(collected) >= max_files:
                return collected
            collected, files_scanned = _append_one_file(
                root, name, collected, files_scanned
            )

    _emit_walk_complete_if_needed(files_scanned)
    return collected


def _safe_full_hash(path: str) -> Optional[str]:
    try:
        return _md5_of_file(path, read_limit=None)
    except OSError as exc:
        logger.warning("Could not hash %s: %s", path, exc, exc_info=True)
        return None


def _full_md5_duplicate_paths(paths: List[str]) -> Set[str]:
    duplicates: Set[str] = set()
    seen_hash_to_path: Dict[str, str] = {}
    for path in sorted(paths):
        digest = _safe_full_hash(path)
        if digest is None:
            continue
        if digest in seen_hash_to_path:
            duplicates.add(path)
        else:
            seen_hash_to_path[digest] = path
    return duplicates


def _safe_partial_hash(path: str) -> Optional[str]:
    try:
        return _partial_file_hash(path)
    except OSError as exc:
        logger.warning(
            "Could not read partial hash for %s: %s",
            path,
            exc,
            exc_info=True,
        )
        return None


def _group_paths_by_partial(paths: Iterable[str], *, sort_paths: bool) -> Dict[str, List[str]]:
    sequence = sorted(paths) if sort_paths else list(paths)
    by_partial: Dict[str, List[str]] = {}
    for path in sequence:
        partial = _safe_partial_hash(path)
        if partial is None:
            continue
        by_partial.setdefault(partial, []).append(path)
    return by_partial


def _partial_only_duplicate_paths(paths: List[str]) -> Set[str]:
    duplicates: Set[str] = set()
    for group in _group_paths_by_partial(paths, sort_paths=True).values():
        if len(group) < 2:
            continue
        duplicates.update(group[1:])
    return duplicates


def _partial_then_full_duplicate_paths(paths: List[str]) -> Set[str]:
    duplicates: Set[str] = set()
    for group in _group_paths_by_partial(paths, sort_paths=False).values():
        if len(group) < 2:
            continue
        duplicates.update(_full_md5_duplicate_paths(group))
    return duplicates


def _duplicate_paths_for_size_group(paths: List[str], mode: ScanMode) -> Set[str]:
    if len(paths) < 2:
        return set()
    if mode is ScanMode.DEEP:
        return _full_md5_duplicate_paths(paths)
    if mode is ScanMode.FAST:
        return _partial_only_duplicate_paths(paths)
    return _partial_then_full_duplicate_paths(paths)


def _paths_grouped_by_size(
    entries: List[Tuple[str, str, stat_result]],
) -> Dict[int, List[str]]:
    by_size: Dict[int, List[str]] = {}
    for path, _name, st in entries:
        if _is_symlink_stat(st):
            continue
        by_size.setdefault(st.st_size, []).append(path)
    return by_size


def _compute_duplicate_paths(
    entries: List[Tuple[str, str, stat_result]], mode: ScanMode
) -> Set[str]:
    """Group by size, then partial hash, then full MD5 when needed."""
    duplicates: Set[str] = set()
    for paths in _paths_grouped_by_size(entries).values():
        if len(paths) >= 2:
            duplicates.update(_duplicate_paths_for_size_group(paths, mode))
    return duplicates


def _build_cleanup_rows(
    entries: List[Tuple[str, str, stat_result]],
    duplicate_paths: Set[str],
    min_size_mb: int,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path, name, st in entries:
        file_info = map_file_info(path, name, st)
        is_duplicate = path in duplicate_paths
        if not file_info.is_cleanup_candidate(min_size_mb, is_duplicate):
            continue
        updated = replace(file_info, is_duplicate=is_duplicate)
        rows.append(updated.to_dict())
    return rows


def scan_for_cleanup(
    directory: str,
    min_size_mb: int = 50,
    *,
    max_files: Optional[int] = None,
    max_depth: Optional[int] = None,
    mode: str = "balanced",
) -> List[Dict[str, Any]]:
    """Scan for cleanup candidates with bounded walk and staged duplicate detection."""
    mode_key = _coerce_scan_mode(mode)
    entries = _collect_file_entries(directory, max_files, max_depth)
    duplicate_paths = _compute_duplicate_paths(entries, mode_key)
    return _build_cleanup_rows(entries, duplicate_paths, min_size_mb)


def delete_file(path: str, confirmed: bool) -> Dict[str, Any]:
    """Remove a file from disk when the caller has confirmed the action."""
    if not confirmed:
        return {"success": False, "message": "User confirmation required for deletion"}
    try:
        os.remove(path)
        return {"success": True, "path": path}
    except OSError as exc:
        return {"success": False, "error": str(exc)}
