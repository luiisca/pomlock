from datetime import date
from itertools import groupby
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Label

from ...constants import ACTIVITY_COLORS
from ...history_store import HistoryStore


def _format_duration(minutes: int) -> str:
    """Format minutes to 'Xh Ym' or 'Ym'."""
    h, m = divmod(minutes, 60)
    if h > 0 and m > 0:
        return f"{h}h {m:02d}m"
    elif h > 0:
        return f"{h}h 00m"
    return f"{m}m"


class ActivityListCard(Vertical):
    """Scrollable chronological activity history with color-coded variable-height bars."""

    DEFAULT_CLASSES = "card-container activity-list-box"

    def __init__(self, id: str | None = "activity-list-card"):
        super().__init__(id=id)

    def compose(self) -> ComposeResult:
        yield Label("list", classes="card-tag")

        with VerticalScroll(id="activity-scroll-container", classes="activity-items-list"):
            pass

    def on_mount(self) -> None:
        """Load and render activity history."""
        self.refresh_list()
        self.set_interval(60.0, self.refresh_list)

    def refresh_list(self) -> None:
        """Query HistoryStore and populate chronological activity entries grouped by date."""
        history_store = getattr(self.app, "history_store", None) or HistoryStore()
        sessions = history_store.get_all_focus_sessions_sorted(ascending=True)

        container = self.query_one("#activity-scroll-container", VerticalScroll)
        container.remove_children()

        if not sessions:
            container.mount(Label("No session history recorded yet.", classes="subtext-dim"))
            return

        # Group sessions by date
        for session_date, day_sessions in groupby(sessions, key=lambda s: s["date"]):
            # Date pill badge format: '26 August, Wed'
            date_str = session_date.strftime("%d %B, %a").lstrip("0")
            container.mount(Label(date_str, classes="date-pill-badge"))

            for s in day_sessions:
                act = s["activity"]
                dur_m = s["duration_minutes"]
                start_time = s["time"]
                dur_text = _format_duration(dur_m)
                bar_color = ACTIVITY_COLORS.get(act.lower(), "bar-gray")

                # Height lines proportional to duration
                bar_lines = max(1, min(4, (dur_m + 30) // 45))
                bar_art = "\n".join(["▌"] * bar_lines)

                row = Horizontal(classes="activity-row")
                container.mount(row)

                time_lbl = Label(start_time, classes="activity-time")
                bar_lbl = Label(bar_art, classes=f"activity-bar {bar_color}")
                name_lbl = Label(act.capitalize(), classes="activity-name")
                dur_lbl = Label(dur_text, classes="activity-duration")

                row.mount(time_lbl)
                row.mount(bar_lbl)
                row.mount(name_lbl)
                row.mount(dur_lbl)

        # Scroll to bottom so newest entries are in view
        container.scroll_end(animate=False)
