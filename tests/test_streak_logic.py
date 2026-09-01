#!/usr/bin/env python3
"""Test the streak logic for the pomlock application."""

import tempfile
import os
from datetime import date, datetime, timedelta

from pomlock.history_store import HistoryStore
from pomlock.constants import GoalPeriod, SessionKind


def test_streak_logic():
    """Test that a day is marked as done only when all activity goals are met."""
    # Create a temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        history_store = HistoryStore(db_path=db_path)

        # Add two activities: coding and reading
        history_store.save_activity(
            name="coding",
            daily_goal=60,  # 60 minutes
            weekly_goal=0,
            monthly_goal=0,
            yearly_goal=0,
        )
        history_store.save_activity(
            name="reading",
            daily_goal=30,  # 30 minutes
            weekly_goal=0,
            monthly_goal=0,
            yearly_goal=0,
        )

        # Today's date
        today = date.today()

        # Initially, no focus recorded, so goals should not be met
        focus_by_activity = history_store.get_period_focus_by_activity(
            period=GoalPeriod.DAILY, target_date=today
        )
        print(f"Focus by activity for today (no records): {focus_by_activity}")

        # Check if goals are met for today (should be False for both)
        activities = history_store.get_activities()
        all_goals_met = True
        for act in activities:
            daily_goal = act.get("daily_goal", 0)
            if daily_goal > 0:
                activity_name = act.get("name", "").lower()
                focused_minutes = focus_by_activity.get(activity_name, 0)
                print(f"Activity {activity_name}: goal={daily_goal}, focused={focused_minutes}")
                if focused_minutes < daily_goal:
                    all_goals_met = False
        print(f"All goals met today (no records): {all_goals_met}")
        assert not all_goals_met, "Should not meet goals when no focus recorded"

        # Now add a focus record for coding: 60 minutes (meets goal)
        # We need to create a block and update its duration.
        # We'll use the record method for simplicity.
        history_store.record(
            activity="coding",
            kind=SessionKind.POMODORO,
            duration_m=60,  # 60 minutes
            cycle=1,
            session=1,
            completed=True,
        )

        # Check again
        focus_by_activity = history_store.get_period_focus_by_activity(
            period=GoalPeriod.DAILY, target_date=today
        )
        print(f"Focus by activity for today (after coding): {focus_by_activity}")

        all_goals_met = True
        for act in activities:
            daily_goal = act.get("daily_goal", 0)
            if daily_goal > 0:
                activity_name = act.get("name", "").lower()
                focused_minutes = focus_by_activity.get(activity_name, 0)
                print(f"Activity {activity_name}: goal={daily_goal}, focused={focused_minutes}")
                if focused_minutes < daily_goal:
                    all_goals_met = False
        print(f"All goals met today (after coding): {all_goals_met}")
        # Reading goal is not met, so overall should be False
        assert not all_goals_met, "Should not meet goals because reading goal is not met"

        # Now add a focus record for reading: 30 minutes (meets goal)
        history_store.record(
            activity="reading",
            kind=SessionKind.POMODORO,
            duration_m=30,  # 30 minutes
            cycle=1,
            session=1,
            completed=True,
        )

        # Check again
        focus_by_activity = history_store.get_period_focus_by_activity(
            period=GoalPeriod.DAILY, target_date=today
        )
        print(f"Focus by activity for today (after coding and reading): {focus_by_activity}")

        all_goals_met = True
        for act in activities:
            daily_goal = act.get("daily_goal", 0)
            if daily_goal > 0:
                activity_name = act.get("name", "").lower()
                focused_minutes = focus_by_activity.get(activity_name, 0)
                print(f"Activity {activity_name}: goal={daily_goal}, focused={focused_minutes}")
                if focused_minutes < daily_goal:
                    all_goals_met = False
        print(f"All goals met today (after coding and reading): {all_goals_met}")
        assert all_goals_met, "Should meet goals after both activities meet their goals"

        # Test a future date: should be pending (we don't check goals for future dates in the streak card logic)
        # In the streak card, we mark future dates as pending regardless of goals.
        # We'll test that the streak card logic (not implemented here) would mark it as pending.
        # For our logic, we just note that we don't check goals for future dates.

        # Test a past date with no records: should be missed
        yesterday = today - timedelta(days=1)
        focus_by_activity_yesterday = history_store.get_period_focus_by_activity(
            period=GoalPeriod.DAILY, target_date=yesterday
        )
        print(f"Focus by activity for yesterday: {focus_by_activity_yesterday}")

        all_goals_met_yesterday = True
        for act in activities:
            daily_goal = act.get("daily_goal", 0)
            if daily_goal > 0:
                activity_name = act.get("name", "").lower()
                focused_minutes = focus_by_activity_yesterday.get(activity_name, 0)
                if focused_minutes < daily_goal:
                    all_goals_met_yesterday = False
        print(f"All goals met yesterday: {all_goals_met_yesterday}")
        assert not all_goals_met_yesterday, "Yesterday should not meet goals (no records)"

        print("All tests passed!")


if __name__ == "__main__":
    test_streak_logic()
