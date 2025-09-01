import logging
from datetime import datetime
from rich.logging import RichHandler
from pathlib import Path

from .log_render import LogRender


class CustomRichHandler(RichHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log_render = LogRender(
            show_time=kwargs.get('show_time', True),
            show_timer=kwargs.get('show_timer', True),
            show_cycle=kwargs.get('show_cycle', True),
            show_level=kwargs.get('show_level', True),
            show_path=kwargs.get('show_path', True),
            time_format=kwargs.get('log_time_format', "[%x %X]"),
            omit_repeated_times=kwargs.get('omit_repeated_times', True),
            level_width=None,
        )

    def render(self, *, record, traceback, message_renderable):
        path = Path(record.pathname).name
        level = self.get_level_text(record)
        time_format = None if self.formatter is None else self.formatter.datefmt
        log_time = datetime.fromtimestamp(record.created)

        log_renderable = self.log_render(
            self.console,
            [message_renderable] if not traceback else [
                message_renderable, traceback],
            log_time=log_time,
            timer_m=getattr(record, 'minutes', ""),
            crr_cycle=getattr(record, 'crr_cycle', None),
            cycles_total=getattr(record, 'cycles_total', None),
            time_format=time_format,
            level=level,
            path=path,
            line_no=record.lineno,
            link_path=record.pathname if self.enable_link_path else None,
        )
        return log_renderable

    def get_level_style(self, levelno):
        """Returns the style for a given level number."""
        return self.LEVEL_STYLES.get(levelno, self.LEVEL_STYLES[logging.INFO])
