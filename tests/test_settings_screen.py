from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from textual.widgets import Button, Input, Label, Select

from pomlock.constants import DAYS_OF_WEEK
from pomlock.history_store import HistoryStore
from pomlock.ui.app import PomlockApp
from pomlock.ui.screens.settings_screen import (
    SettingsScreen,
    ActivityAdded,
    PresetAdded,
)
import configparser

import pomlock.settings as settings_module
from pomlock.settings import Settings


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

        # Redirect Settings to a temp config so tests never touch the real user config
        self._conf_path = Path(self.temp_dir.name) / "test.conf"
        Settings.reset()
        self._conf_patcher = patch.object(settings_module, "DEFAULT_CONFIG_FILE", self._conf_path)
        self._conf_patcher.start()

    async def asyncTearDown(self):
        Settings.reset()
        self._conf_patcher.stop()
        self.temp_dir.cleanup()

    async def test_settings_screen_navigation_and_manual_goals(self):
        app = PomlockApp(history_store=self.history_store)
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

            # Set auto_calc = False to allow selecting and saving 'all' goals
            Settings().auto_calc = False
            screen._refresh_activity_select()
            screen._selected_activity = "all"
            select = screen.query_one("#activity-select", Select)
            select.value = "all"
            await pilot.pause()

            # Clear inputs
            daily_inp.value = ""
            monthly_inp.value = ""
            yearly_inp.value = ""
            await pilot.pause()

            # Fill daily goal with 8h (manual entry only - no auto calculation)
            daily_inp.value = "8h"
            await pilot.pause()

            # Monthly and yearly should remain empty (no auto calculation)
            self.assertEqual(monthly_inp.value, "")
            self.assertEqual(yearly_inp.value, "")

            # Fill monthly goal manually
            monthly_inp.value = "176h"
            await pilot.pause()

            # Yearly should remain empty (no auto calculation from monthly)
            self.assertEqual(yearly_inp.value, "")

            # Fill yearly goal manually
            yearly_inp.value = "2080h"
            await pilot.pause()

            # Save goals for current activity ("all")
            btn_save = screen.query_one("#btn-add-activity", Button)
            btn_save.press()
            await pilot.pause()

            # Verify saved in settings
            activities = Settings().get("activities", {})
            all_act = activities.get("all")
            self.assertIsNotNone(all_act)
            self.assertEqual(all_act["daily"], 480)
            self.assertEqual(all_act["monthly"], 10560)
            self.assertEqual(all_act["yearly"], 124800)

    async def test_settings_add_new_activity(self):
        app = PomlockApp(history_store=self.history_store)
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

            # Check added to settings
            activities = Settings().get("activities", {})
            self.assertIn("swimming", activities)

            # Check selected in dropdown
            select = screen.query_one("#activity-select", Select)
            self.assertEqual(select.value, "swimming")

    async def test_settings_general_settings_load_and_save(self):
        """Test that general settings are correctly loaded from app settings and saved to config file."""
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()

            # Switch to settings screen
            await pilot.press("6")
            await pilot.pause()

            screen = app.screen

            # Check that the input fields are populated with settings
            self.assertEqual(
                screen.query_one("#field-general-break_notify_msg", Input).value,
                "Time for a break!",
            )
            self.assertEqual(
                screen.query_one("#field-overlay-font_size", Input).value,
                str(Settings()["overlay"]["font_size"]),
            )

            # Modify some values
            break_notify_input = screen.query_one(
                "#field-general-break_notify_msg", Input
            )
            break_notify_input.value = "New break message"
            await pilot.pause()

            overlay_font_size_input = screen.query_one(
                "#field-overlay-font_size", Input
            )
            overlay_font_size_input.value = "72"
            await pilot.pause()

            # Check that the config file has been updated
            config_path = Path(app.settings.get("config_file"))
            self.assertTrue(config_path.exists())
            conf = configparser.ConfigParser()
            conf.read(config_path)
            self.assertTrue(conf.has_section("general"))
            self.assertEqual(
                conf.get("general", "break_notify_msg"), "New break message"
            )
            self.assertEqual(conf.get("overlay", "font_size"), "72")

    async def test_settings_general_settings_defaults(self):
        """Test that default values are used when settings are not provided."""
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.press("6")
            await pilot.pause()

            screen = app.screen

            # Check that the input fields have the default values
            self.assertEqual(
                screen.query_one("#field-general-break_notify_msg", Input).value,
                "Time for a break!",
            )
            self.assertEqual(
                screen.query_one("#field-general-long_break_notify_msg", Input).value,
                "Time for a long break!",
            )
            self.assertEqual(
                screen.query_one("#field-general-pomo_notify_msg", Input).value,
                "Time for a pomodoro!",
            )
            self.assertEqual(
                screen.query_one("#field-general-callback", Input).value, ""
            )
            self.assertEqual(
                screen.query_one("#field-overlay-font_size", Input).value,
                str(Settings()["overlay"]["font_size"]),
            )
            self.assertEqual(
                screen.query_one("#field-overlay-color", Input).value,
                str(Settings()["overlay"]["color"]),
            )
            self.assertEqual(
                screen.query_one("#field-overlay-bg_color", Input).value,
                str(Settings()["overlay"]["bg_color"]),
            )
            self.assertEqual(
                screen.query_one("#field-overlay-opacity", Input).value,
                str(Settings()["overlay"]["opacity"]),
            )

            # Check that the selects are set to the default values
            self.assertEqual(
                screen.query_one("#field-overlay-enabled", Select).value, "true"
            )
            self.assertEqual(
                screen.query_one("#field-general-block_input", Select).value, "true"
            )
            self.assertEqual(
                screen.query_one("#field-general-notify", Select).value, "true"
            )

    async def test_activity_added_message_handling(self):
        """Test that the SettingsScreen correctly handles the ActivityAdded message."""
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")  # Switch to settings screen
            await pilot.pause()

            screen = app.screen
            # Post an ActivityAdded message directly
            activity_name = "running"
            message = ActivityAdded(activity_name)
            screen.post_message(message)
            await pilot.pause()

            # Check that the screen's _selected_activity is updated
            self.assertEqual(screen._selected_activity, activity_name)
            # Check that the activity select is updated
            select = screen.query_one("#activity-select", Select)
            self.assertEqual(select.value, activity_name)
            # Check that the activity goals inputs are cleared (since no goals set for new activity)
            daily_inp = screen.query_one("#input-daily-goal", Input)
            weekly_inp = screen.query_one("#input-weekly-goal", Input)
            monthly_inp = screen.query_one("#input-monthly-goal", Input)
            yearly_inp = screen.query_one("#input-yearly-goal", Input)
            self.assertEqual(daily_inp.value, "")
            self.assertEqual(weekly_inp.value, "")
            self.assertEqual(monthly_inp.value, "")
            self.assertEqual(yearly_inp.value, "")

    async def test_preset_added_message_handling(self):
        """Test that the SettingsScreen correctly handles the PresetAdded message."""
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")  # Switch to settings screen
            await pilot.pause()

            screen = app.screen
            # Post a PresetAdded message directly
            preset_name = "custom"
            # 30min work, 10min short break, 30min long break, 5 cycles
            preset_value = "30 10 30 5"
            message = PresetAdded(preset_name, preset_value)
            screen.post_message(message)
            await pilot.pause()

            # Check that the screen's _selected_preset is updated
            self.assertEqual(screen._selected_preset, preset_name)
            # Check that the preset select is updated
            select = screen.query_one("#preset-select", Select)
            self.assertEqual(select.value, preset_name)
            # Check that the preset inputs are updated with the values
            pomodoro_inp = screen.query_one("#input-preset-pomodoro", Input)
            short_inp = screen.query_one("#input-preset-short", Input)
            long_inp = screen.query_one("#input-preset-long", Input)
            cycles_inp = screen.query_one("#input-preset-cycles", Input)
            self.assertEqual(pomodoro_inp.value, "30m")
            self.assertEqual(short_inp.value, "10m")
            self.assertEqual(long_inp.value, "30m")
            self.assertEqual(cycles_inp.value, "5")

    async def test_preset_persistence_to_config_file(self):
        """Test that presets are saved to the [presets] section of the config file."""
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")  # Switch to settings screen
            await pilot.pause()

            screen = app.screen

            # Set up inputs for a new preset
            pomodoro_inp = screen.query_one("#input-preset-pomodoro", Input)
            short_inp = screen.query_one("#input-preset-short", Input)
            long_inp = screen.query_one("#input-preset-long", Input)
            cycles_inp = screen.query_one("#input-preset-cycles", Input)
            name_inp = screen.query_one("#input-preset-name", Input)

            pomodoro_inp.value = "20m"
            short_inp.value = "5m"
            long_inp.value = "15m"
            cycles_inp.value = "3"
            name_inp.value = "my_preset"
            await pilot.pause()

            # Press the Add Preset button
            add_btn = screen.query_one("#btn-add-preset", Button)
            add_btn.press()
            await pilot.pause()

            # Check that the preset was added to the app settings
            self.assertIn("my_preset", app.settings.get("presets", {}))
            self.assertEqual(app.settings["presets"]["my_preset"], "20 5 15 3")

            # Check that the config file has been updated with the [presets] section
            config_path = Path(app.settings.get("config_file"))
            self.assertTrue(config_path.exists())
            conf = configparser.ConfigParser()
            conf.read(config_path)
            self.assertTrue(conf.has_section("presets"))
            self.assertTrue(conf.has_option("presets", "my_preset"))
            self.assertEqual(conf.get("presets", "my_preset"), "20 5 15 3")

            # Also check that the preset is now in the select dropdown
            select = screen.query_one("#preset-select", Select)
            self.assertIn(("My Preset", "my_preset"), select._options)

    async def test_localization_widget(self):
        """Test localization custom widget renders week_start_day select and locale input."""
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")
            await pilot.pause()

            screen = app.screen
            week_select = screen.query_one("#field-localization-week_start_day", Select)
            self.assertEqual(week_select._options, DAYS_OF_WEEK)
            self.assertEqual(week_select.value, "monday")

            locale_input = screen.query_one("#field-localization-locale", Input)
            self.assertEqual(locale_input.value, "en_US")

            # Modify both and verify persistence
            week_select.value = "sunday"
            await pilot.pause()
            locale_input.value = "fr_FR"
            await pilot.pause()

            config_path = Path(app.settings.get("config_file"))
            conf = configparser.ConfigParser()
            conf.read(config_path)
            self.assertEqual(conf.get("localization", "week_start_day"), "sunday")
            self.assertEqual(conf.get("localization", "locale"), "fr_FR")

    async def test_auto_calc_selector(self):
        """Test auto_calc boolean selector exists in activities section."""
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")
            await pilot.pause()

            screen = app.screen
            auto_calc_sel = screen.query_one("#select-auto-calc", Select)
            self.assertIn(("True", "true"), auto_calc_sel._options)
            self.assertIn(("False", "false"), auto_calc_sel._options)
            self.assertEqual(auto_calc_sel.value, "true")

    async def test_all_total_disabled(self):
        """Test all/total title input is disabled when selected with auto_calc=false."""
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")
            await pilot.pause()

            screen = app.screen
            auto_calc_sel = screen.query_one("#select-auto-calc", Select)
            auto_calc_sel.value = "false"
            await pilot.pause()

            act_sel = screen.query_one("#activity-select", Select)
            act_sel.value = "all"
            await pilot.pause()

            title_inp = screen.query_one("#input-new-activity", Input)
            self.assertTrue(title_inp.disabled)

            # Switch to another activity and verify title input is enabled
            act_sel.value = "other"
            await pilot.pause()
            self.assertFalse(title_inp.disabled)

    async def test_null_title_inputs(self):
        """Test activity and preset title inputs are empty, not NULL, when not selected."""
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")
            await pilot.pause()

            screen = app.screen
            act_sel = screen.query_one("#activity-select", Select)
            act_sel.value = Select.NULL
            await pilot.pause()

            act_title = screen.query_one("#input-new-activity", Input)
            self.assertEqual(act_title.value, "")

            preset_sel = screen.query_one("#preset-select", Select)
            preset_sel.value = Select.NULL
            await pilot.pause()

            preset_title = screen.query_one("#input-preset-name", Input)
            self.assertEqual(preset_title.value, "")

    async def test_create_update_labels(self):
        """Test section titles and buttons adapt between create and update."""
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")
            await pilot.pause()

            screen = app.screen
            act_sel = screen.query_one("#activity-select", Select)
            act_sel.value = Select.NULL
            await pilot.pause()

            act_title_lbl = screen.query_one("#label-activity-action", Label)
            self.assertIn("create", str(act_title_lbl.render()).lower())
            act_btn = screen.query_one("#btn-add-activity", Button)
            btn_label_str = str(act_btn.label).lower()
            self.assertTrue("add" in btn_label_str or "create" in btn_label_str)

            act_sel.value = "other"
            await pilot.pause()
            self.assertIn("update", str(act_title_lbl.render()).lower())
            self.assertIn("update", str(act_btn.label).lower())

    async def test_persist_explicit_only(self):
        """Test persist_settings is called only on explicit changes differing from original."""
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("6")
            await pilot.pause()

            screen = app.screen
            with patch.object(screen, "persist_settings") as mock_persist:
                # Switching activity without input changes must not persist
                act_sel = screen.query_one("#activity-select", Select)
                act_sel.value = "other"
                await pilot.pause()
                mock_persist.assert_not_called()

                # Changing input to same value must not persist
                break_inp = screen.query_one("#field-general-break_notify_msg", Input)
                break_inp.value = "Time for a break!"
                await pilot.pause()
                mock_persist.assert_not_called()

                # Changing to different value must persist
                break_inp.value = "Something new"
                await pilot.pause()
                mock_persist.assert_called()
