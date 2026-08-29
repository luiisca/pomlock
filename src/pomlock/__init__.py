import argparse
import configparser
from functools import reduce
from pathlib import Path
import sys

from rich import print
from rich_argparse import RichHelpFormatter

from .constants import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_LOG_FILE,
    STATE_FILE,
)
from .history_store import HistoryStore
from .input_handler import enable_input_devices
from .logger import logger, setup_logging
from .ui.app import PomlockApp
from .utils import deep_merge


class Settings(dict):
    """Configuration loader merging presets, config files, and CLI flags."""

    DEFAULT_PRESETS = {
        "standard": "25 5 20 4",
        "ultradian": "90 20 20 1",
        "fifty_ten": "50 10 10 1",
        "test": "10s 10s 10s 1",
    }
    DEFAULT_ACTIVITIES = {
        "available": "other",
    }
    DEFAULT_GOALS = {
        "total": "420",
        "coding": "240",
        "reading": "40",
    }
    CLI_ARGS = {
        "timer": {
            "group": "pomodoro",
            "default": "standard",
            "type": str,
            "short": "-t",
            "long": "--timer",
            "help": """Set a timer preset (available: {presets}) or custom values: 'POMODORO SHORT_BREAK LONG_BREAK CYCLES'.
                 Examples: --timer "25 5 15 4" or --timer ultradian.""",
        },
        "pomodoro": {
            "group": "pomodoro",
            "default": "25",
            "type": str,
            "short": "-p",
            "long": "--pomodoro",
            "help": "Interval of work time in minutes (or with 's' for seconds).",
        },
        "short_break": {
            "group": "pomodoro",
            "default": "5",
            "type": str,
            "short": "-s",
            "long": "--short-break",
            "help": "Short break duration in minutes (or with 's' for seconds).",
        },
        "long_break": {
            "group": "pomodoro",
            "default": "20",
            "type": str,
            "short": "-l",
            "long": "--long-break",
            "help": "Long break duration in minutes (or with 's' for seconds).",
        },
        "cycles": {
            "group": "pomodoro",
            "default": 4,
            "type": int,
            "short": "-c",
            "long": "--cycles",
            "help": "Cycles before a long break.",
        },
        "activity": {
            "group": "pomodoro",
            "default": "other",
            "type": str,
            "short": "-a",
            "long": "--activity",
            "help": "Name of the activity for the session (available: {activities}).",
        },
        "block_input": {
            "group": "pomodoro",
            "default": True,
            "long": "--block-input",
            "action": argparse.BooleanOptionalAction,
            "help": "Enable/disable keyboard/mouse input during break.",
        },
        "overlay": {
            "group": "pomodoro",
            "default": True,
            "long": "--overlay",
            "action": argparse.BooleanOptionalAction,
            "help": "Enable/disable overlay break window.",
        },
        "notify": {
            "group": "pomodoro",
            "default": True,
            "long": "--notify",
            "action": argparse.BooleanOptionalAction,
            "help": "Enable/disable desktop notificatios.",
        },
        "break_notify_msg": {
            "group": "pomodoro",
            "default": "Time for a break!",
            "type": str,
            "long": "--break-notify-msg",
            "help": "Message for break notifications.",
        },
        "long_break_notify_msg": {
            "group": "pomodoro",
            "default": "Time for a long break!",
            "type": str,
            "long": "--long-break-notify-msg",
            "help": "Message for long break notifications.",
        },
        "pomo_notify_msg": {
            "group": "pomodoro",
            "default": "Time for a pomodoro!",
            "type": str,
            "long": "--pomo-notify-msg",
            "help": "Message for pomodoro notifications.",
        },
        "callback": {
            "group": "pomodoro",
            "default": "",
            "type": str,
            "long": "--callback",
            "help": "Script to call for pomodoro and break events.",
        },
        "overlay_font_size": {
            "group": "overlay_opts",
            "default": 48,
            "type": int,
            "long": "--overlay-font-size",
            "help": "Font size for overlay timer.",
        },
        "overlay_color": {
            "group": "overlay_opts",
            "default": "white",
            "type": str,
            "long": "--overlay-color",
            "help": "Text color for overlay (e.g., 'white', '#FF0000').",
        },
        "overlay_bg_color": {
            "group": "overlay_opts",
            "default": "black",
            "type": str,
            "long": "--overlay-bg-color",
            "help": "Background color for overlay.",
        },
        "overlay_opacity": {
            "group": "overlay_opts",
            "default": 0.8,
            "type": float,
            "long": "--overlay-opacity",
            "help": "Opacity for overlay (0.0 to 1.0).",
        },
        "show_presets": {
            "long": "--show-presets",
            "action": "store_true",
            "default": False,
            "help": "Show presets and exit.",
        },
        "show_activities": {
            "long": "--show-activities",
            "action": "store_true",
            "default": False,
            "help": "Show activities and exit.",
        },
        "config_file": {
            "long": "--config-file",
            "type": str,
            "default": DEFAULT_CONFIG_FILE,
            "help": "Path to config file.",
        },
        "log_file": {
            "long": "--log-file",
            "type": str,
            "default": DEFAULT_LOG_FILE,
            "help": "Path to log file.",
        },
        "verbose": {
            "long": "--verbose",
            "action": "store_true",
            "default": False,
            "help": "Enable verbose logging.",
        },
    }

    def __init__(self):
        self.config_file = self.get_config_file()
        self.conf = configparser.ConfigParser()
        self.conf.read_dict({
            "presets": self.DEFAULT_PRESETS,
            "activities": self.DEFAULT_ACTIVITIES,
            "goals": self.DEFAULT_GOALS,
        })
        config_path = Path(self.config_file)

        if not config_path.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Config file not found at {config_path}. Using default settings.")
        else:
            try:
                logger.debug(f"Loading settings from {config_path}")
                self.conf.read(config_path)
            except configparser.Error as e:
                logger.error(f"Error reading config file {config_path}: {e}. Using defaults.")

        self.conf = dict(self.conf)

        settings = reduce(
            deep_merge,
            [
                self.get_defaults(),
                self.get_conf(),
                self.get_cli(),
            ],
        )

        def parse_duration(val: str | int | float) -> float:
            if isinstance(val, (int, float)):
                return float(val)
            val_str = str(val).strip().lower()
            if val_str.endswith("s"):
                return float(val_str[:-1]) / 60.0
            if val_str.endswith("m"):
                return float(val_str[:-1])
            return float(val_str)

        if settings.get("timer"):
            timer_val = str(settings["timer"]).lower()
            timer_str = settings["presets"].get(
                timer_val, timer_val if " " in timer_val else None
            )

            if timer_str:
                logger.debug(f"Applying timer setting: '{timer_str}'")
                try:
                    parts = timer_str.split()
                    if len(parts) == 4:
                        settings["pomodoro"] = parse_duration(parts[0])
                        settings["short_break"] = parse_duration(parts[1])
                        settings["long_break"] = parse_duration(parts[2])
                        settings["cycles"] = int(parts[3])
                    else:
                        logger.error(f"Invalid timer format '{timer_str}'. Expected 4 values.")
                        sys.exit(1)
                except ValueError:
                    logger.error(f"Invalid values in timer string '{timer_str}'.")

        for key in ["pomodoro", "short_break", "long_break"]:
            try:
                settings[key] = parse_duration(settings.get(key, 0))
                if settings[key] <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                logger.error(f"{key.replace('_', ' ').capitalize()} must be a positive number. Exiting.")
                sys.exit(1)

        try:
            settings["cycles"] = int(settings.get("cycles", 1))
            if settings["cycles"] <= 0:
                raise ValueError
        except (ValueError, TypeError):
            logger.error("Cycles must be a positive integer. Exiting.")
            sys.exit(1)

        if not (0.0 <= float(settings["overlay_opacity"]) <= 1.0):
            logger.error("Overlay opacity must be between 0.0 and 1.0. Exiting.")
            sys.exit(1)

        super().__init__(settings)
        logger.debug(f"Effective settings: {self}")

    def get_defaults(self) -> dict:
        """Generates default settings dictionary."""
        settings = {
            "presets": self.DEFAULT_PRESETS,
            "activities": self.DEFAULT_ACTIVITIES,
            "goals": self.DEFAULT_GOALS,
        }
        for key, arg_config in self.CLI_ARGS.items():
            settings[key] = arg_config["default"]
        return settings

    def get_conf(self) -> dict:
        """Loads settings from config file."""
        settings = {}
        for sect_name, sect in self.conf.items():
            if sect_name == "DEFAULT":
                continue
            if sect_name == "overlay":
                for key, value in dict(sect).items():
                    settings[f"overlay_{key}"] = value
            elif sect_name in ["presets", "activities", "goals"]:
                settings[sect_name] = dict(sect)
            else:
                deep_merge(settings, dict(sect))
        return settings

    def get_cli(self) -> dict:
        """Parses command line flags."""
        settings = {}
        preset_names = ", ".join(self.conf.get("presets").keys())
        activities_str = self.conf["activities"].get("available", "")
        activity_names = ", ".join(
            [a.strip() for a in activities_str.split(",") if a.strip()]
        )

        parser = argparse.ArgumentParser(
            description=f"A Pomodoro timer with input locking. Config: '{DEFAULT_CONFIG_FILE}', Log: '{DEFAULT_LOG_FILE}', State: '{STATE_FILE}'",
            formatter_class=RichHelpFormatter,
        )

        for key, arg_config in self.CLI_ARGS.items():
            if "long" not in arg_config:
                continue

            names = [arg_config["long"]]
            if "short" in arg_config:
                names.append(arg_config["short"])

            help_text = arg_config["help"]
            if "{presets}" in help_text:
                help_text = help_text.format(presets=preset_names)
            elif "{activities}" in help_text:
                help_text = help_text.format(activities=activity_names)

            kwargs = {
                "dest": key,
                "help": help_text,
                "default": arg_config["default"],
            }
            if "type" in arg_config:
                kwargs["type"] = arg_config["type"]
            if "action" in arg_config:
                kwargs["action"] = arg_config["action"]

            parser.add_argument(*names, **kwargs)

        parsed_args = vars(parser.parse_args())
        for key, value in parsed_args.items():
            if value != parser.get_default(key):
                settings[key] = value

        return settings

    def get_config_file(self) -> str:
        pre_parser = argparse.ArgumentParser(add_help=False)
        pre_parser.add_argument("--config-file", default=str(DEFAULT_CONFIG_FILE))
        args, _ = pre_parser.parse_known_args()
        return args.config_file


def main() -> None:
    settings = Settings()

    if "--show-presets" in sys.argv:
        if "presets" in settings:
            for name, value in settings.get("presets").items():
                print(f"{name}: {value}")
        else:
            print("No presets found.")
        sys.exit(0)

    if "--show-activities" in sys.argv:
        activities_config = settings.get("activities", {})
        if activities_config.get("available"):
            activities_list = [
                a.strip() for a in activities_config["available"].split(",") if a.strip()
            ]
            for activity in activities_list:
                print(activity)
        else:
            print("No activities found.")
        sys.exit(0)

    setup_logging(settings.get("log_file"), settings.get("verbose"))
    logger.debug(f"Config after loading: {settings}")

    history_store = HistoryStore()
    app = PomlockApp(settings=settings, history_store=history_store)

    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Exiting...")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
    finally:
        if STATE_FILE.exists():
            try:
                STATE_FILE.unlink()
            except OSError:
                pass
        if settings.get("block_input"):
            enable_input_devices()
        logger.info("Session ended")
