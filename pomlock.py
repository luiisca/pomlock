#!/usr/bin/env python3

# Standard library imports
import argparse
import configparser
import logging
import re
import subprocess
import sys
import time
from pathlib import Path
import tkinter as tk
from tkinter import font

# --- Application Constants ---
APP_NAME = "pomlock"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / APP_NAME
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / APP_NAME
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / f"{APP_NAME}.conf"
DEFAULT_LOG_FILE = DEFAULT_DATA_DIR / f"{APP_NAME}.log"

# --- Argument and Configuration Single Source of Truth ---
# This dictionary drives the entire configuration system:
# - 'group': Maps the setting to a section in the .config config file.
# - 'default': The ultimate fallback value.
# - 'type', 'action', 'help': Used to dynamically build the argparse parser.
# - 'short', 'long': The command-line flags.
ARGUMENT_CONFIG = {
    # Pomodoro Timer Settings
    'timer': {
        'group': 'pomodoro',
        'default': 'standard',
        'type': str,
        'short': '-t', 'long': '--timer',
        'help': """Set a timer preset or custom values: 'POMODORO SHORT_BREAK LONG_BREAK CYCLES'.
                 Example: --timer "25 5 15 4"."""
    },
    'pomodoro': {
        'group': 'pomodoro',
        'default': 25,
        'type': int,
        'long': '--pomodoro', 'help': "Interval of work time in minutes."
    },
    'short_break': {
        'group': 'pomodoro',
        'default': 5,
        'type': int,
        'long': '--short-break', 'help': "Short break duration in minutes."
    },
    'long_break': {
        'group': 'pomodoro',
        'default': 20,
        'type': int,
        'long': '--long-break', 'help': "Long break duration in minutes."
    },
    'cycles_before_long': {
        'group': 'pomodoro',
        'default': 4,
        'type': int,
        'long': '--cycles-before-long', 'help': "Cycles before a long break."
    },
    'enable_input_during_break': {
        'group': 'pomodoro',
        'default': False,
        'long': '--enable-input-during-break',
        'action': argparse.BooleanOptionalAction,
        'help': "Enable/disable keyboard/mouse input during break time."
    },
    # Overlay Settings
    'overlay_font_size': {
        'group': 'overlay',
        'default': 48,
        'type': int,
        'long': '--overlay-font-size',
        'help': "Font size for overlay timer."
    },
    'overlay_color': {
        'group': 'overlay',
        'default': 'white',
        'type': str,
        'long': '--overlay-color',
        'help': "Text color for overlay (e.g., 'white', '#FF0000')."
    },
    'overlay_bg_color': {
        'group': 'overlay',
        'default': 'black',
        'type': str,
        'long': '--overlay-bg-color',
        'help': "Background color for overlay."
    },
    'overlay_opacity': {
        'group': 'overlay',
        'default': 0.8,
        'type': float,
        'long': '--overlay-opacity',
        'help': "Opacity for overlay (0.0 to 1.0)."
    },
    'overlay_notify': {
        'group': 'overlay',
        'default': True,
        'long': '--overlay-notify',
        'action': argparse.BooleanOptionalAction,
        'help': "Enable/disable desktop notification for breaks."
    },
    'overlay_notify_msg': {
        'group': 'overlay',
        'default': 'Time for a break!',
        'type': str,
        'long': '--overlay-notify-msg',
        'help': "Custom message for desktop notification."
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


# --- Logging Setup ---
logger = logging.getLogger(APP_NAME)


def setup_logging(log_file_path_str: str, verbose: bool):
    log_file_path = Path(log_file_path_str)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # add file handler
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.addHandler(console_handler)

    logger.setLevel(logging.DEBUG)


def log_event(event_type: str, duration_minutes: int = 0, cycle_count: int = -1):
    message_parts = [event_type]
    if duration_minutes > 0:
        message_parts.append(f"(Duration: {duration_minutes}m)")
    if cycle_count != -1:
        message_parts.append(f"(Cycle: {cycle_count})")
    logger.info(" ".join(message_parts))


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
    logger.info("Disabling input devices...")
    _set_device_state(_get_xinput_ids(SLAVE_KBD_PATTERN), "disable")
    _set_device_state(_get_xinput_ids(SLAVE_POINTER_PATTERN), "disable")


def enable_input_devices():
    logger.info("Enabling input devices...")
    _set_device_state(_get_xinput_ids(FLOATING_SLAVE_PATTERN), "enable")


# --- Configuration Loading ---
def get_default_settings() -> dict:
    """Generates the default settings dictionary from the single source of truth."""
    defaults = {}
    # Create a nested dictionary for overlay options
    defaults['overlay'] = {}
    for key, config in ARGUMENT_CONFIG.items():
        if key.startswith('overlay_'):
            # Strip 'overlay_' prefix for the key inside overlay
            opt_key = key.replace('overlay_', '', 1)
            defaults['overlay'][opt_key] = config['default']
        else:
            defaults[key] = config['default']
    return defaults


def load_configuration(config_file_path_str: str) -> dict:
    """
    Loads configuration from a .config file, using ARGUMENT_CONFIG for defaults.
    """
    settings = get_default_settings()
    config_file_path = Path(config_file_path_str)

    if not config_file_path.exists():
        config_file_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Config file not found at {
                    config_file_path}. Using default settings.")
        return settings

    logger.info(f"Loading configuration from {config_file_path}")
    parser = configparser.ConfigParser()
    try:
        parser.read(config_file_path)
    except configparser.Error as e:
        logger.error(f"Error reading config file {
                     config_file_path}: {e}. Using defaults.")
        return settings

    # override default settings with config file
    for key, arg_config in ARGUMENT_CONFIG.items():
        group = arg_config.get('group')
        if not group or group not in parser:
            continue

        if group == 'presets':
            for name, value in parser['presets'].items():
                settings['presets'][name.lower()] = value
        elif key in parser[group]:
            # Determine the correct 'get' method based on the defined type
            value_type = arg_config.get('type', str)
            try:
                if value_type == int:
                    value = parser[group].getint(key)
                elif value_type == float:
                    value = parser[group].getfloat(key)
                elif arg_config.get('action') == argparse.BooleanOptionalAction:
                    value = parser[group].getboolean(key)
                else:
                    value = parser[group].get(key)

                # Place value in the correct part of the settings dict
                if key.startswith('overlay_'):
                    settings['overlay'][key.replace(
                        'overlay_', '', 1)] = value
                else:
                    settings[key] = value
            except (ValueError, configparser.NoOptionError) as e:
                logger.warning(f"Could not parse '{
                               key}' from config file: {e}. Using default.")

    return settings


# --- Overlay Display Logic ---
def show_break_overlay(duration_seconds: int, overlay_config: dict):
    if overlay_config.get('notify', False):
        try:
            subprocess.Popen(
                ['notify-send', overlay_config.get('notify_msg', 'Time for a break!')])
        except (FileNotFoundError, Exception) as e:
            logger.warning(f"Failed to send notification: {e}")

    root = tk.Tk()
    root.title("Pomlock Break")
    root.attributes('-fullscreen', True)
    root.attributes('-alpha', overlay_config.get('opacity', 0.8))
    root.configure(background=overlay_config.get('bg_color', 'black'))
    root.attributes('-topmost', True)
    root.focus_force()
    root.config(cursor="none")

    try:
        label_font = font.Font(family="Helvetica", size=int(
            overlay_config.get('font_size', 48)))
    except tk.TclError:
        logger.warning("Helvetica font not found. Using fallback.")
        label_font = font.Font(family="Arial", size=36)

    timer_label = tk.Label(root, text="",
                           fg=overlay_config.get('color', 'white'),
                           bg=overlay_config.get('bg_color', 'black'),
                           font=label_font)
    timer_label.pack(expand=True)

    start_time = time.time()

    def update_timer_display():
        remaining_seconds = duration_seconds - (time.time() - start_time)
        if remaining_seconds <= 0:
            root.destroy()
            return
        mins, secs = divmod(int(remaining_seconds), 60)
        timer_label.config(text=f"BREAK TIME\n{mins:02d}:{secs:02d}")
        root.after(1000, update_timer_display)

    def on_key_press(event):
        if event.keysym.lower() in ['escape', 'q']:
            logger.debug("Overlay closed by user.")
            root.destroy()

    root.bind("<KeyPress>", on_key_press)
    update_timer_display()
    root.mainloop()
    logger.debug("Overlay mainloop finished.")


# --- Main Application Logic ---
def run_pomodoro(config: dict):
    work_m = config['pomodoro']
    short_m = config['short_break']
    long_m = config['long_break']
    cycles_long = config['cycles_before_long']

    log_event(f"Session started - Work: {work_m}m, Short: {
              short_m}m, Long: {long_m}m, Cycles: {cycles_long}")

    cycle_count = 0
    try:
        while True:
            logger.info(f"Pomodoro started ({work_m} minutes).")
            time.sleep(work_m * 60)
            log_event("Pomodoro completed", work_m, cycle_count + 1)

            cycle_count += 1
            if cycle_count >= cycles_long:
                break_m, break_type = long_m, "Long break"
                log_event(break_type + " started", break_m, cycle_count)
                cycle_count = 0
            else:
                break_m, break_type = short_m, "Short break"
                log_event(break_type + " started", break_m, cycle_count)

            if not config['enable_input_during_break']:
                disable_input_devices()

            show_break_overlay(break_m * 60, config['overlay'])
            logger.info(f"{break_type} completed.")
            log_event(
                "Break completed", cycle_count=cycle_count if cycle_count != 0 else cycles_long)

            if not config['enable_input_during_break']:
                enable_input_devices()

    except KeyboardInterrupt:
        logger.info("Session interrupted by user. Exiting.")
    finally:
        if not config.get('enable_input_during_break', False):
            logger.info("Ensuring input devices are enabled on exit...")
            enable_input_devices()
        log_event("Session ended")


def main():
    user_provided_flags = {arg for arg in sys.argv[1:] if arg.startswith('-')}

    parser = argparse.ArgumentParser(
        description=f"A Pomodoro timer with input locking. Config: '{
            DEFAULT_CONFIG_FILE}', Log: '{DEFAULT_LOG_FILE}'.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # --- Dynamically build parser from ARGUMENT_CONFIG ---
    for dest, config in ARGUMENT_CONFIG.items():
        if 'long' not in config:
            continue  # Skip config-only entries like 'presets'

        names = [config['long']]
        if 'short' in config:
            names.append(config['short'])

        # Use **kwargs to unpack the dictionary of arguments into the function call
        kwargs = {'dest': dest,
                  'help': config['help'], 'default': config['default']}
        if 'type' in config:
            kwargs['type'] = config['type']
        if 'action' in config:
            kwargs['action'] = config['action']

        # Default is not set here so we can reliably detect if user provided the arg
        parser.add_argument(*names, **kwargs)

    # Add arguments not in the main config system
    parser.add_argument("-c", "--config-file", type=str,
                        default=str(DEFAULT_CONFIG_FILE), help="Path to configuration file.")
    parser.add_argument("-l", "--log-file", type=str,
                        default=str(DEFAULT_LOG_FILE), help="Path to log file.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose output to console.")

    args = parser.parse_args()

    # --- Settings layering: Defaults -> Config File -> CLI Args ---
    # 1. Load settings from config file (will include defaults where applicable)
    config = load_configuration(args.config_file)

    # 2. Setup logging
    setup_logging(args.log_file, args.verbose)
    logger.debug(f"User provided flags: {user_provided_flags}")
    logger.debug(f"Config after loading file: {config}")

    # 3. Override with any explicit CLI arguments
    for dest, arg_config in ARGUMENT_CONFIG.items():
        # Check if the long or short flag was passed by the user
        was_provided = arg_config.get('long') in user_provided_flags or \
            arg_config.get('short') in user_provided_flags

        if was_provided:
            value = getattr(args, dest)
            if dest.startswith('overlay_'):
                config['overlay'][dest.replace('overlay_', '', 1)] = value
            else:
                config[dest] = value
            logger.debug(f"CLI override: '{dest}' set to '{value}'")

    # --- Process complex settings like timer presets ---
    if config.get('timer'):
        timer_val = config['timer'].lower()
        timer_str = config['presets'].get(
            timer_val, timer_val if ' ' in timer_val else None)

        if timer_str:
            logger.debug(f"Applying timer setting: '{timer_str}'")
            try:
                values = [int(v) for v in timer_str.split()]
                if len(values) == 4:
                    config['pomodoro'], config['short_break'], config['long_break'], config['cycles_before_long'] = values
                else:
                    logger.warning(f"Invalid timer format '{
                                   timer_str}'. Expected 4 numbers.")
                    sys.exit(1)
            except ValueError:
                logger.warning(
                    f"Invalid numbers in timer string '{timer_str}'.")

    logger.debug(f"Effective configuration: {config}")

    # --- Final Validation ---
    for key in ['pomodoro', 'short_break', 'long_break', 'cycles_before_long']:
        if not (isinstance(config.get(key), int) and config.get(key, 0) > 0):
            logger.error(f"{key.replace('_', ' ').capitalize()
                            } must be a positive integer. Exiting.")
            sys.exit(1)
    if not (0.0 <= config['overlay'].get('opacity', 0.8) <= 1.0):
        logger.error(f"Overlay opacity must be between 0.0 and 1.0. Exiting.")
        sys.exit(1)

    print("final config", config)
    run_pomodoro(config)


if __name__ == "__main__":
    main()
