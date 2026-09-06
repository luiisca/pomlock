import configparser
from pathlib import Path
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, Select

from ...constants import (
    DAYS_OF_WEEK,
    DEFAULT_CONFIG_FILE,
)
from ...logger import logger
from ...settings import Settings
from ...utils import parse_duration_m
from ..widgets.nav_bar import TopNavBar
from .utils import hex_ok

DEFAULT_HOURS_DIVISOR = 60
GOAL_PERIODS = ("daily", "weekly", "monthly", "yearly")
BOOLEAN_OPTIONS = [("True", "true"), ("False", "false")]


def _format_hours_str(minutes: int) -> str:
    """Format minutes into clean hour/minute string."""
    h, m = divmod(max(0, minutes), DEFAULT_HOURS_DIVISOR)
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}m"


class ActivityAdded(Message):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__()


class PresetAdded(Message):
    def __init__(self, name: str, preset_value: str) -> None:
        self.name = name
        self.preset_value = preset_value
        super().__init__()


class ActivitySection(Vertical):
    """Section for managing activity goals and colors."""

    def __init__(self, **kwargs):
        super().__init__(classes="settings-group", **kwargs)

    def compose(self) -> ComposeResult:
        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        auto_calc = settings.auto_calc

        # Boolean selector for auto_calc property
        with Horizontal(classes="settings-row auto-calc-row"):
            yield Label("Auto Calculate:", classes="settings-label")
            yield Select(
                BOOLEAN_OPTIONS,
                value="true" if auto_calc else "false",
                allow_blank=False,
                id="select-auto-calc",
                classes="settings-select field-activities-auto_calc",
            )

        yield Label("Activity", classes="settings-section-title")
        with Horizontal(classes="activity-selector-row"):
            yield Select(
                [],
                allow_blank=True,
                id="activity-select",
                classes="settings-select activity-select",
            )
            yield Input(
                placeholder="#FF5733",
                id="input-activity-color",
                classes="settings-input color-input",
            )
            yield Label(
                "■■■■",
                id="color-preview",
                classes="color-preview",
            )
            yield Button(
                "Delete Activity",
                id="btn-delete-activity",
                classes="btn-danger",
                disabled=True,
            )

        with Vertical(classes="settings-group"):
            yield Label(
                "Create activity",
                id="label-activity-action",
                classes="settings-section-title",
            )

            with Horizontal(classes="activity-create-row"):
                yield Input(
                    placeholder="Type new activity name...",
                    id="input-new-activity",
                    classes="settings-input",
                )
                yield Button(
                    "Add Activity",
                    id="btn-add-activity",
                    classes="btn-secondary",
                )

        with Vertical(classes="settings-group goals-group"):
            yield Label("Goals", classes="settings-section-title")

            with Horizontal(classes="goals-row"):
                with Vertical(classes="goal-field"):
                    yield Label("Daily")
                    yield Input(
                        placeholder="e.g. 8h",
                        id="input-daily-goal",
                        classes="settings-input",
                    )
                with Vertical(classes="goal-field"):
                    yield Label("Weekly")
                    yield Input(
                        placeholder="e.g. 40h",
                        id="input-weekly-goal",
                        classes="settings-input",
                    )

                with Vertical(classes="goal-field"):
                    yield Label("Monthly")
                    yield Input(
                        placeholder="e.g. 176h",
                        id="input-monthly-goal",
                        classes="settings-input",
                    )

                with Vertical(classes="goal-field"):
                    yield Label("Yearly")
                    yield Input(
                        placeholder="e.g. 2080h",
                        id="input-yearly-goal",
                        classes="settings-input",
                    )

            yield Label(
                "",
                id="settings-status-msg",
                classes="settings-status",
            )


class PresetSection(Vertical):
    """Section for managing timer presets."""

    def __init__(self, **kwargs):
        super().__init__(classes="settings-group", **kwargs)

    def compose(self) -> ComposeResult:
        yield Label("Preset", classes="settings-section-title")

        with Horizontal(classes="preset-selector-row"):
            yield Select(
                [],
                allow_blank=True,
                id="preset-select",
                classes="settings-select",
            )
            yield Button(
                "Add Preset",
                id="btn-add-preset",
                classes="btn-secondary",
            )
            yield Button(
                "Delete Preset",
                id="btn-delete-preset",
                classes="btn-danger",
                disabled=True,
            )

        with Vertical(classes="settings-group"):
            yield Label(
                "Create preset",
                id="label-preset-action",
                classes="settings-section-title",
            )

            with Horizontal(classes="preset-name-row"):
                yield Input(
                    placeholder="New preset name",
                    id="input-preset-name",
                    classes="settings-input",
                )

        with Vertical(classes="settings-group timer-values-group"):
            yield Label("Timer", classes="settings-section-title")

            with Horizontal(classes="preset-values-row"):
                with Vertical(classes="preset-field"):
                    yield Label("Pomodoro")
                    yield Input(
                        placeholder="25m",
                        id="input-preset-pomodoro",
                        classes="settings-input",
                    )

                with Vertical(classes="preset-field"):
                    yield Label("Short Break")
                    yield Input(
                        placeholder="5m",
                        id="input-preset-short",
                        classes="settings-input",
                    )

                with Vertical(classes="preset-field"):
                    yield Label("Long Break")
                    yield Input(
                        placeholder="20m",
                        id="input-preset-long",
                        classes="settings-input",
                    )

                with Vertical(classes="preset-field"):
                    yield Label("Cycles")
                    yield Input(
                        placeholder="4",
                        id="input-preset-cycles",
                        classes="settings-input",
                    )


