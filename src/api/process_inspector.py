from typing import Dict, List, Any, Optional
from .. import main as _main

def list_targets() -> List[str]:
    return list(_main.TARGETS.keys())

def inspect_processes() -> Dict[str, List[Dict[str, Any]]]:
    return _main.inspect_processes()

def get_state(proc_matches: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> Dict[str, str]:
    if proc_matches is None:
        proc_matches = inspect_processes()
    return _main.get_state(proc_matches)

def format_report(proc_matches: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> str:
    if proc_matches is None:
        proc_matches = inspect_processes()
    return _main.format_report(proc_matches)

def status_dict() -> Dict[str, Any]:
    procs = inspect_processes()
    return {"targets": procs, "state": get_state(procs), "report": format_report(procs)}

def target_matches(name: str) -> List[Dict[str, Any]]:
    return inspect_processes().get(name, [])