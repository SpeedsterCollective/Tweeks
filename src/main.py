#!/usr/bin/env python3
"""Detect when Corporate Clash (native or via Wine) or Toontown Rewritten are running.

Usage:
  python src/main.py --status        # print current status once
  python src/main.py --watch         # continuously poll and report changes

This script uses `psutil` to inspect processes and `wmctrl` (if available)
to read window titles for more reliable detection.
"""
import argparse
import subprocess
import sys
import time
from typing import Dict, List
import os
import json

try:
    import psutil
except Exception:
    print("Missing dependency: psutil. Install with 'pip install -r requirements.txt'", file=sys.stderr)
    raise


TARGETS = {
    "Corporate Clash": [
        # client executable and unique identifiers for the client (not launcher)
        "corporateclash.exe",
        "corporateclash_client",
        "corporate-clash-client",
    ],
    "Toontown Rewritten": [
        # prefer the actual client exe names
        "toontownrewritten.exe",
        "toontown rewritten.exe",
        "toontown.exe",
        "toontownrewritten",
        "toontown rewritten",
        "ttr",
        "ttr_client",
    ],
}

# Common launcher/updater process/window names to ignore
LAUNCHER_NAMES = {
    "launcher",
    "updater",
    "patcher",
    "install",
    "gamecenter",
}

WINE_NAMES = {"wine", "wine64", "wine-preloader", "wineserver"}


def run_wmctrl_list() -> List[str]:
    """Return lines from `wmctrl -l` or empty list if not available."""
    try:
        proc = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, check=True)
        return proc.stdout.splitlines()
    except FileNotFoundError:
        return []
    except subprocess.CalledProcessError:
        return []


def find_windows_for_target(target: str) -> List[str]:
    """Return window titles that match the target name (case-insensitive)."""
    lines = run_wmctrl_list()
    matches = []
    for line in lines:
        # wmctrl output: <win id> <desktop> <pid?> <host> <title...>
        parts = line.split(None, 3)
        if len(parts) >= 4:
            title = parts[3]
            low = title.lower()
            # ignore launcher/update windows
            if any(x in low for x in LAUNCHER_NAMES):
                continue
            if target.lower() in low:
                matches.append(title)
    return matches


def extract_version_from_cmdline(cmdline: str) -> str:
    """Try to extract a version string from a process cmdline like --version or -v 1.2.3."""
    import re
    # common forms: --version=1.2.3, --version 1.2.3, -v 1.2.3
    m = re.search(r"--version(?:=|\s+)([\d\.]+)", cmdline)
    if m:
        return m.group(1)
    m = re.search(r"\b-v(?:ersion)?\s+([\d\.]+)", cmdline)
    if m:
        return m.group(1)
    return ""


def extract_version_from_window(title: str) -> str:
    """Try to find version-like patterns in a window title."""
    import re
    m = re.search(r"v?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", title)
    return m.group(1) if m else ""


def extract_version_from_exe(path: str) -> str:
    """Heuristic: read the last few KB of the exe looking for ASCII version strings.

    This is best-effort and may return an empty string.
    """
    try:
        if not path:
            return ""
        # if exe is a Wine path (inside quotes) try to use basename. If path doesn't exist locally, skip.
        if not os.path.exists(path):
            return ""
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            read_from = max(0, size - 8192)
            f.seek(read_from)
            data = f.read()
        # search for ASCII patterns like 1.2.3 or v1.2.3
        import re
        m = re.search(rb"v?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", data)
        if m:
            return m.group(1).decode(errors="ignore")
    except Exception:
        return ""
    return ""


