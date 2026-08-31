from typing import Optional
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
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
from ..widgets.footer_bar import FooterBar
from ..widgets.nav_bar import TopNavBar
import configparser
from pathlib import Path


def _format_hours_str(minutes: int) -> str:
    """Format minutes into clean hour/minute string."""
    h, m = divmod(max(0, minutes), 60)
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}m"


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
        self.OLIVE_GARDEN_PALETTE = ["#606c38","#283618","#fefae0","#dda15e","#bc6c25"]
        self._timer_settings_loaded = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="app-shell"):
            yield TopNavBar(active_tab="settings", id="settings-top-navbar")

            with Vertical(classes="card-container settings-container"):
                yield Label("Activity Configuration", classes="card-tag")

                # Activity Selector Row with Color and Delete
                with Horizontal(classes="settings-row"):
                    yield Label("Activity:", classes="settings-label")
                    yield Select(
                        [("All / Total", "all")],
                        value="all",
                        allow_blank=False,
                        id="activity-select",
                        classes="settings-select",
                    )
                    yield Input(
                        placeholder="#FF5733",
                        id="input-activity-color",
                        classes="settings-input color-input",
                    )
                    yield Label(id="color-preview", classes="color-preview")
                    yield Button("Delete", id="btn-delete-activity", classes="btn-danger", disabled=True)
                    yield Button("Olive Palette", id="btn-olive-palette", classes="btn-secondary")

                # Add New Activity Row
                with Horizontal(classes="settings-row"):
                    yield Label("New Activity:", classes="settings-label")
                    yield Input(
                        placeholder="Type new activity name...",
                        id="input-new-activity",
                        classes="settings-input",
                    )
                    yield Button("Add", id="btn-add-activity", classes="btn-secondary")

                # Daily Goal Input
                with Horizontal(classes="settings-row"):
                    yield Label("Daily Goal:", classes="settings-label")
                    yield Input(
                        placeholder="e.g. 8h or 480m",
                        id="input-daily-goal",
                        classes="settings-input",
                    )

                # Monthly Goal Input
                with Horizontal(classes="settings-row"):
                    yield Label("Monthly Goal:", classes="settings-label")
                    yield Input(
                        placeholder="e.g. 176h",
                        id="input-monthly-goal",
                        classes="settings-input",
                    )

                # Yearly Goal Input
                with Horizontal(classes="settings-row"):
                    yield Label("Yearly Goal:", classes="settings-label")
                    yield Input(
                        placeholder="e.g. 2080h",
                        id="input-yearly-goal",
                        classes="settings-input",
                    )

                # Action Buttons
                with Horizontal(classes="settings-btn-row"):
                    yield Button("Save Goals", id="btn-save-goals", classes="btn-primary")

                yield Label("", id="settings-status-msg", classes="settings-status")

                # Timer Configuration Section
                yield Label("Timer Configuration", classes="card-tag")

                # Pomodoro Length Input
                with Horizontal(classes="settings-row"):
                    yield Label("Pomodoro:", classes="settings-label")
                    yield Input(
                        placeholder="e.g. 25m or 1500s",
                        id="input-pomodoro",
                        classes="settings-input",
                    )

                # Short Break Input
                with Horizontal(classes="settings-row"):
                    yield Label("Short Break:", classes="settings-label")
                    yield Input(
                        placeholder="e.g. 5m or 300s",
                        id="input-short-break",
                        classes="settings-input",
                    )

                # Long Break Input
                with Horizontal(classes="settings-row"):
                    yield Label("Long Break:", classes="settings-label")
                    yield Input(
                        placeholder="e.g. 20m or 1200s",
                        id="input-long-break",
                        classes="settings-input",
                    )

                # Cycles Input
                with Horizontal(classes="settings-row"):
                    yield Label("Cycles:", classes="settings-label")
                    yield Input(
                        placeholder="e.g. 4",
                        id="input-cycles",
                        classes="settings-input",
                    )

                # Timer Action Buttons
                with Horizontal(classes="settings-btn-row"):
                    yield Button("Save Timer Settings", id="btn-save-timer", classes="btn-primary")
                    yield Button("Apply Standard Preset", id="btn-standard-preset", classes="btn-secondary")

            yield FooterBar()

    def on_mount(self) -> None:
        """Load activities and current goals on mount."""
        self._refresh_activity_select()
        self._load_activity_goals(self._selected_activity)
        self._load_activity_color(self._selected_activity)
        self._load_timer_settings()
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
                    int(color_value[1:], 16)  # Validate it's a valid hex number
                    preview_label = self.query_one("#color-preview", Label)
                    preview_label.update("■")
                    preview_label.styles.background = color_value
                    preview_label.styles.color = color_value
                except ValueError:
                    # Invalid hex, reset preview
                    preview_label = self.query_one("#color-preview", Label)
                    preview_label.update("")
                    preview_label.styles.background = "transparent"
                    preview_label.styles.color = "initial"
            else:
                # Invalid or empty color, reset preview
                preview_label = self.query_one("#color-preview", Label)
                preview_label.update("")
                preview_label.styles.background = "transparent"
                preview_label.styles.color = "initial"
        except Exception:
            # If anything goes wrong, reset preview safely
            try:
                preview_label = self.query_one("#color-preview", Label)
                preview_label.update("")
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
        daily_inp = self.query_one("#input-daily-goal", Input)
        monthly_inp = self.query_one("#input-monthly-goal", Input)
        yearly_inp = self.query_one("#input-yearly-goal", Input)
        color_inp = self.query_one("#input-activity-color", Input)

        daily_mins = parse_duration_string(daily_inp.value)
        monthly_mins = parse_duration_string(monthly_inp.value)
        yearly_mins = parse_duration_string(yearly_inp.value)
        color_value = color_inp.value.strip()

        # Validate color input
        if color_value and (not color_value.startswith('#') or len(color_value) != 7):
            try:
                int(color_value[1:], 16)
            except (ValueError, IndexError):
                color_value = ""  # Invalid color, save as None

        weekly_mins = daily_mins * WORK_DAYS_PER_WEEK if daily_mins > 0 else 0

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
        status_lbl.update(f"✓ Saved goals and color for '{self._selected_activity}'")

        if hasattr(self.app, "notify"):
            self.app.notify(f"Saved goals and color for {
                            self._selected_activity}", title="Settings Updated")

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

    @on(Button.Pressed, "#btn-olive-palette")
    def on_olive_palette_pressed(self) -> None:
        """Apply the Olive Garden Feast palette to activities."""
        history_store = getattr(
            self.app, "history_store", None) or HistoryStore()
        activities = history_store.get_activities()

        # Filter out protected activities and "all"
        activity_names = [
            act.get("name") for act in activities
            if act.get("name") not in ["all", "other"] and act.get("name")
        ]

        if not activity_names:
            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update("✗ No activities to apply palette to")
            return

        # Apply palette colors: use palette for first N activities, then random for the rest
        try:
            with history_store._db._get_connection() as conn:
                for i, activity_name in enumerate(activity_names):
                    if i < len(self.OLIVE_GARDEN_PALETTE):
                        color_value = self.OLIVE_GARDEN_PALETTE[i]
                    else:
                        # Generate a random color for extra activities
                        color_value = "#{:06x}".format(random.randint(0, 0xFFFFFF))
                    conn.execute(
                        """
                        UPDATE activities
                        SET color = ?
                        WHERE name = ?
                        """,
                        (color_value, activity_name.lower()),
                    )
                conn.commit()
        except Exception as e:
            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update(f"✗ Failed to apply palette: {str(e)}")
            return

        # Reload the current activity's color
        self._load_activity_color(self._selected_activity)

        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update(f"✓ Applied Olive Garden palette to {len(activity_names)} activities")

        if hasattr(self.app, "notify"):
            self.app.notify(f"Applied Olive Garden palette to {len(activity_names)} activities",
                          title="Settings Updated")

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
                self.app.notify("Applied standard preset", title="Settings Updated")
        except Exception as e:
            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update(f"✗ Failed to apply preset: {str(e)}")

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
        monthly_inp = self.query_one("#input-monthly-goal", Input)
        yearly_inp = self.query_one("#input-yearly-goal", Input)

        if act_data:
            daily_inp.value = _format_hours_str(act_data.get("daily_goal", 0))
            monthly_inp.value = _format_hours_str(
                act_data.get("monthly_goal", 0))
            yearly_inp.value = _format_hours_str(
                act_data.get("yearly_goal", 0))
        else:
            daily_inp.value = ""
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

    def _load_timer_settings(self) -> None:
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

        pomo_inp.value = f"{pomo_min}m" if pomo_min >= 1 else f"{pomo_min * 60}s"
        short_inp.value = f"{short_min}m" if short_min >= 1 else f"{short_min * 60}s"
        long_inp.value = f"{long_min}m" if long_min >= 1 else f"{long_min * 60}s"
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
            cycles_val = int(cycles_inp.value.strip()) if cycles_inp.value.strip() else 1

            # Validate inputs
            if pomo_mins <= 0 or short_mins < 0 or long_mins < 0 or cycles_val <= 0:
                raise ValueError("Invalid timer values")

            # Update the app settings
            self.app.settings["pomodoro"] = pomo_mins
            self.app.settings["short_break"] = short_mins
            self.app.settings["long_break"] = long_mins
            self.app.settings["cycles"] = cycles_val

            # Also update the config file
            config_path = Path(self.app.settings.get("config_file", DEFAULT_CONFIG_FILE))
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
                self.app.notify("Timer settings saved", title="Settings Updated")

        except Exception as e:
            status_lbl = self.query_one("#settings-status-msg", Label)
            status_lbl.update(f"✗ Failed to save timer settings: {str(e)}")
