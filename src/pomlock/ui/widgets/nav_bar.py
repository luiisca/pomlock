from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Label

from ...constants import StatsView


class TopNavBar(Horizontal):
    """Top navigation bar for switching between Home and Stats views."""

    DEFAULT_CLASSES = "top-navbar-container"

    def __init__(self, active_tab: str = "home", id: str | None = "top-navbar"):
        super().__init__(id=id)
        self._active_tab = active_tab

    def compose(self) -> ComposeResult:
        yield Label("pomlock", classes="nav-brand-title")

        with Horizontal(classes="nav-btn-group"):
            yield Button(
                "[b]1[/b] home",
                id="nav-home",
                classes=f"nav-tab-btn {'nav-tab-active' if self._active_tab == 'home' else ''}",
            )
            yield Button(
                "[b]2[/b] today",
                id="nav-today",
                classes=f"nav-tab-btn {'nav-tab-active' if self._active_tab == 'today' else ''}",
            )
            yield Button(
                "[b]3[/b] week",
                id="nav-week",
                classes=f"nav-tab-btn {'nav-tab-active' if self._active_tab == 'week' else ''}",
            )
            yield Button(
                "[b]4[/b] month",
                id="nav-month",
                classes=f"nav-tab-btn {'nav-tab-active' if self._active_tab == 'month' else ''}",
            )
            yield Button(
                "[b]5[/b] year",
                id="nav-year",
                classes=f"nav-tab-btn {'nav-tab-active' if self._active_tab == 'year' else ''}",
            )

    @on(Button.Pressed, "#nav-home")
    def _go_home(self) -> None:
        self.app.action_show_main()

    @on(Button.Pressed, "#nav-today")
    def _go_today(self) -> None:
        self.app.action_show_today()

    @on(Button.Pressed, "#nav-week")
    def _go_week(self) -> None:
        self.app.action_show_week()

    @on(Button.Pressed, "#nav-month")
    def _go_month(self) -> None:
        self.app.action_show_month()

    @on(Button.Pressed, "#nav-year")
    def _go_year(self) -> None:
        self.app.action_show_year()

    def set_active_tab(self, tab: str) -> None:
        """Update active tab indicator."""
        self._active_tab = tab
        for btn_id, name in [
            ("nav-home", "home"),
            ("nav-today", "today"),
            ("nav-week", "week"),
            ("nav-month", "month"),
            ("nav-year", "year"),
        ]:
            try:
                btn = self.query_one(f"#{btn_id}", Button)
                if name == tab:
                    btn.add_class("nav-tab-active")
                else:
                    btn.remove_class("nav-tab-active")
            except Exception:
                pass
