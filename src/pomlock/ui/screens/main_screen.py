from typing import Optional
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer

from ..widgets.activity_list import ActivityListCard
from ..widgets.footer_bar import FooterBar
from ..widgets.goals_card import GoalsCard
from ..widgets.nav_bar import TopNavBar
from ..widgets.stats_chart_card import StatsChartCard
from ..widgets.streak_card import StreakCard
from ..widgets.timer_card import TimerCard


class MainScreen(Screen):
    """Homepage / Main View layout matching wireframes."""

    def __init__(self, activity: str = "coding", cycles: int = 4):
        super().__init__()
        self._activity = activity
        self._cycles = cycles

    def compose(self) -> ComposeResult:
        with Vertical(classes="app-shell"):
            yield TopNavBar(active_tab="home")

            with Horizontal(classes="main-content-layout"):
                # Left major column (Timer + Goals & Chart)
                with Vertical(classes="main-left-column"):
                    timer_card = TimerCard(activity=self._activity, cycles_total=self._cycles)
                    timer_card.add_class("with-title")
                    yield timer_card

                    with Horizontal(classes="main-bottom-row"):
                        goals_card = GoalsCard(active_activity=self._activity)
                        goals_card.add_class("with-title")
                        yield goals_card
                        yield StatsChartCard()

                # Right column (Streak + Activity list)
                with Vertical(classes="main-right-column"):
                    streak_card = StreakCard()
                    streak_card.add_class("with-title")
                    yield streak_card
                    activity_list = ActivityListCard()
                    activity_list.add_class("with-title")
                    yield activity_list

            # yield FooterBar()
            yield Footer()

    def toggle_zen(self) -> None:
        """Toggle zen mode on the timer card."""
        try:
            timer_card = self.query_one(TimerCard)
            timer_card.toggle_zen()
            self.toggle_class("zen-active")
        except Exception:
            pass

    def cycle_goals_period(self):
        """Cycle timeframe displayed on the GoalsCard."""
        try:
            card = self.query_one(GoalsCard)
            return card.cycle_period()
        except Exception:
            return None

    def update_live_goals(self, active_activity: Optional[str], session_elapsed_s: float) -> None:
        """Forward real-time elapsed seconds to GoalsCard."""
        try:
            self.query_one(GoalsCard).update_live_progress(
                active_activity, session_elapsed_s)
        except Exception:
            pass

    def update_timer_view(
        self,
        remaining_s: int,
        progress_pct: float,
        cycle: int,
        total_cycles: int,
        pomo_m: int,
        break_m: int,
        is_break: bool,
        is_running: bool,
        kind_label: str,
        session_elapsed_s: float = 0.0,
    ) -> None:
        """Forward state update to TimerCard and GoalsCard if mounted."""
        try:
            timer_card = self.query_one(TimerCard)
            timer_card.update_state(
                remaining_s=remaining_s,
                progress_pct=progress_pct,
                cycle=cycle,
                total_cycles=total_cycles,
                pomo_m=pomo_m,
                break_m=break_m,
                is_break=is_break,
                is_running=is_running,
                kind_label=kind_label,
            )
        except Exception:
            pass

        active_act = self._activity if (is_running and not is_break) else None
        self.update_live_goals(active_act, session_elapsed_s)

    def refresh_history_views(self) -> None:
        """Refresh goals, stats chart, and activity list from latest database records."""
        try:
            self.query_one(GoalsCard).refresh_goals()
        except Exception:
            pass
        try:
            self.query_one(StatsChartCard).refresh_chart()
        except Exception:
            pass
        try:
            self.query_one(ActivityListCard).refresh_list()
        except Exception:
            pass