class GeneralSettingsSection(Vertical):
    """Section for general application settings matching Settings() CLI_ARGS."""

    def __init__(self, **kwargs):
        super().__init__(classes="settings-group", **kwargs)

    def compose(self) -> ComposeResult:
        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        gen = settings.get("general", {}) if isinstance(settings.get("general"), dict) else {}

        block_input_val = "true" if gen.get("block_input", settings.get("block_input", True)) else "false"
        notify_val = "true" if gen.get("notify", settings.get("notify", True)) else "false"

        with Horizontal(classes="settings-row"):
            yield Label("Block Input:", classes="settings-label")
            yield Select(
                BOOLEAN_OPTIONS,
                value=block_input_val,
                allow_blank=False,
                id="field-general-block_input",
                classes="settings-select",
            )

        with Horizontal(classes="settings-row"):
            yield Label("Notify:", classes="settings-label")
            yield Select(
                BOOLEAN_OPTIONS,
                value=notify_val,
                allow_blank=False,
                id="field-general-notify",
                classes="settings-select",
            )

        with Horizontal(classes="settings-row"):
            yield Label("Break Message:", classes="settings-label")
            yield Input(
                placeholder="Time for a break!",
                id="field-general-break_notify_msg",
                classes="settings-input",
                value=str(gen.get("break_notify_msg", settings.get("break_notify_msg", "Time for a break!"))),
            )

        with Horizontal(classes="settings-row"):
            yield Label("Long Break Message:", classes="settings-label")
            yield Input(
                placeholder="Time for a long break!",
                id="field-general-long_break_notify_msg",
                classes="settings-input",
                value=str(gen.get("long_break_notify_msg", settings.get("long_break_notify_msg", "Time for a long break!"))),
            )

        with Horizontal(classes="settings-row"):
            yield Label("Pomodoro Message:", classes="settings-label")
            yield Input(
                placeholder="Time for a pomodoro!",
                id="field-general-pomo_notify_msg",
                classes="settings-input",
                value=str(gen.get("pomo_notify_msg", settings.get("pomo_notify_msg", "Time for a pomodoro!"))),
            )

        with Horizontal(classes="settings-row"):
            yield Label("Callback:", classes="settings-label")
            yield Input(
                placeholder="Path to script",
                id="field-general-callback",
                classes="settings-input",
                value=str(gen.get("callback", settings.get("callback", ""))),
            )


class StreakSettingsSection(Vertical):
    """Section for streak widget settings matching Settings() CLI_ARGS."""

    def __init__(self, **kwargs):
        super().__init__(classes="settings-group", **kwargs)

    def compose(self) -> ComposeResult:
        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        streak = settings.get("streak", {}) if isinstance(settings.get("streak"), dict) else {}

        with Horizontal(classes="settings-row"):
            yield Label("Streak Gap:", classes="settings-label")
            yield Input(
                placeholder="1",
                id="field-streak-allowed_gap",
                classes="settings-input",
                value=str(streak.get("allowed_gap", settings.get("allowed_gap", 1))),
            )

        with Horizontal(classes="settings-row"):
            yield Label("Streak Indicator Style:", classes="settings-label")
            yield Select(
                [("Icon", "icon"), ("Color Box", "color-box")],
                value=str(streak.get("indicator_style", settings.get("indicator_style", "icon"))),
                allow_blank=False,
                id="field-streak-indicator_style",
                classes="settings-select",
            )


