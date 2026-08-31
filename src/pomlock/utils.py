import re

MINUTES_PER_HOUR = 60
DURATION_PATTERN = re.compile(
    r"^(?:(\d+(?:\.\d+)?)\s*h(?:ours?|r)?)?\s*(?:(\d+(?:\.\d+)?)\s*m(?:in(?:ute)?s?)?)?$",
    re.IGNORECASE,
)


def plural(str: str, n: int) -> str:
    return f"{str}{'' if n == 1 else 's'}"


def parse_duration_string(val: str | int | float) -> int:
    """Parse a duration string (e.g. '3h20m', '4h', '40m', '90') into integer minutes."""
    if isinstance(val, (int, float)):
        return int(val)

    cleaned = str(val).strip()
    if not cleaned:
        return 0

    # Direct integer or float string
    try:
        return int(float(cleaned))
    except ValueError:
        pass

    # Parse components matching hours and minutes
    match = DURATION_PATTERN.match(cleaned)
    if not match:
        return 0

    hours_str, mins_str = match.groups()
    total_minutes = 0.0

    if hours_str:
        total_minutes += float(hours_str) * MINUTES_PER_HOUR

    if mins_str:
        total_minutes += float(mins_str)

    return int(round(total_minutes))


def deep_merge(dest, src):
    dest_copy = dest.copy()
    for k, v in src.items():
        if (
            k in dest_copy
            and isinstance(dest_copy[k], dict)
            and isinstance(v, dict)
        ):
            dest_copy[k] = deep_merge(dest_copy[k], v)
        else:
            dest_copy[k] = v
    return dest_copy

