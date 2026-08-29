from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pomlock.constants import SessionKind, TimerState
from pomlock.history_store import HistoryStore
from pomlock.timer_engine import TimerEngine


class TestTimerEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / "test_history.csv"
        self.history_store = HistoryStore(file_path=self.csv_path)
        self.settings = {
            "pomodoro": 25,
            "short_break": 5,
            "long_break": 15,
            "cycles": 2,
            "activity": "testing",
            "block_input": False,
            "notify": False,
            "callback": "",
        }
        self.engine = TimerEngine(
            settings=self.settings,
            history_store=self.history_store,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initial_state(self):
        self.assertEqual(self.engine.state, TimerState.STOPPED)
        self.assertEqual(self.engine.kind, SessionKind.POMODORO)
        self.assertEqual(self.engine.crr_cycle, 1)
        self.assertEqual(self.engine.remaining_s, 25 * 60)

    def test_start_pause_resume(self):
        self.engine.start()
        self.assertEqual(self.engine.state, TimerState.RUNNING)

        self.engine.pause()
        self.assertEqual(self.engine.state, TimerState.PAUSED)

        self.engine.resume()
        self.assertEqual(self.engine.state, TimerState.RUNNING)

    def test_phase_advancement(self):
        self.engine.start()
        self.assertEqual(self.engine.kind, SessionKind.POMODORO)

        # Skip pomodoro -> short break (cycle 1)
        self.engine.skip()
        self.assertEqual(self.engine.kind, SessionKind.SHORT_BREAK)
        self.assertEqual(self.engine.duration_s, 5 * 60)

        # Skip short break -> pomodoro (cycle 2)
        self.engine.skip()
        self.assertEqual(self.engine.kind, SessionKind.POMODORO)
        self.assertEqual(self.engine.crr_cycle, 2)

        # Skip pomodoro cycle 2 -> long break (since total cycles = 2)
        self.engine.skip()
        self.assertEqual(self.engine.kind, SessionKind.LONG_BREAK)
        self.assertEqual(self.engine.duration_s, 15 * 60)

        # Skip long break -> new session cycle 1
        self.engine.skip()
        self.assertEqual(self.engine.kind, SessionKind.POMODORO)
        self.assertEqual(self.engine.crr_cycle, 1)
        self.assertEqual(self.engine.crr_session, 2)

    def test_skip_never_loops_breaks(self):
        # Configure with 4 cycles
        self.engine.total_cycles = 4
        self.engine.start()

        # Iterate through 16 phase skips (2 full sessions of 4 cycles each)
        for i in range(16):
            current_kind = self.engine.kind
            self.engine.skip()
            next_kind = self.engine.kind

            # A break must ALWAYS be followed by a POMODORO
            if current_kind in (SessionKind.SHORT_BREAK, SessionKind.LONG_BREAK):
                self.assertEqual(
                    next_kind,
                    SessionKind.POMODORO,
                    f"Break {current_kind} was followed by {next_kind} at step {i}",
                )
            # A POMODORO must be followed by either short or long break
            elif current_kind == SessionKind.POMODORO:
                self.assertIn(
                    next_kind,
                    (SessionKind.SHORT_BREAK, SessionKind.LONG_BREAK),
                    f"Pomodoro was followed by {next_kind} at step {i}",
                )


if __name__ == "__main__":
    unittest.main()
