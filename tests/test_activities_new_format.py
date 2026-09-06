import configparser
import tempfile
import unittest
from pathlib import Path

from pomlock.constants import GoalPeriod
from pomlock.history_store import HistoryStore
from pomlock.settings import Settings
from pomlock.ui.app import PomlockApp
from pomlock.ui.screens.settings_screen import SettingsScreen
from pomlock.utils import format_hm, parse_activities_goals_m, parse_duration_m
from textual.widgets import Button, Input, Select


class TestActivitiesNewFormat(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conf_path = Path(self.temp_dir.name) / "test.conf"
        self.history_store = HistoryStore(db_path=self.db_path)

        Settings._instance = None
        Settings._listeners.clear()

    def tearDown(self):
        self.temp_dir.cleanup()
        Settings._instance = None
        Settings._listeners.clear()

    def test_parse_duration_handles_space(self):
        self.assertEqual(parse_duration_m("3h 20m"), 200)
        self.assertEqual(parse_duration_m("3h20m"), 200)
        self.assertEqual(parse_duration_m("8h"), 480)
        self.assertEqual(parse_duration_m("40m"), 40)

    def test_auto_calc_true_ignores_activities_base_goals(self):
        raw_settings = {
            "activities": {
                "auto_calc": "true",
                "daily": "10h",
                "weekly": "50h",
            },
            "activities.studying": {
                "daily": "8h",
                "weekly": "40h",
                "monthly": "100h",
                "yearly": "1000h",
            },
            "activities.coding": {
                "weekly": "30h",
            },
        }

        parsed = parse_activities_goals_m(raw_settings)

        self.assertEqual(parsed["studying"]["daily"], 480)
        self.assertEqual(parsed["studying"]["weekly"], 2400)
        self.assertEqual(parsed["studying"]["monthly"], 6000)
        self.assertEqual(parsed["studying"]["yearly"], 60000)
        self.assertEqual(parsed["coding"]["weekly"], 1800)

        self.assertIn("all", parsed)
        self.assertEqual(parsed["all"]["daily"], 480)
        self.assertEqual(parsed["all"]["weekly"], 4200)
        self.assertEqual(parsed["all"]["monthly"], 6000)
        self.assertEqual(parsed["all"]["yearly"], 60000)

    def test_auto_calc_false_uses_base_goals_and_falls_back_to_sum(self):
        raw_settings = {
            "activities": {
                "auto_calc": "false",
                "daily": "10h",
                "weekly": "50h",
            },
            "activities.studying": {
                "daily": "8h",
                "weekly": "40h",
                "monthly": "100h",
                "yearly": "1000h",
            },
            "activities.coding": {
                "weekly": "30h",
            },
        }

        parsed = parse_activities_goals_m(raw_settings)

        self.assertIn("all", parsed)
        self.assertEqual(parsed["all"]["daily"], 600)
        self.assertEqual(parsed["all"]["weekly"], 3000)
        self.assertEqual(parsed["all"]["monthly"], 6000)
        self.assertEqual(parsed["all"]["yearly"], 60000)

    async def test_auto_calc_true_hides_all_in_select(self):
        self.conf_path.write_text(
            "[general]\n"
            "block_input = true\n"
            "[activities]\n"
            "auto_calc = true\n"
            "daily = 10h\n"
            "[activities.studying]\n"
            "daily = 8h\n"
            "[activities.coding]\n"
            "weekly = 30h\n"
        )

        Settings._instance = None
        s = Settings()
        s["config_file"] = str(self.conf_path)
        s.preparsed_custom_path_args["config"] = self.conf_path
        s["activities"] = parse_activities_goals_m({
            "activities": {"auto_calc": "true"},
            "activities.studying": {"daily": "8h"},
            "activities.coding": {"weekly": "30h"},
        })
        s.auto_calc = True

        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")
            await pilot.pause()

            screen = app.screen
            select = screen.query_one("#activity-select", Select)
            opt_values = [opt[1] for opt in select._options]

            self.assertNotIn("all", opt_values)
            self.assertIn("studying", opt_values)
            self.assertIn("coding", opt_values)

    async def test_auto_calc_false_shows_all_in_select(self):
        self.conf_path.write_text(
            "[general]\n"
            "block_input = true\n"
            "[activities]\n"
            "auto_calc = false\n"
            "daily = 10h\n"
            "[activities.studying]\n"
            "daily = 8h\n"
        )

        Settings._instance = None
        s = Settings()
        s["config_file"] = str(self.conf_path)
        s.preparsed_custom_path_args["config"] = self.conf_path
        s["activities"] = parse_activities_goals_m({
            "activities": {"auto_calc": "false", "daily": "10h"},
            "activities.studying": {"daily": "8h"},
        })
        s.auto_calc = False

        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")
            await pilot.pause()

            screen = app.screen
            select = screen.query_one("#activity-select", Select)
            opt_values = [opt[1] for opt in select._options]

            self.assertIn("all", opt_values)

    async def test_selecting_existing_populates_title_inputs(self):
        self.conf_path.write_text(
            "[general]\n"
            "block_input = true\n"
            "[presets]\n"
            "standard = 25 5 20 4\n"
            "[activities]\n"
            "auto_calc = true\n"
            "[activities.studying]\n"
            "daily = 8h\n"
            "weekly = 40h\n"
        )

        Settings._instance = None
        s = Settings()
        s["config_file"] = str(self.conf_path)
        s.preparsed_custom_path_args["config"] = self.conf_path
        s["presets"] = {"standard": "25 5 20 4"}
        s["activities"] = parse_activities_goals_m({
            "activities": {"auto_calc": "true"},
            "activities.studying": {"daily": "8h", "weekly": "40h"},
        })
        s.auto_calc = True

        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")
            await pilot.pause()

            screen = app.screen

            act_select = screen.query_one("#activity-select", Select)
            act_select.value = "studying"
            await pilot.pause()

            act_name_inp = screen.query_one("#input-new-activity", Input)
            self.assertEqual(act_name_inp.value, "studying")
            act_btn = screen.query_one("#btn-add-activity", Button)
            self.assertEqual(act_btn.label, "Update Activity")

            preset_select = screen.query_one("#preset-select", Select)
            preset_select.value = "standard"
            await pilot.pause()

            preset_name_inp = screen.query_one("#input-preset-name", Input)
            self.assertEqual(preset_name_inp.value, "standard")
            preset_btn = screen.query_one("#btn-add-preset", Button)
            self.assertEqual(preset_btn.label, "Update Preset")


if __name__ == "__main__":
    unittest.main()
