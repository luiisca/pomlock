from dataclasses import dataclass
from datetime import datetime
from itertools import groupby
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Label

from ...constants import ACTIVITY_COLORS
from ...history_store import HistoryStore

GAP_THRESHOLD_S = 60
BREAK_LABELS = {
    "short_break": "short break",
    "long_break": "long break",
}


@dataclass(frozen=True)
class TimelineEntry:
    """A renderable focus, break, or untracked interval."""

    started_at: datetime
    ended_at: datetime
    duration_s: int
    kind: str
    activity: str = ""


def _format_duration(minutes: int) -> str:
    """Format minutes to 'Xh Ym' or 'Ym'."""
    h, m = divmod(minutes, 60)
    if h > 0 and m > 0:
        return f"{h}h {m:02d}m"
    elif h > 0:
        return f"{h}h 00m"
    return f"{m}m"


def build_timeline(blocks: list[dict]) -> list[TimelineEntry]:
    """Insert untracked intervals between recorded focus and break blocks."""
    entries: list[TimelineEntry] = []
    previous_end: datetime | None = None

    for block in blocks:
        started_at = block["started_at"]
        ended_at = block["ended_at"]

        if previous_end is not None:
            gap_s = int((started_at - previous_end).total_seconds())
            if gap_s > GAP_THRESHOLD_S:
                entries.append(TimelineEntry(
                    started_at=previous_end,
                    ended_at=started_at,
                    duration_s=gap_s,
                    kind="gap",
                ))

        entries.append(TimelineEntry(
            started_at=started_at,
            ended_at=ended_at,
            duration_s=block["duration_s"],
            kind=block["session_type"],
            activity=block["activity"],
        ))

        if previous_end is None or ended_at > previous_end:
            previous_end = ended_at

    return entries


class ActivityListCard(Vertical):
    """Scrollable chronological activity history with color-coded variable-height bars."""

    DEFAULT_CLASSES = "card-container activity-list-box"

    def __init__(self, id: str | None = "activity-list-card"):
        super().__init__(id=id)

    def compose(self) -> ComposeResult:
        self.border_title = "history"
        yield VerticalScroll(id="activity-scroll-container", classes="activity-items-list")

    def on_mount(self) -> None:
        """Load and render activity history."""
        self.refresh_list()
        self.set_interval(60.0, self.refresh_list)

    def refresh_list(self) -> None:
        """Query HistoryStore and populate chronological activity entries grouped by date."""
        history_store = getattr(
            self.app, "history_store", None) or HistoryStore()
        entries = build_timeline(
            history_store.get_all_blocks_sorted(ascending=True))

        container = self.query_one(
            "#activity-scroll-container", VerticalScroll)
        container.remove_children()

        if not entries:
            container.mount(
                Label("No session history recorded yet.", classes="subtext-dim"))
            return

        # Group intervals by their start date.
        for session_date, day_entries in groupby(entries, key=lambda entry: entry.started_at.date()):
            # Date pill badge format: '26 August, Wed'
            date_str = session_date.strftime("%d %B, %a").lstrip("0")
            container.mount(Label(date_str, classes="date-pill-badge"))

            for entry in day_entries:
                container.mount(self._make_row(entry))

        # Scroll to bottom so newest entries are in view
        container.scroll_end(animate=False)

    def _make_row(self, entry: TimelineEntry) -> Horizontal:
        """Build a timeline row with appearance based on interval kind."""
        duration_m = entry.duration_s // 60
        classes = "activity-row"
        bar_color = "bar-gray"
        label = entry.activity.capitalize()
        bar_art = "▌"

        if entry.kind == "gap":
            classes = "activity-row activity-gap-row"
            label = "untracked"
            bar_art = "░"
        elif entry.kind in BREAK_LABELS:
            classes = "activity-row activity-break-row"
            label = BREAK_LABELS[entry.kind]
            bar_art = "│"
        else:
            bar_color = ACTIVITY_COLORS.get(entry.activity.lower(), "bar-gray")
            bar_lines = max(1, min(4, (duration_m + 30) // 45))
            bar_art = "\n".join(["▌"] * bar_lines)

        return Horizontal(
            Label(entry.started_at.strftime("%H:%M"), classes="activity-time"),
            Label(bar_art, classes=f"activity-bar {bar_color}"),
            Label(label, classes="activity-name"),
            Label(_format_duration(duration_m), classes="activity-duration"),
            classes=classes,
        )
