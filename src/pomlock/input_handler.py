import fcntl
import json
import os
import re
import subprocess
from enum import Enum
from pathlib import Path

from .constants import (
    EVIOCGRAB,
    IGNORE_DEVICE_KEYWORDS,
    PROC_BUS_INPUT_DEVICES,
    SESSION_TYPE,
)
from .logger import logger


class DeviceState(Enum):
    ENABLE = "enable"
    DISABLE = "disable"


class GrabAction(Enum):
    RELEASE = 0
    ACQUIRE = 1


# Active evdev descriptors: [(path, fd), ...]
_active_evdev_fds: list[tuple[str, int]] = []
_active_hypr_devs: list[str] = []


# --- Evdev Kernel Control ---

def get_input_devices() -> list[str]:
    """Parse /proc/bus/input/devices for keyboards, mice, and touchpads."""
    if not PROC_BUS_INPUT_DEVICES.exists():
        logger.debug(f"Input devices file not found: {PROC_BUS_INPUT_DEVICES}")
        return []

    try:
        with open(PROC_BUS_INPUT_DEVICES, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        logger.error(f"Failed to read {PROC_BUS_INPUT_DEVICES}: {e}")
        return []

    devices = []
    for section in content.strip().split("\n\n"):
        info = _parse_device_section(section)
        name = info.get("name", "").lower()

        if any(kw in name for kw in IGNORE_DEVICE_KEYWORDS):
            continue

        handlers = info.get("handlers", [])
        event_node = next((h for h in handlers if h.startswith("event")), None)
        if not event_node:
            continue

        is_pointer = any(h.startswith("mouse") or h.startswith("js") for h in handlers)
        is_keyboard = "kbd" in handlers

        if is_pointer or is_keyboard:
            devices.append(f"/dev/input/{event_node}")

    return devices


def _parse_device_section(section: str) -> dict:
    info = {}
    for line in section.splitlines():
        if line.startswith("N: Name="):
            info["name"] = line.split("=", 1)[1].strip('"')
        elif line.startswith("H: Handlers="):
            info["handlers"] = line.split("=", 1)[1].split()
    return info


def _grab_evdev(dev_path: str) -> int | None:
    try:
        fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
    except OSError as e:
        logger.debug(f"Cannot open device {dev_path}: {e}")
        return None

    try:
        fcntl.ioctl(fd, EVIOCGRAB, GrabAction.ACQUIRE.value)
        logger.debug(f"Grabbed evdev device: {dev_path}")
        return fd
    except OSError as e:
        logger.debug(f"Failed to grab {dev_path}: {e}")
        os.close(fd)
        return None


def _ungrab_evdev(dev_path: str, fd: int) -> None:
    try:
        fcntl.ioctl(fd, EVIOCGRAB, GrabAction.RELEASE.value)
    except OSError as e:
        logger.debug(f"Error ungrabbing {dev_path}: {e}")
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    logger.debug(f"Released evdev device: {dev_path}")


# --- Hyprland Fallback ---

def _get_hyprland_devices() -> list[str]:
    """Query hyprctl for keyboards, mice, and touchpads."""
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return []

    try:
        res = subprocess.run(
            ["hyprctl", "-j", "devices"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(res.stdout)
        names = []

        for category in ["mice", "keyboards", "touch"]:
            for item in data.get(category, []):
                name = item.get("name", "")
                if name and not any(kw in name.lower() for kw in IGNORE_DEVICE_KEYWORDS):
                    names.append(name)
        return names
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.debug(f"hyprctl devices query failed: {e}")
        return []


def _set_hypr_state(devices: list[str], state: DeviceState) -> None:
    enabled = "1" if state == DeviceState.ENABLE else "0"
    for dev in devices:
        try:
            subprocess.run(
                ["hyprctl", "keyword", f"device[{dev}]:enabled", enabled],
                capture_output=True,
                check=True,
            )
            logger.debug(f"Hyprland device {dev} -> enabled={enabled}")
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            logger.debug(f"Failed setting Hyprland state for {dev}: {e}")


# --- XInput Fallback ---

SLAVE_KBD_PATTERN = re.compile(r"↳(?!.*xtest).*id=(\d+).*slav[e\s]+keyboard", re.IGNORECASE)
SLAVE_POINTER_PATTERN = re.compile(r"↳(?!.*xtest).*id=(\d+).*slav[e\s]+pointer", re.IGNORECASE)
FLOATING_SLAVE_PATTERN = re.compile(r".*id=(\d+).*\[floating\s*slave\]", re.IGNORECASE)


def _get_xinput_ids(pattern: re.Pattern) -> list[str]:
    ids = []
    try:
        res = subprocess.run(["xinput", "list"], capture_output=True, text=True, check=True)
        for line in res.stdout.splitlines():
            m = pattern.search(line)
            if m:
                ids.append(m.group(1))
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        logger.debug(f"xinput query failed: {e}")
    return ids


def _set_xinput_state(device_ids: list[str], state: DeviceState) -> None:
    action = state.value
    for dev_id in device_ids:
        try:
            subprocess.run(["xinput", action, dev_id], capture_output=True, check=True)
            logger.debug(f"xinput device ID {dev_id} -> {action}")
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            logger.debug(f"Failed to {action} xinput device {dev_id}: {e}")


# --- Public Interface ---

def disable_input_devices() -> None:
    """Disable user keyboard and pointer input devices."""
    global _active_evdev_fds, _active_hypr_devs
    logger.debug(f"Disabling input devices ({SESSION_TYPE})...")

    # Step 1: Attempt direct kernel evdev grab
    devices = get_input_devices()
    for dev in devices:
        fd = _grab_evdev(dev)
        if fd is not None:
            _active_evdev_fds.append((dev, fd))

    if _active_evdev_fds:
        logger.info(f"Grabbed {len(_active_evdev_fds)} input device(s)")
        return

    # Step 2: Fallback to compositor/window manager specific controls
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        _active_hypr_devs = _get_hyprland_devices()
        if _active_hypr_devs:
            _set_hypr_state(_active_hypr_devs, DeviceState.DISABLE)
            logger.info(f"Disabled {len(_active_hypr_devs)} Hyprland device(s)")
            return

    if SESSION_TYPE == "x11":
        kbd_ids = _get_xinput_ids(SLAVE_KBD_PATTERN)
        ptr_ids = _get_xinput_ids(SLAVE_POINTER_PATTERN)
        _set_xinput_state(kbd_ids, DeviceState.DISABLE)
        _set_xinput_state(ptr_ids, DeviceState.DISABLE)


def enable_input_devices() -> None:
    """Re-enable user keyboard and pointer input devices."""
    global _active_evdev_fds, _active_hypr_devs
    logger.debug(f"Enabling input devices ({SESSION_TYPE})...")

    # Step 1: Release all grabbed evdev descriptors
    if _active_evdev_fds:
        for dev, fd in _active_evdev_fds:
            _ungrab_evdev(dev, fd)
        _active_evdev_fds = []

    # Step 2: Restore Hyprland devices
    if _active_hypr_devs:
        _set_hypr_state(_active_hypr_devs, DeviceState.ENABLE)
        _active_hypr_devs = []

    # Step 3: Restore X11 devices
    if SESSION_TYPE == "x11":
        float_ids = _get_xinput_ids(FLOATING_SLAVE_PATTERN)
        _set_xinput_state(float_ids, DeviceState.ENABLE)
