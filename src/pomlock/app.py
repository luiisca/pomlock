from rich.console import Console, ConsoleOptions, RenderResult
from queue import Queue, Empty
import argparse
import configparser
import subprocess
import sys
import json
from time import sleep, time
from pathlib import Path
import tkinter as tk
from tkinter import font
from threading import Thread
from functools import reduce

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
from rich_argparse import RichHelpFormatter

from .constants import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_LOG_FILE,
    STATE_FILE,
    SESSION_TYPE,
)
from .logger import setup_logging, logger
from .input_handler import disable_input_devices, enable_input_devices
from .utils import deep_merge


# --- Configuration Loading ---
class Settings(dict):
    # --- Arguments Single Source of Truth ---
    # This dictionary drives the entire settings system:
    # - 'group': Maps the setting to a section in the .config config file.
    # - 'default': The ultimate fallback value.
    # - 'type', 'action', 'help': Used to dynamically build the argparse parser.
    # - 'short', 'long': The command-line flags.
    DEFAULT_PRESETS = {
        "standard": "25 5 20 4",
        "ultradian": "90 20 20 1",
        "fifty_ten": "50 10 10 1"
    }
    DEFAULT_ACTIVITIES = {
        "available": "other"
    }
    CLI_ARGS = {
        'timer': {
            'group': 'pomodoro',
            'default': 'standard',
            'type': str,
            'short': '-t',
            'long': '--timer',
            'help': """Set a timer preset (available: {presets}) or custom values: 'POMODORO SHORT_BREAK LONG_BREAK CYCLES'.
                 Examples: --timer \"25 5 15 4\" or --timer ultradian."""
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
        'activity': {
            'group': 'pomodoro',
            'default': 'other',
            'type': str,
            'short': '-a',
            'long': '--activity',
            'help': "Name of the activity for the session (available: {activities})."
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
        'show_activities': {
            'long': '--show-activities',
            'action': 'store_true',
            'default': False,
            'help': 'Show activities and exit.'
        },
        'config_file': {
            'long': '--config-file',
            'type': str,
            'default': DEFAULT_CONFIG_FILE,
            'help': 'Path to config file.'
        },
        'log_file': {
            'long': '--log-file',
            'type': str,
            'default': DEFAULT_LOG_FILE,
            'help': 'Path to log file.'
        },
        'verbose': {
            'long': '--verbose',
            'action': 'store_true',
            'default': False,
            'help': 'Enable verbose logging.'
        }
    }

    def __init__(self):
        self.config_file = self.get_config_file()
        self.conf = configparser.ConfigParser()
        self.conf.read_dict({
            'presets': self.DEFAULT_PRESETS,
            'activities': self.DEFAULT_ACTIVITIES
        })
        config_file = Path(self.config_file)
        if not config_file.exists():
            config_file.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Config file not found at {
                         config_file}. Using default settings.")
        else:
            try:
                logger.debug(f"Loading settings from {config_file}")
                self.conf.read(config_file)
            except configparser.Error as e:
                logger.error(f"Error reading config file {
                             config_file}: {e}. Using defaults.")
        self.conf = dict(self.conf)

        settings = reduce(
            deep_merge, [
                self.get_defaults(),
                self.get_conf(),
                self.get_cli()
            ]
        )

        if settings.get('timer'):
            timer_val = settings['timer'].lower()
            timer_str = settings['presets'].get(
                timer_val, timer_val if ' ' in timer_val else None
            )

            if timer_str:
                logger.debug(f"Applying timer setting: '{timer_str}'")
                try:
                    values = [int(v) for v in timer_str.split()]
                    if len(values) == 4:
                        settings['pomodoro'], settings['short_break'], settings[
                            'long_break'], settings['cycles'] = values
                    else:
                        logger.error(f"Invalid timer format '{
                                     timer_str}'. Expected 4 numbers.")
                        sys.exit(1)
                except ValueError:
                    logger.error(
                        f"Invalid numbers in timer string '{timer_str}'.")

        for key in ['pomodoro', 'short_break', 'long_break', 'cycles']:
            if not (isinstance(settings.get(key), int) and settings.get(key, 0) > 0):
                logger.error(f"{key.replace('_', ' ').capitalize()
                                } must be a positive integer. Exiting.")
                sys.exit(1)
        if not (0.0 <= float(settings['overlay_opacity']) <= 1.0):
            logger.error(
                "Overlay opacity must be between 0.0 and 1.0. Exiting."
            )
            sys.exit(1)
        super().__init__(settings)
        logger.debug(f"Effective settings: {self}")

    def get_defaults(self) -> dict:
        """
        Generates the default settings dictionary from the single source of truth.
        """
        settings = {
            'presets': self.DEFAULT_PRESETS,
            'activities': self.DEFAULT_ACTIVITIES
        }
        for key, arg_config in self.CLI_ARGS.items():
            settings[key] = arg_config['default']
        return settings

    def get_conf(self):
        """
        Loads settings from a .config file, using ARGUMENTS_CONFIG for defaults.
        """
        settings = {}

        for sect_name, sect in self.conf.items():
            if sect_name == 'DEFAULT':
                continue
            if sect_name == 'overlay':
                for key, value in dict(sect).items():
                    settings[f'overlay_{key}'] = value
            elif sect_name in ['presets', 'activities']:
                settings[sect_name] = dict(sect)
            else:
                deep_merge(settings, dict(sect))
        return settings

    def get_cli(self):
        settings = {}
        preset_names = ", ".join(self.conf.get('presets').keys())
        activities_str = self.conf['activities'].get('available', '')
        activity_names = ", ".join(
            [a.strip() for a in activities_str.split(',') if a.strip()]
        )
        parser = argparse.ArgumentParser(
            description=f"A Pomodoro timer with input locking. Config: '{
                DEFAULT_CONFIG_FILE}', Log: '{DEFAULT_LOG_FILE}', State: '{STATE_FILE}'",
            formatter_class=RichHelpFormatter
        )
        flags = {
            arg for arg in sys.argv[1:] if arg.startswith('-')
        }

        # --- Dynamically build parser from ARGUMENTS_CONFIG ---
        for key, arg_config in self.CLI_ARGS.items():
            if 'long' not in arg_config:
                continue

            names = [arg_config['long']]
            if 'short' in arg_config:
                names.append(arg_config['short'])

            help_text = arg_config['help']
            if '{presets}' in help_text:
                help_text = help_text.format(presets=preset_names)
            elif '{activities}' in help_text:
                help_text = help_text.format(activities=activity_names)

            # Use **kwargs to unpack the dictionary of arguments into the function call
            kwargs = {
                'dest': key,
                'help': help_text,
                'default': arg_config['default']
            }
            if 'type' in arg_config:
                kwargs['type'] = arg_config['type']
            if 'action' in arg_config:
                kwargs['action'] = arg_config['action']

            parser.add_argument(*names, **kwargs)

        parsed_args = vars(parser.parse_args())
        for key, value in parsed_args.items():
            # only update settings if the user has specified a non-default arg value
            if value != parser.get_default(key):
                settings[key] = value

        return settings

    def get_config_file(self):
        pre_parser = argparse.ArgumentParser(add_help=False)
        pre_parser.add_argument(
            "--config-file", default=str(DEFAULT_CONFIG_FILE)
        )
        args, _ = pre_parser.parse_known_args()
        return args.config_file


class SessionData:
    def __init__(self, activity, completed_sessions):
        self.activity = activity
        self.completed_sessions = completed_sessions

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        session_data = Table.grid(padding=1)
        session_data.add_column(style="bold", justify="right")
        session_data.add_column()
        session_data.add_row("Activity:", f" [cyan]{self.activity}[/cyan]")
        session_data.add_row("Sessions:", f" [cyan]{
                             self.completed_sessions}[/cyan]")
        session_data.add_row("Time Today:", " [cyan]0h 0m[/cyan]")
        yield Panel(
            session_data,
            border_style="cyan",
            padding=(1, 2),
        )


class ConditionalCycleColumn(TextColumn):
    """A column that only displays cycle information if it's available."""

    def render(self, task) -> Text:
        if task.fields.get("crr_cycle") and task.fields.get("cycles_total"):
            return Text(f"{task.fields['crr_cycle']}/{task.fields['cycles_total']}")
        return Text("-", justify="center")


class App(tk.Tk):
    def __init__(self, settings: dict, queue: Queue):
        super().__init__()
        self.settings = settings
        self.queue = queue

        self.setup_overlay()
        self.timer_label = self.setup_overlay_timer_label()
        self.bind("<KeyPress>", self._on_key_press)

        self.process_queue()

    def setup_overlay(self):
        self.title("Pomlock Break")
        if SESSION_TYPE == "x11":
            self.attributes("-fullscreen", True)
        self.attributes(
            '-alpha', self.settings.get('overlay_opacity', 0.8))
        self.configure(cursor="none", background=self.settings.get(
            'overlay_bg_color', 'black'))
        self.attributes('-topmost', True)
        self.focus_force()
        self.withdraw()  # Start hidden

    def setup_overlay_timer_label(self):
        try:
            label_font = font.Font(family="Helvetica", size=int(
                self.settings.get('overlay_font_size', 48)))
        except tk.TclError:
            logger.debug("Helvetica font not found. Using fallback.")
            label_font = font.Font(family="Arial", size=36)

        timer_label = tk.Label(self, text="",
                               fg=self.settings.get(
                                   'overlay_color', 'white'),
                               bg=self.settings.get(
                                   'overlay_bg_color', 'black'),
                               font=label_font)
        timer_label.pack(expand=True)
        return timer_label

    def process_queue(self):
        """ Checks the queue for messages from the worker thread. """
        try:
            item = self.queue.get_nowait()
            if item["type"] == "exit":
                self.destroy()
                return
            if item["type"] == "break":
                self.start_break_timer(item["duration_s"])
        except KeyboardInterrupt:
            logger.info("Exiting...")
            self.destroy()
        except Empty:
            pass
        finally:
            self.after(100, self.process_queue)

    def start_break_timer(self, duration_s: int):
        self.deiconify()  # Show the window
        self.after(50, self._fullscreen)

        start_time = time()

        def update_timer():
            remaining_s = duration_s - (time() - start_time)
            if remaining_s <= 0:
                self.withdraw()  # Hide window when done
                return

            mins, secs = divmod(int(remaining_s), 60)
            self.timer_label.config(text=f"BREAK TIME\n{mins:02d}:{secs:02d}")
            self.after(1000, update_timer)

        update_timer()

    def _on_key_press(self, event):
        if event.keysym.lower() in ['escape', 'q']:
            logger.debug("Overlay closed by user.")
            self.destroy()

    def _fullscreen(self, event=None):
        if SESSION_TYPE == 'wayland':
            self.attributes("-fullscreen", True)
            return "break"


class PomodoroController:
    def __init__(self, settings: dict, queue: Queue = None):
        self.settings = settings
        self.queue = queue  # Can be None if no overlay
        self.crr_cycle = 1
        self.crr_session = 1
        self.total_completed_sessions = 0

    def run(self):
        """ The main pomodoro timer loop. """
        config = self.settings
        pomo_m = config['pomodoro']
        pomo_s = pomo_m * 60
        s_break_m = config['short_break']
        s_break_s = s_break_m * 60
        l_break_m = config['long_break']
        l_break_s = l_break_m * 60
        cycles = config['cycles']

        progress = Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(bar_width=None, table_column=Column(ratio=1)),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            ConditionalCycleColumn(""),
            "•",
            TimeRemainingColumn(),
        )

        session_data = SessionData(config.get(
            'activity', 'N/A'), self.total_completed_sessions)

        layout_table = Table.grid(expand=True)
        layout_table.add_column(ratio=2, vertical="middle")
        layout_table.add_column(ratio=1, vertical="middle")
        layout_table.add_row(
            Panel.fit(
                progress,
                border_style="green",
                padding=(1, 2)
            ),
            session_data
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

            with Live(layout_table, refresh_per_second=10) as live:
                while True:
                    if self.crr_cycle == 1:
                        logger.debug(f"Session #{self.crr_session} started")
                        live.console.print(
                            rule.Rule(f"Session #{self.crr_session} started")
                        )

                    # --- Pomodoro ---
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
                            "cycles_total": cycles,
                            "activity": config.get('activity')
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

                    # --- Break ---
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
                            "activity": config.get('activity')
                        }
                    )

                    progress.reset(
                        cycle_job,
                        total=break_s,
                        description=break_type_msg
                    )

                    if config['block_input']:
                        disable_input_devices()

                    if self.queue:
                        self.queue.put(
                            {"type": "break", "duration_s": break_s}
                        )

                    break_threads = [
                        Thread(target=timer, args=(progress,
                                                   cycle_job, break_s), daemon=True),
                        Thread(target=timer, args=(progress,
                                                   session_job, break_s), daemon=True)
                    ]
                    for t in break_threads:
                        t.start()
                    for t in break_threads:
                        t.join()

                    logger.debug(f"{break_type_msg} completed")
                    if config['block_input']:
                        enable_input_devices()

                    # --- Cycle/Session Management ---
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
                        logger.debug(f"Session #{self.crr_session} completed")
                        self.crr_session += 1
                        self.total_completed_sessions += 1
                        session_data.completed_sessions = self.total_completed_sessions
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
            # Ensure we signal the GUI to exit on error
            if self.queue:
                self.queue.put({"type": "exit"})

    # Helper methods (moved from App)
    def _notify(self, msg):
        if self.settings.get('notify', False):
            try:
                subprocess.Popen(['notify-send', msg])
            except (FileNotFoundError, Exception) as e:
                logger.error(f"Failed to send notification: {e}")

    def _run_callback(self, callback_cmd, data):
        if callback_cmd:
            try:
                cmd = callback_cmd.split() + [json.dumps(data)]
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            except Exception as e:
                logger.error(f"Failed to run callback: {e}")

    def _write_state(self, data):
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f)
        except IOError as e:
            logger.error(f"Failed to write state file: {e}")


