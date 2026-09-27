from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from textual.widgets import Button, Input, Select, Static

from pomlock.constants import StartMode, TimerState
from pomlock.history_store import HistoryStore
import pomlock.settings as settings_module
from pomlock.settings import Settings
from pomlock.timer_engine import TimerEngine
from pomlock.ui.app import PomlockApp
from pomlock.ui.screens.main_screen import MainScreen
from pomlock.ui.screens.setup_screen import SetupScreen


class TestSetupScreen(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_pomlock.db"
        self.history_store = HistoryStore(db_path=self.db_path)

        self._conf_path = Path(self.temp_dir.name) / "test.conf"
        Settings.reset()
        self._conf_patcher = patch.object(
            settings_module, "DEFAULT_CONFIG_FILE", self._conf_path
        )
        self._conf_patcher.start()

    async def asyncTearDown(self):
        Settings.reset()
        self._conf_patcher.stop()
        self.temp_dir.cleanup()

    def test_cli_setup_flag_parsing(self):
        """Verify --setup and -s flags set setup to True in Settings."""
        Settings.reset()
        with patch("sys.argv", ["pomlock", "--setup"]):
            settings = Settings()
            self.assertTrue(settings.get("setup"))

        Settings.reset()
        with patch("sys.argv", ["pomlock", "-s"]):
            settings = Settings()
            self.assertTrue(settings.get("setup"))

        Settings.reset()
        with patch("sys.argv", ["pomlock"]):
            settings = Settings()
            self.assertFalse(settings.get("setup"))

    def test_timer_engine_configure_session(self):
        """Verify configure_session updates preset and activity properly."""
        engine = TimerEngine(history_store=self.history_store)
        self.assertEqual(engine.activity, "other")
        self.assertEqual(engine.pomo_m, 25.0)

        engine.configure_session(preset="ultradian", activity="deep_work")
        self.assertEqual(engine.activity, "deep_work")
        self.assertEqual(engine.pomo_m, 90.0)
        self.assertEqual(engine.s_break_m, 20.0)
        self.assertEqual(engine.l_break_m, 20.0)
        self.assertEqual(engine.total_cycles, 1)
        self.assertEqual(engine.duration_s, 90 * 60)

    async def test_setup_screen_renders_options_and_disabled_task(self):
        """Verify setup screen mounts with presets, activities, and disabled task input."""
        app = PomlockApp(
            history_store=self.history_store,
            start_mode=StartMode.SETUP,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertIsInstance(app.screen, SetupScreen)
            self.assertEqual(app.engine.state, TimerState.STOPPED)

            screen = app.screen
            preset_select = screen.query_one("#setup-preset-select", Select)
            self.assertIsNotNone(preset_select)
            preset_values = [val for _, val in preset_select._options]
            self.assertIn("standard", preset_values)
            self.assertIn("ultradian", preset_values)
            self.assertIn("fifty_ten", preset_values)

            activity_select = screen.query_one("#setup-activity-select", Select)
            self.assertIsNotNone(activity_select)

            task_input = screen.query_one("#setup-task-input", Input)
            self.assertTrue(task_input.disabled)

    async def test_setup_screen_starts_session(self):
        """Verify confirming setup screen applies selections and starts main screen timer."""
        app = PomlockApp(
            history_store=self.history_store,
            start_mode=StartMode.SETUP,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertIsInstance(app.screen, SetupScreen)

            screen = app.screen
            preset_select = screen.query_one("#setup-preset-select", Select)
            preset_select.value = "ultradian"
            await pilot.pause()

            btn_start = screen.query_one("#btn-start-setup", Button)
            btn_start.press()
            await pilot.pause()

            self.assertIsInstance(app.screen, MainScreen)
            self.assertEqual(app.engine.state, TimerState.RUNNING)
            self.assertEqual(app.engine.pomo_m, 90.0)

    async def test_setup_screen_cancel_exits(self):
        """Verify clicking cancel in setup screen stops app cleanly."""
        app = PomlockApp(
            history_store=self.history_store,
            start_mode=StartMode.SETUP,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertIsInstance(app.screen, SetupScreen)

            btn_cancel = app.screen.query_one("#btn-cancel-setup", Button)
            btn_cancel.press()
            await pilot.pause()

            self.assertFalse(app.is_running)

    async def test_direct_mode_starts_immediately(self):
        """Verify direct start mode automatically starts countdown on MainScreen."""
        app = PomlockApp(
            history_store=self.history_store,
            start_mode=StartMode.DIRECT,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertIsInstance(app.screen, MainScreen)
            self.assertEqual(app.engine.state, TimerState.RUNNING)

    async def test_custom_presets_and_activities_displayed(self):
        """Verify custom presets and activities from settings are loaded in selectors."""
        Settings.reset()
        settings = Settings()
        settings.setdefault("presets", {})["deep_flow"] = "60 15 30 2"
        settings.setdefault("activities", {})["research"] = {"daily": 120}

        app = PomlockApp(
            history_store=self.history_store,
            start_mode=StartMode.SETUP,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            self.assertIsInstance(screen, SetupScreen)

            preset_select = screen.query_one("#setup-preset-select", Select)
            preset_vals = [val for _, val in preset_select._options]
            self.assertIn("deep_flow", preset_vals)

            activity_select = screen.query_one("#setup-activity-select", Select)
            activity_vals = [val for _, val in activity_select._options]
            self.assertIn("research", activity_vals)

    async def test_cli_flags_preselect_options_in_setup(self):
        """Verify -t and -a flags preselect initial values on setup screen."""
        Settings.reset()
        with patch("sys.argv", ["pomlock", "--setup", "-t", "fifty_ten", "-a", "coding"]):
            app = PomlockApp(
                history_store=self.history_store,
            )
            self.assertEqual(app._start_mode, StartMode.SETUP)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, SetupScreen)

                preset_select = screen.query_one("#setup-preset-select", Select)
                self.assertEqual(preset_select.value, "fifty_ten")

                activity_select = screen.query_one("#setup-activity-select", Select)
                self.assertEqual(activity_select.value, "coding")