class OverlaySettingsSection(Vertical):
    """Section for overlay settings matching Settings() CLI_ARGS."""

    def __init__(self, **kwargs):
        super().__init__(classes="settings-group", **kwargs)

    def compose(self) -> ComposeResult:
        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        overlay = settings.get("overlay", {}) if isinstance(settings.get("overlay"), dict) else {}

        enabled_val = "true" if overlay.get("enabled", settings.get("overlay", True)) else "false"

        with Horizontal(classes="settings-row"):
            yield Label("Enabled:", classes="settings-label")
            yield Select(
                BOOLEAN_OPTIONS,
                value=enabled_val,
                allow_blank=False,
                id="field-overlay-enabled",
                classes="settings-select",
            )

        with Horizontal(classes="settings-row"):
            yield Label("Font Size:", classes="settings-label")
            yield Input(
                placeholder="48",
                id="field-overlay-font_size",
                classes="settings-input",
                value=str(overlay.get("font_size", settings.get("font_size", 48))),
            )

        with Horizontal(classes="settings-row"):
            yield Label("Text Color:", classes="settings-label")
            yield Input(
                placeholder="white",
                id="field-overlay-color",
                classes="settings-input",
                value=str(overlay.get("color", settings.get("color", "white"))),
            )

        with Horizontal(classes="settings-row"):
            yield Label("Background Color:", classes="settings-label")
            yield Input(
                placeholder="black",
                id="field-overlay-bg_color",
                classes="settings-input",
                value=str(overlay.get("bg_color", settings.get("bg_color", "black"))),
            )

        with Horizontal(classes="settings-row"):
            yield Label("Opacity:", classes="settings-label")
            yield Input(
                placeholder="0.8",
                id="field-overlay-opacity",
                classes="settings-input",
                value=str(overlay.get("opacity", settings.get("opacity", 0.8))),
            )


class LocalizationSettingsSection(Vertical):
    """Custom widget for localization settings rendering DAYS_OF_WEEK select."""

    def __init__(self, **kwargs):
        super().__init__(classes="settings-group", **kwargs)

    def compose(self) -> ComposeResult:
        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        loc = settings.get("localization", {}) if isinstance(settings.get("localization"), dict) else {}

        week_val = str(loc.get("week_start_day", settings.get("week_start_day", "monday"))).lower()
        valid_days = [day[1] for day in DAYS_OF_WEEK]
        if week_val not in valid_days:
            week_val = "monday"

        locale_val = str(loc.get("locale", settings.get("locale", "en_US")))

        with Horizontal(classes="settings-row"):
            yield Label("Week Start Day:", classes="settings-label")
            yield Select(
                DAYS_OF_WEEK,
                value=week_val,
                allow_blank=False,
                id="field-localization-week_start_day",
                classes="settings-select",
            )

        with Horizontal(classes="settings-row"):
            yield Label("Locale:", classes="settings-label")
            yield Input(
                placeholder="en_US",
                id="field-localization-locale",
                classes="settings-input",
                value=locale_val,
            )


class TitledVertical(Vertical):
    """Vertical container with a Textual border title."""

    def __init__(self, title: str, **kwargs):
        super().__init__(**kwargs)
        self.border_title = title