def inspect_processes() -> Dict[str, List[Dict]]:
    """Inspect running processes and return matches for each target.

    Each match is a dict with keys: pid, name, cmdline, is_wine. """
    results: Dict[str, List[Dict]] = {k: [] for k in TARGETS}

    for proc in psutil.process_iter(["pid", "name", "cmdline", "exe"]):
        try:
            info = proc.info
            pid = info.get("pid")
            name = (info.get("name") or "")
            cmdline = " ".join(info.get("cmdline") or [])
            exe = info.get("exe") or ""

            lname = name.lower()
            lcmd = cmdline.lower()
            lexec = (exe or "").lower()

            # Quick wine process detection
            is_wine_proc = lname in WINE_NAMES or any(w in lcmd for w in WINE_NAMES)

            # If this process is wine and carries an .exe arg, check for exe names inside cmdline
            exe_arg = None
            if ".exe" in lcmd:
                # find the word containing .exe
                for part in lcmd.split():
                    if ".exe" in part:
                        # strip surrounding quotes and normalize path separators
                        raw = part.strip('"')
                        # sometimes wine gives full path like C:\path\to\game.exe or /home/.wine/drive_c/.../game.exe
                        exe_arg = os.path.basename(raw.replace('\\', '/'))
                        exe_arg = exe_arg.lower()
                        break

            for target, patterns in TARGETS.items():
                # ignore obvious launcher processes by name/cmdline
                if any(x in lname for x in LAUNCHER_NAMES) or any(x in lcmd for x in LAUNCHER_NAMES):
                    continue

                matched = False
                match_reason = None

                # prefer exact .exe matches (common for Wine)
                if exe_arg:
                    for p in patterns:
                        # compare basenames / lowercased
                        if exe_arg == p.lower() or exe_arg.endswith(p.lower()):
                            matched = True
                            match_reason = f"exe_arg={exe_arg}"
                            break

                # match against exe path, process name, or cmdline as fallback
                if not matched:
                    hay = " ".join([lname, lcmd, lexec, exe_arg or ""]).lower()
                    for p in patterns:
                        if p in hay:
                            matched = True
                            match_reason = f"pattern={p}"
                            break

                if matched:
                    # determine version: prefer cmdline, then window title, then exe file heuristics
                    version = None
                    v = extract_version_from_cmdline(cmdline)
                    if v:
                        version = v
                    else:
                        # check window titles for this target
                        wins = find_windows_for_target(target)
                        if wins:
                            for w in wins:
                                v2 = extract_version_from_window(w)
                                if v2:
                                    version = v2
                                    break
                    if not version:
                        # try exe path heuristic
                        version = extract_version_from_exe(exe) or None

                    results[target].append({
                        "pid": pid,
                        "name": name,
                        "cmdline": cmdline,
                        "exe": exe,
                        "is_wine": is_wine_proc or (exe_arg is not None and exe_arg.lower().endswith('.exe')),
                        "match_reason": match_reason,
                        "version": version,
                    })

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return results


def format_report(proc_matches: Dict[str, List[Dict]]) -> str:
    lines = []
    for target in TARGETS:
        matches = proc_matches.get(target, [])
        win_matches = find_windows_for_target(target)
        if matches or win_matches:
            lines.append(f"{target}: RUNNING")
            if matches:
                for m in matches:
                    typ = "Wine" if m.get("is_wine") else "Native"
                    ver = m.get("version")
                    ver_s = f" version={ver}" if ver else ""
                    lines.append(f" - PID {m['pid']} ({typ}) - name={m['name']} cmdline={m['cmdline']}{ver_s}")
            if win_matches:
                for w in win_matches:
                    lines.append(f" - Window: {w}")
        else:
            lines.append(f"{target}: not running")
    return "\n".join(lines)


def get_state(proc_matches: Dict[str, List[Dict]]) -> Dict[str, str]:
    """Return compact state mapping target -> status string (not-running/native/wine)."""
    state = {}
    for target in TARGETS:
        matches = proc_matches.get(target, [])
        if not matches:
            # still check windows in case process detection failed
            wins = find_windows_for_target(target)
            state[target] = "running-window-only" if wins else "not-running"
        else:
            # if any match is native, prefer native
            if any(not m.get("is_wine") for m in matches):
                state[target] = "native"
            else:
                state[target] = "wine"
    return state


def main():
    parser = argparse.ArgumentParser(description="Detect Corporate Clash and Toontown Rewritten")
    parser.add_argument("--watch", action="store_true", help="Continuously watch and report changes")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds for --watch")
    parser.add_argument("--status", action="store_true", help="Print current status once and exit")
    parser.add_argument("--json", action="store_true", help="When used with --status, output machine-readable JSON")

    args = parser.parse_args()

    if not args.watch and not args.status:
        parser.print_help()
        return

    if args.status:
        procs = inspect_processes()
        if args.json:
            out = {
                "targets": procs,
                "state": get_state(procs),
                "report": format_report(procs),
            }
            # compact JSON for easy parsing
            print(json.dumps(out))
            return
        print(format_report(procs))
        return

    # watch mode
    last_state = None
    try:
        while True:
            procs = inspect_processes()
            state = get_state(procs)
            if state != last_state:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{ts}] State change:")
                print(format_report(procs))
                print("---")
                last_state = state
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Exiting watch mode")


if __name__ == "__main__":
    main()
