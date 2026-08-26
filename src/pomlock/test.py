#!/usr/bin/env python3


import subprocess
from time import sleep


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
        print(f"Failed to list libinput devices: {e}")

    return devices


def disable():
    devices = _get_wayland_input_devices()
    for device in devices:
        try:
            subprocess.Popen(
                ['pkexec', 'evtest', '--grab', device],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"Disabling device: {device}")
        except:
            pass


def enable():
    try:
        subprocess.run(['pkexec', 'pkill', 'evtest'],
                       check=True, capture_output=True)
    except:
        pass


disable()
sleep(60)
enable()
sleep(60)
disable()
