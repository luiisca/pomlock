from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label


class FooterBar(Horizontal):
    """Custom status and keybinding footer bar presenting shortcuts."""

    DEFAULT_CLASSES = "footer-container"

    def __init__(
        self,
        bindings: list[tuple[str, str]] | None = None,
        id: str | None = "footer-bar",
    ) -> None:
        super().__init__(id=id)
        self._bindings = bindings if bindings is not None else [("z", "zen")]

    def compose(self) -> ComposeResult:
        for key, desc in self._bindings:
            yield Label(f"[b]{key}[/b] {desc}", classes="footer-item")
