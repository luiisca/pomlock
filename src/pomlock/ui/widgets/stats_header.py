from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Label, ProgressBar

from ...constants import StatsView


class StatsHeader(Horizontal):
    """Header widget for analytics screens with tabs and ratio indicator."""

    DEFAULT_CLASSES = "stats-header-bar"

    class ViewSelected(Message):
        """Dispatched when a stats tab is clicked."""

        def __init__(self, view: StatsView):
            super().__init__()
            self.view = view

    def __init__(
        self,
        active_view: StatsView = StatsView.TODAY,
        id: str | None = "stats-header",
    ):
        super().__init__(id=id)
        self._active_view = active_view

    def compose(self) -> ComposeResult:
        # Left: Total time block
        with Vertical(classes="stats-header-time-box"):
            yield Label("stats", classes="card-tag")
            yield Label("2h 55m", classes="stats-big-time")
            yield Label("focus per day (avg)", classes="subtext-dim")

        # Center: View Navigation Tabs
        with Horizontal(classes="stats-nav-tabs"):
            yield Button(
                "today",
                id="tab-today",
                classes=f"tab-btn {'tab-active' if self._active_view == StatsView.TODAY else ''}",
            )
            yield Button(
                "this week",
                id="tab-week",
                classes=f"tab-btn {'tab-active' if self._active_view == StatsView.WEEK else ''}",
            )
            yield Button(
                "this month",
                id="tab-month",
                classes=f"tab-btn {'tab-active' if self._active_view == StatsView.MONTH else ''}",
            )
            yield Button(
                "this year",
                id="tab-year",
                classes=f"tab-btn {'tab-active' if self._active_view == StatsView.YEAR else ''}",
            )
            yield Button("⏚ all", id="tab-filter", classes="tab-btn filter-btn")

        # Right: Focus-Break ratio box
        with Vertical(classes="focus-break-box"):
            yield Label("focus-break ratio", classes="card-tag")
            with Horizontal(classes="ratio-bar-row"):
                yield Label("84%", classes="ratio-pct-label")
                yield ProgressBar(
                    total=100,
                    show_percentage=False,
                    show_eta=False,
                    classes="ratio-progress",
                    id="ratio-pb",
                )
                yield Label("16%", classes="ratio-pct-label")

    def on_mount(self) -> None:
        """Set initial ratio progress value."""
        self.query_one("#ratio-pb", ProgressBar).progress = 84

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle tab switching button events."""
        btn_id = event.button.id
        view_map = {
            "tab-today": StatsView.TODAY,
            "tab-week": StatsView.WEEK,
            "tab-month": StatsView.MONTH,
            "tab-year": StatsView.YEAR,
        }
        if btn_id in view_map:
            self._active_view = view_map[btn_id]
            self._update_active_tabs()
            self.post_message(self.ViewSelected(self._active_view))

    def _update_active_tabs(self) -> None:
        """Update active styling on tab buttons."""
        for tab_id, view in [
            ("tab-today", StatsView.TODAY),
            ("tab-week", StatsView.WEEK),
            ("tab-month", StatsView.MONTH),
            ("tab-year", StatsView.YEAR),
        ]:
            btn = self.query_one(f"#{tab_id}", Button)
            if view == self._active_view:
                btn.add_class("tab-active")
            else:
                btn.remove_class("tab-active")
