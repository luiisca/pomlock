import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textual.widgets import Button

import pomlock.settings as settings_module
from pomlock.history_store import HistoryStore
from pomlock.settings import Settings
from pomlock.ui.app import PomlockApp
from pomlock.ui.widgets.timer_card import TimerCard


class TestPauseButton(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_history.db"
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

    async def test_pause_disabled_by_default(self):
        # Verify pause button and space binding are absent when setting is false
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()

            timer_card = app.query_one(TimerCard)
            self.assertEqual(len(timer_card.query("#btn-pause")), 0)

            # Ensure space press does not change running state
            self.assertEqual(app.engine.state.value, "running")
            await pilot.press("space")
            await pilot.pause()
            self.assertEqual(app.engine.state.value, "running")

    async def test_pause_enabled_via_config(self):
        # Enable pause_button in configuration file
        self._conf_path.write_text("[general]\npause_button = true\n")
        Settings.reset()

        # Verify pause button and space binding are present when setting is true
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()

            timer_card = app.query_one(TimerCard)
            self.assertEqual(len(timer_card.query("#btn-pause")), 1)

            # Test space key toggles pause
            self.assertEqual(app.engine.state.value, "running")
            await pilot.press("space")
            await pilot.pause()
            self.assertEqual(app.engine.state.value, "paused")

            await pilot.press("space")
            await pilot.pause()
            self.assertEqual(app.engine.state.value, "running")

            # Test pause button click toggles pause
            btn_pause = timer_card.query_one("#btn-pause", Button)
            btn_pause.press()
            await pilot.pause()
            self.assertEqual(app.engine.state.value, "paused")


if __name__ == "__main__":
    unittest.main()
