#!/usr/bin/env python3

import re
import subprocess

from logger import logger
from constants import SESSION_TYPE

# --- XInput Device Control ---
SLAVE_KBD_PATTERN = re.compile(
    r'↳(?!.*xtest).*id=(\d+).*slav[e\s]+keyboard', re.IGNORECASE)
SLAVE_POINTER_PATTERN = re.compile(
    r'↳(?!.*xtest).*id=(\d+).*slav[e\s]+pointer', re.IGNORECASE)
FLOATING_SLAVE_PATTERN = re.compile(
    r'.*id=(\d+).*\[floating\s*slave\]', re.IGNORECASE)


def _get_xinput_ids(pattern: re.Pattern) -> list[str]:
    ids = []
    try:
        result = subprocess.run(
            ['xinput', 'list'], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            match = pattern.search(line)
            if match:
                ids.append(match.group(1))
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        logger.error(f"xinput command failed: {e}")
    return ids


# --- libinput Device Control ---
def _get_wayland_input_devices() -> list[str]:
    """
    Get all keyboard and pointer event devices for Wayland, filtering out
    devices that are not primarily for user input, like power buttons,
    lid switches, and audio devices with media keys.
    """
    devices = []
    try:
        result = subprocess.run(
            ['pkexec', 'libinput', 'list-devices'],
            capture_output=True, text=True, check=True
        )

        device_blocks = result.stdout.strip().split('\n\n')

        # Keywords to identify devices to IGNORE.
        IGNORE_KEYWORDS = [
            "power", "sleep", "lid", "video", "webcam",
            "headset", "headphone", "speaker", "audio", "mic", "sound",
            "hda", "hdmi", "displayport", "jack",
            "consumer control", "system control", "extra buttons", "avrcp",
        ]

        for block in device_blocks:
            device_info = {}
            for line in block.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    device_info[key.strip()] = value.strip()

            device_name = device_info.get("Device", "").lower()
            capabilities = device_info.get("Capabilities", "")
            kernel_path = device_info.get("Kernel")

            if not kernel_path:
                continue

            if any(keyword in device_name for keyword in IGNORE_KEYWORDS):
                continue

            has_pointer = "pointer" in capabilities
            has_keyboard = "keyboard" in capabilities

            # if has_pointer or ('keyboard' in device_name and has_keyboard):
            if has_pointer or has_keyboard:
                devices.append(kernel_path)

    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        logger.debug(f"Failed to list libinput devices: {e}")

    return devices


def _set_device_state(device_ids: list[str], action: str):
    if not device_ids:
        return
    for device_id in device_ids:
        try:
            subprocess.run(['xinput', action, device_id],
                           check=True, capture_output=True)
            logger.debug(f"{action.capitalize()}d device ID: {device_id}")
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            logger.error(f"Failed to {action} device {device_id}: {e}")
            break


def disable_input_devices():
    logger.debug(f"Disabling input devices ({SESSION_TYPE})...")

    if SESSION_TYPE == 'wayland':
        devices = _get_wayland_input_devices()
        if not devices:
            logger.debug("No input devices found to disable.")
            return
        for device in devices:
            try:
                # Using Popen to run in the background
                subprocess.Popen(
                    ['pkexec', 'evtest', '--grab', device],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logger.debug(f"Disabling device: {device}")
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                logger.debug(f"Failed to disable device {device}: {e}")
    else:
        _set_device_state(_get_xinput_ids(SLAVE_KBD_PATTERN), "disable")
        _set_device_state(_get_xinput_ids(SLAVE_POINTER_PATTERN), "disable")
        return


def enable_input_devices():
    logger.debug(f"Enabling input devices ({SESSION_TYPE})...")

    if SESSION_TYPE == 'wayland':
        try:
            # Use pkill to kill all evtest processes
            subprocess.run(['pkexec', 'pkill', 'evtest'],
                           check=True, capture_output=True)
            logger.debug("Enabled all devices by killing evtest processes.")
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            logger.debug(f"Failed to enable devices: {e}")
    else:
        _set_device_state(_get_xinput_ids(FLOATING_SLAVE_PATTERN), "enable")
        return
