from pathlib import Path
import tempfile
import unittest

from textual.widgets import Button, Input, Select

from pomlock.history_store import HistoryStore
from pomlock.ui.app import PomlockApp
from pomlock.ui.screens.settings_screen import SettingsScreen


class TestSettingsScreen(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_pomlock.db"
        self.history_store = HistoryStore(db_path=self.db_path)
        self.settings = {
            "pomodoro": 25,
            "short_break": 5,
            "long_break": 15,
            "cycles": 4,
            "activity": "coding",
            "block_input": False,
            "overlay": False,
            "notify": False,
        }

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_settings_screen_navigation_and_autocalc(self):
        app = PomlockApp(settings=self.settings, history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()

            # Switch to settings screen (6)
            await pilot.press("6")
            await pilot.pause()
            self.assertIsInstance(app.screen, SettingsScreen)

            screen = app.screen
            daily_inp = screen.query_one("#input-daily-goal", Input)
            monthly_inp = screen.query_one("#input-monthly-goal", Input)
            yearly_inp = screen.query_one("#input-yearly-goal", Input)

            # Clear inputs
            daily_inp.value = ""
            monthly_inp.value = ""
            yearly_inp.value = ""
            await pilot.pause()

            # Fill daily goal with 8h -> monthly should auto-calc to 176h (8 * 22), yearly to 2080h (8 * 260)
            daily_inp.value = "8h"
            await pilot.pause()

            self.assertEqual(monthly_inp.value, "176h")
            self.assertEqual(yearly_inp.value, "2080h")

            # Save goals for current activity ("all")
            btn_save = screen.query_one("#btn-save-goals", Button)
            btn_save.press()
            await pilot.pause()

            # Verify saved in database
            activities = self.history_store.get_activities()
            all_act = next((a for a in activities if a["name"] == "all"), None)
            self.assertIsNotNone(all_act)
            self.assertEqual(all_act["daily_goal"], 480)
            self.assertEqual(all_act["weekly_goal"], 2400)
            self.assertEqual(all_act["monthly_goal"], 10560)
            self.assertEqual(all_act["yearly_goal"], 124800)

    async def test_settings_add_new_activity(self):
        app = PomlockApp(settings=self.settings, history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.press("6")
            await pilot.pause()

            screen = app.screen
            new_inp = screen.query_one("#input-new-activity", Input)
            new_inp.value = "swimming"
            await pilot.pause()

            btn_add = screen.query_one("#btn-add-activity", Button)
            btn_add.press()
            await pilot.pause()

            # Check added to DB
            activities = self.history_store.get_activities()
            act_names = [a["name"] for a in activities]
            self.assertIn("swimming", act_names)

            # Check selected in dropdown
            select = screen.query_one("#activity-select", Select)
            self.assertEqual(select.value, "swimming")
