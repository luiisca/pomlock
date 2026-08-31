import unittest
from unittest.mock import MagicMock

from textual.app import App, ComposeResult

from pomlock.constants import GoalPeriod
from pomlock.history_store import HistoryStore
from pomlock.ui.widgets.goals_card import GoalsCard
from pomlock.ui.widgets.timer_card import ThickProgressBar
from pomlock.utils import parse_duration_string


class GoalsTestApp(App):
    """Test harness app containing GoalsCard."""

    def __init__(self, settings: dict, history_store: HistoryStore):
        super().__init__()
        self.settings = settings
        self.history_store = history_store

    def compose(self) -> ComposeResult:
        yield GoalsCard()


class TestGoalsWidget(unittest.IsolatedAsyncioTestCase):
    """Comprehensive test suite for Today's Goals widget."""

    def test_parse_duration_string(self):
        """Test parsing various string formats into minutes."""
        self.assertEqual(parse_duration_string("3h20m"), 200)
        self.assertEqual(parse_duration_string("3h 20m"), 200)
        self.assertEqual(parse_duration_string("4h"), 240)
        self.assertEqual(parse_duration_string("40m"), 40)
        self.assertEqual(parse_duration_string("90"), 90)
        self.assertEqual(parse_duration_string(120), 120)
        self.assertEqual(parse_duration_string("1.5h"), 90)
        self.assertEqual(parse_duration_string("0h 40m"), 40)
        self.assertEqual(parse_duration_string(""), 0)
        self.assertEqual(parse_duration_string("invalid"), 0)

    async def test_goal_component_four_elements_rendered(self):
        """Verify each goal component contains all 4 required visual elements."""
        mock_history = MagicMock(spec=HistoryStore)
        mock_history.get_period_focus_by_activity.return_value = {"coding": 60}
        mock_history.get_activities.return_value = [
            {"name": "coding", "daily_goal": 240, "weekly_goal": 1200, "monthly_goal": 5280, "yearly_goal": 62400}
        ]

        settings = {
            "goals": {
                "coding": "4h",
            },
        }

        app = GoalsTestApp(settings=settings, history_store=mock_history)
        async with app.run_test() as pilot:
            await pilot.pause()
            card = app.query_one(GoalsCard)

            # Element 1: Sublabel string
            sublabel = card.query_one("#goal-sublabel-coding")
            self.assertIn("coding", str(sublabel.render()))

            # Element 2: Large timer countdown
            countdown = card.query_one("#goal-countdown-coding")
            self.assertEqual(str(countdown.render()), "1h 00m / 4h")

            # Element 3: Thick (2-line) progress bar
            pb = card.query_one("#goal-pb-coding", ThickProgressBar)
            self.assertAlmostEqual(pb.progress, 0.25)

            # Element 4: -+ timer diff label
            diff = card.query_one("#goal-diff-coding")
            self.assertEqual(str(diff.render()), "-3h")

    async def test_goals_ordering_and_zero_goal_filtering(self):
        """Verify total is first, active activity is second, and 0 goals are filtered out."""
        mock_history = MagicMock(spec=HistoryStore)
        mock_history.get_period_focus_by_activity.return_value = {
            "coding": 60,
            "reading": 20,
            "studying": 30,
            "gaming": 10,
        }
        mock_history.get_activities.return_value = [
            {"name": "all", "daily_goal": 480, "weekly_goal": 2400, "monthly_goal": 10560, "yearly_goal": 124800},
            {"name": "coding", "daily_goal": 240, "weekly_goal": 1200, "monthly_goal": 5280, "yearly_goal": 62400},
            {"name": "reading", "daily_goal": 40, "weekly_goal": 200, "monthly_goal": 880, "yearly_goal": 10400},
            {"name": "studying", "daily_goal": 60, "weekly_goal": 300, "monthly_goal": 1320, "yearly_goal": 15600},
            {"name": "gaming", "daily_goal": 0, "weekly_goal": 0, "monthly_goal": 0, "yearly_goal": 0},
        ]

        app = GoalsTestApp(settings={}, history_store=mock_history)
        async with app.run_test() as pilot:
            await pilot.pause()
            card = app.query_one(GoalsCard)

            # 1. No active activity -> total first, then table order (coding, reading, studying)
            container = card.query_one("#goals-entries-container")
            entries = list(container.children)
            self.assertEqual(len(entries), 4)
            self.assertEqual(entries[0].id, "goal-entry-total")
            self.assertEqual(entries[1].id, "goal-entry-coding")
            self.assertEqual(entries[2].id, "goal-entry-reading")
            self.assertEqual(entries[3].id, "goal-entry-studying")

            # 2. Live activity changes re-order active goals.
            card.update_live_progress("studying", 1.0)
            await pilot.pause()

            container = card.query_one("#goals-entries-container")
            entries = list(container.children)
            self.assertEqual(entries[0].id, "goal-entry-total")
            self.assertEqual(entries[1].id, "goal-entry-studying")
            self.assertEqual(entries[2].id, "goal-entry-coding")
            self.assertEqual(entries[3].id, "goal-entry-reading")

    async def test_live_goal_timer_updates_with_ticking_session(self):
        """Test real-time in-memory elapsed seconds updating goal progress and countdowns."""
        mock_history = MagicMock(spec=HistoryStore)
        mock_history.get_period_focus_by_activity.return_value = {
            "coding": 60,
        }
        mock_history.get_activities.return_value = [
            {"name": "all", "daily_goal": 240, "weekly_goal": 1200, "monthly_goal": 5280, "yearly_goal": 62400},
            {"name": "coding", "daily_goal": 120, "weekly_goal": 600, "monthly_goal": 2640, "yearly_goal": 31200},
        ]

        app = GoalsTestApp(settings={}, history_store=mock_history)
        async with app.run_test() as pilot:
            await pilot.pause()
            card = app.query_one(GoalsCard)

            # Initial: coding has 60m / 120m = 0.5
            coding_pb = card.query_one("#goal-pb-coding", ThickProgressBar)
            self.assertAlmostEqual(coding_pb.progress, 0.5)

            # Live tick: 1800s (30m) elapsed in current running session for "coding"
            card.update_live_progress(active_activity="coding", session_elapsed_s=1800.0)
            await pilot.pause()

            # Now: 60m base + 30m live = 90m / 120m = 0.75
            self.assertAlmostEqual(coding_pb.progress, 0.75)
            countdown = card.query_one("#goal-countdown-coding")
            self.assertEqual(str(countdown.render()), "1h 30m / 2h")
            diff = card.query_one("#goal-diff-coding")
            self.assertEqual(str(diff.render()), "-30m")

            # Total should also advance: 60m base + 30m live = 90m / 240m = 0.375
            total_pb = card.query_one("#goal-pb-total", ThickProgressBar)
            self.assertAlmostEqual(total_pb.progress, 0.375)

    async def test_period_cycling_and_multi_timeframe(self):
        """Test cycling periods from daily -> weekly -> monthly -> yearly."""
        mock_history = MagicMock(spec=HistoryStore)
        mock_history.get_period_focus_by_activity.return_value = {"coding": 600}
        mock_history.get_activities.return_value = [
            {"name": "coding", "daily_goal": 240, "weekly_goal": 1200, "monthly_goal": 5280, "yearly_goal": 62400}
        ]

        app = GoalsTestApp(settings={}, history_store=mock_history)
        async with app.run_test() as pilot:
            await pilot.pause()
            card = app.query_one(GoalsCard)
            self.assertEqual(card.current_period, GoalPeriod.DAILY)

            # Cycle to weekly
            next_p = card.cycle_period()
            self.assertEqual(next_p, GoalPeriod.WEEKLY)
            await pilot.pause()
            tag = card.query_one("#goals-card-tag")
            self.assertIn("weekly", str(tag.render()))

            # Cycle to monthly
            next_p = card.cycle_period()
            self.assertEqual(next_p, GoalPeriod.MONTHLY)
            await pilot.pause()

            # Cycle to yearly
            next_p = card.cycle_period()
            self.assertEqual(next_p, GoalPeriod.YEARLY)
            await pilot.pause()

            # Cycle back to daily
            next_p = card.cycle_period()
            self.assertEqual(next_p, GoalPeriod.DAILY)

    async def test_active_indicator_across_activities_and_progress_movement(self):
        """Test active indicator switching across activities and moving progress bar."""
        mock_history = MagicMock(spec=HistoryStore)
        mock_history.get_period_focus_by_activity.return_value = {
            "coding": 120,
            "reading": 20,
            "studying": 30,
        }
        mock_history.get_activities.return_value = [
            {"name": "coding", "daily_goal": 240, "weekly_goal": 1200, "monthly_goal": 5280, "yearly_goal": 62400},
            {"name": "reading", "daily_goal": 40, "weekly_goal": 200, "monthly_goal": 880, "yearly_goal": 10400},
            {"name": "studying", "daily_goal": 60, "weekly_goal": 300, "monthly_goal": 1320, "yearly_goal": 15600},
        ]

        settings = {}
        app = GoalsTestApp(settings=settings, history_store=mock_history)
        async with app.run_test() as pilot:
            await pilot.pause()
            card = app.query_one(GoalsCard)

            # 1. Activate "coding"
            card.set_active_activity("coding")
            await pilot.pause()

            coding_lbl = card.query_one("#goal-sublabel-coding")
            reading_lbl = card.query_one("#goal-sublabel-reading")
            studying_lbl = card.query_one("#goal-sublabel-studying")

            self.assertIn("●", str(coding_lbl.render()))
            self.assertNotIn("●", str(reading_lbl.render()))
            self.assertNotIn("●", str(studying_lbl.render()))

            # Check coding progress: 120 / 240 = 0.5
            coding_pb = card.query_one("#goal-pb-coding", ThickProgressBar)
            self.assertAlmostEqual(coding_pb.progress, 0.5)

            # 2. Switch activity to "reading"
            card.set_active_activity("reading")
            await pilot.pause()

            self.assertNotIn("●", str(coding_lbl.render()))
            self.assertIn("●", str(reading_lbl.render()))
            self.assertNotIn("●", str(studying_lbl.render()))

            # Check reading progress: 20 / 40 = 0.5
            reading_pb = card.query_one("#goal-pb-reading", ThickProgressBar)
            self.assertAlmostEqual(reading_pb.progress, 0.5)

            # 3. Simulate progress advancing on reading (20m -> 40m)
            mock_history.get_period_focus_by_activity.return_value["reading"] = 40
            card.refresh_goals()
            await pilot.pause()

            self.assertAlmostEqual(reading_pb.progress, 1.0)
            reading_diff = card.query_one("#goal-diff-reading")
            self.assertEqual(str(reading_diff.render()), "+0m")

            # 4. Switch activity to "studying"
            card.set_active_activity("studying")
            await pilot.pause()

            self.assertNotIn("●", str(coding_lbl.render()))
            self.assertNotIn("●", str(reading_lbl.render()))
            self.assertIn("●", str(studying_lbl.render()))

    async def test_goal_celebration_once_on_completion(self):
        """Test encouragement notification and badge render only once on first reaching a goal."""
        mock_history = MagicMock(spec=HistoryStore)
        mock_history.get_period_focus_by_activity.return_value = {
            "reading": 39,
        }
        mock_history.get_activities.return_value = [
            {"name": "reading", "daily_goal": 40, "weekly_goal": 200, "monthly_goal": 880, "yearly_goal": 10400}
        ]

        app = GoalsTestApp(settings={}, history_store=mock_history)
        app.notify = MagicMock()

        async with app.run_test() as pilot:
            await pilot.pause()
            card = app.query_one(GoalsCard)

            # Not completed yet
            app.notify.assert_not_called()
            with self.assertRaises(Exception):
                card.query_one("#goal-badge-reading")

            # Reaches goal (40m / 40m)
            mock_history.get_period_focus_by_activity.return_value["reading"] = 40
            card.refresh_goals()
            await pilot.pause()

            # Encouragement badge appears
            badge = card.query_one("#goal-badge-reading")
            self.assertIn("Goal Completed", str(badge.render()))
            self.assertEqual(app.notify.call_count, 1)

            # Refresh again (e.g. at 45m) - notification should not be repeated
            mock_history.get_period_focus_by_activity.return_value["reading"] = 45
            card.refresh_goals()
            await pilot.pause()

            self.assertEqual(app.notify.call_count, 1)


if __name__ == "__main__":
    unittest.main()
