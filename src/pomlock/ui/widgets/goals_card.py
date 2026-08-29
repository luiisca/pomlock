from typing import cast
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, ProgressBar

from ...constants import DEFAULT_GOALS
from ...history_store import HistoryStore


def _format_hm(minutes: int) -> str:
    """Format minutes to 'Xh Ym' string."""
    h, m = divmod(minutes, 60)
    if h > 0 and m > 0:
        return f"{h}h {m:02d}m"
    elif h > 0:
        return f"{h}h"
    return f"{m}m"


def _format_diff(tracked_m: int, target_m: int) -> str:
    """Format difference between tracked and target minutes."""
    diff = tracked_m - target_m
    if diff >= 0:
        return f"+{_format_hm(diff)}"
    return f"-{_format_hm(abs(diff))}"


class GoalsCard(Vertical):
    """Card displaying daily goals with real-time progress against CSV history."""

    DEFAULT_CLASSES = "card-container goals-box"

    def __init__(self, id: str | None = "goals-card"):
        super().__init__(id=id)

    def compose(self) -> ComposeResult:
        yield Label("today goals", classes="card-tag")
        # Dynamic goal entries container
        with Vertical(id="goals-entries-container"):
            pass

    def on_mount(self) -> None:
        """Populate and refresh goals periodically."""
        self.refresh_goals()
        # Auto refresh every minute
        self.set_interval(60.0, self.refresh_goals)

    def refresh_goals(self) -> None:
        """Query history store and update daily goal progress."""
        history_store = getattr(self.app, "history_store", None) or HistoryStore()
        settings = getattr(self.app, "settings", {})
        configured_goals = settings.get("goals", DEFAULT_GOALS)

        # Get today's tracked focus minutes
        today_by_act = history_store.get_today_focus_by_activity()
        total_tracked = history_store.get_today_total_focus_minutes()

        # Parse targets
        targets: list[tuple[str, int, int]] = []

        # Total goal
        total_target_str = configured_goals.get("total", 420)
        try:
            total_target = int(total_target_str)
        except ValueError:
            total_target = 420
        targets.append(("total", total_tracked, total_target))

        # Activity goals
        for key, target_val in configured_goals.items():
            if key == "total":
                continue
            act_name = key.lower()
            try:
                target_m = int(target_val)
            except ValueError:
                target_m = 60
            tracked_m = today_by_act.get(act_name, 0)
            targets.append((act_name, tracked_m, target_m))

        container = self.query_one("#goals-entries-container", Vertical)
        container.remove_children()

        for idx, (label, tracked, target) in enumerate(targets):
            pct = min(100, int((tracked / max(1, target)) * 100))
            header_text = f"{_format_hm(tracked)} / {_format_hm(target)}"
            diff_text = _format_diff(tracked, target)

            entry = Vertical(classes="goal-entry")
            container.mount(entry)
            entry.mount(Label(header_text, classes="goal-header"))

            bar_row = Horizontal(classes="goal-bar-row")
            entry.mount(bar_row)
            pb = ProgressBar(
                total=100,
                show_percentage=False,
                show_eta=False,
                classes="goal-progress",
                id=f"goal-pb-{idx}",
            )
            bar_row.mount(pb)
            bar_row.mount(Label(diff_text, classes="goal-diff"))
            entry.mount(Label(label, classes="goal-sublabel"))

            pb.progress = pct
