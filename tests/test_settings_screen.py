from pathlib import Path
import tempfile
import unittest

from textual.widgets import Button, Input, Select

from pomlock.history_store import HistoryStore
from pomlock.ui.app import PomlockApp
from pomlock.ui.screens.settings_screen import (
    SettingsScreen,
    ActivityAdded,
    PresetAdded,
)
import configparser


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

            # Check added to DB
            activities = self.history_store.get_activities()
            act_names = [a["name"] for a in activities]
            self.assertIn("swimming", act_names)

            # Check selected in dropdown
            select = screen.query_one("#activity-select", Select)
            self.assertEqual(select.value, "swimming")

    async def test_settings_general_settings_load_and_save(self):
        """Test that general settings are correctly loaded from app settings and saved to config file."""
        # Set up settings with custom values for the new fields
        custom_settings = {
            "pomodoro": 25,
            "short_break": 5,
            "long_break": 15,
            "cycles": 4,
            "activity": "coding",
            "block_input": True,
            "overlay": True,
            "notify": True,
            "break_notify_msg": "Custom break message",
            "long_break_notify_msg": "Custom long break message",
            "pomo_notify_msg": "Custom pomodoro message",
            "callback": "/path/to/script.sh",
            "overlay_font_size": 60,
            "overlay_color": "#FF0000",
            "overlay_bg_color": "#0000FF",
            "overlay_opacity": 0.5,
            "config_file": str(Path(self.temp_dir.name) / "test.conf"),
        }
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()

            # Switch to settings screen
            await pilot.press("6")
            await pilot.pause()

            screen = app.screen

            # Check that the input fields are populated with the custom settings
            self.assertEqual(
                screen.query_one("#input-break-notify-msg", Input).value,
                "Custom break message",
            )
            self.assertEqual(
                screen.query_one("#input-long-break-notify-msg", Input).value,
                "Custom long break message",
            )
            self.assertEqual(
                screen.query_one("#input-pomo-notify-msg", Input).value,
                "Custom pomodoro message",
            )
            self.assertEqual(
                screen.query_one("#input-callback", Input).value, "/path/to/script.sh"
            )
            self.assertEqual(
                screen.query_one("#input-overlay-font-size", Input).value, "60"
            )
            self.assertEqual(
                screen.query_one("#input-overlay-color", Input).value, "#FF0000"
            )
            self.assertEqual(
                screen.query_one("#input-overlay-bg-color", Input).value, "#0000FF"
            )
            self.assertEqual(
                screen.query_one("#input-overlay-opacity", Input).value, "0.5"
            )

            # Check that the selects are set correctly
            self.assertEqual(screen.query_one("#select-overlay", Select).value, "true")
            self.assertEqual(
                screen.query_one("#select-block-input", Select).value, "true"
            )
            self.assertEqual(screen.query_one("#select-notify", Select).value, "true")

            # Modify some values
            break_notify_input = screen.query_one("#input-break-notify-msg", Input)
            break_notify_input.value = "New break message"
            await pilot.pause()

            overlay_font_size_input = screen.query_one(
                "#input-overlay-font-size", Input
            )
            overlay_font_size_input.value = "72"
            await pilot.pause()

            # Click the Save General Settings button
            save_btn = screen.query_one("#btn-save-general", Button)
            save_btn.press()
            await pilot.pause()

            # Check that the app settings have been updated
            self.assertEqual(app.settings["break_notify_msg"], "New break message")
            self.assertEqual(app.settings["overlay_font_size"], 72)

            # Check that the config file has been updated
            config_path = Path(app.settings.get("config_file"))
            self.assertTrue(config_path.exists())
            conf = configparser.ConfigParser()
            conf.read(config_path)
            self.assertTrue(conf.has_section("general"))
            self.assertEqual(
                conf.get("general", "break_notify_msg"), "New break message"
            )
            self.assertEqual(conf.get("general", "overlay_font_size"), "72")
            self.assertEqual(conf.get("general", "overlay_color"), "#FF0000")
            self.assertEqual(conf.get("general", "overlay_bg_color"), "#0000FF")
            self.assertEqual(conf.get("general", "overlay_opacity"), "0.5")  # unchanged
            self.assertEqual(conf.get("general", "overlay"), "true")
            self.assertEqual(conf.get("general", "block_input"), "true")
            self.assertEqual(conf.get("general", "notify"), "true")

    async def test_settings_general_settings_defaults(self):
        """Test that default values are used when settings are not provided."""
        # Use minimal settings (only the required ones)
        minimal_settings = {
            "pomodoro": 25,
            "short_break": 5,
            "long_break": 15,
            "cycles": 4,
            "activity": "coding",
            # block_input, overlay, notify will default to True, True, True? Actually, from Settings class, defaults are True, True, True?
            # But note: in the Settings class, the CLI_ARGS have defaults: block_input=True, overlay=True, notify=True.
            # However, we are not setting them in minimal_settings, so they will come from the Settings class defaults.
            # We'll rely on the Settings class to provide defaults.
        }
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.press("6")
            await pilot.pause()

            screen = app.screen

            # Check that the input fields have the default values
            self.assertEqual(
                screen.query_one("#input-break-notify-msg", Input).value,
                "Time for a break!",
            )
            self.assertEqual(
                screen.query_one("#input-long-break-notify-msg", Input).value,
                "Time for a long break!",
            )
            self.assertEqual(
                screen.query_one("#input-pomo-notify-msg", Input).value,
                "Time for a pomodoro!",
            )
            self.assertEqual(screen.query_one("#input-callback", Input).value, "")
            self.assertEqual(
                screen.query_one("#input-overlay-font-size", Input).value, "48"
            )
            self.assertEqual(
                screen.query_one("#input-overlay-color", Input).value, "white"
            )
            self.assertEqual(
                screen.query_one("#input-overlay-bg-color", Input).value, "black"
            )
            self.assertEqual(
                screen.query_one("#input-overlay-opacity", Input).value, "0.8"
            )

            # Check that the selects are set to the default values (from minimal_settings, they are not set, so they come from Settings class defaults)
            # The Settings class defaults for block_input, overlay, notify are True, True, True.
            self.assertEqual(screen.query_one("#select-overlay", Select).value, "true")
            self.assertEqual(
                screen.query_one("#select-block-input", Select).value, "true"
            )
            self.assertEqual(screen.query_one("#select-notify", Select).value, "true")

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
            self.assertIn(("My Preset", "my_preset"), select.options)
