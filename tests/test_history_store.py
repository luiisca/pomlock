from pathlib import Path
import tempfile
import unittest

from datetime import datetime, timedelta

from pomlock.constants import GoalPeriod, SessionKind
from pomlock.history_store import HistoryStore


class TestHistoryStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_history.db"
        self.store = HistoryStore(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_database_initialization(self):
        self.assertTrue(self.db_path.exists())
        records = self.store.get_records()
        self.assertEqual(len(records), 0)

    def test_record_session(self):
        initial_count = len(self.store.get_records())
        self.store.record(
            activity="coding",
            kind=SessionKind.POMODORO,
            duration_m=25,
            cycle=1,
            session=1,
            completed=True,
        )
        records = self.store.get_records()
        self.assertEqual(len(records), initial_count + 1)
        last_rec = records[-1]
        self.assertEqual(last_rec["activity"], "coding")
        self.assertEqual(last_rec["session_type"], "pomodoro")
        self.assertEqual(last_rec["duration_minutes"], 25)
        self.assertEqual(last_rec["duration_s"], 1500)
        self.assertEqual(last_rec["cycle"], 1)
        self.assertEqual(last_rec["session"], 1)
        self.assertEqual(last_rec["completed"], "True")

    def test_block_open_and_update(self):
        block_id = self.store.start_block(
            activity="studying",
            kind=SessionKind.POMODORO,
            cycle=1,
            session=1,
        )
        self.assertIsNotNone(block_id)

        # Initially duration_s should be 0
        records = self.store.get_records()
        open_rec = next(r for r in records if r["id"] == block_id)
        self.assertEqual(open_rec["duration_s"], 0)

        # Update duration
        self.store.update_block_duration(block_id=block_id, duration_s=42, completed=False)
        records = self.store.get_records()
        updated_rec = next(r for r in records if r["id"] == block_id)
        self.assertEqual(updated_rec["duration_s"], 42)
        self.assertEqual(updated_rec["completed"], "False")

    def test_auto_activity_creation_on_start_block(self):
        """Starting a block with an unknown activity auto-creates it in activities with 0 goals."""
        activities_before = self.store.get_activities()
        self.assertNotIn("chess", [a["name"] for a in activities_before])

        self.store.start_block(
            activity="chess",
            kind=SessionKind.POMODORO,
            cycle=1,
            session=1,
        )

        activities_after = self.store.get_activities()
        chess_act = next((a for a in activities_after if a["name"] == "chess"), None)
        self.assertIsNotNone(chess_act)
        self.assertEqual(chess_act["daily_goal"], 0)
        self.assertEqual(chess_act["weekly_goal"], 0)
        self.assertEqual(chess_act["monthly_goal"], 0)
        self.assertEqual(chess_act["yearly_goal"], 0)

    def test_activity_goals_crud(self):
        self.store.save_activity(
            name="writing",
            daily_goal=60,
            weekly_goal=300,
            monthly_goal=1320,
            yearly_goal=15600,
        )
        activities = self.store.get_activities()
        writing = next((a for a in activities if a["name"] == "writing"), None)
        self.assertIsNotNone(writing)
        self.assertEqual(writing["daily_goal"], 60)
        self.assertEqual(writing["weekly_goal"], 300)

    def test_aggregations(self):
        self.store.record("coding", SessionKind.POMODORO, 50, 1, 1)
        self.store.record("reading", SessionKind.POMODORO, 30, 1, 2)

        today_focus = self.store.get_today_focus_by_activity()
        self.assertIsInstance(today_focus, dict)
        self.assertEqual(today_focus.get("coding"), 50)
        self.assertEqual(today_focus.get("reading"), 30)

        total_today = self.store.get_today_total_focus_minutes()
        self.assertEqual(total_today, 80)

        week_label, week_data = self.store.get_weekly_focus_by_day(0)
        self.assertIn("-", week_label)
        self.assertEqual(len(week_data), 7)

        chronological = self.store.get_all_focus_sessions_sorted(ascending=True)
        self.assertEqual(len(chronological), 2)
        for i in range(len(chronological) - 1):
            self.assertLessEqual(chronological[i]["datetime"], chronological[i + 1]["datetime"])

    def test_all_blocks_include_breaks_and_end_times(self):
        start = datetime(2026, 8, 31, 9, 0)
        focus_id = self.store.start_block(
            "coding", SessionKind.POMODORO, 1, 1, start.isoformat()
        )
        break_id = self.store.start_block(
            "coding", SessionKind.SHORT_BREAK, 1, 1,
            (start + timedelta(minutes=26)).isoformat(),
        )
        self.store.update_block_duration(focus_id, duration_s=25 * 60, completed=True)
        self.store.update_block_duration(break_id, duration_s=5 * 60, completed=True)

        blocks = self.store.get_all_blocks_sorted()

        self.assertEqual([block["session_type"] for block in blocks], [
            SessionKind.POMODORO.value,
            SessionKind.SHORT_BREAK.value,
        ])
        self.assertEqual(blocks[0]["started_at"], start)
        self.assertEqual(blocks[0]["ended_at"], start + timedelta(minutes=25))


if __name__ == "__main__":
    unittest.main()
