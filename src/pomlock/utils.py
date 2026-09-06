import re
import sys

from pomlock.constants import GoalPeriod, Pomodoro
from pomlock.logger import logger

MINUTES_PER_HOUR = 60
DURATION_PATTERN = re.compile(
    r"^(?:(\d+(?:\.\d+)?)\s*h(?:ours?|r)?)?\s*(?:(\d+(?:\.\d+)?)\s*m(?:in(?:ute)?s?)?)?$",
    re.IGNORECASE,
)


def plural(str: str, n: int) -> str:
    return f"{str}{'' if n == 1 else 's'}"


def to_bool(val: bool | str) -> bool:
    """Coerce config-file string booleans ('true'/'false') or real bools to bool."""
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def parse_duration_m(val: str | float) -> int | float:
    if isinstance(val, (int, float)):
        return abs(float(val))

    val_str = str(val).strip().lower()
    val_str = val_str.removeprefix("-")

    # Combined hours/minutes format: "9h20m", "3h 20m", "100h", "0h40m"
    match = DURATION_PATTERN.match(val_str)
    if match and (match.group(1) or match.group(2)):
        hours = float(match.group(1)) if match.group(1) else 0.0
        minutes = float(match.group(2)) if match.group(2) else 0.0
        return abs(hours * 60.0 + minutes)

    if val_str.endswith("s"):
        return abs(float(val_str[:-1]) / 60.0)

    if val_str.endswith("m"):
        return abs(float(val_str[:-1]))

    try:
        return abs(float(val_str))
    except ValueError:
        return 0.0


def parse_activities_goals_m(
    settings: dict[str, dict[str, str]],
) -> dict[str, dict[str, int | float]]:
    """Parse activities goals supporting [activities] and [activities.<name>] sections."""
    valid_periods = {p.value for p in GoalPeriod}
    activities_section = settings.get("activities", {})

    # Extract auto_calc setting
    auto_calc_raw = (
        activities_section.get("auto_calc", True)
        if isinstance(activities_section, dict)
        else True
    )
    auto_calc = to_bool(auto_calc_raw)

    base_goals: dict[str, int | float | str] = {}
    raw_activities: dict[str, dict[str, int | float | str]] = {}

    # 1. Parse individual [activities.<name>] sections
    for sect_name, sect_data in list(settings.items()):
        if not sect_name.startswith("activities."):
            continue

        act_name = sect_name[len("activities.") :].strip().lower()
        if not act_name:
            continue

        goals: dict[str, int | float | str] = {}
        if isinstance(sect_data, dict):
            for k, v in sect_data.items():
                k_lower = k.strip().lower()
                if k_lower in valid_periods:
                    goals[k_lower] = parse_duration_m(v)
                elif k_lower == "color":
                    goals["color"] = str(v).strip()

        raw_activities[act_name] = goals

    # 2. Parse goals under [activities] section
    if isinstance(activities_section, dict):
        for k, v in activities_section.items():
            k_lower = k.strip().lower()
            if k_lower == "auto_calc":
                continue

            if k_lower in valid_periods:
                base_goals[k_lower] = parse_duration_m(v)
                continue

            if isinstance(v, dict):
                raw_activities[k_lower] = v
                continue

    # 3. Calculate 'all' goals based on auto_calc
    summed_goals: dict[str, float] = {}
    for p in valid_periods:
        total_p = 0.0
        for act_name, act_goals in raw_activities.items():
            if act_name in ("all", "total") or not isinstance(act_goals, dict):
                continue
            val = act_goals.get(p, 0)
            if isinstance(val, (int, float)):
                total_p += val
        summed_goals[p] = total_p

    all_goals: dict[str, int | float] = {}
    if auto_calc:
        for p in valid_periods:
            all_goals[p] = summed_goals[p]
    else:
        for p in valid_periods:
            if p in base_goals and base_goals[p] > 0:
                all_goals[p] = base_goals[p]
            else:
                all_goals[p] = summed_goals[p]

    raw_activities["all"] = all_goals

    # Clean up sections starting with "activities." from settings dict
    for sect_name in list(settings.keys()):
        if sect_name.startswith("activities."):
            del settings[sect_name]

    raw_activities["auto_calc"] = auto_calc
    return raw_activities


def format_hm(minutes: float, pad_zero_hour: bool = False) -> str:
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


def parse_timer_m(settings: dict[str, dict[str, str]]):
    new_pomodoro_settings: dict[str, int | float] = {}
    timer_val = str(settings.get("general", {}).get("timer", "standard")).lower()
    preset_val = settings.get("presets", {}).get(timer_val)
    if not preset_val and " " in timer_val and len(timer_val.split()) == 4:
        preset_val = timer_val

    if preset_val:
        logger.debug(f"Applying timer setting: '{preset_val}'")
        try:
            parts = preset_val.split()
            if len(parts) == 4:
                keys = [p.value for p in Pomodoro]
                for key, part in zip(keys[:3], parts[:3]):
                    new_pomodoro_settings[key] = parse_duration_m(part)
                new_pomodoro_settings["cycles"] = int(parts[3])
            else:
                logger.error(f"Invalid timer format '{preset_val}'. Expected 4 values.")
        except ValueError:
            logger.error(f"Invalid values in timer string '{preset_val}'.")
    return new_pomodoro_settings
