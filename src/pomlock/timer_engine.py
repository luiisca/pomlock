import json
import subprocess
import time
from typing import Callable, Optional

from .constants import STATE_FILE, SessionKind, TimerState
from .history_store import HistoryStore
from .input_handler import disable_input_devices, enable_input_devices
from .logger import logger


class TimerEngine:
    """Core state machine and countdown logic for pomlock."""

    def __init__(
        self,
        settings: dict,
        history_store: Optional[HistoryStore] = None,
        on_tick: Optional[Callable[[int, float], None]] = None,
        on_phase_change: Optional[Callable[[SessionKind, int], None]] = None,
    ):
        self.settings = settings
        self.history = history_store or HistoryStore()
        self._on_tick = on_tick
        self._on_phase_change = on_phase_change

        self.pomo_m = float(settings.get("pomodoro", 25))
        self.s_break_m = float(settings.get("short_break", 5))
        self.l_break_m = float(settings.get("long_break", 20))
        self.total_cycles = int(settings.get("cycles", 4))
        self.activity = str(settings.get("activity", "other"))

        self.state = TimerState.STOPPED
        self.kind = SessionKind.POMODORO
        self.crr_cycle = 1
        self.crr_session = 1
        self.completed_sessions = 0

        self.duration_s = int(round(self.pomo_m * 60))
        self.elapsed_s = 0.0
        self._last_tick_time = 0.0
        self._current_block_id: Optional[str] = None
        self._is_cleaned_up = False

    @property
    def remaining_s(self) -> int:
        return max(0, int(self.duration_s - self.elapsed_s))

    @property
    def progress_pct(self) -> float:
        if self.duration_s <= 0:
            return 1.0
        return min(1.0, self.elapsed_s / self.duration_s)

    @property
    def next_break_m(self) -> int:
        if self.crr_cycle >= self.total_cycles:
            return self.l_break_m
        return self.s_break_m

    def start(self) -> None:
        """Start or restart the timer loop."""
        if self._current_block_id is None:
            self._open_block()

        self.state = TimerState.RUNNING
        self._last_tick_time = time.time()
        self._notify_phase_start()

    def pause(self) -> None:
        """Pause current countdown without writing to database."""
        if self.state == TimerState.RUNNING:
            self.state = TimerState.PAUSED
            logger.debug(f"Paused block {self._current_block_id} at {self.elapsed_s:.1f}s")

    def resume(self) -> None:
        """Resume counting down."""
        if self.state == TimerState.PAUSED:
            self.state = TimerState.RUNNING
            self._last_tick_time = time.time()
            logger.debug(f"Resumed block {self._current_block_id}")

    def toggle_pause(self) -> None:
        """Toggle between paused and running states."""
        if self.state == TimerState.RUNNING:
            self.pause()
        elif self.state == TimerState.PAUSED:
            self.resume()
        elif self.state == TimerState.STOPPED:
            self.start()

    def reset(self) -> None:
        """Finalize current elapsed run time and start fresh block."""
        self._capture_elapsed()
        self._flush_block(completed=False)
        self.elapsed_s = 0.0
        self._last_tick_time = time.time()
        self._open_block()
        self._sync_state()

        if self._on_tick:
            self._on_tick(self.remaining_s, self.progress_pct)

    def skip(self) -> None:
        """Skip current phase, flush elapsed time, and advance to next."""
        self._capture_elapsed()
        self._flush_block(completed=False)
        self._current_block_id = None
        self._advance_phase()

    def tick(self) -> None:
        """Update timer state by elapsed wall clock time."""
        if self.state != TimerState.RUNNING:
            return

        self._capture_elapsed()

        if self.elapsed_s >= self.duration_s:
            self.elapsed_s = float(self.duration_s)
            self._on_interval_end()
            return

        self._sync_state()
        if self._on_tick:
            self._on_tick(self.remaining_s, self.progress_pct)

    def cleanup(self) -> None:
        """Clean up state file, flush open block, and restore input devices."""
        if self._is_cleaned_up:
            return

        self._is_cleaned_up = True
        self._capture_elapsed()
        self._flush_block(completed=False)
        self._current_block_id = None

        if self.settings.get("block_input"):
            enable_input_devices()

        if STATE_FILE.exists():
            try:
                STATE_FILE.unlink()
            except OSError as e:
                logger.debug(f"Error removing state file: {e}")

    def _capture_elapsed(self) -> None:
        """Account for running time since the last clock update."""
        if self.state != TimerState.RUNNING:
            return

        now = time.time()
        delta = max(0.0, now - self._last_tick_time)
        self._last_tick_time = now
        self.elapsed_s = min(float(self.duration_s), self.elapsed_s + delta)

    def _open_block(self) -> None:
        """Create new active block entry in database."""
        self._current_block_id = self.history.start_block(
            activity=self.activity,
            kind=self.kind,
            cycle=self.crr_cycle,
            session=self.crr_session,
        )
        logger.debug(f"Opened block {self._current_block_id} for {self.activity}")

    def _flush_block(self, completed: bool = False) -> None:
        """Persist exact elapsed seconds to database."""
        if self._current_block_id is None:
            return

        dur_s = int(round(self.elapsed_s))
        self.history.update_block_duration(
            block_id=self._current_block_id,
            duration_s=dur_s,
            completed=completed,
        )
        logger.debug(f"Flushed block {self._current_block_id}: {dur_s}s (completed={completed})")

    def _on_interval_end(self) -> None:
        """Handle phase completion."""
        self._flush_block(completed=True)
        self._current_block_id = None
        self._advance_phase()

    def _advance_phase(self) -> None:
        """Switch between pomodoro and breaks, managing cycles."""
        # Unblock input if we are exiting a break
        if self.kind != SessionKind.POMODORO and self.settings.get("block_input"):
            enable_input_devices()

        if self.kind == SessionKind.POMODORO:
            # Transition to break
            if self.crr_cycle >= self.total_cycles:
                self.kind = SessionKind.LONG_BREAK
                self.duration_s = int(round(self.l_break_m * 60))
            else:
                self.kind = SessionKind.SHORT_BREAK
                self.duration_s = int(round(self.s_break_m * 60))

            if self.settings.get("block_input"):
                disable_input_devices()
        else:
            # Break completed, transition to Pomodoro
            if self.kind == SessionKind.LONG_BREAK:
                self.crr_session += 1
                self.completed_sessions += 1
                self.crr_cycle = 1
            else:
                self.crr_cycle += 1

            self.kind = SessionKind.POMODORO
            self.duration_s = int(round(self.pomo_m * 60))

        self.elapsed_s = 0.0
        self._last_tick_time = time.time()
        self._open_block()
        self._notify_phase_start()

    def _notify_phase_start(self) -> None:
        """Send notifications, execute callbacks, and notify UI listeners."""
        duration_m = int(self.duration_s // 60)
        is_pomo = self.kind == SessionKind.POMODORO
        msg_key = "pomo_notify_msg" if is_pomo else (
            "long_break_notify_msg" if self.kind == SessionKind.LONG_BREAK else "break_notify_msg"
        )
        notify_msg = self.settings.get(msg_key, "Phase started")

        self._send_notification(notify_msg, self.activity)
        self._sync_state()

        event_data = {
            "action": self.kind.value,
            "time": duration_m,
            "start_time": time.time(),
            "crr-cycle": self.crr_cycle,
            "total-cycles": self.total_cycles,
            "crr-session": self.crr_session,
        }
        self._exec_callback(self.settings.get("callback"), event_data)

        if self._on_phase_change:
            self._on_phase_change(self.kind, duration_m)

        if self._on_tick:
            self._on_tick(self.remaining_s, self.progress_pct)

    def _sync_state(self) -> None:
        """Write current status to state file for external tools (e.g. Waybar)."""
        duration_m = int(self.duration_s // 60)
        state_data = {
            "action": self.kind.value,
            "time": duration_m,
            "start_time": time.time() - self.elapsed_s,
            "crr_cycle": self.crr_cycle,
            "total_cycles": self.total_cycles,
            "crr_session": self.crr_session,
            "state": self.state.value,
        }

        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state_data, f)
        except OSError as e:
            logger.debug(f"Failed to write state file: {e}")

    def _send_notification(self, msg: str, activity: Optional[str] = None) -> None:
        """Trigger desktop notification via notify-send."""
        if not self.settings.get("notify", False):
            return

        text = f"{msg} - {activity}" if activity else msg
        try:
            subprocess.Popen(["notify-send", text])
        except (FileNotFoundError, OSError) as e:
            logger.debug(f"Notification error: {e}")

    def _exec_callback(self, callback_cmd: Optional[str], data: dict) -> None:
        """Execute user-configured callback script."""
        if not callback_cmd:
            return

        try:
            cmd = callback_cmd.split() + [json.dumps(data)]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            logger.debug(f"Callback execution failed: {e}")
