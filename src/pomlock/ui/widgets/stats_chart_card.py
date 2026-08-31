from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label

from ...history_store import HistoryStore


class StatsChartCard(Vertical):
    """Interactive weekly stats bar chart with arrow navigation pulling real CSV data."""

    DEFAULT_CLASSES = "card-container stats-chart-box"

    def __init__(self, id: str | None = "stats-chart-card"):
        super().__init__(id=id)
        self._week_offset = 0

    def compose(self) -> ComposeResult:
        yield Label("stats", classes="card-title")

        # Timeframe header with interactive navigation arrows
        with Horizontal(classes="stats-nav-header-row"):
            yield Button("◀", id="btn-chart-prev", classes="btn-chart-nav")
            yield Label("<< --/-- - --/-- >>", id="chart-date-range", classes="date-range-header")
            yield Button("▶", id="btn-chart-next", classes="btn-chart-nav")

        # Renderable ASCII chart area
        yield Label("", id="stats-ascii-chart", classes="ascii-chart")

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

    def refresh_chart(self) -> None:
        """Fetch weekly data from HistoryStore and generate 7-column vertical bar chart."""
        history_store = getattr(self.app, "history_store", None) or HistoryStore()
        week_label, days_data = history_store.get_weekly_focus_by_day(self._week_offset)

        # Update date range label
        range_label = self.query_one("#chart-date-range", Label)
        range_label.update(f"<< {week_label} >>")

        # Calculate max hours (minimum 6h baseline like wireframe)
        max_minutes = max([minutes for _, minutes in days_data] + [360])
        max_hours = max(6, (max_minutes + 59) // 60)

        # Build 7-column chart rows
        lines: list[str] = []
        for h in range(max_hours, 0, -1):
            row = f"{h}h │ "
            for _, minutes in days_data:
                day_hours = minutes / 60.0
                if day_hours >= h:
                    row += " █  "
                elif day_hours >= h - 0.5:
                    row += " ▄  "
                else:
                    row += "    "
            lines.append(row.rstrip())

        # Axis line
        lines.append("───┴────────────────────────")

        # Day numbers row (e.g. 10 11 12 13 14 15 16)
        day_nums_row = "     " + " ".join(f"{d.day:02d} " for d, _ in days_data)
        lines.append(day_nums_row)

        chart_label = self.query_one("#stats-ascii-chart", Label)
        chart_label.update("\n".join(lines))
