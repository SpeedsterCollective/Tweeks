"""Version extraction helpers (delegates to main.py implementations)."""
from typing import List
from .. import main as _main

def extract_version_from_cmdline(cmdline: str) -> str:
    return _main.extract_version_from_cmdline(cmdline)

def extract_version_from_window(title: str) -> str:
    return _main.extract_version_from_window(title)

def extract_version_from_exe(path: str) -> str:
    return _main.extract_version_from_exe(path)