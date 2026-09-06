from datetime import date
import math
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label
from textual_plot import HiResMode, PlotWidget

from ...history_store import HistoryStore
from ...settings import Settings

MIN_HOURS_SCALE = 1.0
MINUTES_PER_HOUR = 60
PLOT_MARGIN_TOP = 0
PLOT_MARGIN_LEFT = 6
PLOT_MARGIN_BOTTOM = 1

ACTIVITY_PLOT_COLORS: dict[str, str] = {
    "all": "cyan",
    "coding": "blue",
    "studying": "yellow",
    "reading": "magenta",
    "sleep": "green",
    "anki": "purple",
    "system": "cyan",
    "exercise": "red",
    "other": "white",
}


class StatsChartCard(Vertical):
    """Weekly focus bar chart card using textual-plot for data visualization."""

    DEFAULT_CLASSES = "card-container stats-chart-box"

    BINDINGS = [
        Binding("left", "prev_week", "Prev Week", show=False),
        Binding("right", "next_week", "Next Week", show=False),
        Binding("a", "cycle_act", "Cycle Activity", show=False),
    ]

    def __init__(self, id: str | None = "stats-chart-card"):
        super().__init__(id=id)
        self._week_offset = 0
        self._selected_activity = "all"

    def _get_activities(self) -> list[str]:
        # Extract configured activities from Settings singleton
        settings = Settings()
        raw_acts = settings.get("activities", {})
        activities = ["all"]

        if isinstance(raw_acts, dict):
            for name in raw_acts.keys():
                clean_name = str(name).strip().lower()
                if (
                    clean_name not in ("auto_calc", "all", "total")
                    and clean_name not in activities
                ):
                    activities.append(clean_name)

        return activities

    def cycle_activity(self) -> str:
        # Cycle through available activity filters
        activities = self._get_activities()
        if not activities:
            return "all"

        try:
            curr_idx = activities.index(self._selected_activity)
            next_idx = (curr_idx + 1) % len(activities)
        except ValueError:
            next_idx = 0

        self._selected_activity = activities[next_idx]
        self.refresh_chart()
        return self._selected_activity

    def compose(self) -> ComposeResult:
        self.border_title = f"stats ({self._selected_activity})"

        # Header with navigation controls and active activity toggle
        with Horizontal(classes="stats-nav-header-row"):
            yield Button("◀", id="btn-chart-prev", classes="btn-chart-nav")
            yield Label(
                "--/-- - --/--", id="chart-date-range", classes="date-range-header"
            )
            yield Button("▶", id="btn-chart-next", classes="btn-chart-nav")
            yield Button(
                self._selected_activity, id="btn-chart-act", classes="btn-chart-act"
            )

        yield PlotWidget(id="stats-plot-widget")

    def on_mount(self) -> None:
        """Render chart on mount."""
        self.refresh_chart()

    @on(Button.Pressed, "#btn-chart-prev")
    def action_prev_week(self) -> None:
        """Navigate to previous week."""
        self._week_offset -= 1
        self.refresh_chart()

    @on(Button.Pressed, "#btn-chart-next")
    def action_next_week(self) -> None:
        """Navigate to next week."""
        self._week_offset += 1
        self.refresh_chart()

    @on(Button.Pressed, "#btn-chart-act")
    def action_cycle_act(self) -> None:
        """Cycle activity filter."""
        self.cycle_activity()

    def refresh_chart(self) -> None:
        """Fetch weekly data from HistoryStore and plot bars using textual-plot."""
        history_store = getattr(self.app, "history_store", None) or HistoryStore()
        week_label, days_data = history_store.get_weekly_focus_by_day(
            week_offset=self._week_offset,
            activity=self._selected_activity,
        )

        self.border_title = f"stats ({self._selected_activity})"

        try:
            act_btn = self.query_one("#btn-chart-act", Button)
            act_btn.label = self._selected_activity
        except Exception:
            pass

        # Update date range label
        try:
            range_label = self.query_one("#chart-date-range", Label)
            range_label.update(f"{week_label}")
        except Exception:
            pass

        # Plot data using PlotWidget
        try:
            plot = self.query_one(PlotWidget)
            plot.margin_top = PLOT_MARGIN_TOP
            plot.margin_left = PLOT_MARGIN_LEFT
            plot.margin_bottom = PLOT_MARGIN_BOTTOM

            plot.clear()

            x_vals = [d.strftime("%a") for d, _ in days_data]
            y_vals = [minutes / float(MINUTES_PER_HOUR) for _, minutes in days_data]

            max_hours = max(y_vals + [0.0])
            upper_limit = max(MIN_HOURS_SCALE, math.ceil(max_hours))
            plot.set_ylimits(ymin=0.0, ymax=upper_limit)

            color = ACTIVITY_PLOT_COLORS.get(self._selected_activity, "cyan")
            plot.bar(
                x=x_vals,
                y=y_vals,
                bar_style=color,
                hires_mode=HiResMode.HALFBLOCK,
            )
        except Exception:
            pass
