from typing import Optional
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, Footer
from textual.binding import Binding

from ...constants import (
    WORK_DAYS_PER_MONTH,
    WORK_DAYS_PER_WEEK,
    WORK_DAYS_PER_YEAR,
    GoalPeriod,
    DEFAULT_CONFIG_FILE,
)
from ...history_store import HistoryStore
from ...utils import parse_duration_string
from ..widgets.nav_bar import TopNavBar
import configparser
from pathlib import Path


def _format_hours_str(minutes: int) -> str:
    """Format minutes into clean hour/minute string."""
    h, m = divmod(max(0, minutes), 60)
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}m"


class TitledVertical(Vertical):
    """Vertical container with a Textual border title."""

    def __init__(self, title: str, **kwargs):
        super().__init__(**kwargs)
        self.border_title = title


class SettingsScreen(Screen):
    """Settings screen for configuring multi-timeframe activity goals and preferences."""
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
        self._selected_activity: str = "all"
        self._selected_preset: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="app-shell"):
            yield TopNavBar(active_tab="settings", id="settings-top-navbar")
            with VerticalScroll(classes="settings-scroll"):
                # ---------------------------------------------------------
                # Activities
                # ---------------------------------------------------------
                with TitledVertical("activities", classes="card-container settings-container"):
                    with Vertical(classes="settings-group"):
                        yield Label("Activity", classes="settings-section-title")
                        with Horizontal(classes="activity-selector-row"):
                            yield Select(
                                [("All / Total", "all")],
                                value="all",
                                allow_blank=False,
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

                    with Horizontal(classes="settings-btn-row"):
                        yield Button(
                            "Save Goals",
                            id="btn-save-goals",
                            classes="btn-primary",
                        )

                    yield Label(
                        "",
                        id="settings-status-msg",
                        classes="settings-status",
                    )

                # ---------------------------------------------------------
                # Presets
                # ---------------------------------------------------------
                with TitledVertical("presets", classes="card-container settings-container"):
                    with Vertical(classes="settings-group"):
                        yield Label("Preset", classes="settings-section-title")

                        with Horizontal(classes="preset-selector-row"):
                            yield Select(
                                [("Select...", "")],
                                value="",
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
                            "New preset",
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

                    with Horizontal(classes="settings-btn-row"):
                        yield Button(
                            "Save Preset",
                            id="btn-save-preset",
                            classes="btn-primary",
                        )

                # ---------------------------------------------------------
                # General settings
                # ---------------------------------------------------------
                with TitledVertical("general", classes="card-container settings-container"):
                    with Horizontal(classes="settings-row"):
                        yield Label("Block Input:", classes="settings-label")
                        yield Select(
                            [("True", "true"), ("False", "false")],
                            value=(
                                "true"
                                if self.app.settings.get("block_input", True)
                                else "false"
                            ),
                            id="select-block-input",
                            classes="settings-select",
                        )

                    with Horizontal(classes="settings-row"):
                        yield Label("Notify:", classes="settings-label")
                        yield Select(
                            [("True", "true"), ("False", "false")],
                            value=(
                                "true"
                                if self.app.settings.get("notify", True)
                                else "false"
                            ),
                            id="select-notify",
                            classes="settings-select",
                        )

                    with Horizontal(classes="settings-row"):
                        yield Label(
                            "Break Message:",
                            classes="settings-label",
                        )
                        yield Input(
                            placeholder="Time for a break!",
                            id="input-break-notify-msg",
                            classes="settings-input",
                            value=self.app.settings.get(
                                "break_notify_msg",
                                "Time for a break!",
                            ),
                        )

                    with Horizontal(classes="settings-row"):
                        yield Label(
                            "Long Break Message:",
                            classes="settings-label",
                        )
                        yield Input(
                            placeholder="Time for a long break!",
                            id="input-long-break-notify-msg",
                            classes="settings-input",
                            value=self.app.settings.get(
                                "long_break_notify_msg",
                                "Time for a long break!",
                            ),
                        )

                    with Horizontal(classes="settings-row"):
                        yield Label(
                            "Pomodoro Message:",
                            classes="settings-label",
                        )
                        yield Input(
                            placeholder="Time for a pomodoro!",
                            id="input-pomo-notify-msg",
                            classes="settings-input",
                            value=self.app.settings.get(
                                "pomo_notify_msg",
                                "Time for a pomodoro!",
                            ),
                        )

                    with Horizontal(classes="settings-row"):
                        yield Label("Callback:", classes="settings-label")
                        yield Input(
                            placeholder="Path to script",
                            id="input-callback",
                            classes="settings-input",
                            value=self.app.settings.get("callback", ""),
                        )
                    # New: Streak Indicator Style selector
                    with Horizontal(classes="settings-row"):
                        yield Label("Streak Indicator Style:", classes="settings-label")
                        yield Select(
                            [("Icon", "icon"), ("Color Box", "color-box")],
                            value=self.app.settings.get("streak_indicator_style", "icon"),
                            id="select-streak-style",
                            classes="settings-select",
                        )

                    with Horizontal(classes="settings-btn-row"):
                        yield Button(
                            "Save General Settings",
                            id="btn-save-general",
                            classes="btn-primary",
                        )

                # ---------------------------------------------------------
                # Overlay settings
                # ---------------------------------------------------------
                with TitledVertical("overlay", classes="card-container settings-container"):
                    with Horizontal(classes="settings-row"):
                        yield Label("Enabled:", classes="settings-label")
                        yield Select(
                            [("True", "true"), ("False", "false")],
                            value=(
                                "true"
                                if self.app.settings.get("overlay", True)
                                else "false"
                            ),
                            id="select-overlay",
                            classes="settings-select",
                        )

                    with Horizontal(classes="settings-row"):
                        yield Label("Font Size:", classes="settings-label")
                        yield Input(
                            placeholder="48",
                            id="input-overlay-font-size",
                            classes="settings-input",
                            value=str(
                                self.app.settings.get("overlay_font_size", 48)
                            ),
                        )

                    with Horizontal(classes="settings-row"):
                        yield Label("Text Color:", classes="settings-label")
                        yield Input(
                            placeholder="white",
                            id="input-overlay-color",
                            classes="settings-input",
                            value=self.app.settings.get(
                                "overlay_color",
                                "white",
                            ),
                        )

                    with Horizontal(classes="settings-row"):
                        yield Label(
                            "Background Color:",
                            classes="settings-label",
                        )
                        yield Input(
                            placeholder="black",
                            id="input-overlay-bg-color",
                            classes="settings-input",
                            value=self.app.settings.get(
                                "overlay_bg_color",
                                "black",
                            ),
                        )

                    with Horizontal(classes="settings-row"):
                        yield Label("Opacity:", classes="settings-label")
                        yield Input(
                            placeholder="0.8",
                            id="input-overlay-opacity",
                            classes="settings-input",
                            value=str(
                                self.app.settings.get("overlay_opacity", 0.8)
                            ),
                        )

                    with Horizontal(classes="settings-btn-row"):
                        yield Button(
                            "Save Overlay Settings",
                            id="btn-save-overlay",
                            classes="btn-primary",
                        )

            yield Footer()

    def on_mount(self) -> None:
        """Load activities, presets, and current goals on mount."""
        self._refresh_activity_select()
        self._load_activity_goals(self._selected_activity)
        self._load_activity_color(self._selected_activity)
        self._load_presets()
        self._timer_settings_loaded = True

    def _refresh_activity_select(self) -> None:
        """Populate the Select dropdown with all activities currently in the database."""
        history_store = getattr(
            self.app, "history_store", None) or HistoryStore()
        activities = history_store.get_activities()

        options = [("All / Total", "all")]
        for act in activities:
            name = act.get("name", "").lower()
            if name and name not in ("all", "total"):
                display_label = name.title()
                options.append((display_label, name))

        try:
            sel = self.query_one("#activity-select", Select)
            sel.set_options(options)
            if self._selected_activity in [opt[1] for opt in options]:
                sel.value = self._selected_activity
            else:
                sel.value = "all"
        except Exception:
            pass
        """Populate the Select dropdown with all activities currently in the database."""
        history_store = getattr(
            self.app, "history_store", None) or HistoryStore()
        activities = history_store.get_activities()

        options = [("All / Total", "all")]
        for act in activities:
            name = act.get("name", "").lower()
            if name and name not in ("all", "total"):
                display_label = name.title()
                options.append((display_label, name))

        try:
            sel = self.query_one("#activity-select", Select)
            sel.set_options(options)
            if self._selected_activity in [opt[1] for opt in options]:
                sel.value = self._selected_activity
            else:
                sel.value = "all"
        except Exception:
            pass

    @on(Button.Pressed, "#btn-add-activity")
    def on_add_activity_pressed(self) -> None:
        """Create a new activity in the database and select it."""
        new_act_inp = self.query_one("#input-new-activity", Input)
        name = new_act_inp.value.strip().lower()
        if not name:
            return

        history_store = getattr(
            self.app, "history_store", None) or HistoryStore()
        history_store.save_activity(
            name=name, daily_goal=0, weekly_goal=0, monthly_goal=0, yearly_goal=0)

        self._selected_activity = name
        new_act_inp.value = ""
        self._refresh_activity_select()
        self._load_activity_goals(name)

        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update(f"✓ Added activity '{name}'")

    @on(Select.Changed, "#activity-select")
    def on_activity_changed(self, event: Select.Changed) -> None:
        """Switch loaded values when activity selection changes."""
        if event.value is not None:
            self._selected_activity = str(event.value)
            self._load_activity_goals(self._selected_activity)
            self._load_activity_color(self._selected_activity)

    @on(Input.Changed, "#input-daily-goal")
    def on_daily_changed(self, event: Input.Changed) -> None:
        """Manual goal entry - no auto calculation as per requirements."""
        pass

    @on(Input.Changed, "#input-monthly-goal")
    def on_monthly_changed(self, event: Input.Changed) -> None:
        """Manual goal entry - no auto calculation as per requirements."""
        pass

    @on(Input.Changed, "#input-yearly-goal")
    def on_yearly_changed(self, event: Input.Changed) -> None:
        """Manual goal entry - no auto calculation as per requirements."""
        # Manual entry only - no automatic calculation
        pass

    @on(Input.Changed, "#input-activity-color")
    def on_activity_color_changed(self, event: Input.Changed) -> None:
        """Update color preview when color input changes."""
        self._update_color_preview()

    def _update_color_preview(self) -> None:
        """Update the color preview label with the current color value."""
        try:
            color_input = self.query_one("#input-activity-color", Input)
            color_value = color_input.value.strip()

            # Validate hex color format
            if color_value and (color_value.startswith('#') and len(color_value) == 7):
                try:
                    # Validate it's a valid hex number
                    int(color_value[1:], 16)
                    preview_label = self.query_one("#color-preview", Label)
                    preview_label.update("■■■■")
                    preview_label.styles.background = color_value
                    preview_label.styles.color = color_value
                except ValueError:
                    # Invalid hex, reset preview
                    preview_label = self.query_one("#color-preview", Label)
                    preview_label.update("■■■■")
                    preview_label.styles.background = "transparent"
                    preview_label.styles.color = "initial"
            else:
                # Invalid or empty color, reset preview
                preview_label = self.query_one("#color-preview", Label)
                preview_label.update("■■■■")
                preview_label.styles.background = "transparent"
                preview_label.styles.color = "initial"
        except Exception:
            # If anything goes wrong, reset preview safely
            try:
                preview_label = self.query_one("#color-preview", Label)
                preview_label.update("■■■■")
                preview_label.styles.background = "transparent"
                preview_label.styles.color = "initial"
            except Exception:
                pass  # Give up gracefully

    @on(Button.Pressed, "#btn-auto-calc")
    def on_auto_calc_pressed(self) -> None:
        """Auto calculation disabled as per requirements."""
        # Auto calculation disabled - button kept for potential future use
        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update("Auto calculation disabled per requirements")

    @on(Button.Pressed, "#btn-save-goals")
    def on_save_pressed(self) -> None:
        """Persist entered goals and color to SQLite database."""
        try:
            daily_inp = self.query_one("#input-daily-goal", Input)
            weekly_inp = self.query_one("#input-weekly-goal", Input)
            monthly_inp = self.query_one("#input-monthly-goal", Input)
            yearly_inp = self.query_one("#input-yearly-goal", Input)
            color_inp = self.query_one("#input-activity-color", Input)

            daily_mins = parse_duration_string(daily_inp.value)
            weekly_mins = parse_duration_string(weekly_inp.value)
            monthly_mins = parse_duration_string(monthly_inp.value)
            yearly_mins = parse_duration_string(yearly_inp.value)
            color_value = color_inp.value.strip()

            # Validate color input
            if color_value and (not color_value.startswith('#') or len(color_value) != 7):
                try:
                    int(color_value[1:], 16)
                except (ValueError("Color must be a 6-digit hex value such as #FF5733"), IndexError):
                    color_value = ""  # Invalid color, save as None

            if daily_mins < 0 or monthly_mins < 0 or yearly_mins < 0:
                raise ValueError("Goals cannot be negative")

            history_store = getattr(
                self.app, "history_store", None) or HistoryStore()
            history_store.save_activity(
                name=self._selected_activity,
                daily_goal=daily_mins,
                weekly_goal=weekly_mins,
                monthly_goal=monthly_mins,
                yearly_goal=yearly_mins,
                color=color_value if color_value else None,
            )

            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update(f"✓ Saved goals and color for '{
                              self._selected_activity}'")

            if hasattr(self.app, "notify"):
                self.app.notify(f"Saved goals and color for {
                                self._selected_activity}", title="Settings Updated")
        except Exception as e:
            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update(f"✗ Failed to save goals: {e}")

    @on(Button.Pressed, "#btn-delete-activity")
    def on_delete_activity_pressed(self) -> None:
        """Delete the selected activity from the database."""
        if self._selected_activity in ["all", "other"]:
            # Don't allow deletion of protected activities
            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update("✗ Cannot delete protected activity")
            return

        history_store = getattr(
            self.app, "history_store", None) or HistoryStore()

        # Delete the activity from database
        try:
            with history_store._db._get_connection() as conn:
                conn.execute(
                    "DELETE FROM activities WHERE name = ?",
                    (self._selected_activity.lower(),),
                )
                conn.commit()
        except Exception as e:
            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update(f"✗ Failed to delete activity: {str(e)}")
            return

        # Reset to "all" selection
        self._selected_activity = "all"
        self._refresh_activity_select()
        self._load_activity_goals(self._selected_activity)
        self._load_activity_color(self._selected_activity)

        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update(f"✓ Deleted activity")

        if hasattr(self.app, "notify"):
            self.app.notify("Activity deleted", title="Settings Updated")

    @on(Button.Pressed, "#btn-standard-preset")
    def on_standard_preset_pressed(self) -> None:
        """Apply the standard pomodoro preset (25/5/20/4)."""
        try:
            pomo_inp = self.query_one("#input-pomodoro", Input)
            short_inp = self.query_one("#input-short-break", Input)
            long_inp = self.query_one("#input-long-break", Input)
            cycles_inp = self.query_one("#input-cycles", Input)

            pomo_inp.value = "25m"
            short_inp.value = "5m"
            long_inp.value = "20m"
            cycles_inp.value = "4"

            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update("✓ Applied standard preset (25/5/20/4)")

            if hasattr(self.app, "notify"):
                self.app.notify("Applied standard preset",
                                title="Settings Updated")
        except Exception as e:
            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update(f"✗ Failed to apply preset: {str(e)}")

    @on(Select.Changed, "#preset-select")
    def on_preset_changed(self, event: Select.Changed) -> None:
        """Load selected preset values into inputs."""
        if event.value:
            self._selected_preset = str(event.value)
            self._load_preset_values(self._selected_preset)
            # Enable delete button
            delete_btn = self.query_one("#btn-delete-preset", Button)
            delete_btn.disabled = False
        else:
            self._selected_preset = None
            # Clear fields
            self._load_preset_values("")
            delete_btn = self.query_one("#btn-delete-preset", Button)
            delete_btn.disabled = True

    @on(Button.Pressed, "#btn-add-preset")
    def on_add_preset_pressed(self) -> None:
        """Add a new preset with name from input and values from fields."""
        name_input = self.query_one("#input-preset-name", Input)
        name = name_input.value.strip().lower()
        if not name:
            return
        # Gather values
        pomodoro = self.query_one(
            "#input-preset-pomodoro", Input).value.strip()
        short = self.query_one("#input-preset-short", Input).value.strip()
        long = self.query_one("#input-preset-long", Input).value.strip()
        cycles = self.query_one("#input-preset-cycles", Input).value.strip()
        if not all([pomodoro, short, long, cycles]):
            return
        # Update settings dict
        self.app.settings.setdefault("presets", {})[name] = f"{pomodoro.rstrip('m')} {
            short.rstrip('m')} {long.rstrip('m')} {cycles}"
        self._selected_preset = name
        self._write_presets_to_config()
        self._load_presets()
        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update(f"✓ Added preset '{name}'")
        if hasattr(self.app, "notify"):
            self.app.notify(f"Added preset {name}", title="Settings Updated")
        # Disable add button? keep enabled
        name_input.value = ""

    @on(Button.Pressed, "#btn-delete-preset")
    def on_delete_preset_pressed(self) -> None:
        """Delete the selected preset."""
        if not self._selected_preset:
            return
        # Remove from settings
        self.app.settings.get("presets", {}).pop(self._selected_preset, None)
        self._selected_preset = None
        self._write_presets_to_config()
        self._load_presets()
        # Clear fields
        self._load_preset_values("")
        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update("✓ Preset deleted")
        if hasattr(self.app, "notify"):
            self.app.notify("Preset deleted", title="Settings Updated")
        # Disable delete button
        delete_btn = self.query_one("#btn-delete-preset", Button)
        delete_btn.disabled = True

    @on(Button.Pressed, "#btn-save-preset")
    def on_save_preset_pressed(self) -> None:
        """Save changes to the selected preset."""
        if not self._selected_preset:
            return
        pomodoro = self.query_one(
            "#input-preset-pomodoro", Input).value.strip()
        short = self.query_one("#input-preset-short", Input).value.strip()
        long = self.query_one("#input-preset-long", Input).value.strip()
        cycles = self.query_one("#input-preset-cycles", Input).value.strip()
        if not all([pomodoro, short, long, cycles]):
            return
        self.app.settings.setdefault("presets", {})[self._selected_preset] = f"{
            pomodoro.rstrip('m')} {short.rstrip('m')} {long.rstrip('m')} {cycles}"
        self._write_presets_to_config()
        self._load_presets()
        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update(f"✓ Preset '{self._selected_preset}' saved")
        if hasattr(self.app, "notify"):
            self.app.notify(
                f"Preset {self._selected_preset} saved", title="Settings Updated")

    @on(Button.Pressed, "#btn-save-timer")
    def on_save_timer_pressed(self) -> None:
        """Save timer configuration settings."""
        self._save_timer_settings()

    def _load_activity_goals(self, activity_name: str) -> None:
        """Populate input fields from SQLite database for the selected activity."""
        history_store = getattr(
            self.app, "history_store", None) or HistoryStore()
        activities = history_store.get_activities()

        act_data = next((a for a in activities if a.get(
            "name") == activity_name.lower()), None)
        daily_inp = self.query_one("#input-daily-goal", Input)
        weekly_inp = self.query_one("#input-weekly-goal", Input)
        monthly_inp = self.query_one("#input-monthly-goal", Input)
        yearly_inp = self.query_one("#input-yearly-goal", Input)

        if act_data:
            daily_inp.value = _format_hours_str(act_data.get("daily_goal", 0))
            weekly_inp.value = _format_hours_str(
                act_data.get("weekly_goal", 0))
            monthly_inp.value = _format_hours_str(
                act_data.get("monthly_goal", 0))
            yearly_inp.value = _format_hours_str(
                act_data.get("yearly_goal", 0))
        else:
            daily_inp.value = ""
            weekly_inp.value = ""
            monthly_inp.value = ""
            yearly_inp.value = ""

    def _load_activity_color(self, activity_name: str) -> None:
        """Load and display the color for the selected activity."""
        if activity_name == "all":
            # Clear color input for "All / Total"
            color_input = self.query_one("#input-activity-color", Input)
            color_input.value = ""
            self._update_color_preview()
            delete_btn = self.query_one("#btn-delete-activity", Button)
            delete_btn.disabled = True
            return

        history_store = getattr(
            self.app, "history_store", None) or HistoryStore()
        activities = history_store.get_activities()

        act_data = next((a for a in activities if a.get(
            "name") == activity_name.lower()), None)

        color_input = self.query_one("#input-activity-color", Input)
        if act_data and act_data.get("color"):
            color_input.value = act_data["color"]
        else:
            color_input.value = ""

        self._update_color_preview()

        # Enable delete button for non-system activities
        delete_btn = self.query_one("#btn-delete-activity", Button)
        # Don't allow deletion of protected activities
        protected_activities = ["all", "other"]
        delete_btn.disabled = activity_name.lower() in protected_activities
        """Load and display the color for the selected activity."""
        if activity_name == "all":
            # Clear color input for "All / Total"
            color_input = self.query_one("#input-activity-color", Input)
            color_input.value = ""
            self._update_color_preview()
            delete_btn = self.query_one("#btn-delete-activity", Button)
            delete_btn.disabled = True
            return

        history_store = getattr(
            self.app, "history_store", None) or HistoryStore()
        activities = history_store.get_activities()

        act_data = next((a for a in activities if a.get(
            "name") == activity_name.lower()), None)

        color_input = self.query_one("#input-activity-color", Input)
        if act_data and act_data.get("color"):
            color_input.value = act_data["color"]
        else:
            color_input.value = ""

        self._update_color_preview()

        # Enable delete button for non-system activities
        delete_btn = self.query_one("#btn-delete-activity", Button)
        # Don't allow deletion of protected activities
        protected_activities = ["all", "other"]
        delete_btn.disabled = activity_name.lower() in protected_activities

    def _load_presets(self) -> None:
        """Populate the preset selector with available presets."""
        settings = getattr(self.app, "settings", {})
        presets = settings.get("presets", {})
        options = []
        for name in presets.keys():
            options.append((name.title(), name))
        try:
            sel = self.query_one("#preset-select", Select)
            sel.set_options(options)
            # If a preset is already selected and still exists, keep it
            if self._selected_preset and self._selected_preset in presets:
                sel.value = self._selected_preset
                self._load_preset_values(self._selected_preset)
            else:
                sel.value = ""
                self._selected_preset = None
        except Exception:
            pass

    def _load_preset_values(self, preset_name: str) -> None:
        """Load the values of the given preset into the input fields."""
        settings = getattr(self.app, "settings", {})
        preset_str = settings.get("presets", {}).get(preset_name, "")
        parts = preset_str.split()
        if len(parts) == 4:
            self.query_one("#input-preset-pomodoro",
                           Input).value = f"{parts[0]}m"
            self.query_one("#input-preset-short", Input).value = f"{parts[1]}m"
            self.query_one("#input-preset-long", Input).value = f"{parts[2]}m"
            self.query_one("#input-preset-cycles", Input).value = parts[3]
        else:
            # Clear fields if malformed
            self.query_one("#input-preset-pomodoro", Input).value = ""
            self.query_one("#input-preset-short", Input).value = ""
            self.query_one("#input-preset-long", Input).value = ""
            self.query_one("#input-preset-cycles", Input).value = ""

    def _write_presets_to_config(self) -> None:
        """Persist the current presets dict to the config file."""
        config_path = Path(self.app.settings.get(
            "config_file", DEFAULT_CONFIG_FILE))
        conf = configparser.ConfigParser()
        if config_path.exists():
            conf.read(config_path)
        if not conf.has_section("presets"):
            conf.add_section("presets")
        for name, value in self.app.settings.get("presets", {}).items():
            conf.set("presets", name, str(value))
        with open(config_path, "w") as f:
            conf.write(f)

        """Load timer settings from the app configuration."""
        if not hasattr(self.app, 'settings'):
            return

        settings = self.app.settings

        # Format and display the timer settings
        pomo_inp = self.query_one("#input-pomodoro", Input)
        short_inp = self.query_one("#input-short-break", Input)
        long_inp = self.query_one("#input-long-break", Input)
        cycles_inp = self.query_one("#input-cycles", Input)

        # Convert minutes to appropriate display format
        pomo_min = settings.get("pomodoro", 25)
        short_min = settings.get("short_break", 5)
        long_min = settings.get("long_break", 20)
        cycles = settings.get("cycles", 1)

        pomo_inp.value = f"{
            pomo_min}m" if pomo_min >= 1 else f"{pomo_min * 60}s"
        short_inp.value = f"{
            short_min}m" if short_min >= 1 else f"{short_min * 60}s"
        long_inp.value = f"{
            long_min}m" if long_min >= 1 else f"{long_min * 60}s"
        cycles_inp.value = str(cycles)

    def _save_timer_settings(self) -> None:
        """Save timer settings to the app configuration."""
        if not hasattr(self.app, 'settings'):
            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update("✗ Cannot access application settings")
            return

        try:
            pomo_inp = self.query_one("#input-pomodoro", Input)
            short_inp = self.query_one("#input-short-break", Input)
            long_inp = self.query_one("#input-long-break", Input)
            cycles_inp = self.query_one("#input-cycles", Input)

            # Parse the input values
            pomo_mins = parse_duration_string(pomo_inp.value.strip())
            short_mins = parse_duration_string(short_inp.value.strip())
            long_mins = parse_duration_string(long_inp.value.strip())
            cycles_val = int(cycles_inp.value.strip()
                             ) if cycles_inp.value.strip() else 1

            # Validate inputs
            if pomo_mins <= 0 or short_mins < 0 or long_mins < 0 or cycles_val <= 0:
                raise ValueError("Invalid timer values")

            # Update the app settings
            self.app.settings["pomodoro"] = pomo_mins
            self.app.settings["short_break"] = short_mins
            self.app.settings["long_break"] = long_mins
            self.app.settings["cycles"] = cycles_val

            # Also update the config file
            config_path = Path(self.app.settings.get(
                "config_file", DEFAULT_CONFIG_FILE))
            conf = configparser.ConfigParser()

            # Read existing config
            if config_path.exists():
                conf.read(config_path)

            # Update pomodoro section
            if not conf.has_section("pomodoro"):
                conf.add_section("pomodoro")

            conf.set("pomodoro", "pomodoro", f"{int(pomo_mins)}")
            conf.set("pomodoro", "short_break", f"{int(short_mins)}")
            conf.set("pomodoro", "long_break", f"{int(long_mins)}")
            conf.set("pomodoro", "cycles", str(cycles_val))

            # Write back to config file
            with open(config_path, 'w') as f:
                conf.write(f)

            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update("✓ Timer settings saved")

            if hasattr(self.app, "notify"):
                self.app.notify("Timer settings saved",
                                title="Settings Updated")

        except Exception as e:
            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update(f"✗ Failed to save timer settings: {str(e)}")

    def _write_general_config(self) -> None:
        """Write the current general/overlay settings to the config file."""
        config_path = Path(
            self.app.settings.get(
                "config_file",
                DEFAULT_CONFIG_FILE,
            )
        )
        conf = configparser.ConfigParser()

        if config_path.exists():
            conf.read(config_path)

        if not conf.has_section("general"):
            conf.add_section("general")

        values = {
            "overlay": str(self.app.settings["overlay"]).lower(),
            "block_input": str(
                self.app.settings["block_input"]
            ).lower(),
            "notify": str(self.app.settings["notify"]).lower(),
            "break_notify_msg": self.app.settings["break_notify_msg"],
            "long_break_notify_msg": self.app.settings[
                "long_break_notify_msg"
            ],
            "pomo_notify_msg": self.app.settings["pomo_notify_msg"],
            "callback": self.app.settings["callback"],
            "overlay_font_size": str(
                self.app.settings["overlay_font_size"]
            ),
            "overlay_color": self.app.settings["overlay_color"],
            "overlay_bg_color": self.app.settings[
                "overlay_bg_color"
            ],
            "overlay_opacity": str(
                self.app.settings["overlay_opacity"]
            ),
        }

        for key, value in values.items():
            conf.set("general", key, value)

        with open(config_path, "w") as f:
            conf.write(f)

    @on(Button.Pressed, "#btn-save-general")
    def on_save_general_pressed(self) -> None:
        """Save general settings."""
        self.app.settings["block_input"] = (
            self.query_one("#select-block-input", Select).value == "true"
        )
        self.app.settings["notify"] = (
            self.query_one("#select-notify", Select).value == "true"
        )
        self.app.settings["break_notify_msg"] = self.query_one(
            "#input-break-notify-msg",
            Input,
        ).value
        self.app.settings["long_break_notify_msg"] = self.query_one(
            "#input-long-break-notify-msg",
            Input,
        ).value
        self.app.settings["pomo_notify_msg"] = self.query_one(
            "#input-pomo-notify-msg",
            Input,
        ).value
        self.app.settings["callback"] = self.query_one(
            "#input-callback",
            Input,
        ).value
        # Save new streak indicator style
        self.app.settings["streak_indicator_style"] = self.query_one(
            "#select-streak-style",
            Select,
        ).value

        self._write_general_config()

        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update("✓ General settings saved")

        if hasattr(self.app, "notify"):
            self.app.notify(
                "General settings saved",
                title="Settings Updated",
            )

    @on(Button.Pressed, "#btn-save-overlay")
    def on_save_overlay_pressed(self) -> None:
        """Save overlay settings."""
        self.app.settings["overlay"] = (
            self.query_one("#select-overlay", Select).value == "true"
        )

        try:
            self.app.settings["overlay_font_size"] = int(
                self.query_one("#input-overlay-font-size", Input).value
            )
        except ValueError:
            self.app.settings["overlay_font_size"] = 48

        self.app.settings["overlay_color"] = self.query_one(
            "#input-overlay-color",
            Input,
        ).value
        self.app.settings["overlay_bg_color"] = self.query_one(
            "#input-overlay-bg-color",
            Input,
        ).value

        try:
            opacity = float(
                self.query_one("#input-overlay-opacity", Input).value
            )
            self.app.settings["overlay_opacity"] = max(
                0.0,
                min(1.0, opacity),
            )
        except ValueError:
            self.app.settings["overlay_opacity"] = 0.8

        self._write_general_config()

        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update("✓ Overlay settings saved")

        if hasattr(self.app, "notify"):
            self.app.notify(
                "Overlay settings saved",
                title="Settings Updated",
            )
