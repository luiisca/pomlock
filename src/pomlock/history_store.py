from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .constants import DEFAULT_DB_FILE, GoalPeriod, SessionKind
from .db import BlockStatus, Database
from .logger import logger


class HistoryStore:
    """Manages SQLite session persistence, goals, and statistical aggregations."""

    def __init__(
        self,
        db_path: Optional[Path | str] = None,
        db: Optional[Database] = None,
        file_path: Optional[Path | str] = None,
    ):
        target_path = db_path or file_path or DEFAULT_DB_FILE
        self._db = db or Database(db_path=target_path)

    @property
    def db(self) -> Database:
        return self._db

    def start_block(
        self,
        activity: str,
        kind: SessionKind,
        cycle: int,
        session: int,
        timestamp: Optional[str] = None,
    ) -> str:
        """Start a new block in the database with 0 elapsed seconds."""
        return self._db.start_block(
            activity=activity,
            kind=kind,
            cycle=cycle,
            session=session,
            timestamp=timestamp,
        )

    def update_block_duration(
        self,
        block_id: str,
        duration_s: int,
        completed: bool = False,
    ) -> None:
        """Update elapsed seconds and completion state of an active block."""
        status = BlockStatus.COMPLETED if completed else BlockStatus.INCOMPLETE
        self._db.update_block(block_id=block_id, duration_s=duration_s, status=status)

    def record(
        self,
        activity: str,
        kind: SessionKind,
        duration_m: int,
        cycle: int,
        session: int,
        completed: bool = True,
    ) -> None:
        """Compatibility method: record a completed or interrupted session."""
        duration_s = duration_m * 60
        block_id = self.start_block(activity=activity, kind=kind, cycle=cycle, session=session)
        self.update_block_duration(block_id=block_id, duration_s=duration_s, completed=completed)

    def get_records(self) -> list[dict[str, Any]]:
        """Read all session records from database."""
        return self._db.get_records()

    def get_period_focus_by_activity(
        self,
        period: GoalPeriod = GoalPeriod.DAILY,
        target_date: Optional[date] = None,
    ) -> dict[str, int]:
        """Aggregate focus duration in minutes by activity for a specific period."""
        sec_map = self._db.get_period_focus_seconds(period=period, target_date=target_date)
        return {act: dur_s // 60 for act, dur_s in sec_map.items()}

    def get_today_focus_by_activity(self, target_date: Optional[date] = None) -> dict[str, int]:
        """Aggregate focus minutes by activity for a specific day (default: today)."""
        return self.get_period_focus_by_activity(period=GoalPeriod.DAILY, target_date=target_date)

    def get_today_total_focus_minutes(self, target_date: Optional[date] = None) -> int:
        """Total focus minutes across all activities for today."""
        by_act = self.get_today_focus_by_activity(target_date)
        return sum(by_act.values())

    def get_weekly_focus_by_day(
        self,
        week_offset: int = 0,
        activity: Optional[str] = None,
        week_start_day: Optional[str | int] = None,
        reference_date: Optional[date] = None,
    ) -> tuple[str, list[tuple[date, int]]]:
        """Return formatted week range label and 7-day focus minute pairs."""
        # Resolve week start day from settings if not explicitly provided
        if week_start_day is None:
            from .settings import Settings
            settings = Settings()
            loc_data = settings.get("localization", {}) if isinstance(settings.get("localization"), dict) else {}
            week_start_day = loc_data.get("week_start_day", "monday")

        day_map = {
            "monday": 0, "mon": 0,
            "tuesday": 1, "tue": 1,
            "wednesday": 2, "wed": 2,
            "thursday": 3, "thu": 3,
            "friday": 4, "fri": 4,
            "saturday": 5, "sat": 5,
            "sunday": 6, "sun": 6,
        }
        start_idx = (
            day_map.get(str(week_start_day).lower(), 0)
            if isinstance(week_start_day, str)
            else int(week_start_day or 0) % 7
        )

        # Calculate week boundaries using calendar dates
        today = reference_date or date.today()
        days_to_subtract = (today.weekday() - start_idx) % 7
        start_of_current_week = today - timedelta(days=days_to_subtract)
        start_of_week = start_of_current_week + timedelta(weeks=week_offset)
        end_of_week = start_of_week + timedelta(days=6)

        label = f"{start_of_week.day}/{start_of_week.month} - {end_of_week.day}/{end_of_week.month}"

        # Initialize all 7 days with zero duration
        day_minutes: dict[date, int] = {
            start_of_week + timedelta(days=i): 0 for i in range(7)
        }

        # Query database for pomodoro focus records in week range
        start_iso = datetime(start_of_week.year, start_of_week.month, start_of_week.day).isoformat()
        end_dt = datetime(end_of_week.year, end_of_week.month, end_of_week.day) + timedelta(days=1)
        end_iso = end_dt.isoformat()

        records = self._db.get_focus_records_in_range(
            start_iso=start_iso,
            end_iso=end_iso,
            activity=activity,
        )

        for r in records:
            ts_str = r.get("timestamp", "")
            try:
                rec_dt = datetime.fromisoformat(ts_str)
                rec_date = rec_dt.date()
                if rec_date in day_minutes:
                    dur_s = int(r.get("duration_s", 0))
                    day_minutes[rec_date] += dur_s // 60
            except (ValueError, TypeError):
                continue

        days_list = [(d, day_minutes[d]) for d in sorted(day_minutes.keys())]
        return label, days_list

    def get_all_focus_sessions_sorted(self, ascending: bool = True) -> list[dict[str, Any]]:
        """Return all focus sessions chronologically sorted."""
        blocks = self.get_all_blocks_sorted(ascending=ascending)
        return [block for block in blocks if block["session_type"] == SessionKind.POMODORO.value]

    def get_all_blocks_sorted(self, ascending: bool = True) -> list[dict[str, Any]]:
        """Return every recorded focus and break block chronologically."""
        records = self.get_records()
        parsed: list[dict[str, Any]] = []

        for r in records:
            ts_str = r.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts_str)
                dur_s = int(r.get("duration_s", 0))
                parsed.append({
                    "datetime": dt,
                    "date": dt.date(),
                    "time": dt.strftime("%H:%M"),
                    "activity": r.get("activity", "other"),
                    "duration_minutes": dur_s // 60,
                    "duration_s": dur_s,
                    "session_type": r.get("session_type"),
                    "completed": r.get("completed") == "True",
                    "started_at": dt,
                    "ended_at": dt + timedelta(seconds=dur_s),
                })
            except (ValueError, TypeError):
                continue

        parsed.sort(key=lambda x: x["datetime"], reverse=not ascending)
        return parsed

