#!/usr/bin/env python3

# Standard library imports
# For parsing command-line arguments (e.g., --help, --work-duration)
import argparse
import configparser     # For reading configuration from .ini style files
import logging          # For creating log messages
import re               # For regular expressions, used here to parse xinput output
# For safely splitting shell-like command strings (used for overlay_opts)
# For running external commands (like xinput, notify-send)
import subprocess
# For system-specific parameters and functions (e.g., sys.argv, sys.exit)
import sys
import time             # For time-related functions, especially time.sleep()
# For object-oriented path manipulation (makes handling file paths cleaner)
from pathlib import Path

# Third-party library import (standard with Python, but often considered separate for GUIs)
# For creating the graphical user interface (GUI) overlay
import tkinter as tk
from tkinter import font  # Specifically for font management in Tkinter

# --- Application Constants and Default Configuration ---
APP_NAME = "pomlock"
# Pathlib makes it easy to construct paths relative to the user's home directory
DEFAULT_CONFIG_DIR = Path.home() / ".config" / APP_NAME
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / APP_NAME
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / f"{APP_NAME}.conf"
DEFAULT_LOG_FILE = DEFAULT_DATA_DIR / f"{APP_NAME}.log"

# Default Pomodoro settings. These are used if no config file is found or specific settings are missing.
DEFAULT_SETTINGS = {
    "timer": "standard",
    "work_duration": 25,    # minutes
    "short_break": 5,       # minutes
    "long_break": 20,       # minutes
    "cycles_before_long": 4,
    "enable_input_during_break": False,  # If True, keyboard/mouse won't be disabled
    # Default options for the overlay window. These are passed to the overlay function.
    "overlay_opts": {
        'font_size': 48,
        'color': 'white',
        'bg_color': 'black',
        'opacity': 0.8,
        'notify': True,
        'notify_msg': 'Time for a break!'
    },
    "presets": {
        "standard": "25 5 20 4",
        "extended": "40 10 20 3"
    }
}

config = {}

# --- Logging Setup ---
# Get a logger instance for this application. It's good practice to name loggers.
logger = logging.getLogger(APP_NAME)


