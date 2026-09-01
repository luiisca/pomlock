# Test gap-aware streak counting logic in StreakCard

import tempfile
import os
from datetime import date, timedelta

from pomlock.history_store import HistoryStore
from pomlock.constants import SessionKind
from pomlock.ui.widgets.streak_card import StreakCard


def test_streak_count_respects_gap():
    """Streak count should include missed days up to the allowed gap."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        history_store = HistoryStore(db_path=db_path)
        # Add an activity with a daily goal
        history_store.save_activity(
            name="coding",
            daily_goal=60,
            weekly_goal=0,
            monthly_goal=0,
            yearly_goal=0,
        )
        # Simulate focus for day before yesterday (met goal)
        day_before = date.today() - timedelta(days=2)
        history_store.record(
            activity="coding",
            kind=SessionKind.POMODORO,
            duration_m=60,
            cycle=1,
            session=1,
            completed=True,
        )
        # No record for yesterday (missed)
        # Record for today (met goal)
        history_store.record(
            activity="coding",
            kind=SessionKind.POMODORO,
            duration_m=60,
            cycle=1,
            session=1,
            completed=True,
        )
        # Settings allow one missed day gap
        settings = {"streak_allowed_gap": 1}
        card = StreakCard(
            history_store=history_store,
            reference_date=date.today(),
            settings=settings,
        )
        # Build days list using the same logic as compose (but we can reuse the private method directly)
        # For simplicity, we manually construct a days list representing the week where
        # today is the last element, and the three relevant days are present.
        # We'll assume week start is Monday for this test.
        days = []
        # Monday (day before yesterday) - done
        days.append(("Mon", "✓", "status-done"))
        # Tuesday (yesterday) - missed
        days.append(("Tue", "✗", "status-miss"))
        # Wednesday (today) - done
        days.append(("Wed", "✓", "status-done"))
        # The rest of the week can be pending (·) – they will be ignored by the method
        for _ in range(4):
            days.append(("", "·", "status-pending"))
        # Call the private calculation method
        streak = card._calculate_streak_count(days)
        assert streak == 3, f"Expected streak of 3 with gap allowed, got {streak}"


def test_streak_count_no_gap_breaks_on_miss():
    """When gap is zero, a missed day should break the streak."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        history_store = HistoryStore(db_path=db_path)
        history_store.save_activity(
            name="coding",
            daily_goal=60,
            weekly_goal=0,
            monthly_goal=0,
            yearly_goal=0,
        )
        # Record for today only
        history_store.record(
            activity="coding",
            kind=SessionKind.POMODORO,
            duration_m=60,
            cycle=1,
            session=1,
            completed=True,
        )
        settings = {"streak_allowed_gap": 0}
        card = StreakCard(
            history_store=history_store,
            reference_date=date.today(),
            settings=settings,
        )
        days = []
        # Monday (missed)
        days.append(("Mon", "✗", "status-miss"))
        # Tuesday (today) - done
        days.append(("Tue", "✓", "status-done"))
        for _ in range(5):
            days.append(("", "·", "status-pending"))
        streak = card._calculate_streak_count(days)
        # With zero gap, the missed Monday should stop counting, leaving only today
        assert streak == 1, f"Expected streak of 1 with zero gap, got {streak}"
