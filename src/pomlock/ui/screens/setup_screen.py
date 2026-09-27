from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static

from pomlock.logger import logger
from pomlock.settings import Settings
from pomlock.utils import format_hm, parse_duration_m


class StartSessionRequested(Message):
    """Event emitted when user confirms session setup."""

    def __init__(self, preset: str, activity: str) -> None:
        self.preset = preset
        self.activity = activity
        super().__init__()


class CancelSetupRequested(Message):
    """Event emitted when user cancels session setup."""


class SetupScreen(Screen):
    """Textual screen for pre-session configuration."""

    DEFAULT_CLASSES = "setup-screen"

    BINDINGS = [
        Binding("enter", "confirm_setup", "Start Session"),
        Binding("escape", "cancel_setup", "Cancel"),
        Binding("q", "cancel_setup", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._settings = Settings()
        self._selected_preset = str(
            self._settings.get("general", {}).get("timer", "standard")
        )
        self._selected_activity = str(
            self._settings.get("activity", "other")
        )

    def compose(self) -> ComposeResult:
        with Vertical(classes="setup-container"):
            # Header banner
            with Vertical(classes="setup-header-banner"):
                yield Label("⚡ POMODORO SESSION SETUP", classes="setup-title")
                yield Label(
                    "Configure your flow parameters before locking in.",
                    classes="setup-subtitle",
                )

            # Main setup cards grid
            with Horizontal(classes="setup-grid"):
                # Left card: Preset selection
                with Vertical(classes="setup-card preset-card"):
                    yield Label("1. TIMER PRESET", classes="setup-card-title")
                    yield Label(
                        "Equivalent to -t / --timer",
                        classes="setup-card-subtitle",
                    )
                    yield Select(
                        self._build_preset_options(),
                        value=self._selected_preset,
                        allow_blank=False,
                        id="setup-preset-select",
                        classes="setup-select",
                    )
                    yield Label("Session Timeline Preview:", classes="setup-section-label")
                    yield Static(
                        self._render_timeline(self._selected_preset),
                        id="setup-timeline-preview",
                        classes="setup-timeline-box",
                    )

                # Right card: Activity selection
                with Vertical(classes="setup-card activity-card"):
                    yield Label("2. ACTIVITY", classes="setup-card-title")
                    yield Label(
                        "Equivalent to -a / --activity",
                        classes="setup-card-subtitle",
                    )
                    yield Select(
                        self._build_activity_options(),
                        value=self._selected_activity,
                        allow_blank=False,
                        id="setup-activity-select",
                        classes="setup-select",
                    )
                    yield Label("Current Session Target:", classes="setup-section-label")
                    yield Static(
                        f"Target: [b]{self._selected_activity.upper()}[/b]",
                        id="setup-activity-preview",
                        classes="setup-activity-box",
                    )

            # Disabled optional task card
            with Vertical(classes="setup-card task-card-disabled"):
                with Horizontal(classes="task-card-header-row"):
                    yield Label("3. TASK (OPTIONAL)", classes="setup-card-title")
                    yield Label("[ COMING SOON ]", classes="task-badge-disabled")
                yield Label(
                    "Task filtering and Obsidian vault notes linking arriving in future update.",
                    classes="setup-card-subtitle task-dim-text",
                )
                yield Input(
                    placeholder="Task integration currently disabled...",
                    disabled=True,
                    id="setup-task-input",
                    classes="setup-task-input-disabled",
                )

            # Summary and launch bar
            with Horizontal(classes="setup-launch-bar"):
                yield Static(
                    self._render_summary(),
                    id="setup-summary-text",
                    classes="setup-summary-label",
                )
                with Horizontal(classes="setup-action-buttons"):
                    yield Button(
                        "Cancel (Esc)",
                        variant="default",
                        id="btn-cancel-setup",
                        classes="setup-btn-cancel",
                    )
                    yield Button(
                        "Start Focus Session (Enter)",
                        variant="primary",
                        id="btn-start-setup",
                        classes="setup-btn-start",
                    )

            yield Footer()

    def on_mount(self) -> None:
        """Set initial focus to preset selector."""
        try:
            self.query_one("#setup-preset-select", Select).focus()
        except Exception:
            pass

    def _build_preset_options(self) -> list[tuple[str, str]]:
        """Construct preset choices from Settings."""
        presets = self._settings.get("presets", {})
        options: list[tuple[str, str]] = []

        for name in sorted(presets.keys()):
            val = presets[name]
            label = f"{name.replace('_', ' ').title()} ({val})"
            options.append((label, name))

        if not options:
            options.append(("Standard (25 5 20 4)", "standard"))

        existing_vals = {val for _, val in options}
        if self._selected_preset not in existing_vals:
            options.append(
                (self._selected_preset.replace("_", " ").title(), self._selected_preset)
            )

        return options

    def _build_activity_options(self) -> list[tuple[str, str]]:
        """Construct activity choices from Settings."""
        activities = self._settings.get("activities", {})
        options: list[tuple[str, str]] = []

        for name in sorted(activities.keys()):
            if name in ("all", "total", "auto_calc"):
                continue
            if isinstance(activities[name], dict):
                label = name.replace("_", " ").title()
                options.append((label, name))

        if not options:
            options.append(("Other", "other"))

        existing_vals = {val for _, val in options}
        if self._selected_activity not in existing_vals:
            options.append(
                (self._selected_activity.replace("_", " ").title(), self._selected_activity)
            )

        return options

    def _render_timeline(self, preset_name: str) -> str:
        """Render ASCII timeline representation of preset."""
        presets = self._settings.get("presets", {})
        preset_val = presets.get(preset_name, "25 5 20 4")
        parts = preset_val.split()

        if len(parts) != 4:
            return f"Preset: {preset_val}"

        try:
            pomo = int(parts[0])
            s_break = int(parts[1])
            l_break = int(parts[2])
            cycles = int(parts[3])
        except ValueError:
            return f"Preset: {preset_val}"

        total_focus_m = pomo * cycles
        blocks: list[str] = []

        for i in range(cycles):
            blocks.append(f"[b]{pomo}m[/b]")
            if i < cycles - 1:
                blocks.append(f"─{s_break}m─")

        if cycles > 0:
            blocks.append(f"═[italic]{l_break}m break[/italic]═")

        timeline = " ".join(blocks)
        total_str = format_hm(total_focus_m)
        return f"{timeline}\n[dim]Total Focus Time: {total_str}[/dim]"

    def _render_summary(self) -> str:
        """Build summary line for launch footer."""
        return (
            f"[bold]Session Plan:[/bold] "
            f"Preset: [accent]{self._selected_preset}[/accent]  |  "
            f"Activity: [primary]{self._selected_activity.upper()}[/primary]"
        )

    @on(Select.Changed, "#setup-preset-select")
    def _on_preset_changed(self, event: Select.Changed) -> None:
        """Update selected preset and refresh timeline preview."""
        if event.value != Select.NULL:
            self._selected_preset = str(event.value)
            self._refresh_views()

    @on(Select.Changed, "#setup-activity-select")
    def _on_activity_changed(self, event: Select.Changed) -> None:
        """Update selected activity and refresh target preview."""
        if event.value != Select.NULL:
            self._selected_activity = str(event.value)
            self._refresh_views()

    def _refresh_views(self) -> None:
        """Refresh timeline and summary display."""
        try:
            timeline_box = self.query_one("#setup-timeline-preview", Static)
            timeline_box.update(self._render_timeline(self._selected_preset))

            act_box = self.query_one("#setup-activity-preview", Static)
            act_box.update(f"Target: [b]{self._selected_activity.upper()}[/b]")

            summary_box = self.query_one("#setup-summary-text", Static)
            summary_box.update(self._render_summary())
        except Exception as e:
            logger.debug(f"Error updating setup previews: {e}")

    @on(Button.Pressed, "#btn-start-setup")
    def _on_start_pressed(self) -> None:
        """Confirm setup from button click."""
        self.action_confirm_setup()

    @on(Button.Pressed, "#btn-cancel-setup")
    def _on_cancel_pressed(self) -> None:
        """Cancel setup from button click."""
        self.action_cancel_setup()

    def action_confirm_setup(self) -> None:
        """Post session start event to application."""
        self.post_message(
            StartSessionRequested(
                preset=self._selected_preset,
                activity=self._selected_activity,
            )
        )

    def action_cancel_setup(self) -> None:
        """Post cancel event to application."""
        self.post_message(CancelSetupRequested())
