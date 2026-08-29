from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Middle, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from ..widgets.timer_card import render_digital_clock


class BreakScreen(ModalScreen):
    """Full screen break overlay screen."""

    BINDINGS = [
        Binding("s", "skip_break", "Skip Break", show=False),
        Binding("space", "toggle_timer", "Toggle Pause", show=False),
        Binding("q", "quit_app", "Quit", show=False),
    ]

    def __init__(self, break_type: str = "Short break"):
        super().__init__()
        self._break_type = break_type

    def compose(self) -> ComposeResult:
        with Middle(classes="break-modal-container"):
            with Center():
                with Vertical(classes="break-modal-box"):
                    yield Label(f"{self._break_type.upper()}", classes="break-title")
                    yield Static(render_digital_clock("05:00"), id="break-digits", classes="timer-digital-display")
                    yield Label("Step away from the screen. Input is locked.", classes="break-subtitle")

    def update_countdown(self, remaining_s: int) -> None:
        """Update break countdown timer if mounted."""
        try:
            mins, secs = divmod(remaining_s, 60)
            digits = self.query_one("#break-digits", Static)
            digits.update(render_digital_clock(f"{mins:02d}:{secs:02d}"))
        except Exception:
            pass

    def action_skip_break(self) -> None:
        """Skip the break phase."""
        self.app.engine.skip()

    def action_toggle_timer(self) -> None:
        """Toggle pause state."""
        self.app.engine.toggle_pause()

    def action_quit_app(self) -> None:
        """Quit the application."""
        self.app.action_quit_app()
