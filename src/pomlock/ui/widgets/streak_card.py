from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label


class StreakCard(Vertical):
    """Streak tracking card displaying week status boxes."""

    DEFAULT_CLASSES = "card-container streak-box"

    def __init__(self, streak_days: int = 4, id: str | None = "streak-card"):
        super().__init__(id=id)
        self._streak_days = streak_days

    def compose(self) -> ComposeResult:
        self.border_title = "streak"

        # Week day check indicators
        with Horizontal(classes="streak-days-row"):
            days = [
                ("M", "✓", "status-done"),
                ("T", "✓", "status-done"),
                ("W", "✗", "status-miss"),
                ("T", "✓", "status-done"),
                ("F", "✓", "status-done"),
                ("S", "✗", "status-miss"),
                ("S", "·", "status-pending"),
            ]
            for day_name, icon, status_class in days:
                with Vertical(classes="streak-col"):
                    yield Label(icon, classes=f"streak-icon-box {status_class}")
                    yield Label(day_name, classes="streak-day-label")