def main():
    settings = Settings()
    app = None
    if '--show-presets' in sys.argv:
        if 'presets' in settings:
            for name, value in settings.get('presets').items():
                print(f"{name}: {value}")
        else:
            print("No presets found.")
        sys.exit(0)

    if '--show-activities' in sys.argv:
        activities_config = settings.get('activities', {})
        if activities_config.get('available'):
            activities_list = [
                a.strip() for a in activities_config['available'].split(',') if a.strip()
            ]
            for activity in activities_list:
                print(activity)
        else:
            print("No activities found.")
        sys.exit(0)

    try:
        setup_logging(settings.get('log_file'), settings.get('verbose'))
        logger.debug(f"Config after loading file: {settings}")

        if settings.get('overlay'):
            # With GUI
            gui_queue = Queue()
            controller = PomodoroController(settings, gui_queue)

            # Start the pomodoro logic in a worker thread
            worker_thread = Thread(target=controller.run, daemon=True)
            worker_thread.start()

            # Create and run the GUI in the main thread
            app = App(settings, gui_queue)
            app.mainloop()
        else:
            # Without GUI
            controller = PomodoroController(settings, None)
            controller.run()

    except KeyboardInterrupt:
        logger.info("Exiting...")
        if app:
            app.destroy()
    except Exception as e:
        logger.error(e, exc_info=True)  # Log traceback for better debugging
        if app and app.settings.get('block_input'):
            logger.info("Ensuring input devices are enabled on exit...")
            enable_input_devices()
        logger.info("Session ended")

    finally:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
        if app and app.settings.get('block_input'):
            logger.info("Ensuring input devices are enabled on exit...")
            enable_input_devices()
        logger.info("Session ended")
