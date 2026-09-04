from pathlib import Path
import tempfile
import unittest

from pomlock.constants import SessionKind
from pomlock.history_store import HistoryStore
from pomlock.ui.app import PomlockApp
from pomlock.ui.screens.main_screen import MainScreen


class TestInfiniteBreak(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / "test_history.csv"
        self.history_store = HistoryStore(file_path=self.csv_path)
        self.settings = {
            "pomodoro": 1,
            "short_break": 1,
            "long_break": 1,
            "cycles": 1,
            "activity": "testing",
            "block_input": False,
            "overlay": True,
            "notify": False,
            "callback": "",
        }

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_break_auto_transition_to_focus(self):
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test() as pilot:
            await pilot.pause()

            # Skip from Pomodoro to break
            await pilot.press("s")
            await pilot.pause()

            self.assertIn(
                app.engine.kind, (SessionKind.SHORT_BREAK, SessionKind.LONG_BREAK)
            )
            self.assertIsInstance(app.screen, MainScreen)

            # Fast-forward engine elapsed time to simulate break expiring
            app.engine.elapsed_s = float(app.engine.duration_s)
            app._tick_engine()
            await pilot.pause()

            # Should transition back to Pomodoro
            self.assertEqual(app.engine.kind, SessionKind.POMODORO)
            self.assertIsInstance(app.screen, MainScreen)


if __name__ == "__main__":
    unittest.main()
