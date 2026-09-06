import argparse
import configparser
import sys
from functools import reduce
from pathlib import Path

from rich_argparse import RichHelpFormatter

from .constants import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_LOG_FILE,
    STATE_FILE,
)
from .logger import logger
from .utils import deep_merge, parse_activities_goals_m


class Settings(dict):
    """Configuration loader merging presets, config files, and CLI flags."""

    _instance: "Settings | None" = None
    _listeners: list = []

    @classmethod
    def subscribe(cls, callback) -> None:
        # Register observer callback for settings updates
        if callback not in cls._listeners:
            cls._listeners.append(callback)

    @classmethod
    def unsubscribe(cls, callback) -> None:
        # Remove observer callback
        if callback in cls._listeners:
            cls._listeners.remove(callback)

    @classmethod
    def reset(cls) -> None:
        # Reset singleton instance for test isolation
        cls._instance = None

    def notify(self) -> None:
        # Notify all registered observer callbacks when settings change
        for callback in list(self._listeners):
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in settings listener: {e}")

    DEFAULT_PRESETS = {
        "standard": "25 5 20 4",
        "ultradian": "90 20 20 1",
        "fifty_ten": "50 10 10 1",
    }
    DEFAULT_ACTIVITIES = {
        "auto_calc": True,
        "other": {},
    }

    @property
    def auto_calc(self) -> bool:
        if "activities" in self and isinstance(self["activities"], dict) and "auto_calc" in self["activities"]:
            return bool(self["activities"]["auto_calc"])
        return bool(self.get("auto_calc", True))

    @auto_calc.setter
    def auto_calc(self, value: bool) -> None:
        self["auto_calc"] = bool(value)
        if "activities" in self and isinstance(self["activities"], dict):
            self["activities"]["auto_calc"] = bool(value)

    CLI_ARGS = {
        # --- [general] ---
        "timer": {
            "group": "general",
            "default": "standard",
            "type": str,
            "short": "-t",
            "long": "--timer",
            "help": """Set a timer preset (available: {presets}) or custom values: 'POMODORO SHORT_BREAK LONG_BREAK CYCLES'.
                 Examples: --timer "25 5 15 4" or --timer ultradian.""",
        },
        "block_input": {
            "group": "general",
            "default": True,
            "long": "--block-input",
            "action": argparse.BooleanOptionalAction,
            "help": "Enable/disable keyboard/mouse input during break.",
        },
        "notify": {
            "group": "general",
            "default": True,
            "long": "--notify",
            "action": argparse.BooleanOptionalAction,
            "help": "Enable/disable desktop notificatios.",
        },
        "break_notify_msg": {
            "group": "general",
            "default": "Time for a break!",
            "type": str,
            "long": "--break-notify-msg",
            "help": "Message for break notifications.",
        },
        "long_break_notify_msg": {
            "group": "general",
            "default": "Time for a long break!",
            "type": str,
            "long": "--long-break-notify-msg",
            "help": "Message for long break notifications.",
        },
        "pomo_notify_msg": {
            "group": "general",
            "default": "Time for a pomodoro!",
            "type": str,
            "long": "--pomo-notify-msg",
            "help": "Message for pomodoro notifications.",
        },
        "callback": {
            "group": "general",
            "default": "",
            "type": str,
            "long": "--callback",
            "help": "Script to call for pomodoro and break events.",
        },
        # --- [overlay] ---
        "enabled": {
            "group": "overlay",
            "default": True,
            "long": "--overlay",
            "action": argparse.BooleanOptionalAction,
            "help": "Enable/disable overlay break window.",
        },
        "font_size": {
            "group": "overlay",
            "default": 48,
            "type": int,
            "long": "--overlay-font-size",
            "help": "Font size for overlay timer.",
        },
        "color": {
            "group": "overlay",
            "default": "white",
            "type": str,
            "long": "--overlay-color",
            "help": "Text color for overlay (e.g., 'white', '#FF0000').",
        },
        "bg_color": {
            "group": "overlay",
            "default": "black",
            "type": str,
            "long": "--overlay-bg-color",
            "help": "Background color for overlay.",
        },
        "opacity": {
            "group": "overlay",
            "default": 0.8,
            "type": float,
            "long": "--overlay-opacity",
            "help": "Opacity for overlay (0.0 to 1.0).",
        },
        # --- [activities] ---
        "activity": {
            "group": None,
            "default": "other",
            "type": str,
            "short": "-a",
            "long": "--activity",
            "help": "Name of the activity for the session (available: {activities}).",
        },
        # --- [streak] ---
        "allowed_gap": {
            "group": "streak",
            "default": 1,
            "type": int,
            "long": "--streak-gap",
            "help": "Allowed gap days for streak counting.",
        },
        "indicator_style": {
            "group": "streak",
            "default": "icon",
            "type": str,
            "long": "--streak-style",
            "help": "Streak indicator style: icon or color-box.",
        },
        # --- [localization] ---
        "week_start_day": {
            "group": "localization",
            "default": "monday",
            "type": str,
            "long": "--week-start",
            "help": "First day of week for streak widget (monday, tuesday, ...).",
        },
        "locale": {
            "group": "localization",
            "default": "en_US",
            "type": str,
            "long": "--locale",
            "help": "Locale for streak widget (e.g., en_US).",
        },
        # --- not part of the config file (CLI-only utility flags) ---
        "show_presets": {
            "long": "--show-presets",
            "action": "store_true",
            "default": True,
            "help": "Show presets and exit.",
        },
        "show_activities": {
            "long": "--show-activities",
            "action": "store_true",
            "default": True,
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

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return  # already built, don't redo the merge every call
        super().__init__()

        self.preparsed_custom_path_args = self._preparse_custom_paths_args()
        self.conf_file_parser = self._get_conf_parser()

        self.update(
            reduce(
                deep_merge,
                [
                    self._get_default_settings(),
                    self._get_conf_settings(),
                    self._get_cli_settings(),
                ],
            )
        )

        # parse timer and activities goals to minutes and replace correspoding
        # settings in merged_settings
        logger.debug(f"merged settings: {self}")
        self["activities"] = parse_activities_goals_m(self)

        if not (0.0 <= float(self["overlay"]["opacity"]) <= 1.0):
            logger.error("Overlay opacity must be between 0.0 and 1.0. Exiting.")
            sys.exit(1)

        self._initialized = True

    def _get_default_settings(self):
        """Generates default settings dictionary."""
        settings = {
            "presets": self.DEFAULT_PRESETS,
            "activities": self.DEFAULT_ACTIVITIES,
        }
        for dest, spec in self.CLI_ARGS.items():
            group = spec.get("group")
            if group is None:
                settings[dest] = spec["default"]
            else:
                settings.setdefault(group, {})[dest] = spec["default"]
        return settings

    def _get_conf_settings(self):
        """Loads settings from config file."""
        settings: dict[str, dict[str, str]] = {}
        for sect_name, sect in self.conf_file_parser.items():
            if sect_name == "DEFAULT":
                continue
            else:
                settings[sect_name] = dict(sect)
        logger.debug(f"_get_conf_settings: {settings}")
        return settings

    def _build_parser(self) -> argparse.ArgumentParser:
        """Builds an ArgumentParser from CLI_ARGS."""
        preset_names = (
            ", ".join(self.conf_file_parser.options("presets"))
            if self.conf_file_parser.has_section("presets")
            else ""
        )
        act_sections = [
            s[len("activities."):]
            for s in self.conf_file_parser.sections()
            if s.startswith("activities.")
        ]
        if not act_sections and self.conf_file_parser.has_section("activities"):
            valid = {"auto_calc", "daily", "weekly", "monthly", "yearly"}
            act_sections = [
                opt for opt in self.conf_file_parser.options("activities")
                if opt not in valid
            ]
        activity_names = ", ".join(act_sections or ["other"])
        parser = argparse.ArgumentParser(
            description=f"A Pomodoro timer with input locking. Config: '{
                self.preparsed_custom_path_args['config']
            }', Log: '{self.preparsed_custom_path_args['log']}', State: '{STATE_FILE}'",
            formatter_class=RichHelpFormatter,
        )

        for dest, spec in self.CLI_ARGS.items():
            spec = dict(spec)
            if "long" not in spec:
                continue

            long = spec.pop("long")
            short = spec.pop("short", None)
            flags = [long] if not short else [short, long]

            spec.pop("group", None)

            help_text = spec.pop("help", "")
            if "{presets}" in help_text:
                help_text = help_text.format(presets=preset_names)
            elif "{activities}" in help_text:
                help_text = help_text.format(activities=activity_names)

            _ = parser.add_argument(*flags, dest=dest, help=help_text, **spec)
        return parser

    def _get_cli_settings(self):
        """Parses command line flags."""
        settings: dict[str, dict[str, str]] = {}
        parser = self._build_parser()
        parsed_known, _ = parser.parse_known_args()
        parsed_args = vars(parsed_known)
        for dest, spec in self.CLI_ARGS.items():
            group = spec.get("group")
            value = parsed_args[dest]
            if value == spec["default"]:
                continue
            elif group is None:
                settings[dest] = value
            else:
                settings.setdefault(group, {})[dest] = value
        return settings

    def _preparse_custom_paths_args(self):
        "config and log filepaths are later needed in main parser"
        preparser = argparse.ArgumentParser(add_help=False)
        _ = preparser.add_argument("--config-file", default=str(DEFAULT_CONFIG_FILE))
        _ = preparser.add_argument("--log-file", default=str(DEFAULT_LOG_FILE))
        args, _ = preparser.parse_known_args()
        return {
            "config": Path(args.config_file),
            "log": Path(args.log_file),
        }

    def _get_conf_parser(self):
        path = self.preparsed_custom_path_args["config"]
        conf = configparser.ConfigParser()
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Config file not found at {path}. Using default settings.")
        else:
            try:
                logger.debug(f"Loading settings from {path}")
                _ = conf.read(path)
            except configparser.Error as e:
                logger.error(f"Error reading config file {path}: {e}. Using defaults.")
        return conf
