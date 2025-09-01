#!/usr/bin/env python3

import argparse
import configparser
import subprocess
import sys
import json
from time import sleep, time
from pathlib import Path
import tkinter as tk
from tkinter import font
from queue import Queue
from threading import Thread

from rich import print, rule
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

from constants import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_LOG_FILE,
    STATE_FILE,
    ARGUMENTS_CONFIG,
    SESSION_TYPE,
)
from logger import setup_logging, logger
from input_handler import disable_input_devices, enable_input_devices


# --- Configuration Loading ---
def get_default_settings() -> dict:
    """Generates the default settings dictionary from the single source of truth."""
    defaults = {}
    # Create a nested dictionary for overlay options
    defaults['overlay_opts'] = {}
    for key, config in ARGUMENTS_CONFIG.items():
        if key.startswith('overlay_'):
            # Strip 'overlay_' prefix for the key inside overlay
            opt_key = key.replace('overlay_', '', 1)
            defaults['overlay_opts'][opt_key] = config['default']
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
        self.crr_cycle = 1
        self.crr_session = 1
        self.total_completed_sessions = 0

        self.flags, self.args = self.parse_args()
        self.settings = self.parse_config(self.flags, self.args)

        if self.settings["overlay"]:
            super().__init__()

            self.bind("<KeyPress>", self._on_key_press)
            self.mainloop_run = False
            self.queue = Queue()

            self.setup_overlay(self.settings)
            self.timer_label = self.setup_overlay_timer_label(self.settings)

            Thread(target=self.run_pomodoro, kwargs={
                   "config": self.settings}, daemon=True).start()

            self.update_overlay_window(
                self.settings,
                self.queue,
                self.timer_label
            )
        else:
            self.queue = None
            self.run_pomodoro(self.settings)

    def setup_overlay(self, config):
        self.title("Pomlock Break")
        if SESSION_TYPE == "x11":
            self.attributes("-fullscreen", True)

        self.attributes('-alpha', config["overlay_opts"].get('opacity', 0.8))
        self.configure(
            cursor="none", background=config["overlay_opts"].get('bg_color', 'black'))
        self.attributes('-topmost', True)
        self.focus_force()

    def setup_overlay_timer_label(self, config):
        try:
            label_font = font.Font(family="Helvetica", size=int(
                config["overlay_opts"].get('font_size', 48)))
        except tk.TclError:
            logger.debug("Helvetica font not found. Using fallback.")
            label_font = font.Font(family="Arial", size=36)

        timer_label = tk.Label(self, text="",
                               fg=config["overlay_opts"].get('color', 'white'),
                               bg=config["overlay_opts"].get(
                                   'bg_color', 'black'),
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
                    self.after(10, self._fullscreen)
                else:
                    self.mainloop_run = True
                    self.after(10, self._fullscreen)
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
                        settings['overlay_opts'][key.replace(
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
            was_no_overlay_provided = "--no-overlay" in flags

            if was_provided:
                value = getattr(args, dest)
                if dest.startswith('overlay_'):
                    config['overlay_opts'][dest.replace(
                        'overlay_', '', 1)] = value
                else:
                    config[dest] = value
                logger.debug(f"CLI override: '{dest}' set to '{value}'")

            if was_no_block_input_provided:
                config['block_input'] = False
            if was_no_overlay_provided:
                config['overlay'] = False

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
        if not (0.0 <= config['overlay_opts'].get('opacity', 0.8) <= 1.0):
            logger.error(
                "Overlay opacity must be between 0.0 and 1.0. Exiting."
            )
            sys.exit(1)

        return config

    def run_pomodoro(self, config):
        pomo_m = config['pomodoro']
        pomo_s = pomo_m * 60
        s_break_m = config['short_break']
        s_break_s = s_break_m * 60
        l_break_m = config['long_break']
        l_break_s = l_break_m * 60
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
                initial_completed = progress.tasks[job].completed
                start_time = time()
                while (elapsed := time() - start_time) < duration_s:
                    progress.update(job, completed=initial_completed + elapsed)
                    sleep(0.1)
                # Ensure it finishes at 100%
                progress.update(job, completed=initial_completed + duration_s)

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
                    pomo_data = {
                        "action": "pomodoro",
                        "time": pomo_m,
                        "start_time": time(),
                        "crr-cycle": self.crr_cycle,
                        "total-cycles": cycles,
                        "crr-session": self.crr_session
                    }
                    self._write_state(pomo_data)
                    self._run_callback(config.get('callback'), pomo_data)
                    self._notify(config['pomo_notify_msg'])
                    logger.info(
                        "Pomodoro started",
                        extra={
                            "minutes": pomo_m,
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
                    break_type = "short_break"
                    break_type_msg = "Short break"
                    if self.crr_cycle >= cycles:
                        break_m = l_break_m
                        break_s = l_break_s
                        break_type = "long_break"
                        break_type_msg = "Long break"

                    break_data = {
                        "action": break_type,
                        "time": break_m,
                        "start_time": time(),
                        "crr-cycle": self.crr_cycle,
                        "total-cycles": cycles,
                        "crr-session": self.crr_session
                    }
                    self._write_state(break_data)
                    self._run_callback(config.get('callback'), break_data)
                    self._notify(config['break_notify_msg'])
                    logger.info(
                        f"{break_type_msg} started",
                        extra={
                            "minutes": break_m,
                        }
                    )

                    progress.reset(
                        cycle_job,
                        total=break_s,
                        description=break_type_msg
                    )

                    if config['block_input']:
                        disable_input_devices()

                    break_threads = [
                        Thread(target=timer, args=(progress,
                                                   cycle_job, break_s), daemon=True),
                        Thread(target=timer, args=(progress,
                                                   session_job, break_s), daemon=True)
                    ]
                    if self.queue:
                        self.queue.put({
                            "type": "break",
                            "msg": break_s
                        })
                    for t in break_threads:
                        t.start()
                    for t in break_threads:
                        t.join()

                    logger.debug(f"{break_type_msg} completed")

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

    def _run_callback(self, callback_cmd, data):
        if callback_cmd:
            try:
                cmd = callback_cmd.split() + [json.dumps(data)]
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception as e:
                logger.error(f"Failed to run callback: {e}")

    def _write_state(self, data):
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f)
        except IOError as e:
            logger.error(f"Failed to write state file: {e}")

    def _fullscreen(self, event=None):
        if SESSION_TYPE == 'wayland':
            self.attributes("-fullscreen", True)
            return "break"


if __name__ == "__main__":
    if '--show-presets' in sys.argv:
        # Minimal parsing to find config file
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--config-file", default=str(DEFAULT_CONFIG_FILE))
        args, _ = parser.parse_known_args()

        # Load config just for presets
        config = configparser.ConfigParser()
        defaults = get_default_settings()
        config.read_dict({'presets': defaults['presets']})
        if Path(args.config_file).exists():
            config.read(args.config_file)

        if 'presets' in config:
            for name, value in config['presets'].items():
                print(f"{name}: {value}")
        sys.exit(0)

    app = None
    try:
        app = App()
    except KeyboardInterrupt:
        logger.info("Exiting...")
        if app:
            app.destroy()
    except Exception as e:
        logger.error(e)
        if app and app.settings.get('block_input'):
            logger.info("Ensuring input devices are enabled on exit...")
            enable_input_devices()
        logger.info("Session ended")

    # this breaks -h for some reason but ensures devices are enabled
    # if the program is interrupted on the middle of a break
    finally:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
        if app and app.settings.get('block_input'):
            logger.info("Ensuring input devices are enabled on exit...")
            enable_input_devices()
        logger.info("Session ended")
