from typing import List
from .. import main as _main

def run_wmctrl_list() -> List[str]:
    return _main.run_wmctrl_list()

def find_windows_for_target(target: str) -> List[str]:
    return _main.find_windows_for_target(target)