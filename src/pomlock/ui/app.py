from pathlib import Path
from typing import Optional

from textual import on
from textual.app import App
from textual.binding import Binding

from ..constants import DEFAULT_OVERLAY_ACCENT, SessionKind, StatsView, TimerState
from ..history_store import HistoryStore
from ..logger import logger
from ..timer_engine import TimerEngine
from .break_overlay import BreakOverlayManager
from .screens.break_screen import BreakScreen
from .screens.main_screen import MainScreen
from .screens.settings_screen import SettingsScreen
from .screens.stats_screen import StatsScreen
from .widgets.timer_card import TimerCard

CSS_FILE = Path(__file__).parent / "styles.tcss"


class PomlockApp(App):
    """Main Textual application for pomlock."""

    CSS_PATH = CSS_FILE
    DEFAULT_MODE = "main"

    BINDINGS = [
        Binding("z", "toggle_zen", "Zen Mode"),
        Binding("g", "cycle_goals", "Cycle Goals"),
        Binding("space", "toggle_timer", "Toggle Pause"),
        Binding("r", "reset_timer", "Reset"),
        Binding("s", "skip_timer", "Skip"),
        Binding("q", "quit_app", "Quit"),
        Binding("ctrl+q", "quit_app", show=False),
        Binding("1", "show_main", "Home", show=False),
        Binding("2", "show_today", "Today", show=False),
        Binding("3", "show_week", "Week", show=False),
        Binding("4", "show_month", "Month", show=False),
        Binding("5", "show_year", "Year", show=False),
        Binding("6", "show_settings", "Settings", show=False),
    ]

    def __init__(
        self,
        settings: dict,
        history_store: Optional[HistoryStore] = None,
    ):
        super().__init__()
        self.settings = settings
        self.history_store = history_store or HistoryStore()

        self.engine = TimerEngine(
            settings=self.settings,
            history_store=self.history_store,
            on_tick=self._handle_engine_tick,
            on_phase_change=self._handle_phase_change,
        )
        self._break_modal: Optional[BreakScreen] = None
        self._break_overlay = BreakOverlayManager()

        self.add_mode(
            "main",
            lambda: MainScreen(
                activity=self.engine.activity,
                cycles=self.engine.total_cycles,
            ),
        )
        self.add_mode("stats", StatsScreen)
        self.add_mode("settings", SettingsScreen)

    def on_mount(self) -> None:
        """Start countdown engine and switch to main mode."""
        self.switch_mode("main")
        self.engine.start()
        self.set_interval(0.2, self._tick_engine)

    def _tick_engine(self) -> None:
        """Periodic clock update."""
        self.engine.tick()

    def _handle_engine_tick(self, remaining_s: int, progress_pct: float) -> None:
        """Update active screens with current countdown values."""
        is_running = self.engine.state == TimerState.RUNNING
        is_break = self.engine.kind in (
            SessionKind.SHORT_BREAK, SessionKind.LONG_BREAK)
        kind_label = self.engine.kind.value.replace("_", " ").title()

        break_duration_m = self.engine.l_break_m if self.engine.kind == SessionKind.LONG_BREAK else self.engine.s_break_m
        if not is_break:
            break_duration_m = self.engine.next_break_m

        # Only accumulate live elapsed seconds during a running pomodoro (not during breaks)
        session_elapsed_s = self.engine.elapsed_s if (
            is_running and not is_break) else 0.0
        active_activity = self.engine.activity if (
            is_running and not is_break) else None

        try:
            if isinstance(self.screen, MainScreen):
                self.screen.update_timer_view(
                    remaining_s=remaining_s,
                    progress_pct=progress_pct,
                    cycle=self.engine.crr_cycle,
                    total_cycles=self.engine.total_cycles,
                    pomo_m=self.engine.pomo_m,
                    break_m=break_duration_m,
                    is_break=is_break,
                    is_running=is_running,
                    kind_label=kind_label,
                    session_elapsed_s=session_elapsed_s,
                )
            elif isinstance(self.screen, StatsScreen):
                self.screen.update_live_goals(
                    active_activity, session_elapsed_s)

            if is_break:
                self._break_overlay.update_timer(remaining_s)
        except Exception:
            pass

    def _handle_phase_change(self, kind: SessionKind, duration_m: int) -> None:
        """Respond to phase changes (pomodoro vs break)."""
        is_break = kind in (SessionKind.SHORT_BREAK, SessionKind.LONG_BREAK)
        overlay_enabled = self.settings.get("overlay", True)

        if is_break and overlay_enabled:
            # Launch multi-monitor Tkinter break overlay
            try:
                css_vars = self.get_css_variables()
                accent = css_vars.get("accent", DEFAULT_OVERLAY_ACCENT)
            except Exception:
                accent = DEFAULT_OVERLAY_ACCENT

            self._break_overlay.start_overlay(
                break_title=kind.value.replace("_", " "),
                initial_remaining_s=self.engine.remaining_s,
                accent_color=str(accent),
            )
        elif not is_break:
            # Stop multi-monitor Tkinter overlay
            self._break_overlay.stop_overlay()

        # Refresh goals, charts, and activity history after a phase change
        try:
            if isinstance(self.screen, MainScreen):
                self.screen.refresh_history_views()
            elif isinstance(self.screen, StatsScreen):
                self.screen.update_live_goals(None, 0.0)
                for card in self.screen.query("GoalsCard"):
                    card.refresh_goals()
        except Exception:
            pass

    # --- Button and Keybinding Actions ---

    @on(TimerCard.PauseRequested)
    def on_timer_card_pause_requested(self, event: TimerCard.PauseRequested) -> None:
        self.engine.toggle_pause()

    @on(TimerCard.ResetRequested)
    def on_timer_card_reset_requested(self, event: TimerCard.ResetRequested) -> None:
        self.engine.reset()

    @on(TimerCard.SkipRequested)
    def on_timer_card_skip_requested(self, event: TimerCard.SkipRequested) -> None:
        self.engine.skip()

    def action_toggle_timer(self) -> None:
        self.engine.toggle_pause()

    def action_reset_timer(self) -> None:
        self.engine.reset()

    def action_skip_timer(self) -> None:
        self.engine.skip()

    def action_cycle_goals(self) -> None:
        """Cycle timeframe displayed on main screen GoalsCard."""
        if isinstance(self.screen, MainScreen):
            new_period = self.screen.cycle_goals_period()
            if new_period and hasattr(self, "notify"):
                self.notify(f"Goals timeframe: {
                            new_period.value}", title="Goals View")

    def action_show_main(self) -> None:
        try:
            if self.current_mode != "main":
                self.switch_mode("main")
        except Exception:
            pass

    def action_show_today(self) -> None:
        self._switch_stats(StatsView.TODAY)

    def action_show_week(self) -> None:
        self._switch_stats(StatsView.WEEK)

    def action_show_month(self) -> None:
        self._switch_stats(StatsView.MONTH)

    def action_show_year(self) -> None:
        self._switch_stats(StatsView.YEAR)

    def action_show_settings(self) -> None:
        try:
            if self.current_mode != "settings":
                self.switch_mode("settings")
        except Exception:
            pass

    def action_toggle_zen(self) -> None:
        logger.debug("Zen mode toggle requested")
        if isinstance(self.screen, MainScreen):
            self.screen.toggle_zen()

    def action_quit_app(self) -> None:
        self._break_overlay.stop_overlay()
        self.engine.cleanup()
        self.exit()

    def _switch_stats(self, view: StatsView) -> None:
        """Switch to stats screen and set active tab view."""
        try:
            if self.current_mode != "stats":
                self.switch_mode("stats")
            if isinstance(self.screen, StatsScreen):
                self.screen.set_view(view)
        except Exception:
            pass
