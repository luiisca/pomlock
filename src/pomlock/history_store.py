import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .constants import DEFAULT_CSV_FILE, SessionKind
from .logger import logger

CSV_HEADERS = [
    "timestamp",
    "activity",
    "session_type",
    "duration_minutes",
    "cycle",
    "session",
    "completed",
]


class HistoryStore:
    """Manages CSV session persistence and statistical aggregations."""

    def __init__(self, file_path: Path | str = DEFAULT_CSV_FILE):
        self._path = Path(file_path)
        self._init_file()

    def _init_file(self) -> None:
        """Create directory and header row if file does not exist, and seed dummy data."""
        if not self._path.exists():
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(CSV_HEADERS)
                logger.debug(f"Initialized history CSV at {self._path}")
                self._seed_dummy_data()
            except OSError as e:
                logger.error(f"Failed to initialize CSV history file: {e}")
        else:
            # If existing file is empty or only contains header, seed sample data
            try:
                with open(self._path, mode="r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                if len(lines) <= 1:
                    self._seed_dummy_data()
            except OSError:
                pass

    def _seed_dummy_data(self) -> None:
        """Populate realistic sample records for today and recent days for testing."""
        today = date.today()
        # Seed records for today and past 7 days
        sample_sessions = [
            # 6 days ago
            (today - timedelta(days=6), "09:00", "coding", 50, 1, 1),
            (today - timedelta(days=6), "10:30", "studying", 90, 2, 1),
            (today - timedelta(days=6), "14:00", "coding", 50, 3, 1),
            # 5 days ago
            (today - timedelta(days=5), "08:30", "coding", 90, 1, 1),
            (today - timedelta(days=5), "11:00", "reading", 30, 2, 1),
            (today - timedelta(days=5), "15:00", "coding", 90, 3, 1),
            # 4 days ago
            (today - timedelta(days=4), "09:30", "studying", 50, 1, 1),
            (today - timedelta(days=4), "14:00", "reading", 40, 2, 1),
            # 3 days ago
            (today - timedelta(days=3), "08:00", "coding", 90, 1, 1),
            (today - timedelta(days=3), "10:30", "studying", 60, 2, 1),
            (today - timedelta(days=3), "13:30", "coding", 60, 3, 1),
            # 2 days ago
            (today - timedelta(days=2), "09:00", "coding", 120, 1, 1),
            (today - timedelta(days=2), "14:00", "studying", 90, 2, 1),
            (today - timedelta(days=2), "16:30", "reading", 40, 3, 1),
            # Yesterday
            (today - timedelta(days=1), "09:00", "coding", 90, 1, 1),
            (today - timedelta(days=1), "11:30", "coding", 60, 2, 1),
            (today - timedelta(days=1), "15:00", "studying", 90, 3, 1),
            # Today
            (today, "08:30", "sleep", 416, 1, 1),
            (today, "08:30", "coding", 120, 1, 1),
            (today, "12:00", "studying", 120, 2, 1),
            (today, "15:00", "reading", 40, 3, 1),
        ]

        try:
            with open(self._path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for s_date, s_time, act, dur, cyc, sess in sample_sessions:
                    dt_str = f"{s_date.isoformat()}T{s_time}:00"
                    writer.writerow([
                        dt_str,
                        act,
                        SessionKind.POMODORO.value,
                        dur,
                        cyc,
                        sess,
                        "True",
                    ])
            logger.debug(f"Prepopulated dummy history in {self._path}")
        except OSError as e:
            logger.error(f"Failed to seed dummy history: {e}")

    def record(
        self,
        activity: str,
        kind: SessionKind,
        duration_m: int,
        cycle: int,
        session: int,
        completed: bool = True,
    ) -> None:
        """Append a completed or interrupted session record."""
        self._init_file()
        now_str = datetime.now().isoformat()

        row = [
            now_str,
            activity,
            kind.value if isinstance(kind, SessionKind) else str(kind),
            duration_m,
            cycle,
            session,
            str(completed),
        ]

        try:
            with open(self._path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)
            logger.debug(f"Saved session record: {row}")
        except OSError as e:
            logger.error(f"Failed to write history record: {e}")

    def get_records(self) -> list[dict[str, Any]]:
        """Read all session records from CSV."""
        if not self._path.exists():
            return []

        records: list[dict[str, Any]] = []
        try:
            with open(self._path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(row)
        except OSError as e:
            logger.error(f"Failed to read history CSV: {e}")

        return records

    def get_today_focus_by_activity(self, target_date: Optional[date] = None) -> dict[str, int]:
        """Aggregate focus minutes by activity for a specific day (default: today)."""
        check_date = target_date or date.today()
        records = self.get_records()
        totals: dict[str, int] = {}

        for r in records:
            # Only count pomodoro / focus work
            if r.get("session_type") != SessionKind.POMODORO.value:
                continue

            ts_str = r.get("timestamp", "")
            try:
                rec_dt = datetime.fromisoformat(ts_str)
                if rec_dt.date() == check_date:
                    act = r.get("activity", "other").lower()
                    dur = int(r.get("duration_minutes", 0))
                    totals[act] = totals.get(act, 0) + dur
            except (ValueError, TypeError):
                continue

        return totals

    def get_today_total_focus_minutes(self, target_date: Optional[date] = None) -> int:
        """Total focus minutes across all activities for today."""
        by_act = self.get_today_focus_by_activity(target_date)
        return sum(by_act.values())

    def get_weekly_focus_by_day(
        self,
        week_offset: int = 0,
    ) -> tuple[str, list[tuple[date, int]]]:
        """Return formatted week range label (e.g. '10/8 - 16/8') and 7-day focus minute pairs."""
        today = date.today()
        # Monday of reference week
        start_of_current_week = today - timedelta(days=today.weekday())
        start_of_week = start_of_current_week + timedelta(weeks=week_offset)
        end_of_week = start_of_week + timedelta(days=6)

        label = f"{start_of_week.day}/{start_of_week.month} - {end_of_week.day}/{end_of_week.month}"

        records = self.get_records()
        day_minutes: dict[date, int] = {
            start_of_week + timedelta(days=i): 0 for i in range(7)
        }

        for r in records:
            if r.get("session_type") != SessionKind.POMODORO.value:
                continue

            ts_str = r.get("timestamp", "")
            try:
                rec_dt = datetime.fromisoformat(ts_str)
                rec_date = rec_dt.date()
                if rec_date in day_minutes:
                    dur = int(r.get("duration_minutes", 0))
                    day_minutes[rec_date] += dur
            except (ValueError, TypeError):
                continue

        days_list = [(d, day_minutes[d]) for d in sorted(day_minutes.keys())]
        return label, days_list

    def get_all_focus_sessions_sorted(self, ascending: bool = True) -> list[dict[str, Any]]:
        """Return all focus sessions chronologically sorted."""
        records = self.get_records()
        parsed: list[dict[str, Any]] = []

        for r in records:
            ts_str = r.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts_str)
                dur = int(r.get("duration_minutes", 0))
                parsed.append({
                    "datetime": dt,
                    "date": dt.date(),
                    "time": dt.strftime("%H:%M"),
                    "activity": r.get("activity", "other"),
                    "duration_minutes": dur,
                    "session_type": r.get("session_type"),
                    "completed": r.get("completed") == "True",
                })
            except (ValueError, TypeError):
                continue

        parsed.sort(key=lambda x: x["datetime"], reverse=not ascending)
        return parsed
