#!/usr/bin/env python3

import argparse
import configparser
import logging
import re
import subprocess
import sys
from time import sleep, time
from pathlib import Path
import tkinter as tk
from tkinter import font
from queue import Queue
from threading import Thread

from rich import print, rule
from rich.console import Group
from rich.live import Live
from rich.table import Table, Column
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
)
from rich.text import Text
from utils import plural
from custom_rich_handler import CustomRichHandler

APP_NAME = "pomlock"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / APP_NAME
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / APP_NAME
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / f"{APP_NAME}.conf"
DEFAULT_LOG_FILE = DEFAULT_DATA_DIR / f"{APP_NAME}.log"

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
logger.setLevel(logging.DEBUG)


class ExtraDataFormatter(logging.Formatter):
    def format(self, record):
        s = super().format(record)
        extra = {k: v for k, v in record.__dict__.items(
        ) if k not in logging.LogRecord.__dict__ and k not in ['message', 'asctime']}

        if hasattr(record, 'crr_cycle') and hasattr(record, 'cycles_total'):
            s += f" - Cycle: {record.crr_cycle}/{record.cycles_total}"
        if hasattr(record, 'minutes'):
            s += f" - Timer: {record.minutes} minutes"
        return s


def setup_logging(log_file_path_str: str, verbose: bool):
    log_file_path = Path(log_file_path_str)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    fh = logging.FileHandler(log_file_path)
    fh.setLevel(logging.DEBUG)

    rh = CustomRichHandler(
        rich_tracebacks=True,
        show_path=False,
        show_level=False,
        log_time_format='[%H:%M:%S]'
    )
    rh.setLevel(logging.DEBUG if verbose else logging.INFO)

    fh_formatter = ExtraDataFormatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    fh.setFormatter(fh_formatter)

    logger.addHandler(fh)
    logger.addHandler(rh)


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
    logger.debug("Disabling input devices...")
    _set_device_state(_get_xinput_ids(SLAVE_KBD_PATTERN), "disable")
    _set_device_state(_get_xinput_ids(SLAVE_POINTER_PATTERN), "disable")


def enable_input_devices():
    logger.debug("Enabling input devices...")
    _set_device_state(_get_xinput_ids(FLOATING_SLAVE_PATTERN), "enable")


# --- Configuration Loading ---
def get_default_settings() -> dict:
    """Generates the default settings dictionary from the single source of truth."""
    defaults = {}
    # Create a nested dictionary for overlay options
    defaults['overlay'] = {}
    for key, config in ARGUMENTS_CONFIG.items():
        if key.startswith('overlay_'):
            # Strip 'overlay_' prefix for the key inside overlay
            opt_key = key.replace('overlay_', '', 1)
            defaults['overlay'][opt_key] = config['default']
        else:
            defaults[key] = config['default']
    return defaults


