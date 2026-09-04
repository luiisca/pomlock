from datetime import date, timedelta

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label

from pomlock.settings import Settings

from ...constants import GoalPeriod
from ...history_store import HistoryStore


class StreakCard(Vertical):
    """Streak tracking card displaying week status boxes and current streak info."""

    DEFAULT_CLASSES = "card-container streak-box"

    def __init__(
        self,
        history_store: HistoryStore | None = None,
        reference_date: date | None = None,
        id: str | None = "streak-card",
    ):
        super().__init__(id=id)
        self._history_store = history_store or HistoryStore()
        self._reference_date = reference_date or date.today()
        # We'll refresh the status every minute
        self._refresh_timer = None

    def _calculate_streak_count(self, days: list[tuple[str, str, str]]) -> int:
        """
        Calculate the streak count based on day icons, respecting gap allowance.

        Args:
            days: List of tuples (day_name, icon, status_class) for each day in the week

        Returns:
            The current streak count, respecting the streak_allowed_gap setting
        """
        # Calculate current streak (consecutive days up to today, respecting gap allowance)
        # We count days where goals were met OR days missed within gap allowance
        # First, skip any leading future days (pending) in the reversed list
        streak_count = 0

        streak_settings = Settings().get("streak", {})
        gap_remaining = int(streak_settings.get("allowed_gap", 1))

        # Iterate through days in reverse order (from today backwards)
        # Skip initial pending days which represent future days
        for _, icon, _ in reversed(days):
            if icon == "·":
                # This is a future day - skip it
                continue
            elif icon == "✓":
                # Goal met day - always count it
                streak_count += 1
            elif icon == "✗" and gap_remaining > 0:
                # Missed day but we have gap allowance - count it and use up one gap
                streak_count += 1
                gap_remaining -= 1
            else:
                # Either a missed day with no gap remaining - stop counting
                break
        return streak_count

    def on_mount(self) -> None:
        """Start the periodic refresh timer."""
        self._refresh_timer = self.set_interval(60, self.refresh_status)

    def on_unmount(self) -> None:
        """Stop the periodic refresh timer."""
        if self._refresh_timer:
            self._refresh_timer.stop()

    def refresh_status(self) -> None:
        """Refresh the status of the streak card."""
        # We need to re-compose the widget to update the status.
        self.refresh()

    def compose(self) -> ComposeResult:
        localization_settings = Settings().get("localization", {})
        streak_settings = Settings().get("streak", {})

        week_start_day_str = str(
            localization_settings.get("week_start_day", "monday")
        ).lower()
        # Map string to day number (Monday=0, Sunday=6)
        day_map = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        week_start_day = day_map.get(week_start_day_str, 0)

        # Get the reference date (today or the one passed in)
        ref_date = self._reference_date
        # Calculate the start of the week (the week_start_day)
        days_to_subtract = (ref_date.weekday() - week_start_day) % 7
        week_start = ref_date - timedelta(days=days_to_subtract)

        # Generate the week days (from week_start to week_start + 6 days)
        days = []
        for i in range(7):
            current_day = week_start + timedelta(days=i)
            day_name = current_day.strftime("%a")  # Mon, Tue, etc.
            # Determine if the day is done, missed, or pending
            # Determine logical status (done, miss, pending)
            if current_day > date.today():
                logical_status = "pending"
            else:
                focus_by_activity = self._history_store.get_period_focus_by_activity(
                    period=GoalPeriod.DAILY, target_date=current_day
                )
                activities = self._history_store.get_activities()
                all_goals_met = True
                for act in activities:
                    daily_goal = act.get("daily_goal", 0)
                    if daily_goal > 0:
                        activity_name = act.get("name", "").lower()
                        focused_minutes = focus_by_activity.get(activity_name, 0)
                        if focused_minutes < daily_goal:
                            all_goals_met = False
                            break
                logical_status = "done" if all_goals_met else "miss"
            # Map logical_status to visual icon based on user setting from current settings
            style = streak_settings.get("indicator_style", "icon")
            if style == "color-box":
                if logical_status == "done":
                    icon = "🟩"
                    status_class = "status-done"
                elif logical_status == "miss":
                    icon = "🟥"
                    status_class = "status-miss"
                else:
                    icon = "⬜"
                    status_class = "status-pending"
            else:
                if logical_status == "done":
                    icon = "✓"
                    status_class = "status-done"
                elif logical_status == "miss":
                    icon = "✗"
                    status_class = "status-miss"
                else:
                    icon = "·"
                    status_class = "status-pending"
            days.append((day_name, icon, status_class))

        # Week day check indicators
        # Calculate current streak (consecutive done days up to today, respecting gap allowance)
        streak_count = self._calculate_streak_count(days)
        self.border_title = (
            f"Current Streak: {streak_count} day{'s' if streak_count != 1 else ''}"
        )
        with Horizontal(classes="streak-days-row"):
            for day_name, icon, status_class in days:
                with Vertical(classes="streak-col"):
                    yield Label(icon, classes=f"streak-icon-box {status_class}")
                    yield Label(day_name, classes="streak-day-label")
