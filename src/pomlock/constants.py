import os
from pathlib import Path

APP_NAME = "pomlock"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / APP_NAME
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / APP_NAME
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / f"{APP_NAME}.conf"
DEFAULT_LOG_FILE = DEFAULT_DATA_DIR / f"{APP_NAME}.log"
STATE_FILE = Path(f"/tmp/{APP_NAME}.json")
SESSION_TYPE = os.environ.get('XDG_SESSION_TYPE', 'x11')

# Linux evdev ioctl constants
EVIOCGRAB = 0x40044590
PROC_BUS_INPUT_DEVICES = Path("/proc/bus/input/devices")

# Device filter keywords
IGNORE_DEVICE_KEYWORDS = (
    "power", "sleep", "lid", "video", "webcam",
    "headset", "headphone", "speaker", "audio", "mic", "sound",
    "hda", "hdmi", "displayport", "jack", "rfkill",
    "consumer control", "system control", "extra buttons", "avrcp",
)
