from datetime import datetime
from typing import Iterable, List, Optional, TYPE_CHECKING, Union, Callable

from rich.text import Text, TextType

if TYPE_CHECKING:
    from .console import Console, ConsoleRenderable, RenderableType
    from .table import Table

FormatTimeCallable = Callable[[datetime], Text]


class LogRender:
    def __init__(
        self,
        show_time: bool = True,
        show_timer: bool = True,
        show_cycle: bool = True,
        show_level: bool = False,
        show_path: bool = True,
        time_format: Union[str, FormatTimeCallable] = "[%x %X]",
        omit_repeated_times: bool = True,
        level_width: Optional[int] = 8,
    ) -> None:
        self.show_time = show_time
        self.show_timer = show_timer
        self.show_level = show_level
        self.show_cycle = show_cycle
        self.show_path = show_path
        self.time_format = time_format
        self.omit_repeated_times = omit_repeated_times
        self.level_width = level_width
        self._last_time: Optional[Text] = None

    def __call__(
        self,
        console: "Console",
        renderables: Iterable["ConsoleRenderable"],
        log_time: Optional[datetime] = None,
        timer_m: Optional[str] = None,
        crr_cycle: Optional[int] = None,
        cycles_total: Optional[int] = None,
        time_format: Optional[Union[str, FormatTimeCallable]] = None,
        level: TextType = "",
        path: Optional[str] = None,
        line_no: Optional[int] = None,
        link_path: Optional[str] = None,
    ) -> "Table":
        from rich.containers import Renderables
        from rich.table import Table

        output = Table.grid(padding=(0, 1))
        output.expand = True
        if self.show_time:
            output.add_column(style="log.time")
        if self.show_level:
            output.add_column(style="log.level", width=self.level_width)
        output.add_column(ratio=1, style="log.message", overflow="fold")
        if self.show_path and path:
            output.add_column(style="log.path")
        if self.show_cycle:
            output.add_column(style="log.time", justify="full")
        if self.show_timer:
            output.add_column(style="log.time", justify="full")

        row: List["RenderableType"] = []
        if self.show_time:
            log_time = log_time or console.get_datetime()
            time_format = time_format or self.time_format
            if callable(time_format):
                log_time_display = time_format(log_time)
            else:
                log_time_display = Text(log_time.strftime(time_format))
            if log_time_display == self._last_time and self.omit_repeated_times:
                row.append(Text(" " * len(log_time_display)))
            else:
                row.append(log_time_display)
                self._last_time = log_time_display
        if self.show_level:
            row.append(level)

        row.append(Renderables(renderables))
        if self.show_path and path:
            path_text = Text()
            path_text.append(
                path, style=f"link file://{link_path}" if link_path else ""
            )
            if line_no:
                path_text.append(":")
                path_text.append(
                    f"{line_no}",
                    style=f"link file://{link_path}#{
                        line_no}" if link_path else "",
                )
            row.append(path_text)

        if self.show_cycle:
            row.append(
                Text(str(f"[{crr_cycle}/{cycles_total}]"),
                     style="bold") if crr_cycle and cycles_total else ""
            )
        if self.show_timer and timer_m:
            # TODO: could be more dynamic
            # instead of adding leading/trailing empty spaces
            # we could predetermine the entire string length based on the largest timer_m
            spaces = " " * (4 - len(str(timer_m)))
            row.append(
                Text(str(f"[{spaces}{timer_m} min  ]"), style="bold")
            )

        output.add_row(*row)
        return output


if __name__ == "__main__":  # pragma: no cover
    from rich.console import Console

    c = Console()
    c.print("[on blue]Hello", justify="right")
    c.log("[on blue]hello", justify="right")