class ConditionalCycleColumn(TextColumn):
    """A column that only displays cycle information if it's available."""

    def render(self, task) -> Text:
        if task.fields.get("crr_cycle") and task.fields.get("cycles_total"):
            return Text(f"{task.fields['crr_cycle']}/{task.fields['cycles_total']}")
        return Text("-", justify="center")


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.bind("<KeyPress>", self._on_key_press)
        self.mainloop_run = False
        self.queue = Queue()
        self.crr_cycle = 1
        self.crr_session = 1
        self.total_completed_sessions = 0

        self.flags, self.args = self.parse_args()
        self.settings = self.parse_config(self.flags, self.args)
        self.setup_overlay(self.settings)
        self.timer_label = self.setup_overlay_timer_label(self.settings)

        Thread(target=self.run_pomodoro, kwargs={
               "config": self.settings}, daemon=True).start()

        self.update_overlay_window(
            self.settings,
            self.queue,
            self.timer_label
        )

    def setup_overlay(self, config):
        self.title("Pomlock Break")
        self.attributes("-fullscreen", 1)

        self.attributes('-alpha', config["overlay"].get('opacity', 0.8))
        self.configure(
            cursor="none", background=config["overlay"].get('bg_color', 'black'))
        self.attributes('-topmost', True)
        self.focus_force()

    def setup_overlay_timer_label(self, config):
        try:
            label_font = font.Font(family="Helvetica", size=int(
                config["overlay"].get('font_size', 48)))
        except tk.TclError:
            logger.debug("Helvetica font not found. Using fallback.")
            label_font = font.Font(family="Arial", size=36)

        timer_label = tk.Label(self, text="",
                               fg=config["overlay"].get('color', 'white'),
                               bg=config["overlay"].get('bg_color', 'black'),
                               font=label_font)
        timer_label.pack(expand=True)

        return timer_label

    def update_overlay_window(self, config, queue, timer_label):
        try:
            queue_item = self.queue.get()

            if queue_item["type"] == "exit":
                self.destroy()
                return

            if queue_item["type"] == "break":
                queue.task_done()
                duration_s = queue_item["msg"]

                start_time = time()

                def update_overlay_timer():
                    remaining_s = duration_s - (time() - start_time)
                    if remaining_s <= 0:
                        self.withdraw()
                        self.update_overlay_window(config, queue, timer_label)
                        return

                    mins, secs = divmod(int(remaining_s), 60)
                    timer_label.config(text=f"BREAK TIME\n{
                                       mins:02d}:{secs:02d}")
                    self.after(1000, update_overlay_timer)

                update_overlay_timer()
                if self.mainloop_run:
                    self.deiconify()
                else:
                    self.mainloop_run = True
                    self.mainloop()

        except KeyboardInterrupt:
            logger.info("Exiting...")
            self.destroy()

    def parse_args(self):
        flags = {
            arg for arg in sys.argv[1:] if arg.startswith('-')}

        parser = argparse.ArgumentParser(
            description=f"A Pomodoro timer with input locking. Config: '{
                DEFAULT_CONFIG_FILE}', Log: '{DEFAULT_LOG_FILE}'.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )

        # --- Dynamically build parser from ARGUMENTS_CONFIG ---
        for dest, config in ARGUMENTS_CONFIG.items():
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
        parser.add_argument("--config-file", type=str,
                            default=str(DEFAULT_CONFIG_FILE), help="Path to settings file.")
        parser.add_argument("--log-file", type=str,
                            default=str(DEFAULT_LOG_FILE), help="Path to log file.")
        parser.add_argument("--verbose", action="store_true",
                            help="Enable verbose output to console.")

        return flags, parser.parse_args()

    def load_configuration(self, args):
        """
        Loads settings from a .config file, using ARGUMENTS_CONFIG for defaults.
        """
        settings = get_default_settings()
        config_file_path = Path(args.config_file)

        if not config_file_path.exists():
            config_file_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Config file not found at {
                config_file_path}. Using default settings.")
            return settings

        logger.debug(f"Loading settings from {config_file_path}")
        parser = configparser.ConfigParser()
        try:
            parser.read(config_file_path)
        except configparser.Error as e:
            logger.error(f"Error reading config file {
                         config_file_path}: {e}. Using defaults.")
            return settings

        # override default settings with config file
        for key, arg_config in ARGUMENTS_CONFIG.items():
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
                    logger.debug(f"Could not parse '{
                        key}' from config file: {e}. Using default.")

        return settings

    def parse_config(self, flags, args):
        # --- Settings layering: Defaults -> Config File -> CLI Args ---
        # 1. Load settings from config file (will include defaults where applicable)
        config = self.load_configuration(args)

        # 2. Setup logging
        setup_logging(args.log_file, args.verbose)
        logger.debug(f"User provided flags: {flags}")
        logger.debug(f"Config after loading file: {config}")

        # 3. Override with any explicit CLI arguments
        for dest, arg_config in ARGUMENTS_CONFIG.items():
            # Check if any long or short flag was passed by the user
            was_provided = arg_config.get('long') in flags or arg_config.get(
                'short') in flags
            was_no_block_input_provided = "--no-block-input" in flags

            if was_provided:
                value = getattr(args, dest)
                if dest.startswith('overlay_'):
                    config['overlay'][dest.replace(
                        'overlay_', '', 1)] = value
                else:
                    config[dest] = value
                logger.debug(f"CLI override: '{dest}' set to '{value}'")

            if was_no_block_input_provided:
                config['block_input'] = False

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
                        config['pomodoro'], config['short_break'], config[
                            'long_break'], config['cycles'] = values
                    else:
                        logger.error(f"Invalid timer format '{
                            timer_str}'. Expected 4 numbers.")
                        sys.exit(1)
                except ValueError:
                    logger.error(
                        f"Invalid numbers in timer string '{timer_str}'.")

        logger.debug(f"Effective settings: {config}")

        # --- Final Validation ---
        for key in ['pomodoro', 'short_break', 'long_break', 'cycles']:
            if not (isinstance(config.get(key), int) and config.get(key, 0) > 0):
                logger.error(f"{key.replace('_', ' ').capitalize()
                                } must be a positive integer. Exiting.")
                sys.exit(1)
        if not (0.0 <= config['overlay'].get('opacity', 0.8) <= 1.0):
            logger.error(
                f"Overlay opacity must be between 0.0 and 1.0. Exiting.")
            sys.exit(1)

        return config

    def run_pomodoro(self, config):
        pomo_m = config['pomodoro']
        pomo_s = pomo_m * 5
        s_break_m = config['short_break']
        s_break_s = s_break_m * 5
        l_break_m = config['long_break']
        l_break_s = l_break_m * 5
        cycles = config['cycles']

        progress = Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(table_column=Column(ratio=1)),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            ConditionalCycleColumn(""),
            "•",
            TimeRemainingColumn(),
        )

        progress_table = Table.grid()
        progress_table.add_row(
            Panel.fit(
                progress,
                border_style="green",
                padding=(1, 2),
            ),
            # Panel.fit(
            #     Group(
            #         Text("[bold]Pomodoro Timer"),
            #         Text("[bold]Session Timer")
            #     ), border_style="green", padding=(1, 2)
            # ),
        )

        total_time_s = (((pomo_m + s_break_m) * cycles) +
                        (l_break_m - s_break_m)) * 60
        session_job = progress.add_task(
            "Session",
            total=total_time_s,
            cycles_total=cycles,
            crr_cycle=1
        )
        cycle_job = progress.add_task(
            "Pomodoro",
            total=pomo_s
        )

        try:
            def timer(progress: Progress, job: TaskID, duration_s: int):
                for _ in range(duration_s):
                    progress.advance(job)
                    sleep(1)

            with Live(progress_table, refresh_per_second=10):
                while True:
                    if self.crr_cycle == 1:
                        logger.debug(
                            f"Session #{self.crr_session} started"
                        )
                        print(rule.Rule(
                            f"Session #{self.crr_session} started"
                        ))

                    # pomodoro
                    self._notify(config['pomo_notify_msg'])
                    logger.info(
                        "Pomodoro started",
                        extra={
                            "minutes": pomo_s,
                            "crr_cycle": self.crr_cycle,
                            "cycles_total": cycles
                        }
                    )

                    progress.reset(
                        cycle_job,
                        total=pomo_s,
                        description="Pomodoro"
                    )

                    pomo_threads = [
                        Thread(target=timer, args=(progress,
                                                   cycle_job, pomo_s), daemon=True),
                        Thread(target=timer, args=(progress,
                                                   session_job, pomo_s), daemon=True)
                    ]
                    for t in pomo_threads:
                        t.start()
                    for t in pomo_threads:
                        t.join()

                    logger.debug(
                        f"Pomodoro {self.crr_cycle}/{cycles} completed")

                    # break
                    break_m = s_break_m
                    break_s = s_break_s
                    break_type = "Short break"
                    if self.crr_cycle >= cycles:
                        break_m = l_break_m
                        break_s = l_break_s
                        break_type = "Long break"

                    self._notify(config['break_notify_msg'])
                    logger.info(
                        f"{break_type} started",
                        extra={
                            "minutes": break_s,
                        }
                    )

                    progress.reset(
                        cycle_job,
                        total=break_s,
                        description=break_type
                    )

                    if config['block_input']:
                        disable_input_devices()

                    break_threads = [
                        Thread(target=timer, args=(progress,
                                                   cycle_job, break_s), daemon=True),
                        Thread(target=timer, args=(progress,
                                                   session_job, break_s), daemon=True)
                    ]
                    self.queue.put({
                        "type": "break",
                        "msg": break_s
                    })
                    for t in break_threads:
                        t.start()
                    for t in break_threads:
                        t.join()

                    logger.debug(f"{break_type} completed")

                    if config['block_input']:
                        enable_input_devices()

                    # session completed
                    if self.crr_cycle >= cycles:
                        progress.reset(
                            cycle_job,
                            total=pomo_s,
                            description="Pomodoro"
                        )
                        progress.reset(
                            session_job,
                            total=total_time_s,
                            crr_cycle=1,
                            cycles_total=cycles
                        )

                        logger.debug(
                            f"Session #{self.crr_session} completed")
                        self.crr_session += 1
                        self.total_completed_sessions += 1
                        self.crr_cycle = 1
                    else:
                        # cycle completed
                        progress.update(
                            task_id=session_job,
                            crr_cycle=self.crr_cycle + 1
                        )
                        self.crr_cycle += 1

        except Exception as e:
            logger.error(f"{e}")

    def _on_key_press(self, event):
        if event.keysym.lower() in ['escape', 'q']:
            logger.debug("Overlay closed by user.")
            self.destroy()

    def _notify(self, msg):
        if self.settings.get('notify', False):
            try:
                subprocess.Popen(
                    ['notify-send', msg])
            except (FileNotFoundError, Exception) as e:
                logger.error(f"Failed to send notification: {e}")


if __name__ == "__main__":
    try:
        app = App()
    except KeyboardInterrupt:
        logger.info("Exiting...")
        app.destroy()
    except Exception as e:
        logger.error(e)
        if app.settings.get('block_input'):
            logger.info("Ensuring input devices are enabled on exit...")
            enable_input_devices()
        logger.info("Session ended")