def setup_logging(log_file_path_str: str, verbose: bool):
    """
    Configures the logging system for the application.
    Logs will go to a file and, if verbose, to the console with more detail.
    """
    log_file_path = Path(log_file_path_str)
    # Ensure the directory for the log file exists
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Define the format for log messages
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # File Handler: Writes log messages to the specified log file
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler: Writes log messages to the standard output (terminal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    # Set logging level for console based on verbosity
    if verbose:
        console_handler.setLevel(logging.DEBUG)  # Show detailed debug messages
    else:
        # Show informational messages and above
        console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # Set the overall logging level for the logger.
    # Handlers can have their own stricter levels, but they won't receive messages below this.
    logger.setLevel(logging.DEBUG)


def log_event(event_type: str, duration_minutes: int = 0, cycle_count: int = -1):
    """
    Logs a Pomodoro event.
    This function is a simplified way to log common events with consistent formatting.
    """
    # Constructing the message parts conditionally
    message_parts = [event_type]
    if duration_minutes > 0:
        message_parts.append(f"(Duration: {duration_minutes}m)")
    if cycle_count != -1:
        message_parts.append(f"(Cycle: {cycle_count})")

    logger.info(" ".join(message_parts))


# --- XInput Device Control ---
# These are regular expressions (re) used to find keyboard and mouse device IDs from `xinput list` output.
# `re.compile` pre-compiles the pattern for efficiency if used multiple times.
# `re.IGNORECASE` makes the matching case-insensitive.
# The `(\d+)` part is a capturing group that extracts the device ID.

# Pattern to find ENABLED (active slave) keyboards/mice to disable them
KBD_ENABLED_PATTERN = re.compile(
    r'.*↳.*(?:AT Translated Set 2 keyboard|SONiX USB DEVICE|SONiX USB DEVICE Keyboard)\s*id=(\d+)\s*\[slave\s*keyboard\s*\(\d+\)\]',
    re.IGNORECASE
)
MOUSE_ENABLED_PATTERN = re.compile(
    r'.*↳.*(?:Mouse|Trackpad|TouchPad)\s*id=(\d+)\s*\[slave\s*pointer\s*\(\d+\)\]',
    re.IGNORECASE
)

# Pattern to find DISABLED (floating slave) keyboards/mice to enable them
KBD_DISABLED_PATTERN = re.compile(
    r'.*(?:AT Translated Set 2 keyboard|SONiX USB DEVICE|SONiX USB DEVICE Keyboard)\s*id=(\d+)\s*\[floating\s*slave\]', re.IGNORECASE)
MOUSE_DISABLED_PATTERN = re.compile(
    r'.*(?:Mouse|Trackpad|TouchPad)\s*id=(\d+)\s*\[floating\s*slave\]', re.IGNORECASE)


def _get_xinput_ids(pattern: re.Pattern) -> list[str]:
    """
    Runs `xinput list` and parses its output using the given regex pattern
    to find device IDs.
    Returns a list of found device ID strings.
    """
    ids = []
    try:
        # `subprocess.run()` executes an external command.
        # `capture_output=True` gets stdout/stderr.
        # `text=True` decodes output as text.
        # `check=True` raises an exception if the command fails (non-zero exit code).
        result = subprocess.run(
            ['xinput', 'list'], capture_output=True, text=True, check=True)
        # Iterate over each line of the `xinput list` output
        for line in result.stdout.splitlines():
            # Try to find a match for the pattern in the line
            match = pattern.search(line)
            if match:
                # `group(1)` is the first captured group (the ID)
                ids.append(match.group(1))
    except FileNotFoundError:
        logger.error(
            "xinput command not found. Please ensure it's installed and in your PATH.")
    except subprocess.CalledProcessError as e:
        logger.error(f"xinput list failed: {e.stderr or e.stdout or e}")
    return ids


def _set_device_state(device_ids: list[str], action: str):
    """
    Enables or disables a list of XInput devices by their IDs.
    `action` should be 'enable' or 'disable'.
    """
    if not device_ids:
        logger.debug(f"No device IDs found to {action}.")
        return
    for device_id in device_ids:
        try:
            logger.info(f"{action.capitalize()}ing device ID: {device_id}")
            subprocess.run(['xinput', action, device_id],
                           check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to {action} device {
                         device_id}: {e.stderr or e.stdout or e}")
        except FileNotFoundError:
            logger.error(
                "xinput command not found. Cannot change device state.")
            break  # Stop trying if xinput isn't there


def disable_input_devices():
    """Disables keyboards and mice found by xinput."""
    logger.info("Disabling input devices...")
    # Get IDs of currently enabled keyboards and mice
    kbd_ids = _get_xinput_ids(KBD_ENABLED_PATTERN)
    mouse_ids = _get_xinput_ids(MOUSE_ENABLED_PATTERN)

    if kbd_ids:
        _set_device_state(kbd_ids, "disable")
    else:
        logger.debug("No enabled keyboards found to disable.")

    if mouse_ids:
        _set_device_state(mouse_ids, "disable")
    else:
        logger.debug("No enabled mice/trackpads found to disable.")


def enable_input_devices():
    """Enables keyboards and mice found by xinput."""
    logger.info("Enabling input devices...")
    # Get IDs of currently disabled keyboards and mice
    kbd_ids = _get_xinput_ids(KBD_DISABLED_PATTERN)
    mouse_ids = _get_xinput_ids(MOUSE_DISABLED_PATTERN)

    if kbd_ids:
        _set_device_state(kbd_ids, "enable")
    else:
        logger.debug("No disabled keyboards found to enable.")

    if mouse_ids:
        _set_device_state(mouse_ids, "enable")
    else:
        logger.debug("No disabled mice/trackpads found to enable.")

# --- Configuration Loading ---


def load_configuration(config_file_path_str: str = DEFAULT_CONFIG_FILE) -> dict:
    """
    Loads configuration from an .ini file.
    Starts with DEFAULT_SETTINGS and overrides them with values from the file.
    """
    # Start with a copy of the default settings
    settings = {
        "timer": DEFAULT_SETTINGS["timer"],
        "work_duration": DEFAULT_SETTINGS["work_duration"],
        "short_break": DEFAULT_SETTINGS["short_break"],
        "long_break": DEFAULT_SETTINGS["long_break"],
        "cycles_before_long": DEFAULT_SETTINGS["cycles_before_long"],
        "enable_input_during_break": DEFAULT_SETTINGS["enable_input_during_break"],
        # Important to copy nested dicts
        "overlay_opts": DEFAULT_SETTINGS["overlay_opts"].copy(),
        "presets": DEFAULT_SETTINGS["presets"].copy()
    }

    config_file_path = Path(config_file_path_str)

    if not config_file_path.exists():
        # Ensure default dir exists for user
        DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Ensure default dir exists for user
        DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading configuration from {config_file_path}")
    # `configparser.ConfigParser()` is the class to read .ini files
    parser = configparser.ConfigParser()
    try:
        parser.read(config_file_path)
    except configparser.Error as e:
        logger.error(f"Error reading config file {
                     config_file_path}: {e}. Using defaults.")
        return settings

    # Read values from the '[pomodoro]' section
    if 'pomodoro' in parser:
        pom_config = parser['pomodoro']
        # `pom_config.getint/getboolean/get` safely retrieves values, falling back to current `settings` value if key is missing
        settings['timer'] = pom_config.get(
            'timer', settings['timer'])
        settings['work_duration'] = pom_config.getint(
            'work_duration', settings['work_duration'])
        settings['short_break'] = pom_config.getint(
            'short_break', settings['short_break'])
        settings['long_break'] = pom_config.getint(
            'long_break', settings['long_break'])
        settings['cycles_before_long'] = pom_config.getint(
            'cycles_before_long', settings['cycles_before_long'])
        settings['enable_input_during_break'] = pom_config.getboolean(
            'enable_input_during_break', settings['enable_input_during_break'])

    # Read values from the '[overlay]' section for overlay options
    if 'overlay' in parser:
        overlay_config = parser['overlay']
        # Iterate over known overlay options and update them if present in the config file
        for key in settings['overlay_opts']:
            if key in overlay_config:
                if isinstance(settings['overlay_opts'][key], bool):
                    settings['overlay_opts'][key] = overlay_config.getboolean(
                        key, settings['overlay_opts'][key])
                elif isinstance(settings['overlay_opts'][key], int):
                    settings['overlay_opts'][key] = overlay_config.getint(
                        key, settings['overlay_opts'][key])
                elif isinstance(settings['overlay_opts'][key], float):
                    settings['overlay_opts'][key] = overlay_config.getfloat(
                        key, settings['overlay_opts'][key])
                else:  # string
                    settings['overlay_opts'][key] = overlay_config.get(
                        key, settings['overlay_opts'][key])

    # Presets can also be in config, allowing users to define their own
    if 'presets' in parser:
        for name, value in parser['presets'].items():
            settings['presets'][name.lower()] = value
            logger.debug(f"Loaded preset '{name}' from config: {value}")
    return settings


# --- Overlay Display Logic (formerly pomlock-overlay.py) ---
def show_break_overlay(duration_seconds: int, overlay_config: dict):
    """
    Displays a full-screen overlay for the break duration.
    `overlay_config` is a dictionary with keys like 'font_size', 'color', etc.
    """
    if overlay_config.get('notify', False):
        try:
            # `subprocess.Popen` starts a command in the background (non-blocking)
            subprocess.Popen(
                ['notify-send', overlay_config.get('notify_msg', 'Time for a break!')])
        except FileNotFoundError:
            logger.warning(
                "notify-send command not found. Cannot send desktop notification.")
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")

    # --- Tkinter GUI Setup ---
    # `tk.Tk()` creates the main window (root) of the Tkinter application.
    root = tk.Tk()
    # Set window title (may not be visible in fullscreen)
    root.title("Pomlock Break")

    # Configure root window attributes
    root.attributes('-fullscreen', True)    # Make the window fullscreen
    # Set transparency
    root.attributes('-alpha', overlay_config.get('opacity', 0.8))
    root.configure(background=overlay_config.get(
        'bg_color', 'black'))  # Set background color
    # Keep the window on top of all others
    root.attributes('-topmost', True)

    root.focus_force()  # Try to force focus to this window
    root.config(cursor="none")  # Hide the mouse cursor over the window

    # Setup font for the timer display
    try:
        label_font = font.Font(family="Helvetica", size=int(
            overlay_config.get('font_size', 48)))
    except tk.TclError:  # Handle cases where font might not be available
        logger.warning(
            "Helvetica font not found or invalid size. Using default.")
        label_font = font.Font(family="Arial", size=36)  # Fallback font

    # `tk.Label` is a widget to display text or images.
    timer_label = tk.Label(root, text="",
                           fg=overlay_config.get('color', 'white'),
                           bg=overlay_config.get('bg_color', 'black'),
                           font=label_font)
    # `pack()` is a geometry manager that arranges widgets in blocks.
    # `expand=True` makes the label fill available space.
    timer_label.pack(expand=True)

    start_time = time.time()  # Record the time the overlay starts

    def update_timer_display():
        """Updates the timer text on the overlay."""
        nonlocal root  # Allow modification of root if needed (e.g. root.destroy)
        elapsed_time = time.time() - start_time
        remaining_seconds = duration_seconds - elapsed_time

        if remaining_seconds <= 0:
            root.destroy()  # Close the Tkinter window, which also ends root.mainloop()
            return

        # `divmod` returns quotient and remainder (minutes, seconds)
        mins, secs = divmod(int(remaining_seconds), 60)
        # Update the label text with formatted time
        timer_label.config(text=f"BREAK TIME\n{mins:02d}:{secs:02d}")

        # `root.after(milliseconds, function)` schedules `function` to be called
        # after `milliseconds`. This creates the 1-second update cycle.
        root.after(1000, update_timer_display)

    def on_key_press(event):
        """Handles key presses (e.g., Esc to close early)."""
        if event.keysym == 'Escape' or event.keysym == 'q':
            logger.info("Overlay closed by user (Esc/q).")
            root.destroy()

    # Bind key press events to the on_key_press function
    root.bind("<KeyPress>", on_key_press)

    update_timer_display()  # Start the timer update loop
    # `root.mainloop()` starts the Tkinter event loop.
    # It listens for events (mouse clicks, key presses, window events) and
    # processes them. This call BLOCKS until `root.destroy()` is called.
    root.mainloop()
    logger.debug("Overlay mainloop finished.")


# --- Main Application Logic ---
def run_pomodoro(config: dict):
    """
    The main Pomodoro timer loop.
    `config` is the fully resolved configuration dictionary.
    """
    work_duration_m = config['work_duration']
    short_break_m = config['short_break']
    long_break_m = config['long_break']
    cycles_before_long = config['cycles_before_long']
    enable_input_during_break = config['enable_input_during_break']
    overlay_config = config['overlay_opts']  # This is now a dictionary

    log_event(f"Session started - Work: {work_duration_m}m, Short Break: {
              short_break_m}m, Long Break: {long_break_m}m, Cycles: {cycles_before_long}")

    cycle_count = 0
    try:
        while True:
            # --- Work Period ---
            logger.info(f"Work period started ({work_duration_m} minutes).")
            # `time.sleep()` pauses execution for the given number of seconds.
            time.sleep(work_duration_m * 60)  # Convert minutes to seconds
            log_event("Work period completed", duration_minutes=work_duration_m,
                      cycle_count=cycle_count + 1)  # +1 because cycle_count updates after

            # --- Break Logic ---
            cycle_count += 1
            if cycle_count >= cycles_before_long:
                break_duration_m = long_break_m
                current_break_type = "Long break"
                log_event("Long break started",
                          duration_minutes=break_duration_m, cycle_count=cycle_count)
                cycle_count = 0  # Reset for next long break cycle
            else:
                break_duration_m = short_break_m
                current_break_type = "Short break"
                log_event("Short break started",
                          duration_minutes=break_duration_m, cycle_count=cycle_count)

            break_duration_s = break_duration_m * 60

            # Block input (if configured) and show overlay
            # TODO: uncomment
            # if not enable_input_during_break:
            #     disable_input_devices()

            logger.info(f"{current_break_type} overlay starting ({
                        break_duration_m} minutes).")
            # Call the overlay function
            show_break_overlay(break_duration_s, overlay_config)

            logger.info(f"{current_break_type} completed.")
            # Log cycle count relevant to the *end* of the break
            log_event("Break completed", cycle_count=(
                cycle_count if cycle_count != 0 else cycles_before_long))

            # Restore input (if it was disabled)
            # TODO: uncomment
            # if not enable_input_during_break:
            #     enable_input_devices()

    except KeyboardInterrupt:  # Handle Ctrl+C gracefully
        logger.info("Pomodoro session interrupted by user. Exiting.")
    finally:
        # This `finally` block ensures that input devices are re-enabled
        # if the script exits for any reason (Ctrl+C, error, etc.),
        # provided they were being managed by the script.
        if not config.get('enable_input_during_break', False):  # Check config again
            logger.info("Ensuring input devices are enabled on exit...")
            enable_input_devices()
        log_event("Session ended")


def main():
    # --- Step 0: Argument Parsing using argparse ---
    # `argparse.ArgumentParser` is the main class for handling command-line arguments.
    # `description` is shown in the --help message.
    parser = argparse.ArgumentParser(
        description=f"A Pomodoro timer with input locking. Uses '{
            DEFAULT_CONFIG_FILE}' and logs to '{DEFAULT_LOG_FILE}'.",
        # Shows default values in help
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    default_presets = load_configuration()['presets']

    # Define command-line arguments the script can accept.
    # `add_argument` defines each one.
    # `-c` or `--config-file`
    parser.add_argument("-c", "--config-file", type=str, default=str(DEFAULT_CONFIG_FILE),
                        help="Path to configuration file.")
    parser.add_argument("-l", "--log-file", type=str,  # Default is set after config load
                        help="Path to log file.")

    # Pomodoro timing arguments (these override config file settings)
    parser.add_argument("--timer", "-t", type=str, choices=list(default_presets.keys()),  # Restrict choices or allow custom
                        help="""Set a timer configuration. Choose from presets (e.g., 'standard', 'extended') or provide custom space-separated values: 'WORK_DURATION SHORT_BREAK_DURATION LONG_BREAK_DURATION CYCLES_BEFORE_LONG'.
                        Example custom: '25 5 15 4' for 25m work, 5m short break, 15m long break, 4 cycles.""")
    parser.add_argument("--work-duration", type=int,
                        help="Work duration in minutes.")
    parser.add_argument("--short-break", type=int,
                        help="Short break duration in minutes.")
    parser.add_argument("--long-break", type=int,
                        help="Long break duration in minutes.")
    parser.add_argument("--cycles-before-long", type=int,
                        help="Cycles before a long break.")

    # Behavior arguments
    parser.add_argument("--enable-input-during-break", action=argparse.BooleanOptionalAction,
                        help="Enable/disable keyboard/mouse input during break time (overrides config).")

    # Overlay specific arguments (these override config file overlay settings)
    parser.add_argument("--overlay-font-size", type=int,
                        help="Font size for overlay timer.")
    parser.add_argument("--overlay-color", type=str,
                        help="Text color for overlay (e.g., 'white', '#FF0000').")
    parser.add_argument("--overlay-bg-color", type=str,
                        help="Background color for overlay.")
    parser.add_argument("--overlay-opacity", type=float,
                        help="Opacity for overlay (0.0 to 1.0).")
    parser.add_argument("--overlay-notify", action=argparse.BooleanOptionalAction,  # Allows --overlay-notify / --no-overlay-notify
                        help="Enable/disable desktop notification for breaks.")
    parser.add_argument("--overlay-notify-msg", type=str,
                        help="Custom message for desktop notification.")

    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose output to console.")

    # `parser.parse_args()` reads arguments from `sys.argv` and returns an object
    args = parser.parse_args()

    # --- Step 1: Load configuration from file ---
    # The config file path itself can be an argument.
    config = load_configuration(args.config_file)

    # --- Step 2: Setup Logging ---
    # Log file path can be default, from config, or from CLI argument. CLI takes precedence.
    log_file_path = args.log_file if args.log_file else config.get(
        'log_file_path', str(DEFAULT_LOG_FILE))
    config['log_file_path'] = log_file_path
    setup_logging(log_file_path, args.verbose)  # Initialize logging

    logger.debug(f"Initial configuration loaded from file: {config}")
    logger.debug(f"Command line arguments received: {vars(args)}")

    # --- Step 3: Override config with command-line arguments ---
    # If a CLI argument is provided, it overrides the value from the config file.
    if args.timer is not None:
        config['timer'] = args.timer
    if args.work_duration is not None:
        config['work_duration'] = args.work_duration
    if args.short_break is not None:
        config['short_break'] = args.short_break
    if args.long_break is not None:
        config['long_break'] = args.long_break
    if args.cycles_before_long is not None:
        config['cycles_before_long'] = args.cycles_before_long

    # We check if '--enable-input-during-break' was used.
    if args.enable_input_during_break is not None:
        config['enable_input_during_break'] = args.enable_input_during_break

    # process timer setting
    if config['timer']:
        timer_values_str = None
        if config['timer'].lower() in config['presets']:
            timer_values_str = config['presets'][config['timer'].lower()]
            logger.info(f"Applying timer preset '{
                        config['timer']}': {timer_values_str}")
        else:
            timer_values_str = config['timer']
            logger.info(f"Applying custom timer settings: '{
                        timer_values_str}'")

        if timer_values_str:
            try:
                values = [int(v) for v in timer_values_str.split()]
                if len(values) == 4:
                    config['work_duration'], config['short_break'], config['long_break'], config['cycles_before_long'] = values
                else:
                    logger.warning(f"Invalid timer format '{
                                   timer_values_str}'. Expected 4 numbers. Using previous settings.")
            except ValueError:
                logger.warning(f"Invalid numbers in timer '{
                               timer_values_str}'. Using previous settings.")

    # Override overlay options from CLI
    if args.overlay_font_size is not None:
        config['overlay_opts']['font_size'] = args.overlay_font_size
    if args.overlay_color is not None:
        config['overlay_opts']['color'] = args.overlay_color
    if args.overlay_bg_color is not None:
        config['overlay_opts']['bg_color'] = args.overlay_bg_color
    if args.overlay_opacity is not None:
        config['overlay_opts']['opacity'] = args.overlay_opacity
    if args.overlay_notify is not None:
        # BooleanOptionalAction
        config['overlay_opts']['notify'] = args.overlay_notify
    if args.overlay_notify_msg is not None:
        config['overlay_opts']['notify_msg'] = args.overlay_notify_msg

    logger.info(f"Effective configuration after CLI overrides: {config}")

    # Validate durations and cycles (must be positive integers)
    for key in ['work_duration', 'short_break', 'long_break', 'cycles_before_long']:
        if not (isinstance(config.get(key), int) and config.get(key, 0) > 0):
            logger.error(f"{key.replace('_', ' ').capitalize(
            )} must be a positive integer. Current value: {config.get(key)}. Exiting.")
            sys.exit(1)
    if not (0.0 <= config['overlay_opts'].get('opacity', 0.8) <= 1.0):
        logger.error(f"Overlay opacity must be between 0.0 and 1.0. Current value: {
                     config['overlay_opts']['opacity']}. Exiting.")
        sys.exit(1)

    # --- Step 4: Run the Pomodoro logic ---
    run_pomodoro(config)


if __name__ == "__main__":
    # This block ensures `main()` is called only when the script is executed directly
    # (not when imported as a module).
    main()
