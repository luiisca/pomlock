from datetime import datetime, timedelta
import unittest

from pomlock.constants import SessionKind
from pomlock.ui.widgets.activity_list import build_timeline


class TestActivityTimeline(unittest.TestCase):
    def test_renders_breaks_and_untracked_gaps(self):
        start = datetime(2026, 8, 31, 9, 0)
        focus_end = start + timedelta(minutes=25)
        break_start = focus_end + timedelta(minutes=2)
        break_end = break_start + timedelta(minutes=5)
        blocks = [
            self._block(start, focus_end, SessionKind.POMODORO, "coding"),
            self._block(break_start, break_end, SessionKind.SHORT_BREAK, "coding"),
        ]

        entries = build_timeline(blocks)

        self.assertEqual([entry.kind for entry in entries], [
            SessionKind.POMODORO.value,
            "gap",
            SessionKind.SHORT_BREAK.value,
        ])
        self.assertEqual(entries[1].duration_s, 120)

    def test_skips_contiguous_and_overlapping_gaps(self):
        start = datetime(2026, 8, 31, 9, 0)
        focus_end = start + timedelta(minutes=25)
        blocks = [
            self._block(start, focus_end, SessionKind.POMODORO, "coding"),
            self._block(focus_end, focus_end + timedelta(minutes=5), SessionKind.SHORT_BREAK, "coding"),
            self._block(focus_end + timedelta(minutes=2), focus_end + timedelta(minutes=7), SessionKind.POMODORO, "reading"),
        ]

        entries = build_timeline(blocks)

        self.assertNotIn("gap", [entry.kind for entry in entries])

    @staticmethod
    def _block(started_at, ended_at, kind, activity):
        return {
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_s": int((ended_at - started_at).total_seconds()),
            "session_type": kind.value,
            "activity": activity,
        }
