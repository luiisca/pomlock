from pathlib import Path
import tempfile
import unittest

from pomlock.constants import SessionKind
from pomlock.history_store import HistoryStore
from pomlock.ui.app import PomlockApp
from pomlock.ui.screens.main_screen import MainScreen
from pomlock.ui.screens.stats_screen import StatsScreen
from pomlock.ui.widgets.activity_list import ActivityListCard
from pomlock.ui.widgets.goals_card import GoalsCard
from pomlock.ui.widgets.stats_chart_card import StatsChartCard
from pomlock.ui.widgets.timer_card import TimerCard
from textual.widgets import Button, Label


class TestTextualUI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / "test_history.csv"
        self.history_store = HistoryStore(file_path=self.csv_path)
        self.settings = {
            "pomodoro": 25,
            "short_break": 5,
            "long_break": 15,
            "cycles": 4,
            "activity": "coding",
            "block_input": False,
            "overlay": False,
            "notify": False,
            "callback": "",
            "goals": {
                "total": "420",
                "coding": "240",
                "reading": "40",
            },
        }

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_screens_and_navigation(self):
        app = PomlockApp(settings=self.settings,
                         history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Verify home screen mounted
            self.assertIsInstance(app.screen, MainScreen)

            # Switch to today view (2)
            await pilot.press("2")
            await pilot.pause()
            self.assertIsInstance(app.screen, StatsScreen)

            # Switch back to main (1)
            await pilot.press("1")
            await pilot.pause()
            self.assertIsInstance(app.screen, MainScreen)

            # Pause timer (space)
            await pilot.press("space")
            self.assertEqual(app.engine.state.value, "paused")

            # Resume timer (space)
            await pilot.press("space")
            self.assertEqual(app.engine.state.value, "running")

            # Test text buttons
            btn_pause = app.query_one("#btn-pause", Button)
            btn_pause.press()
            await pilot.pause()
            self.assertEqual(app.engine.state.value, "paused")

            btn_pause.press()
            await pilot.pause()
            self.assertEqual(app.engine.state.value, "running")

            btn_skip = app.query_one("#btn-skip", Button)
            btn_skip.press()
            await pilot.pause()
            self.assertEqual(app.engine.kind.value, "short_break")

            # Test TopNavBar buttons
            nav_today = app.query_one("#nav-today", Button)
            nav_today.press()
            await pilot.pause()
            self.assertIsInstance(app.screen, StatsScreen)
            self.assertEqual(app.screen._current_view.value, "today")

            nav_home = app.query_one("#nav-home", Button)
            nav_home.press()
            await pilot.pause()
            self.assertIsInstance(app.screen, MainScreen)

    async def test_stats_chart_navigation(self):
        app = PomlockApp(settings=self.settings,
                         history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            chart_card = app.query_one(StatsChartCard)
            initial_offset = chart_card._week_offset
            self.assertEqual(initial_offset, 0)

            # Click prev week button
            btn_prev = app.query_one("#btn-chart-prev", Button)
            btn_prev.press()
            await pilot.pause()
            self.assertEqual(chart_card._week_offset, -1)

            # Click next week button
            btn_next = app.query_one("#btn-chart-next", Button)
            btn_next.press()
            await pilot.pause()
            self.assertEqual(chart_card._week_offset, 0)

            # Check chart label is mounted and rendered
            chart_label = app.query_one("#stats-ascii-chart", Label)
            self.assertIsNotNone(chart_label)

    async def test_goals_and_activity_list_rendering(self):
        app = PomlockApp(settings=self.settings,
                         history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            goals_card = app.query_one(GoalsCard)
            self.assertIsNotNone(goals_card)

            act_card = app.query_one(ActivityListCard)
            self.assertIsNotNone(act_card)

    async def test_break_overlay_and_skip(self):
        settings_with_overlay = dict(self.settings)
        settings_with_overlay["overlay"] = True
        app = PomlockApp(settings=settings_with_overlay,
                         history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()

            # Skip into break
            await pilot.press("s")
            await pilot.pause()

            # Main screen remains active, displaying the break timer
            self.assertIsInstance(app.screen, MainScreen)
            self.assertIn(app.engine.kind,
                          (SessionKind.SHORT_BREAK, SessionKind.LONG_BREAK))

            # Press s to skip back to Pomodoro
            await pilot.press("s")
            await pilot.pause()
            self.assertEqual(app.engine.kind, SessionKind.POMODORO)
            self.assertIsInstance(app.screen, MainScreen)

    async def test_zen_mode_toggle(self):
        app = PomlockApp(settings=self.settings,
                         history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertIsInstance(app.screen, MainScreen)

            timer_card = app.query_one(TimerCard)
            self.assertFalse(timer_card.has_class("zen-mode"))
            self.assertFalse(app.screen.has_class("zen-active"))

            # Press 'z' to enter zen mode
            await pilot.press("z")
            await pilot.pause()
            self.assertTrue(timer_card.has_class("zen-mode"))
            self.assertTrue(app.screen.has_class("zen-active"))

            # Press 'z' again to exit zen mode
            await pilot.press("z")
            await pilot.pause()
            self.assertFalse(timer_card.has_class("zen-mode"))
            self.assertFalse(app.screen.has_class("zen-active"))

    async def test_ctrl_q_finalizes_active_block(self):
        app = PomlockApp(settings=self.settings,
                         history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.engine.pause()
            app.engine.elapsed_s = 11.0

            await pilot.press("ctrl+q")

        record = self.history_store.get_records()[0]
        self.assertEqual(record["duration_s"], 11)
        self.assertEqual(record["completed"], "False")

    async def test_custom_activity_flag(self):
        custom_settings = dict(self.settings)
        custom_settings["activity"] = "reading"
        app = PomlockApp(settings=custom_settings,
                         history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertIsInstance(app.screen, MainScreen)
            self.assertEqual(app.screen._activity, "reading")
            act_label = app.query_one("#timer-activity-name", Label)
            self.assertIn("reading", str(act_label.render()))


if __name__ == "__main__":
    unittest.main()
