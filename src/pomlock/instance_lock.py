"""Single-instance locking and best-effort terminal focus."""

import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from .constants import APP_NAME, STATE_FILE
from .logger import logger

RUNTIME_DIR_ENV = "XDG_RUNTIME_DIR"
LOCK_FILE_NAME = f"{APP_NAME}.lock"
LOCK_MODE = 0o600


def runtime_lock_path() -> Path:
    """Return the per-user lock path."""
    runtime_dir = Path(os.environ.get(RUNTIME_DIR_ENV, "/tmp"))
    return runtime_dir / LOCK_FILE_NAME


def read_status(state_path: Path = STATE_FILE) -> str:
    """Return a concise description of the active timer state."""
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        action = str(state["action"])
        minutes = int(state["time"])
        status = str(state["state"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""

    return f"{action}: {minutes}m ({status})"


class InstanceLock:
    """Own an advisory runtime lock for a running Pomlock process."""

    def __init__(self, path: Path | None = None):
        self._path = path or runtime_lock_path()
        self._file: Any = None
        self.pid = os.getpid()

    def acquire(self) -> bool:
        """Acquire the lock and publish the owner PID."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._path.open("a+", encoding="utf-8")

        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._file.close()
            self._file = None
            return False

        metadata = json.dumps({"pid": self.pid})
        self._file.seek(0)
        self._file.truncate()
        self._file.write(metadata)
        self._file.flush()
        os.fchmod(self._file.fileno(), LOCK_MODE)
        return True

    def release(self) -> None:
        """Release the lock owned by this process."""
        if self._file is None:
            return

        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None

    def owner_pid(self) -> int | None:
        """Read the current owner's PID from the lock metadata."""
        try:
            metadata = json.loads(self._path.read_text(encoding="utf-8"))
            return int(metadata["pid"])
        except (OSError, ValueError, KeyError, TypeError):
            return None


def focus_terminal(owner_pid: int | None) -> bool:
    """Focus a terminal window belonging to the owner process."""
    if owner_pid is None:
        return False

    pids = _parent_pids(owner_pid)
    return _focus_hyprland(pids) or _focus_x11(pids)


def _parent_pids(pid: int) -> list[int]:
    """Return a process and its ancestors for terminal-window matching."""
    pids: list[int] = []
    current_pid = pid

    while current_pid > 1:
        pids.append(current_pid)
        parent_pid = _parent_pid(current_pid)
        if parent_pid is None or parent_pid == current_pid:
            break
        current_pid = parent_pid

    return pids


def _parent_pid(pid: int) -> int | None:
    """Read a process parent PID from procfs."""
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None

    return None


def _focus_hyprland(pids: list[int]) -> bool:
    """Focus a matching Hyprland client when available."""
    if shutil.which("hyprctl") is None:
        return False

    try:
        clients = json.loads(_run("hyprctl", "clients", "-j"))
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return False

    for client in clients:
        if client.get("pid") not in pids:
            continue

        address = client.get("address")
        if not address:
            continue

        try:
            _run("hyprctl", "dispatch", "focuswindow", f"address:{address}")
            return True
        except subprocess.CalledProcessError:
            return False

    return False


def _focus_x11(pids: list[int]) -> bool:
    """Focus a matching X11 window when xdotool is available."""
    if shutil.which("xdotool") is None:
        return False

    for pid in pids:
        try:
            window_ids = _run("xdotool", "search", "--pid", str(pid)).splitlines()
        except subprocess.CalledProcessError:
            continue

        if not window_ids:
            continue

        try:
            _run("xdotool", "windowactivate", "--sync", window_ids[0])
            return True
        except subprocess.CalledProcessError:
            return False

    return False


def _run(*command: str) -> str:
    """Run a window-manager command and return its standard output."""
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout
