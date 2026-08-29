from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Label, Static

DIGIT_GLYPHS = {
    "0": ["█████", "█   █", "█   █", "█   █", "█████"],
    "1": ["   ██", "   ██", "   ██", "   ██", "   ██"],
    "2": ["█████", "    █", "█████", "█    ", "█████"],
    "3": ["█████", "    █", "█████", "    █", "█████"],
    "4": ["█   █", "█   █", "█████", "    █", "    █"],
    "5": ["█████", "█    ", "█████", "    █", "█████"],
    "6": ["█████", "█    ", "█████", "█   █", "█████"],
    "7": ["█████", "    █", "    █", "    █", "    █"],
    "8": ["█████", "█   █", "█████", "█   █", "█████"],
    "9": ["█████", "█   █", "█████", "    █", "█████"],
    ":": ["     ", "  █  ", "     ", "  █  ", "     "],
}

GLYPH_ROWS = 5
SPACE_GLYPH = ["     "] * GLYPH_ROWS


def render_digital_clock(time_str: str) -> str:
    """Render a time string as bold digital alarm clock ASCII digits."""
    lines = ["", "", "", "", ""]
    for char in time_str:
        glyph = DIGIT_GLYPHS.get(char, SPACE_GLYPH)
        for i in range(GLYPH_ROWS):
            lines[i] += glyph[i] + "  "

    return "\n".join(lines)


class ThickProgressBar(Widget):
    """Custom multi-row block progress bar with contrasting track background."""

    DEFAULT_CSS = """
    ThickProgressBar {
        width: 100%;
        height: 2;
        margin-top: 1;
        margin-bottom: 1;
    }
    """

    progress: reactive[float] = reactive(0.0)

    def __init__(
        self,
        progress: float = 0.0,
        id: str | None = None,
        classes: str | None = None,
    ):
        super().__init__(id=id, classes=classes)
        self.progress = progress

    def render(self) -> Text:
        w = self.size.width if self.size.width > 0 else 40
        h = self.size.height if self.size.height > 0 else 2
        pct = max(0.0, min(1.0, self.progress))
        filled = int(round(pct * w))
        empty = w - filled

        try:
            vars = self.app.get_css_variables()
            accent = str(vars.get("accent", "#FEA62B"))
            track_bg = str(vars.get("panel-lighten-1", vars.get("panel", "#343F49")))
            track_fg = str(vars.get("panel-lighten-3", vars.get("text-muted", "#69747D")))
        except Exception:
            accent = "#FEA62B"
            track_bg = "#343F49"
            track_fg = "#69747D"

        t = Text()
        for row in range(h):
            if filled > 0:
                t.append("█" * filled, style=f"bold {accent} on {track_bg}")
            if empty > 0:
                t.append("░" * empty, style=f"{track_fg} on {track_bg}")
            if row < h - 1:
                t.append("\n")

        return t


class TimerCard(Vertical):
    """Timer widget displaying clock digits, progress bar, and text-based controls."""

    DEFAULT_CLASSES = "card-container timer-box"

    class PauseRequested(Message):
        """Dispatched when pause/resume button is pressed."""

    class ResetRequested(Message):
        """Dispatched when reset button is pressed."""

    class SkipRequested(Message):
        """Dispatched when skip button is pressed."""

    def __init__(
        self,
        activity: str = "coding",
        cycles_total: int = 4,
        id: str | None = "timer-card",
    ):
        super().__init__(id=id)
        self._activity = activity
        self._cycles_total = cycles_total

    def compose(self) -> ComposeResult:
        yield Label("timer", classes="card-tag")

        # Main digital clock display
        with Horizontal(classes="timer-display-row"):
            yield Static(
                render_digital_clock("25:00"),
                id="main-timer-digits",
                classes="timer-digital-display timer-active",
            )

        # Sub-info row with upcoming phase and cycle count
        with Horizontal(classes="timer-sub-row"):
            yield Label("next: 05:00 short break", id="timer-next-phase", classes="subtext-dim")
            yield Label(f"1/{self._cycles_total}", id="cycle-badge")

        # Thick progress bar spanning full width of card
        yield ThickProgressBar(id="timer-progress")

        # Controls and activity status
        with Horizontal(classes="timer-controls-row"):
            with Horizontal(classes="timer-buttons"):
                yield Button("play/pause", id="btn-pause", classes="timer-text-btn")
                yield Button("reset", id="btn-reset", classes="timer-text-btn")
                yield Button("skip", id="btn-skip", classes="timer-text-btn")

            with Vertical(classes="timer-activity-info"):
                yield Label(self._activity, id="timer-activity-name")
                yield Label("task assigned", classes="subtext-dim")

    def toggle_zen(self) -> None:
        """Toggle fullscreen zen display mode."""
        self.toggle_class("zen-mode")

    @on(Button.Pressed, "#btn-pause")
    def _on_pause_click(self) -> None:
        self.app.post_message(self.PauseRequested())

    @on(Button.Pressed, "#btn-reset")
    def _on_reset_click(self) -> None:
        self.app.post_message(self.ResetRequested())

    @on(Button.Pressed, "#btn-skip")
    def _on_skip_click(self) -> None:
        self.app.post_message(self.SkipRequested())

    def update_state(
        self,
        remaining_s: int,
        progress_pct: float,
        cycle: int,
        total_cycles: int,
        pomo_m: float | int,
        break_m: float | int,
        is_break: bool,
        is_running: bool,
        kind_label: str,
    ) -> None:
        """Update timer display, next phase info, and progress bar."""
        try:
            mins, secs = divmod(remaining_s, 60)
            time_str = f"{mins:02d}:{secs:02d}"

            # Update digital clock with active phase countdown
            clock_widget = self.query_one("#main-timer-digits", Static)
            clock_widget.update(render_digital_clock(time_str))

            # Update next phase description (support float / seconds durations)
            next_label = self.query_one("#timer-next-phase", Label)
            next_s = int(round((pomo_m if is_break else break_m) * 60))
            nm, ns = divmod(next_s, 60)
            suffix = "focus" if is_break else "break"
            next_label.update(f"next: {nm:02d}:{ns:02d} {suffix}")

            # Update cycle indicator
            cycle_badge = self.query_one("#cycle-badge", Label)
            cycle_badge.update(f"{cycle}/{total_cycles}")

            # Update thick progress bar
            progress_bar = self.query_one("#timer-progress", ThickProgressBar)
            progress_bar.progress = progress_pct

            # Update text pause/play button label
            pause_btn = self.query_one("#btn-pause", Button)
            pause_btn.label = "pause" if is_running else "play"

            # Update activity / phase label
            act_label = self.query_one("#timer-activity-name", Label)
            act_label.update(f"{self._activity} ({kind_label})")
        except Exception:
            pass
