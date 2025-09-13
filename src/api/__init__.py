"""
Public API for programmatic use.

This module re-exports the useful helpers from the submodules so consumers can:
  from api import inspect_processes, get_state, list_targets, status_dict, ...
"""
from .process_inspector import (
    list_targets,
    inspect_processes,
    get_state,
    format_report,
    status_dict,
    target_matches,
)
from .windows import run_wmctrl_list, find_windows_for_target
from .version import (
    extract_version_from_cmdline,
    extract_version_from_window,
    extract_version_from_exe,
)

__all__ = [
    "list_targets",
    "inspect_processes",
    "get_state",
    "format_report",
    "status_dict",
    "target_matches",
    "run_wmctrl_list",
    "find_windows_for_target",
    "extract_version_from_cmdline",
    "extract_version_from_window",
    "extract_version_from_exe",
]