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
        self.db_path = Path(self.temp_dir.name) / "test_history.db"
        self.history_store = HistoryStore(db_path=self.db_path)
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

    def test_cleanup_records_elapsed_wall_time(self):
        self.engine.start()
        self.engine._last_tick_time = 100.0

        with patch("pomlock.timer_engine.time.time", return_value=142.0):
            self.engine.cleanup()

        record = self.history_store.get_records()[0]
        self.assertEqual(record["duration_s"], 42)
        self.assertEqual(record["completed"], "False")

    def test_cleanup_records_active_break(self):
        self.engine.start()
        self.engine.skip()
        self.engine._last_tick_time = 100.0

        with patch("pomlock.timer_engine.time.time", return_value=107.0):
            self.engine.cleanup()

        record = self.history_store.get_records()[-1]
        self.assertEqual(record["session_type"], SessionKind.SHORT_BREAK.value)
        self.assertEqual(record["duration_s"], 7)
        self.assertEqual(record["completed"], "False")

    def test_cleanup_is_idempotent(self):
        self.engine.start()
        self.engine._last_tick_time = 100.0

        with patch("pomlock.timer_engine.time.time", return_value=105.0):
            self.engine.cleanup()

        with patch("pomlock.timer_engine.time.time", return_value=110.0):
            self.engine.cleanup()

        records = self.history_store.get_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["duration_s"], 5)

    def test_interrupted_session_flow_with_three_entries(self):
        """
        Test flow:
        - start a session of 25 min
        - pause after 10 seconds
        - continue after 5 seconds
        - reset after 15 seconds
        - skip after 10 seconds
        - close the app after 5 seconds
        Verifies 3 entries in pomodoros table:
        1. pomodoro: duration_s: 25
        2. pomodoro 2: duration_s: 10
        3. break: duration_s: 5
        """
        initial_record_count = len(self.history_store.get_records())

        # 1. Start a session of 25 min
        self.engine.start()

        # 2. Pause after 10 seconds
        self.engine.elapsed_s = 10.0
        self.engine.pause()

        # 3. Continue after 5 seconds (pause does not accumulate countdown elapsed_s)
        self.engine.resume()

        # 4. Reset after 15 seconds (10s before pause + 15s after = 25s total elapsed on block 1)
        self.engine.elapsed_s = 25.0
        self.engine.reset()

        # 5. Skip after 10 seconds (10s elapsed on block 2 / pomodoro 2)
        self.engine.elapsed_s = 10.0
        self.engine.skip()

        # 6. Close the app after 5 seconds (5s elapsed on block 3 / break)
        self.engine.elapsed_s = 5.0
        self.engine.cleanup()

        # Retrieve new records
        all_records = self.history_store.get_records()
        new_records = all_records[initial_record_count:]

        self.assertEqual(len(new_records), 3)

        # Block 1: pomodoro with duration_s = 25
        rec1 = new_records[0]
        self.assertIsNotNone(rec1["id"])
        self.assertIsNotNone(rec1["timestamp"])
        self.assertEqual(rec1["session_type"], SessionKind.POMODORO.value)
        self.assertEqual(rec1["duration_s"], 25)

        # Block 2: pomodoro 2 with duration_s = 10
        rec2 = new_records[1]
        self.assertIsNotNone(rec2["id"])
        self.assertIsNotNone(rec2["timestamp"])
        self.assertEqual(rec2["session_type"], SessionKind.POMODORO.value)
        self.assertEqual(rec2["duration_s"], 10)

        # Block 3: break with duration_s = 5
        rec3 = new_records[2]
        self.assertIsNotNone(rec3["id"])
        self.assertIsNotNone(rec3["timestamp"])
        self.assertEqual(rec3["session_type"], SessionKind.SHORT_BREAK.value)
        self.assertEqual(rec3["duration_s"], 5)

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
        self.engine.total_cycles = 4
        self.engine.start()

        for i in range(16):
            current_kind = self.engine.kind
            self.engine.skip()
            next_kind = self.engine.kind

            if current_kind in (SessionKind.SHORT_BREAK, SessionKind.LONG_BREAK):
                self.assertEqual(
                    next_kind,
                    SessionKind.POMODORO,
                    f"Break {current_kind} was followed by {next_kind} at step {i}",
                )
            elif current_kind == SessionKind.POMODORO:
                self.assertIn(
                    next_kind,
                    (SessionKind.SHORT_BREAK, SessionKind.LONG_BREAK),
                    f"Pomodoro was followed by {next_kind} at step {i}",
                )


if __name__ == "__main__":
    unittest.main()
