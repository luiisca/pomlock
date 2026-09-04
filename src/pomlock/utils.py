import re

from pomlock import logger
from pomlock.constants import GoalPeriod

MINUTES_PER_HOUR = 60
DURATION_PATTERN = re.compile(
    r"^(?:(\d+(?:\.\d+)?)\s*h(?:ours?|r)?)?\s*(?:(\d+(?:\.\d+)?)\s*m(?:in(?:ute)?s?)?)?$",
    re.IGNORECASE,
)


def plural(str: str, n: int) -> str:
    return f"{str}{'' if n == 1 else 's'}"


def parse_duration_m(val: str | float) -> int | float:
    if isinstance(val, (int, float)):
        return abs(float(val))

    val_str = str(val).strip().lower()
    val_str = val_str.removeprefix("-")

    # Combined hours/minutes format: "9h20m", "100h", "9h0m", "0h40m"
    match = re.fullmatch(r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m)?", val_str)
    if match and (match.group(1) or match.group(2)):
        hours = float(match.group(1)) if match.group(1) else 0.0
        minutes = float(match.group(2)) if match.group(2) else 0.0
        return abs(hours * 60.0 + minutes)

    if val_str.endswith("s"):
        return abs(float(val_str[:-1]) / 60.0)
    if val_str.endswith("m"):
        return abs(float(val_str[:-1]))
    return abs(float(val_str))


def parse_activities_goals_m(
    settings: dict[str, dict[str, str]],
) -> dict[str, dict[str, int | float]]:
    valid_periods = {p.value for p in GoalPeriod}
    new_activities_goals_settings: dict[str, dict[str, int | float]] = {}

    for activity, v in settings["activities"].items():
        goals: dict[str, int | float] = {}
        for part in v.split():
            if "=" not in part:
                logger.error(
                    f"Invalid goal entry '{part}' for '{
                        activity
                    }'. Expected 'period=value'."
                )
                continue
            period, _, value = part.partition("=")
            period = period.strip().lower()
            if period not in valid_periods:
                logger.error(
                    f"Unknown goal period '{period}' for '{activity}'. "
                    f"Expected one of {sorted(valid_periods)}."
                )
                continue
            goals[period] = parse_duration_m(value.strip())

        if goals:
            new_activities_goals_settings[activity] = goals

    return new_activities_goals_settings


def format_hm(minutes: int | float, pad_zero_hour: bool = False) -> str:
    """Format minutes to 'Xh Ym' or 'Xh' representation."""
    minutes = round(max(0, minutes))
    h, m = divmod(minutes, 60)
    if pad_zero_hour:
        return f"{h}h {m:02d}m"
    if h > 0 and m > 0:
        return f"{h}h {m:02d}m"
    elif h > 0:
        return f"{h}h"
    return f"{m}m"


def deep_merge(dest, src):
    dest_copy = dest.copy()
    for k, v in src.items():
        if k in dest_copy and isinstance(dest_copy[k], dict) and isinstance(v, dict):
            dest_copy[k] = deep_merge(dest_copy[k], v)
        else:
            dest_copy[k] = v
    return dest_copy
