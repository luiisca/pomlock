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
)
from ...history_store import HistoryStore
from ...utils import parse_duration_string
from ..widgets.footer_bar import FooterBar
from ..widgets.nav_bar import TopNavBar


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

    def compose(self) -> ComposeResult:
        with Vertical(classes="app-shell"):
            yield TopNavBar(active_tab="settings", id="settings-top-navbar")

            with Vertical(classes="card-container settings-container"):
                yield Label("Goal Configuration", classes="card-tag")

                # Activity Selector Row
                with Horizontal(classes="settings-row"):
                    yield Label("Activity:", classes="settings-label")
                    yield Select(
                        [("All / Total", "all")],
                        value="all",
                        allow_blank=False,
                        id="activity-select",
                        classes="settings-select",
                    )

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
                    yield Button("Auto Calculate", id="btn-auto-calc", classes="btn-secondary")

                yield Label("", id="settings-status-msg", classes="settings-status")

            # yield FooterBar(bindings=[("1", "home"), ("q", "quit")], id="settings-footer")
            yield Footer()

    def on_mount(self) -> None:
        """Load activities and current goals on mount."""
        self._refresh_activity_select()
        self._load_activity_goals(self._selected_activity)

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

    @on(Input.Changed, "#input-daily-goal")
    def on_daily_changed(self, event: Input.Changed) -> None:
        """Auto calculate monthly and yearly if they are currently blank."""
        val = event.value.strip()
        if not val:
            return

        monthly_inp = self.query_one("#input-monthly-goal", Input)
        yearly_inp = self.query_one("#input-yearly-goal", Input)

        if not monthly_inp.value.strip() and not yearly_inp.value.strip():
            d_mins = parse_duration_string(val)
            if d_mins > 0:
                monthly_inp.value = _format_hours_str(
                    d_mins * WORK_DAYS_PER_MONTH)
                yearly_inp.value = _format_hours_str(
                    d_mins * WORK_DAYS_PER_YEAR)

    @on(Input.Changed, "#input-monthly-goal")
    def on_monthly_changed(self, event: Input.Changed) -> None:
        """Auto calculate daily and yearly if they are currently blank."""
        val = event.value.strip()
        if not val:
            return

        daily_inp = self.query_one("#input-daily-goal", Input)
        yearly_inp = self.query_one("#input-yearly-goal", Input)

        if not daily_inp.value.strip() and not yearly_inp.value.strip():
            m_mins = parse_duration_string(val)
            if m_mins > 0:
                d_mins = max(1, m_mins // WORK_DAYS_PER_MONTH)
                daily_inp.value = _format_hours_str(d_mins)
                yearly_inp.value = _format_hours_str(
                    d_mins * WORK_DAYS_PER_YEAR)

    @on(Input.Changed, "#input-yearly-goal")
    def on_yearly_changed(self, event: Input.Changed) -> None:
        """Auto calculate daily and monthly if they are currently blank."""
        val = event.value.strip()
        if not val:
            return

        daily_inp = self.query_one("#input-daily-goal", Input)
        monthly_inp = self.query_one("#input-monthly-goal", Input)

        if not daily_inp.value.strip() and not monthly_inp.value.strip():
            y_mins = parse_duration_string(val)
            if y_mins > 0:
                d_mins = max(1, y_mins // WORK_DAYS_PER_YEAR)
                daily_inp.value = _format_hours_str(d_mins)
                monthly_inp.value = _format_hours_str(
                    d_mins * WORK_DAYS_PER_MONTH)

    @on(Button.Pressed, "#btn-auto-calc")
    def on_auto_calc_pressed(self) -> None:
        """Force recalculation based on first non-empty input."""
        daily_inp = self.query_one("#input-daily-goal", Input)
        monthly_inp = self.query_one("#input-monthly-goal", Input)
        yearly_inp = self.query_one("#input-yearly-goal", Input)

        if daily_inp.value.strip():
            d_mins = parse_duration_string(daily_inp.value)
            if d_mins > 0:
                monthly_inp.value = _format_hours_str(
                    d_mins * WORK_DAYS_PER_MONTH)
                yearly_inp.value = _format_hours_str(
                    d_mins * WORK_DAYS_PER_YEAR)
        elif monthly_inp.value.strip():
            m_mins = parse_duration_string(monthly_inp.value)
            if m_mins > 0:
                d_mins = max(1, m_mins // WORK_DAYS_PER_MONTH)
                daily_inp.value = _format_hours_str(d_mins)
                yearly_inp.value = _format_hours_str(
                    d_mins * WORK_DAYS_PER_YEAR)
        elif yearly_inp.value.strip():
            y_mins = parse_duration_string(yearly_inp.value)
            if y_mins > 0:
                d_mins = max(1, y_mins // WORK_DAYS_PER_YEAR)
                daily_inp.value = _format_hours_str(d_mins)
                monthly_inp.value = _format_hours_str(
                    d_mins * WORK_DAYS_PER_MONTH)

    @on(Button.Pressed, "#btn-save-goals")
    def on_save_pressed(self) -> None:
        """Persist entered goals to SQLite database."""
        daily_inp = self.query_one("#input-daily-goal", Input)
        monthly_inp = self.query_one("#input-monthly-goal", Input)
        yearly_inp = self.query_one("#input-yearly-goal", Input)

        daily_mins = parse_duration_string(daily_inp.value)
        monthly_mins = parse_duration_string(monthly_inp.value)
        yearly_mins = parse_duration_string(yearly_inp.value)

        weekly_mins = daily_mins * WORK_DAYS_PER_WEEK if daily_mins > 0 else (
            monthly_mins // WORK_DAYS_PER_MONTH) * WORK_DAYS_PER_WEEK

        history_store = getattr(
            self.app, "history_store", None) or HistoryStore()
        history_store.save_activity(
            name=self._selected_activity,
            daily_goal=daily_mins,
            weekly_goal=weekly_mins,
            monthly_goal=monthly_mins,
            yearly_goal=yearly_mins,
        )

        status_lbl = self.query_one("#settings-status-msg", Label)
        status_lbl.update(f"✓ Saved goals for '{self._selected_activity}'")

        if hasattr(self.app, "notify"):
            self.app.notify(f"Saved goals for {
                            self._selected_activity}", title="Settings Updated")

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
