import re
from typing import Optional
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Label

from ...constants import (
    ACTIVE_GOAL_INDICATOR,
    DEFAULT_GOALS,
    GOAL_COMPLETED_TEXT,
    GoalPeriod,
    WORK_DAYS_PER_MONTH,
    WORK_DAYS_PER_WEEK,
    WORK_DAYS_PER_YEAR,
)
from ...history_store import HistoryStore
from ...utils import parse_duration_string
from .timer_card import ThickProgressBar

DEFAULT_TOTAL_GOAL_MINUTES = 420
DEFAULT_ACTIVITY_GOAL_MINUTES = 60


def _format_hm(minutes: int, pad_zero_hour: bool = False) -> str:
    """Format minutes to 'Xh Ym' or 'Xh' representation."""
    h, m = divmod(max(0, minutes), 60)

    if pad_zero_hour:
        return f"{h}h {m:02d}m"

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


def _sanitize_id(name: str) -> str:
    """Sanitize activity name for use in widget IDs."""
    return re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower())


class GoalsCard(Vertical):
    """Card displaying activity goals with real-time progress against SQLite history."""

    DEFAULT_CLASSES = "card-container goals-box"

    def __init__(
        self,
        active_activity: Optional[str] = None,
        period: GoalPeriod = GoalPeriod.DAILY,
        id: Optional[str] = "goals-card",
    ):
        super().__init__(id=id)
        self._active_activity = active_activity
        self._current_period = period
        self._achieved_goals: set[str] = set()
        self._base_tracked_s: dict[str, int] = {}
        self._cached_targets: list[tuple[str, int]] = []
        self._session_elapsed_s: float = 0.0

    @property
    def current_period(self) -> GoalPeriod:
        return self._current_period

    def set_period(self, period: GoalPeriod) -> None:
        """Update active timeframe and refresh card content."""
        if self._current_period == period:
            return
        self._current_period = period
        self._achieved_goals.clear()
        self.refresh_goals()

    def cycle_period(self) -> GoalPeriod:
        """Cycle between daily, weekly, monthly, and yearly timeframes."""
        transitions = {
            GoalPeriod.DAILY: GoalPeriod.WEEKLY,
            GoalPeriod.WEEKLY: GoalPeriod.MONTHLY,
            GoalPeriod.MONTHLY: GoalPeriod.YEARLY,
            GoalPeriod.YEARLY: GoalPeriod.DAILY,
        }
        next_period = transitions.get(self._current_period, GoalPeriod.DAILY)
        self.set_period(next_period)
        return self._current_period

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="goals-entries-container")

    def on_mount(self) -> None:
        """Populate and refresh goals periodically."""
        self.refresh_goals()
        self.set_interval(60.0, self.refresh_goals)

    def set_active_activity(self, activity: Optional[str]) -> None:
        """Update currently tracked activity and refresh goal indicators."""
        if self._active_activity == activity:
            return
        self._active_activity = activity
        self.refresh_goals()

    def update_live_progress(self, active_activity: Optional[str], session_elapsed_s: float) -> None:
        """Update active goal progress in real-time on timer tick."""
        activity_changed = self._active_activity != active_activity
        self._active_activity = active_activity
        self._session_elapsed_s = session_elapsed_s

        if activity_changed:
            self.refresh_goals()
            return

        try:
            container = self.query_one(
                "#goals-entries-container", VerticalScroll)
        except Exception:
            return

        total_base_s = sum(self._base_tracked_s.values())
        active_name = active_activity.lower() if active_activity else None

        for label, target_m in self._cached_targets:
            slug = _sanitize_id(label)
            is_active = (
                active_name is not None
                and (
                    label == active_name
                    or (label == "total" and bool(active_name))
                )
            )

            base_s = total_base_s if label == "total" else self._base_tracked_s.get(
                label, 0)
            effective_s = base_s + (session_elapsed_s if is_active else 0.0)
            tracked_m = int(effective_s // 60)
            target_s = target_m * 60

            progress_ratio = max(0.0, min(1.0, effective_s / max(1, target_s)))
            countdown_text = f"{_format_hm(
                tracked_m, pad_zero_hour=True)} / {_format_hm(target_m)}"
            diff_text = _format_diff(tracked_m, target_m)

            try:
                sublabel = container.query_one(f"#goal-sublabel-{slug}", Label)
                sublabel.update(f"{ACTIVE_GOAL_INDICATOR} {
                                label}" if is_active else label)
                if is_active:
                    sublabel.add_class("goal-sublabel-active")
                else:
                    sublabel.remove_class("goal-sublabel-active")
            except Exception:
                pass

            try:
                countdown = container.query_one(
                    f"#goal-countdown-{slug}", Label)
                countdown.update(countdown_text)
            except Exception:
                pass

            try:
                pb = container.query_one(f"#goal-pb-{slug}", ThickProgressBar)
                pb.progress = progress_ratio
            except Exception:
                pass

            try:
                diff_lbl = container.query_one(f"#goal-diff-{slug}", Label)
                diff_lbl.update(diff_text)
            except Exception:
                pass

    def refresh_goals(self) -> None:
        """Query history store and update goal progress with prioritized sorting."""
        history_store = getattr(
            self.app, "history_store", None) or HistoryStore()
        settings = getattr(self.app, "settings", {})

        try:
            self.border_title = f"{self._current_period.value} goals"
        except Exception:
            pass

        # Query baseline tracked focus seconds by activity for current period
        min_map = history_store.get_period_focus_by_activity(
            period=self._current_period)
        self._base_tracked_s = {k: v * 60 for k, v in min_map.items()}

        total_base_s = sum(self._base_tracked_s.values())

        # Retrieve configured activities from SQLite or settings fallback
        db_activities = history_store.get_activities()
        raw_targets: list[tuple[str, int]] = []

        if db_activities:
            goal_key_map = {
                GoalPeriod.DAILY: "daily_goal",
                GoalPeriod.WEEKLY: "weekly_goal",
                GoalPeriod.MONTHLY: "monthly_goal",
                GoalPeriod.YEARLY: "yearly_goal",
            }
            goal_col = goal_key_map.get(self._current_period, "daily_goal")

            for act in db_activities:
                name = act.get("name", "").lower()
                target_m = act.get(goal_col, 0)
                if name in ("all", "total"):
                    raw_targets.append(("total", target_m))
                else:
                    raw_targets.append((name, target_m))
        else:
            configured_goals = settings.get("goals", DEFAULT_GOALS)
            multiplier_map = {
                GoalPeriod.DAILY: 1,
                GoalPeriod.WEEKLY: WORK_DAYS_PER_WEEK,
                GoalPeriod.MONTHLY: WORK_DAYS_PER_MONTH,
                GoalPeriod.YEARLY: WORK_DAYS_PER_YEAR,
            }
            mult = multiplier_map.get(self._current_period, 1)

            total_target_val = configured_goals.get(
                "total", DEFAULT_TOTAL_GOAL_MINUTES)
            total_target = parse_duration_string(total_target_val) * mult
            if total_target <= 0:
                total_target = DEFAULT_TOTAL_GOAL_MINUTES * mult
            raw_targets.append(("total", total_target))

            for key, target_val in configured_goals.items():
                if key in ("total", "all"):
                    continue

                act_name = key.lower()
                target_m = parse_duration_string(target_val) * mult
                if target_m <= 0:
                    target_m = DEFAULT_ACTIVITY_GOAL_MINUTES * mult

                raw_targets.append((act_name, target_m))

        # Filter: only display activities that have a configured goal > 0
        filtered_targets = [t for t in raw_targets if t[1] > 0]

        # Prioritize order:
        # 1. 'total' at index 0
        # 2. Currently active activity at index 1
        # 3. Remaining in table order
        total_entry = next(
            (t for t in filtered_targets if t[0] == "total"), None)
        active_name = self._active_activity.lower() if self._active_activity else None
        active_entry = next(
            (t for t in filtered_targets if active_name and t[0]
             == active_name and t[0] != "total"),
            None,
        )

        ordered_targets: list[tuple[str, int]] = []
        if total_entry:
            ordered_targets.append(total_entry)
        if active_entry:
            ordered_targets.append(active_entry)

        for t in filtered_targets:
            if t != total_entry and t != active_entry:
                ordered_targets.append(t)

        self._cached_targets = ordered_targets

        try:
            container = self.query_one(
                "#goals-entries-container", VerticalScroll)
        except Exception:
            return

        active_entry_ids = set()

        for label, target in ordered_targets:
            slug = _sanitize_id(label)
            is_active = (
                self._active_activity is not None
                and (
                    label == self._active_activity.lower()
                    or (label == "total" and bool(self._active_activity))
                )
            )

            base_s = total_base_s if label == "total" else self._base_tracked_s.get(
                label, 0)
            effective_s = base_s + \
                (self._session_elapsed_s if is_active else 0.0)
            tracked_m = int(effective_s // 60)
            target_s = target * 60

            progress_ratio = max(0.0, min(1.0, effective_s / max(1, target_s)))
            countdown_text = f"{_format_hm(
                tracked_m, pad_zero_hour=True)} / {_format_hm(target)}"
            diff_text = _format_diff(tracked_m, target)

            # Check goal achievement celebration
            is_completed = target > 0 and tracked_m >= target
            if is_completed and label not in self._achieved_goals:
                self._achieved_goals.add(label)
                if hasattr(self.app, "notify"):
                    self.app.notify(
                        f"🎉 Goal reached: {label} {
                            self._current_period.value} goal completed!",
                        title="Goal Achieved",
                    )

            entry_id = f"goal-entry-{slug}"
            active_entry_ids.add(entry_id)

            entry = None
            try:
                entry = container.query_one(f"#{entry_id}", Vertical)
            except Exception:
                entry = None

            if entry is None:
                entry = Vertical(classes="goal-entry", id=entry_id)
                container.mount(entry)

                header_row = Horizontal(
                    classes="goal-header-row", id=f"goal-header-row-{slug}")
                entry.mount(header_row)

                sublabel_text = f"{ACTIVE_GOAL_INDICATOR} {
                    label}" if is_active else label
                sublabel_classes = "goal-sublabel goal-sublabel-active" if is_active else "goal-sublabel"
                header_row.mount(
                    Label(
                        sublabel_text,
                        classes=sublabel_classes,
                        id=f"goal-sublabel-{slug}",
                    )
                )

                if is_completed:
                    header_row.mount(
                        Label(
                            GOAL_COMPLETED_TEXT,
                            classes="goal-badge-completed",
                            id=f"goal-badge-{slug}",
                        )
                    )

                entry.mount(
                    Label(
                        countdown_text,
                        classes="goal-countdown",
                        id=f"goal-countdown-{slug}",
                    )
                )

                bar_row = Horizontal(classes="goal-bar-row")
                entry.mount(bar_row)

                pb = ThickProgressBar(
                    progress=progress_ratio,
                    classes="goal-thick-pb",
                    id=f"goal-pb-{slug}",
                )
                bar_row.mount(pb)
                bar_row.mount(
                    Label(
                        diff_text,
                        classes="goal-diff",
                        id=f"goal-diff-{slug}",
                    )
                )
            else:
                try:
                    sublabel = entry.query_one(f"#goal-sublabel-{slug}", Label)
                    sublabel.update(f"{ACTIVE_GOAL_INDICATOR} {
                                    label}" if is_active else label)
                    if is_active:
                        sublabel.add_class("goal-sublabel-active")
                    else:
                        sublabel.remove_class("goal-sublabel-active")
                except Exception:
                    pass

                try:
                    header_row = entry.query_one(
                        f"#goal-header-row-{slug}", Horizontal)
                    try:
                        badge = header_row.query_one(
                            f"#goal-badge-{slug}", Label)
                        if not is_completed:
                            badge.remove()
                    except Exception:
                        if is_completed:
                            header_row.mount(
                                Label(
                                    GOAL_COMPLETED_TEXT,
                                    classes="goal-badge-completed",
                                    id=f"goal-badge-{slug}",
                                )
                            )
                except Exception:
                    pass

                try:
                    countdown = entry.query_one(
                        f"#goal-countdown-{slug}", Label)
                    countdown.update(countdown_text)
                except Exception:
                    pass

                try:
                    pb = entry.query_one(f"#goal-pb-{slug}", ThickProgressBar)
                    pb.progress = progress_ratio
                except Exception:
                    pass

                try:
                    diff_lbl = entry.query_one(f"#goal-diff-{slug}", Label)
                    diff_lbl.update(diff_text)
                except Exception:
                    pass

        # Remove entries that are no longer active / 0 goals
        for child in list(container.children):
            if child.id not in active_entry_ids:
                child.remove()

        # Re-sort container children to match ordered_targets
        ordered_ids = [
            f"goal-entry-{_sanitize_id(label)}" for label, _ in ordered_targets]
        try:
            container.sort_children(
                key=lambda node: ordered_ids.index(
                    node.id) if node.id in ordered_ids else 999
            )
        except Exception:
            pass
