#!/usr/bin/env python3

import os
from pathlib import Path
import argparse

APP_NAME = "pomlock"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / APP_NAME
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / APP_NAME
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / f"{APP_NAME}.conf"
DEFAULT_LOG_FILE = DEFAULT_DATA_DIR / f"{APP_NAME}.log"
STATE_FILE = Path(f"/tmp/{APP_NAME}.json")
SESSION_TYPE = os.environ.get('XDG_SESSION_TYPE', 'x11')

# --- Argument and Configuration Single Source of Truth ---
# This dictionary drives the entire settings system:
# - 'group': Maps the setting to a section in the .config config file.
# - 'default': The ultimate fallback value.
# - 'type', 'action', 'help': Used to dynamically build the argparse parser.
# - 'short', 'long': The command-line flags.
ARGUMENTS_CONFIG = {
    # Pomodoro Timer Settings
    'timer': {
        'group': 'pomodoro',
        'default': 'standard',
        'type': str,
        'short': '-t',
        'long': '--timer',
        'help': """Set a timer preset or custom values: 'POMODORO SHORT_BREAK LONG_BREAK CYCLES'.
                 Example: --timer "25 5 15 4"."""
    },
    'pomodoro': {
        'group': 'pomodoro',
        'default': 25,
        'type': int,
        'short': '-p',
        'long': '--pomodoro',
        'help': "Interval of work time in minutes."
    },
    'short_break': {
        'group': 'pomodoro',
        'default': 5,
        'type': int,
        'short': '-s',
        'long': '--short-break', 'help': "Short break duration in minutes."
    },
    'long_break': {
        'group': 'pomodoro',
        'default': 20,
        'type': int,
        'short': '-l',
        'long': '--long-break',
        'help': "Long break duration in minutes."
    },
    'cycles': {
        'group': 'pomodoro',
        'default': 4,
        'type': int,
        'short': '-c',
        'long': '--cycles',
        'help': "Cycles before a long break."
    },
    'block_input': {
        'group': 'pomodoro',
        'default': True,
        'long': '--block-input',
        'action': argparse.BooleanOptionalAction,
        'help': "Enable/disable keyboard/mouse input during break."
    },
    'overlay': {
        'group': 'pomodoro',
        'default': True,
        'long': '--overlay',
        'action': argparse.BooleanOptionalAction,
        'help': "Enable/disable overlay break window."
    },
    'notify': {
        'group': 'pomodoro',
        'default': True,
        'long': '--notify',
        'action': argparse.BooleanOptionalAction,
        'help': "Enable/disable desktop notificatios."
    },
    'break_notify_msg': {
        'group': 'pomodoro',
        'default': 'Time for a break!',
        'type': str,
        'long': '--break-notify-msg',
        'help': "Message for break notifications."
    },
    'long_break_notify_msg': {
        'group': 'pomodoro',
        'default': 'Time for a long break!',
        'type': str,
        'long': '--long-break-notify-msg',
        'help': "Message for long break notifications."
    },
    'pomo_notify_msg': {
        'group': 'pomodoro',
        'default': 'Time for a pomodoro!',
        'type': str,
        'long': '--pomo-notify-msg',
        'help': "Message for pomodoro notifications."
    },
    'callback': {
        'group': 'pomodoro',
        'default': '',
        'type': str,
        'long': '--callback',
        'help': "Script to call for pomodoro and break events."
    },
    # Overlay Settings
    'overlay_font_size': {
        'group': 'overlay_opts',
        'default': 48,
        'type': int,
        'long': '--overlay-font-size',
        'help': "Font size for overlay timer."
    },
    'overlay_color': {
        'group': 'overlay_opts',
        'default': 'white',
        'type': str,
        'long': '--overlay-color',
        'help': "Text color for overlay (e.g., 'white', '#FF0000')."
    },
    'overlay_bg_color': {
        'group': 'overlay_opts',
        'default': 'black',
        'type': str,
        'long': '--overlay-bg-color',
        'help': "Background color for overlay."
    },
    'overlay_opacity': {
        'group': 'overlay_opts',
        'default': 0.8,
        'type': float,
        'long': '--overlay-opacity',
        'help': "Opacity for overlay (0.0 to 1.0)."
    },
    'show_presets': {
        'long': '--show-presets',
        'action': 'store_true',
        'default': False,
        'help': 'Show presets and exit.'
    },
    # Presets - not a CLI arg, but part of config
    'presets': {
        'group': 'presets',
        'default': {
            "standard": "25 5 20 4",
            "ultradian": "90 20 20 1",
            "fifty_ten": "50 10 10 1"
        }
    }
}
