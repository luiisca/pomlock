from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
import sqlite3
from typing import Any, Optional
import uuid

from .constants import DEFAULT_DB_FILE, GoalPeriod, SessionKind
from .logger import logger


class BlockStatus(str, Enum):
    INCOMPLETE = "incomplete"
    COMPLETED = "completed"


class Database:
    """Encapsulates SQLite persistence for session blocks and goals."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_FILE):
        self._path = Path(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and return a configured SQLite connection."""
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize directory and schema tables."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS pomodoros (
                        id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        duration_s INTEGER NOT NULL DEFAULT 0,
                        activity TEXT NOT NULL,
                        session_type TEXT NOT NULL,
                        cycle INTEGER NOT NULL,
                        session INTEGER NOT NULL,
                        completed INTEGER NOT NULL DEFAULT 0
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS activities (
                        name TEXT PRIMARY KEY,
                        daily_goal INTEGER NOT NULL DEFAULT 0,
                        weekly_goal INTEGER NOT NULL DEFAULT 0,
                        monthly_goal INTEGER NOT NULL DEFAULT 0,
                        yearly_goal INTEGER NOT NULL DEFAULT 0
                    )
                """)
                conn.commit()

            logger.debug(f"Initialized SQLite database at {self._path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize SQLite database: {e}")

    def ensure_activity(self, name: str) -> None:
        """Ensure an activity exists in the database, inserting with 0 goals if missing."""
        clean_name = name.strip().lower()
        if not clean_name:
            return

        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO activities (name, daily_goal, weekly_goal, monthly_goal, yearly_goal)
                    VALUES (?, 0, 0, 0, 0)
                    """,
                    (clean_name,),
                )
                conn.commit()
            logger.debug(f"Ensured activity '{clean_name}' exists in database")
        except sqlite3.Error as e:
            logger.error(f"Failed to ensure activity '{clean_name}': {e}")

    def start_block(
        self,
        activity: str,
        kind: SessionKind,
        cycle: int,
        session: int,
        timestamp: Optional[str] = None,
    ) -> str:
        """Insert a new active block with 0 duration and return its ID."""
        self.ensure_activity(activity)

        block_id = str(uuid.uuid4())
        now_str = timestamp or datetime.now().isoformat()
        type_val = kind.value if isinstance(kind, SessionKind) else str(kind)

        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO pomodoros (id, timestamp, duration_s, activity, session_type, cycle, session, completed)
                    VALUES (?, ?, 0, ?, ?, ?, ?, 0)
                    """,
                    (block_id, now_str, activity, type_val, cycle, session),
                )
                conn.commit()
            logger.debug(f"Started block {block_id} ({activity}, {type_val})")
        except sqlite3.Error as e:
            logger.error(f"Failed to start block: {e}")

        return block_id

    def update_block(
        self,
        block_id: str,
        duration_s: int,
        status: BlockStatus = BlockStatus.INCOMPLETE,
    ) -> None:
        """Update duration and completion status of an existing block."""
        completed_val = 1 if status == BlockStatus.COMPLETED else 0

        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE pomodoros
                    SET duration_s = ?, completed = ?
                    WHERE id = ?
                    """,
                    (duration_s, completed_val, block_id),
                )
                conn.commit()
            logger.debug(f"Updated block {block_id} (duration_s: {duration_s}, status: {status})")
        except sqlite3.Error as e:
            logger.error(f"Failed to update block {block_id}: {e}")

    def get_records(self) -> list[dict[str, Any]]:
        """Return all block records mapped as dictionary rows."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, timestamp, duration_s, activity, session_type, cycle, session, completed
                    FROM pomodoros
                    ORDER BY timestamp ASC
                """)
                rows = cursor.fetchall()
                return [
                    {
                        "id": row["id"],
                        "timestamp": row["timestamp"],
                        "duration_s": row["duration_s"],
                        "duration_minutes": row["duration_s"] // 60,
                        "activity": row["activity"],
                        "session_type": row["session_type"],
                        "cycle": row["cycle"],
                        "session": row["session"],
                        "completed": "True" if row["completed"] == 1 else "False",
                    }
                    for row in rows
                ]
        except sqlite3.Error as e:
            logger.error(f"Failed to fetch records: {e}")
            return []

    def get_period_focus_seconds(
        self,
        period: GoalPeriod = GoalPeriod.DAILY,
        target_date: Optional[date] = None,
    ) -> dict[str, int]:
        """Aggregate focus duration in seconds by activity for a specific period."""
        ref_date = target_date or date.today()
        totals: dict[str, int] = {}

        if period == GoalPeriod.DAILY:
            start_dt = datetime(ref_date.year, ref_date.month, ref_date.day)
            end_dt = start_dt + timedelta(days=1)
        elif period == GoalPeriod.WEEKLY:
            start_of_week = ref_date - timedelta(days=ref_date.weekday())
            start_dt = datetime(start_of_week.year, start_of_week.month, start_of_week.day)
            end_dt = start_dt + timedelta(days=7)
        elif period == GoalPeriod.MONTHLY:
            start_dt = datetime(ref_date.year, ref_date.month, 1)
            if ref_date.month == 12:
                end_dt = datetime(ref_date.year + 1, 1, 1)
            else:
                end_dt = datetime(ref_date.year, ref_date.month + 1, 1)
        elif period == GoalPeriod.YEARLY:
            start_dt = datetime(ref_date.year, 1, 1)
            end_dt = datetime(ref_date.year + 1, 1, 1)
        else:
            start_dt = datetime(ref_date.year, ref_date.month, ref_date.day)
            end_dt = start_dt + timedelta(days=1)

        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT activity, SUM(duration_s) as total_s
                    FROM pomodoros
                    WHERE session_type = ? AND timestamp >= ? AND timestamp < ?
                    GROUP BY activity
                    """,
                    (SessionKind.POMODORO.value, start_iso, end_iso),
                )
                for row in cursor.fetchall():
                    totals[row["activity"].lower()] = row["total_s"] or 0
        except sqlite3.Error as e:
            logger.error(f"Failed to query period focus seconds: {e}")

        return totals

    def get_activities(self) -> list[dict[str, Any]]:
        """Return all defined activities and their multi-period goals in minutes."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name, daily_goal, weekly_goal, monthly_goal, yearly_goal
                    FROM activities
                    ORDER BY name ASC
                """)
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Failed to query activities: {e}")
            return []

    def save_activity(
        self,
        name: str,
        daily_goal: int,
        weekly_goal: int,
        monthly_goal: int,
        yearly_goal: int,
    ) -> None:
        """Insert or update activity goals in minutes."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO activities (name, daily_goal, weekly_goal, monthly_goal, yearly_goal)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        daily_goal = excluded.daily_goal,
                        weekly_goal = excluded.weekly_goal,
                        monthly_goal = excluded.monthly_goal,
                        yearly_goal = excluded.yearly_goal
                    """,
                    (name.lower(), daily_goal, weekly_goal, monthly_goal, yearly_goal),
                )
                conn.commit()
            logger.debug(f"Saved activity {name} goals")
        except sqlite3.Error as e:
            logger.error(f"Failed to save activity {name}: {e}")
