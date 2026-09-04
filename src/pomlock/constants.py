from enum import Enum
import os
from pathlib import Path

APP_NAME = "pomlock"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / APP_NAME
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / APP_NAME
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / f"{APP_NAME}.conf"
DEFAULT_LOG_FILE = DEFAULT_DATA_DIR / f"{APP_NAME}.log"
DEFAULT_CSV_FILE = DEFAULT_DATA_DIR / "history.csv"
DEFAULT_DB_FILE = DEFAULT_DATA_DIR / "pomlock.db"
STATE_FILE = Path(f"/tmp/{APP_NAME}.json")
SESSION_TYPE = os.environ.get("XDG_SESSION_TYPE", "x11")


class GoalPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


WORK_DAYS_PER_WEEK = 5
WORK_DAYS_PER_MONTH = 22
WORK_DAYS_PER_YEAR = 260


class SessionKind(str, Enum):
    POMODORO = "pomodoro"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


class TimerState(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class StatsView(str, Enum):
    TODAY = "today"
    WEEK = "this week"
    MONTH = "this month"
    YEAR = "this year"


# Linux evdev ioctl constants
EVIOCGRAB = 0x40044590
PROC_BUS_INPUT_DEVICES = Path("/proc/bus/input/devices")

# Device filter keywords
IGNORE_DEVICE_KEYWORDS = (
    "power",
    "sleep",
    "lid",
    "video",
    "webcam",
    "headset",
    "headphone",
    "speaker",
    "audio",
    "mic",
    "sound",
    "hda",
    "hdmi",
    "displayport",
    "jack",
    "rfkill",
    "consumer control",
    "system control",
    "extra buttons",
    "avrcp",
)

# Color mapping for activities in list & charts
ACTIVITY_COLORS = {
    "sleep": "bar-green",
    "coding": "bar-blue",
    "studying": "bar-yellow",
    "reading": "bar-pink",
    "anki": "bar-purple",
    "system": "bar-cyan",
    "exercise": "bar-red",
    "other": "bar-gray",
}

# Default daily goals in minutes
DEFAULT_GOALS = {
    "total": 420,  # 7h
    "coding": 240,  # 4h
    "reading": 40,  # 40m
}

# Goal widget UI indicators
ACTIVE_GOAL_INDICATOR = "●"
GOAL_COMPLETED_TEXT = "🎉 Goal Completed!"

# Fonts and overlay styling
DEFAULT_OVERLAY_ACCENT = "#b48ead"
DEFAULT_FONTS_DIR = Path(__file__).parent / "ui" / "fonts"
DSEG7_FONT_FILE = DEFAULT_FONTS_DIR / "DSEG7Classic-Bold.ttf"
