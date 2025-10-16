import logging
from pathlib import Path

from .constants import APP_NAME
from .custom_rich_handler import CustomRichHandler

logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.DEBUG)


class ExtraDataFormatter(logging.Formatter):
    def format(self, record):
        log_parts = [
            super().format(record)
        ]

        extra_items = []
        if hasattr(record, 'activity'):
            extra_items.append(f"activity:{record.activity}")
        if hasattr(record, 'crr_cycle') and hasattr(record, 'cycles_total'):
            extra_items.append(
                f"cycle:{record.crr_cycle}/{record.cycles_total}")
        if hasattr(record, 'minutes'):
            extra_items.append(f"timer:{record.minutes}m")

        if extra_items:
            log_parts.append(" | ".join(extra_items))

        return " | ".join(log_parts)


def setup_logging(log_file_path_str: str, verbose: bool):
    log_file_path = Path(log_file_path_str)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    fh = logging.FileHandler(log_file_path)
    fh.setLevel(logging.DEBUG)

    rh = CustomRichHandler(
        rich_tracebacks=True,
        show_path=False,
        show_level=False,
        log_time_format='[%H:%M:%S]'
    )
    rh.setLevel(logging.DEBUG if verbose else logging.INFO)

    fh_formatter = ExtraDataFormatter(
        '%(asctime)s | %(levelname)s | %(message)s'
    )
    fh.setFormatter(fh_formatter)

    logger.addHandler(fh)
    logger.addHandler(rh)