class SettingsScreen(Screen):
    """Settings screen matching Settings() instance 1-to-1."""

    BINDINGS = [
        Binding("1", "show_main", "Home"),
        Binding("q", "quit_app", "Quit"),
        Binding("z", "toggle_zen", "Zen Mode", show=False),
        Binding("g", "cycle_goals", "Cycle Goals", show=False),
        Binding("space", "toggle_timer", "Toggle Pause", show=False),
        Binding("r", "reset_timer", "Reset", show=False),
        Binding("s", "skip_timer", "Skip", show=False),
    ]

    def __init__(self):
        super().__init__()
        self._selected_activity: str | None = None
        self._selected_preset: str | None = None
        self._suppress_persist: bool = True
        self._initial_values: dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        with Vertical(classes="app-shell"):
            yield TopNavBar(active_tab="settings", id="settings-top-navbar")
            with VerticalScroll(classes="settings-scroll"):
                # Activities section
                with TitledVertical(
                    "activities", classes="card-container settings-container"
                ):
                    yield ActivitySection()

                # Presets section
                with TitledVertical(
                    "presets", classes="card-container settings-container"
                ):
                    yield PresetSection()

                # General settings section
                with TitledVertical(
                    "general", classes="card-container settings-container"
                ):
                    yield GeneralSettingsSection()

                # Streak widget settings section
                with TitledVertical(
                    "streak", classes="card-container settings-container"
                ):
                    yield StreakSettingsSection()

                # Overlay settings section
                with TitledVertical(
                    "overlay", classes="card-container settings-container"
                ):
                    yield OverlaySettingsSection()

                # Localization custom section
                with TitledVertical(
                    "localization", classes="card-container settings-container"
                ):
                    yield LocalizationSettingsSection()

            yield Footer()

    def on_mount(self) -> None:
        """Populate initial values from Settings and capture baseline."""
        self._suppress_persist = True

        self._refresh_activity_select()
        self._load_presets()
        self._clear_activity_fields()
        self._update_activity_labels(is_selected=False)
        self._clear_preset_fields()
        self._update_preset_labels(is_selected=False)

        self._snapshot_initial_values()
        self._suppress_persist = False

    def _snapshot_initial_values(self) -> None:
        """Record baseline widget values to detect user modifications."""
        for widget in self.query("Input, Select"):
            if widget.id:
                self._initial_values[widget.id] = widget.value

    def _refresh_activity_select(self) -> None:
        """Populate activity Select dropdown respecting auto_calc flag."""
        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        activities = settings.get("activities", {})
        auto_calc = settings.auto_calc

        options: list[tuple[str, str]] = []
        if not auto_calc:
            options.append(("All / Total", "all"))

        for name in sorted(activities.keys()):
            if name in ("all", "total", "auto_calc"):
                continue
            if isinstance(activities[name], dict):
                options.append((name.replace("_", " ").title(), name))

        if not options:
            options.append(("Other", "other"))

        try:
            sel = self.query_one("#activity-select", Select)
            sel.set_options(options)
            opt_vals = [opt[1] for opt in options]

            if self._selected_activity and self._selected_activity in opt_vals:
                sel.value = self._selected_activity
            else:
                sel.value = Select.NULL
                self._selected_activity = None
        except Exception:
            pass

    def _load_presets(self) -> None:
        """Populate preset selector with available presets from Settings."""
        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        presets = settings.get("presets", {})

        options: list[tuple[str, str]] = []
        for name in sorted(presets.keys()):
            options.append((name.replace("_", " ").title(), name))

        try:
            sel = self.query_one("#preset-select", Select)
            sel.set_options(options)
            opt_vals = [opt[1] for opt in options]

            if self._selected_preset and self._selected_preset in opt_vals:
                sel.value = self._selected_preset
            else:
                sel.value = Select.NULL
                self._selected_preset = None
        except Exception:
            pass

    @on(Select.Changed, "#select-auto-calc")
    def on_auto_calc_changed(self, event: Select.Changed) -> None:
        """Handle auto_calc boolean selector toggling."""
        val_str = str(event.value).lower()
        is_auto = (val_str == "true")

        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        if settings.auto_calc == is_auto:
            return

        settings.auto_calc = is_auto
        self._refresh_activity_select()

        # Deselect 'all' when switching back to auto_calc
        if is_auto and self._selected_activity == "all":
            self._selected_activity = None
            self._clear_activity_fields()
            self._update_activity_labels(is_selected=False)

        self._on_widget_changed("select-auto-calc", event.value)

    @on(Select.Changed, "#activity-select")
    def on_activity_changed(self, event: Select.Changed) -> None:
        """Switch loaded values when activity selection changes."""
        val = event.value
        if val is Select.NULL or val == Select.NULL or val is None or val == "" or event.control.is_blank():
            self._selected_activity = None
            self._clear_activity_fields()
            self._update_activity_labels(is_selected=False)
            return

        self._selected_activity = str(val).lower()
        self._load_activity_goals(self._selected_activity)
        self._load_activity_color(self._selected_activity)
        self._update_activity_labels(is_selected=True)

    @on(Select.Changed, "#preset-select")
    def on_preset_changed(self, event: Select.Changed) -> None:
        """Load selected preset values into inputs."""
        val = event.value
        if val is Select.NULL or val == Select.NULL or val is None or val == "" or event.control.is_blank():
            self._selected_preset = None
            self._clear_preset_fields()
            self._update_preset_labels(is_selected=False)
            return

        self._selected_preset = str(val).lower()
        self._load_preset_values(self._selected_preset)
        self._update_preset_labels(is_selected=True)

    def _clear_activity_fields(self) -> None:
        """Clear goal and color inputs when no activity is selected."""
        prev = self._suppress_persist
        self._suppress_persist = True

        try:
            for inp_id in (
                "#input-new-activity",
                "#input-activity-color",
                "#input-daily-goal",
                "#input-weekly-goal",
                "#input-monthly-goal",
                "#input-yearly-goal",
            ):
                self.query_one(inp_id, Input).value = ""

            self._update_color_preview()
            self.query_one("#input-new-activity", Input).disabled = False
            self.query_one("#btn-delete-activity", Button).disabled = True
        except Exception:
            pass
        finally:
            self._suppress_persist = prev

    def _update_activity_labels(self, is_selected: bool) -> None:
        """Adapt labels and buttons between create and update states."""
        try:
            action_lbl = self.query_one("#label-activity-action", Label)
            btn = self.query_one("#btn-add-activity", Button)
            title_inp = self.query_one("#input-new-activity", Input)
            delete_btn = self.query_one("#btn-delete-activity", Button)

            if not is_selected or not self._selected_activity:
                action_lbl.update("Create activity")
                btn.label = "Add Activity"
                title_inp.value = ""
                title_inp.disabled = False
                delete_btn.disabled = True
                return

            action_lbl.update("Update activity")
            btn.label = "Update Activity"

            # All / Total activity title cannot be modified
            if self._selected_activity == "all":
                title_inp.value = ""
                title_inp.disabled = True
                delete_btn.disabled = True
            else:
                title_inp.value = self._selected_activity
                title_inp.disabled = False
                delete_btn.disabled = (self._selected_activity == "other")
        except Exception:
            pass

    def _clear_preset_fields(self) -> None:
        """Clear preset inputs when no preset is selected."""
        prev = self._suppress_persist
        self._suppress_persist = True

        try:
            for inp_id in (
                "#input-preset-name",
                "#input-preset-pomodoro",
                "#input-preset-short",
                "#input-preset-long",
                "#input-preset-cycles",
            ):
                self.query_one(inp_id, Input).value = ""

            self.query_one("#btn-delete-preset", Button).disabled = True
        except Exception:
            pass
        finally:
            self._suppress_persist = prev

    def _update_preset_labels(self, is_selected: bool) -> None:
        """Adapt labels and buttons between create and update states."""
        try:
            action_lbl = self.query_one("#label-preset-action", Label)
            btn = self.query_one("#btn-add-preset", Button)
            name_inp = self.query_one("#input-preset-name", Input)
            delete_btn = self.query_one("#btn-delete-preset", Button)

            if not is_selected or not self._selected_preset:
                action_lbl.update("Create preset")
                btn.label = "Add Preset"
                name_inp.value = ""
                delete_btn.disabled = True
                return

            action_lbl.update("Update preset")
            btn.label = "Update Preset"
            name_inp.value = self._selected_preset
            delete_btn.disabled = False
        except Exception:
            pass

    def _load_activity_goals(self, activity_name: str) -> None:
        """Populate input fields from Settings for selected activity."""
        prev = self._suppress_persist
        self._suppress_persist = True

        try:
            settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
            activities = settings.get("activities", {})
            act_data = activities.get(activity_name, {})
            if not isinstance(act_data, dict):
                act_data = {}

            for p in GOAL_PERIODS:
                val = parse_duration_m(act_data.get(p, 0))
                inp = self.query_one(f"#input-{p}-goal", Input)
                inp.value = _format_hours_str(int(val)) if val > 0 else ""
                self._initial_values[inp.id] = inp.value
        finally:
            self._suppress_persist = prev

    def _load_activity_color(self, activity_name: str) -> None:
        """Load and display color for selected activity."""
        prev = self._suppress_persist
        self._suppress_persist = True

        try:
            color_input = self.query_one("#input-activity-color", Input)
            if activity_name == "all":
                color_input.value = ""
            else:
                settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
                activities = settings.get("activities", {})
                act_data = activities.get(activity_name, {})
                color_val = act_data.get("color", "") if isinstance(act_data, dict) else ""
                color_input.value = color_val or ""

            self._initial_values[color_input.id] = color_input.value
            self._update_color_preview()
        finally:
            self._suppress_persist = prev

    def _load_preset_values(self, preset_name: str) -> None:
        """Load values of given preset into input fields."""
        prev = self._suppress_persist
        self._suppress_persist = True

        try:
            settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
            preset_str = settings.get("presets", {}).get(preset_name, "")
            parts = preset_str.split()

            if len(parts) == 4:
                p_inp = self.query_one("#input-preset-pomodoro", Input)
                s_inp = self.query_one("#input-preset-short", Input)
                l_inp = self.query_one("#input-preset-long", Input)
                c_inp = self.query_one("#input-preset-cycles", Input)

                p_inp.value = f"{parts[0]}m"
                s_inp.value = f"{parts[1]}m"
                l_inp.value = f"{parts[2]}m"
                c_inp.value = parts[3]

                for w in (p_inp, s_inp, l_inp, c_inp):
                    self._initial_values[w.id] = w.value
            else:
                self._clear_preset_fields()
        finally:
            self._suppress_persist = prev

    def _update_color_preview(self) -> None:
        """Update color preview label safely."""
        try:
            color_input = self.query_one("#input-activity-color", Input)
            color_value = color_input.value.strip()
            preview_label = self.query_one("#color-preview", Label)

            if color_value and color_value.startswith("#") and len(color_value) == 7 and hex_ok(color_value):
                preview_label.update("■■■■")
                preview_label.styles.background = color_value
                preview_label.styles.color = color_value
            else:
                preview_label.update("■■■■")
                preview_label.styles.background = "transparent"
                preview_label.styles.color = "initial"
        except Exception:
            pass

    def _on_widget_changed(self, widget_id: str, new_value: Any) -> None:
        """Persist settings only on explicit modifications differing from baseline."""
        if self._suppress_persist:
            return

        orig_value = self._initial_values.get(widget_id)
        if orig_value is not None and str(orig_value) == str(new_value):
            return

        self._initial_values[widget_id] = new_value
        self.persist_settings()

    # Event handlers for interactable inputs & selects
    @on(Input.Changed, "#input-daily-goal")
    @on(Input.Changed, "#input-weekly-goal")
    @on(Input.Changed, "#input-monthly-goal")
    @on(Input.Changed, "#input-yearly-goal")
    @on(Input.Changed, "#input-activity-color")
    def on_activity_inputs_changed(self, event: Input.Changed) -> None:
        if event.control.id == "input-activity-color":
            self._update_color_preview()
        self._on_widget_changed(event.control.id, event.value)

    @on(Input.Changed, "#input-preset-pomodoro")
    @on(Input.Changed, "#input-preset-short")
    @on(Input.Changed, "#input-preset-long")
    @on(Input.Changed, "#input-preset-cycles")
    def on_preset_inputs_changed(self, event: Input.Changed) -> None:
        self._on_widget_changed(event.control.id, event.value)

    @on(Select.Changed, "#field-general-block_input")
    @on(Select.Changed, "#field-general-notify")
    @on(Input.Changed, "#field-general-break_notify_msg")
    @on(Input.Changed, "#field-general-long_break_notify_msg")
    @on(Input.Changed, "#field-general-pomo_notify_msg")
    @on(Input.Changed, "#field-general-callback")
    def on_general_inputs_changed(self, event) -> None:
        self._on_widget_changed(event.control.id, event.value)

    @on(Input.Changed, "#field-streak-allowed_gap")
    @on(Select.Changed, "#field-streak-indicator_style")
    def on_streak_inputs_changed(self, event) -> None:
        self._on_widget_changed(event.control.id, event.value)

    @on(Select.Changed, "#field-overlay-enabled")
    @on(Input.Changed, "#field-overlay-font_size")
    @on(Input.Changed, "#field-overlay-color")
    @on(Input.Changed, "#field-overlay-bg_color")
    @on(Input.Changed, "#field-overlay-opacity")
    def on_overlay_inputs_changed(self, event) -> None:
        self._on_widget_changed(event.control.id, event.value)

    @on(Select.Changed, "#field-localization-week_start_day")
    @on(Input.Changed, "#field-localization-locale")
    def on_loc_changed(self, event) -> None:
        self._on_widget_changed(event.control.id, event.value)

    @on(Button.Pressed, "#btn-add-activity")
    def on_add_activity_pressed(self) -> None:
        """Create or update activity in Settings and persist."""
        new_act_inp = self.query_one("#input-new-activity", Input)
        name = new_act_inp.value.strip().lower()

        if not name:
            if self._selected_activity:
                name = self._selected_activity
            else:
                return

        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        activities = settings.setdefault("activities", {})

        if name not in activities or not isinstance(activities[name], dict):
            activities[name] = {"daily": 0, "weekly": 0, "monthly": 0, "yearly": 0}

        self._selected_activity = name
        self._refresh_activity_select()
        self._update_activity_labels(is_selected=True)
        self.persist_settings()

        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update(f"✓ Saved activity '{name}'")

    @on(Button.Pressed, "#btn-delete-activity")
    def on_delete_activity_pressed(self) -> None:
        """Delete selected activity from Settings and persist."""
        if not self._selected_activity or self._selected_activity in ["all", "other"]:
            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update("✗ Cannot delete protected activity")
            return

        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        activities = settings.get("activities", {})

        if self._selected_activity in activities:
            del activities[self._selected_activity]

        self._selected_activity = None
        self._refresh_activity_select()
        self._clear_activity_fields()
        self._update_activity_labels(is_selected=False)
        self.persist_settings()

        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update("✓ Deleted activity")

    @on(Button.Pressed, "#btn-add-preset")
    def on_add_preset_pressed(self) -> None:
        """Add or update preset with values from fields."""
        name_input = self.query_one("#input-preset-name", Input)
        name = name_input.value.strip().lower()
        if not name and self._selected_preset:
            name = self._selected_preset
        if not name:
            return

        pomodoro = self.query_one("#input-preset-pomodoro", Input).value.strip()
        short = self.query_one("#input-preset-short", Input).value.strip()
        long = self.query_one("#input-preset-long", Input).value.strip()
        cycles = self.query_one("#input-preset-cycles", Input).value.strip()

        if not all([pomodoro, short, long, cycles]):
            return

        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        settings.setdefault("presets", {})[name] = (
            f"{pomodoro.rstrip('m')} {short.rstrip('m')} {long.rstrip('m')} {cycles}"
        )

        self._selected_preset = name
        self._load_presets()
        self._update_preset_labels(is_selected=True)
        self.persist_settings()

        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update(f"✓ Saved preset '{name}'")

    @on(Button.Pressed, "#btn-delete-preset")
    def on_delete_preset_pressed(self) -> None:
        """Delete selected preset."""
        if not self._selected_preset:
            return

        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        settings.get("presets", {}).pop(self._selected_preset, None)

        self._selected_preset = None
        self._load_presets()
        self._clear_preset_fields()
        self._update_preset_labels(is_selected=False)
        self.persist_settings()

        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update("✓ Preset deleted")

    def _sync_active_activity_inputs(self) -> None:
        """Sync UI goal and color inputs for selected activity to Settings() in memory."""
        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        activities_settings = settings.setdefault("activities", {})
        selected = getattr(self, "_selected_activity", None)

        if not selected:
            return

        selected = selected.lower()

        try:
            daily_m = parse_duration_m(self.query_one("#input-daily-goal", Input).value)
            weekly_m = parse_duration_m(self.query_one("#input-weekly-goal", Input).value)
            monthly_m = parse_duration_m(self.query_one("#input-monthly-goal", Input).value)
            yearly_m = parse_duration_m(self.query_one("#input-yearly-goal", Input).value)
            color_val = self.query_one("#input-activity-color", Input).value.strip()
        except Exception:
            return

        if selected == "all":
            all_dict = activities_settings.setdefault("all", {})
            all_dict["daily"] = daily_m
            all_dict["weekly"] = weekly_m
            all_dict["monthly"] = monthly_m
            all_dict["yearly"] = yearly_m
        else:
            act_dict = activities_settings.setdefault(selected, {})
            act_dict["daily"] = daily_m
            act_dict["weekly"] = weekly_m
            act_dict["monthly"] = monthly_m
            act_dict["yearly"] = yearly_m
            if color_val:
                act_dict["color"] = color_val
            elif "color" in act_dict:
                del act_dict["color"]

        # If auto_calc is True, sum up goals for 'all' in memory
        auto_calc = activities_settings.get("auto_calc", True)
        if auto_calc:
            summed = {"daily": 0.0, "weekly": 0.0, "monthly": 0.0, "yearly": 0.0}
            for act_name, act_goals in activities_settings.items():
                if act_name in ("all", "total", "auto_calc") or not isinstance(act_goals, dict):
                    continue
                for p in summed.keys():
                    summed[p] += parse_duration_m(act_goals.get(p, 0))
            activities_settings["all"] = summed

    def _sync_general_inputs(self) -> None:
        """Sync general, streak, overlay, and localization inputs to Settings."""
        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()

        try:
            gen = settings.setdefault("general", {})
            gen["block_input"] = (self.query_one("#field-general-block_input", Select).value == "true")
            gen["notify"] = (self.query_one("#field-general-notify", Select).value == "true")
            gen["break_notify_msg"] = self.query_one("#field-general-break_notify_msg", Input).value
            gen["long_break_notify_msg"] = self.query_one("#field-general-long_break_notify_msg", Input).value
            gen["pomo_notify_msg"] = self.query_one("#field-general-pomo_notify_msg", Input).value
            gen["callback"] = self.query_one("#field-general-callback", Input).value

            streak = settings.setdefault("streak", {})
            raw_gap = self.query_one("#field-streak-allowed_gap", Input).value
            streak["allowed_gap"] = int(raw_gap) if raw_gap.isdigit() else 1
            streak["indicator_style"] = str(self.query_one("#field-streak-indicator_style", Select).value)

            overlay = settings.setdefault("overlay", {})
            overlay["enabled"] = (self.query_one("#field-overlay-enabled", Select).value == "true")
            raw_font = self.query_one("#field-overlay-font_size", Input).value
            overlay["font_size"] = int(raw_font) if raw_font.isdigit() else 48
            overlay["color"] = self.query_one("#field-overlay-color", Input).value
            overlay["bg_color"] = self.query_one("#field-overlay-bg_color", Input).value
            try:
                overlay["opacity"] = float(self.query_one("#field-overlay-opacity", Input).value)
            except ValueError:
                overlay["opacity"] = 0.8

            loc = settings.setdefault("localization", {})
            loc_week = str(self.query_one("#field-localization-week_start_day", Select).value)
            loc_locale = self.query_one("#field-localization-locale", Input).value
            loc["week_start_day"] = loc_week
            loc["locale"] = loc_locale
            settings["week_start_day"] = loc_week
            settings["locale"] = loc_locale
        except Exception:
            pass

    def _write_general_config_to_parser(self, conf: configparser.ConfigParser) -> None:
        """Write general, overlay, streak, and localization settings to parser."""
        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        general_cfg = settings.get("general", {}) if isinstance(settings.get("general"), dict) else {}
        overlay_cfg = settings.get("overlay", {}) if isinstance(settings.get("overlay"), dict) else {}
        streak_cfg = settings.get("streak", {}) if isinstance(settings.get("streak"), dict) else {}
        loc_cfg = settings.get("localization", {}) if isinstance(settings.get("localization"), dict) else {}

        sections_map = {
            "general": {
                "block_input": str(general_cfg.get("block_input", settings.get("block_input", True))).lower(),
                "notify": str(general_cfg.get("notify", settings.get("notify", True))).lower(),
                "break_notify_msg": str(general_cfg.get("break_notify_msg", settings.get("break_notify_msg", "Time for a break!"))),
                "long_break_notify_msg": str(general_cfg.get("long_break_notify_msg", settings.get("long_break_notify_msg", "Time for a long break!"))),
                "pomo_notify_msg": str(general_cfg.get("pomo_notify_msg", settings.get("pomo_notify_msg", "Time for a pomodoro!"))),
                "callback": str(general_cfg.get("callback", settings.get("callback", ""))),
            },
            "overlay": {
                "enabled": str(overlay_cfg.get("enabled", settings.get("overlay", True))).lower(),
                "font_size": str(overlay_cfg.get("font_size", settings.get("overlay_font_size", 48))),
                "color": str(overlay_cfg.get("color", settings.get("overlay_color", "white"))),
                "bg_color": str(overlay_cfg.get("bg_color", settings.get("overlay_bg_color", "black"))),
                "opacity": str(overlay_cfg.get("opacity", settings.get("overlay_opacity", 0.8))),
            },
            "streak": {
                "allowed_gap": str(streak_cfg.get("allowed_gap", settings.get("streak_allowed_gap", 1))),
                "indicator_style": str(streak_cfg.get("indicator_style", settings.get("streak_indicator_style", "icon"))),
            },
            "localization": {
                "locale": str(loc_cfg.get("locale", settings.get("locale", "en_US"))),
                "week_start_day": str(loc_cfg.get("week_start_day", settings.get("week_start_day", "monday"))),
            },
        }

        for sect_name, kvs in sections_map.items():
            if not conf.has_section(sect_name):
                conf.add_section(sect_name)
            for k, v in kvs.items():
                conf.set(sect_name, k, v)

    def persist_settings(self) -> None:
        """Persist all settings to config file respecting auto_calc rule."""
        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        config_path = Path(settings.get("config_file", DEFAULT_CONFIG_FILE))
        conf = configparser.ConfigParser()

        if config_path.exists():
            conf.read(config_path)

        # 1. Update in-memory settings from current active inputs
        self._sync_active_activity_inputs()
        self._sync_general_inputs()

        # 2. Persist activities
        activities_settings = settings.get("activities", {})
        auto_calc = settings.auto_calc

        if not conf.has_section("activities"):
            conf.add_section("activities")
        conf.set("activities", "auto_calc", "true" if auto_calc else "false")

        if auto_calc:
            # General activity goals ignored when auto_calc is true
            for p in GOAL_PERIODS:
                if conf.has_option("activities", p):
                    conf.remove_option("activities", p)
        else:
            all_goals = activities_settings.get("all", {})
            for p in GOAL_PERIODS:
                val = all_goals.get(p)
                target_m = parse_duration_m(val) if val is not None else 0
                if target_m > 0:
                    conf.set("activities", p, _format_hours_str(int(target_m)))
                elif conf.has_option("activities", p):
                    conf.remove_option("activities", p)

        # Clean up deleted activity sections in conf
        for sect in list(conf.sections()):
            if sect.startswith("activities."):
                act_name = sect[len("activities."):].strip().lower()
                if act_name not in activities_settings:
                    conf.remove_section(sect)

        # Persist individual activities
        for act_name, act_data in activities_settings.items():
            if act_name in ("all", "total", "auto_calc") or not isinstance(act_data, dict):
                continue

            sect_name = f"activities.{act_name.lower()}"
            if not conf.has_section(sect_name):
                conf.add_section(sect_name)

            for p in GOAL_PERIODS:
                val = act_data.get(p)
                target_m = parse_duration_m(val) if val is not None else 0
                if target_m > 0:
                    conf.set(sect_name, p, _format_hours_str(int(target_m)))
                elif conf.has_option(sect_name, p):
                    conf.remove_option(sect_name, p)

            color_val = act_data.get("color")
            if color_val:
                conf.set(sect_name, "color", str(color_val))
            elif conf.has_option(sect_name, "color"):
                conf.remove_option(sect_name, "color")

        # 3. Persist presets
        if not conf.has_section("presets"):
            conf.add_section("presets")
        for name, value in settings.get("presets", {}).items():
            conf.set("presets", name, str(value))

        # 4. Persist general, overlay, streak, localization
        self._write_general_config_to_parser(conf)

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            conf.write(f)

        settings.notify()

    def on_activity_added(self, message: ActivityAdded) -> None:
        """Handle activity added message."""
        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        activities = settings.setdefault("activities", {})
        name = message.name.strip().lower()

        if name not in activities:
            activities[name] = {"daily": 0, "weekly": 0, "monthly": 0, "yearly": 0}

        self._selected_activity = name
        self._refresh_activity_select()
        self._load_activity_goals(name)
        self._load_activity_color(name)
        self._update_activity_labels(is_selected=True)
        self.persist_settings()

        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update(f"✓ Added activity '{message.name}'")

    def on_preset_added(self, message: PresetAdded) -> None:
        """Handle preset added message."""
        settings = getattr(getattr(self, "app", None), "settings", None) or Settings()
        presets = settings.setdefault("presets", {})
        presets[message.name] = message.preset_value

        self._selected_preset = message.name
        self._load_presets()
        self._load_preset_values(message.name)
        self._update_preset_labels(is_selected=True)
        self.persist_settings()

        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update(f"✓ Added preset '{message.name}'")
