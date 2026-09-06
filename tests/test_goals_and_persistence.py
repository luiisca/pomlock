import configparser
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pomlock.constants import GoalPeriod
from pomlock.history_store import HistoryStore
from pomlock.settings import Settings
from pomlock.ui.app import PomlockApp
from pomlock.ui.screens.settings_screen import SettingsScreen
from pomlock.ui.widgets.goals_card import GoalsCard
from textual.widgets import Input, Select


class TestGoalsAndPersistence(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.db_path = self.temp_path / "test.db"
        self.conf_path = self.temp_path / "test.conf"
        self.history_store = HistoryStore(db_path=self.db_path)

        Settings.reset()
        self._conf_patcher = patch.object(
            Settings, "_get_conf_settings", return_value={}
        )
        self._conf_patcher.start()

    async def asyncTearDown(self):
        self._conf_patcher.stop()
        Settings.reset()
        self.temp_dir.cleanup()

    async def test_goals_card_displays_nothing_when_no_goals(self):
        """When Settings()['activities'] has no goals, GoalsCard should display nothing (no 7h default)."""
        s = Settings()
        s["activities"] = {
            "auto_calc": True,
            "other": {},
            "all": {"daily": 0, "weekly": 0, "monthly": 0, "yearly": 0},
        }

        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            card = app.query_one(GoalsCard)
            card.refresh_goals()

            self.assertEqual(card._cached_targets, [])
            container = card.query_one("#goals-entries-container")
            self.assertEqual(len(container.children), 0)

    async def test_persist_settings_auto_calc_true_does_not_persist_all_goals(self):
        """When auto_calc is True, auto-calculated 'all' goals exist in Settings() but are omitted from conf."""
        self.conf_path.write_text(
            "[general]\n"
            "block_input = true\n"
            "[activities]\n"
            "auto_calc = true\n"
            "daily = 7h\n"
        )

        s = Settings()
        s["config_file"] = str(self.conf_path)
        s.preparsed_custom_path_args["config"] = self.conf_path
        s["activities"] = {
            "auto_calc": True,
            "coding": {"daily": 240},
            "all": {"daily": 240, "weekly": 0, "monthly": 0, "yearly": 0},
        }

        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")
            await pilot.pause()

            screen = app.screen
            self.assertIsInstance(screen, SettingsScreen)

            # Invoke persist_settings
            self.assertTrue(hasattr(screen, "persist_settings"))
            screen.persist_settings()

            # Inspect Settings() instance - auto-calculated 'all' must still exist
            self.assertEqual(s["activities"]["all"]["daily"], 240)

            # Inspect written conf file
            conf = configparser.ConfigParser()
            conf.read(self.conf_path)
            self.assertTrue(conf.has_section("activities"))
            self.assertEqual(conf.get("activities", "auto_calc"), "true")
            # Auto-calculated periods must not be written to [activities]
            self.assertFalse(conf.has_option("activities", "daily"))
            self.assertFalse(conf.has_option("activities", "weekly"))
            self.assertFalse(conf.has_option("activities", "monthly"))
            self.assertFalse(conf.has_option("activities", "yearly"))

    async def test_persist_settings_auto_calc_false_persists_manual_all_goals(self):
        """When auto_calc is False, manual 'all' goals from settings screen are persisted to conf."""
        self.conf_path.write_text(
            "[general]\n"
            "block_input = true\n"
            "[activities]\n"
            "auto_calc = false\n"
        )

        s = Settings()
        s["config_file"] = str(self.conf_path)
        s.preparsed_custom_path_args["config"] = self.conf_path
        s["activities"] = {
            "auto_calc": False,
            "all": {"daily": 0, "weekly": 0, "monthly": 0, "yearly": 0},
        }

        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")
            await pilot.pause()

            screen = app.screen
            self.assertIsInstance(screen, SettingsScreen)

            # In auto_calc=False mode, select 'all' and change daily goal
            select = screen.query_one("#activity-select", Select)
            opt_values = [opt[1] for opt in select._options]
            self.assertIn("all", opt_values)
            select.value = "all"
            await pilot.pause()

            daily_inp = screen.query_one("#input-daily-goal", Input)
            daily_inp.value = "8h"
            await pilot.pause()

            screen.persist_settings()

            conf = configparser.ConfigParser()
            conf.read(self.conf_path)
            self.assertTrue(conf.has_section("activities"))
            self.assertEqual(conf.get("activities", "auto_calc"), "false")
            self.assertEqual(conf.get("activities", "daily"), "8h")


if __name__ == "__main__":
    unittest.main()
