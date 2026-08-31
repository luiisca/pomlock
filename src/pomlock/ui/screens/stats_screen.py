from typing import Optional
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen

from ...constants import GoalPeriod, StatsView
from ..widgets.activity_list import ActivityListCard
from ..widgets.footer_bar import FooterBar
from ..widgets.goals_card import GoalsCard
from ..widgets.nav_bar import TopNavBar
from ..widgets.placeholders import (
    MonthStatsWidget,
    TodayStatsWidget,
    WeekStatsWidget,
    YearStatsWidget,
)
from ..widgets.stats_header import StatsHeader


class StatsScreen(Screen):
    """Analytics screen supporting Today, Week, Month, and Year views with goal tracking."""

    def __init__(self, initial_view: StatsView = StatsView.TODAY):
        super().__init__()
        self._current_view = initial_view

    def compose(self) -> ComposeResult:
        with Vertical(classes="app-shell"):
            tab_name_map = {
                StatsView.TODAY: "today",
                StatsView.WEEK: "week",
                StatsView.MONTH: "month",
                StatsView.YEAR: "year",
            }
            yield TopNavBar(
                active_tab=tab_name_map.get(self._current_view, "today"),
                id="stats-top-navbar",
            )
            yield StatsHeader(active_view=self._current_view)

            # Container for interchangeable view content
            with Horizontal(id="stats-body-container", classes="stats-body-layout"):
                yield from self._get_view_widgets(self._current_view)

            yield FooterBar(
                bindings=[("z", "zen")],
                id="stats-footer",
            )

    def on_stats_header_view_selected(self, event: StatsHeader.ViewSelected) -> None:
        """Handle view change requests from tabs."""
        self.set_view(event.view)

    def update_live_goals(self, active_activity: Optional[str], session_elapsed_s: float) -> None:
        """Forward real-time elapsed seconds to any mounted GoalsCard in the stats view."""
        try:
            for card in self.query(GoalsCard):
                card.update_live_progress(active_activity, session_elapsed_s)
        except Exception:
            pass

    def set_view(self, view: StatsView) -> None:
        """Re-populate stats container with active view widget."""
        self._current_view = view
        tab_name_map = {
            StatsView.TODAY: "today",
            StatsView.WEEK: "week",
            StatsView.MONTH: "month",
            StatsView.YEAR: "year",
        }
        try:
            navbar = self.query_one("#stats-top-navbar", TopNavBar)
            navbar.set_active_tab(tab_name_map.get(view, "today"))
        except Exception:
            pass

        try:
            header = self.query_one(StatsHeader)
            header._active_view = view
            header._update_active_tabs()
        except Exception:
            pass

        try:
            container = self.query_one("#stats-body-container", Horizontal)
            container.remove_children()

            for widget in self._get_view_widgets(view):
                container.mount(widget)
        except Exception:
            pass

    def _get_view_widgets(self, view: StatsView) -> list:
        """Return the widgets corresponding to the selected view with respective goals."""
        if view == StatsView.TODAY:
            return [
                Vertical(TodayStatsWidget(), GoalsCard(period=GoalPeriod.DAILY), classes="stats-left-area"),
                Vertical(ActivityListCard(), classes="stats-right-area"),
            ]
        if view == StatsView.WEEK:
            return [
                Vertical(WeekStatsWidget(), classes="stats-left-area"),
                Vertical(GoalsCard(period=GoalPeriod.WEEKLY), classes="stats-right-area"),
            ]
        if view == StatsView.MONTH:
            return [
                Vertical(MonthStatsWidget(), classes="stats-left-area"),
                Vertical(GoalsCard(period=GoalPeriod.MONTHLY), classes="stats-right-area"),
            ]
        if view == StatsView.YEAR:
            return [
                Vertical(YearStatsWidget(), classes="stats-left-area"),
                Vertical(GoalsCard(period=GoalPeriod.YEARLY), classes="stats-right-area"),
            ]
        return [TodayStatsWidget()]
