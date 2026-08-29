import csv
from datetime import date
from pathlib import Path
import tempfile
import unittest

from pomlock.constants import SessionKind
from pomlock.history_store import CSV_HEADERS, HistoryStore


class TestHistoryStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / "test_history.csv"
        self.store = HistoryStore(file_path=self.csv_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_file_initialization_and_seeding(self):
        self.assertTrue(self.csv_path.exists())
        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(header, CSV_HEADERS)

        # Seeded dummy records exist
        records = self.store.get_records()
        self.assertGreater(len(records), 0)

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
        self.assertEqual(last_rec["duration_minutes"], "25")
        self.assertEqual(last_rec["cycle"], "1")
        self.assertEqual(last_rec["session"], "1")
        self.assertEqual(last_rec["completed"], "True")

    def test_aggregations(self):
        today_focus = self.store.get_today_focus_by_activity()
        self.assertIsInstance(today_focus, dict)

        total_today = self.store.get_today_total_focus_minutes()
        self.assertGreaterEqual(total_today, 0)

        week_label, week_data = self.store.get_weekly_focus_by_day(0)
        self.assertIn("-", week_label)
        self.assertEqual(len(week_data), 7)

        chronological = self.store.get_all_focus_sessions_sorted(ascending=True)
        self.assertGreater(len(chronological), 0)
        # Ensure chronological order
        for i in range(len(chronological) - 1):
            self.assertLessEqual(chronological[i]["datetime"], chronological[i + 1]["datetime"])


if __name__ == "__main__":
    unittest.main()
