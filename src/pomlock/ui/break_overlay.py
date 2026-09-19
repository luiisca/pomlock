import argparse
import json
import os
import re
import select
import subprocess
import sys
import time
import tkinter as tk
from typing import Optional

from ..constants import DEFAULT_OVERLAY_ACCENT
from ..logger import logger

POLL_INTERVAL_MS = 50
SUBTITLE_TEXT = "Step away from the screen. Input is locked."
FONT_FAMILY_FALLBACK = "DejaVu Sans Mono"
CMD_STOP = "STOP"
TCL_INIT_FILE = "init.tcl"
TK_INIT_FILE = "tk.tcl"
ENV_TCL_LIBRARY = "TCL_LIBRARY"
ENV_TK_LIBRARY = "TK_LIBRARY"
TCL_SEARCH_PATHS = (
    "/usr/share/tcltk",
    "/usr/share",
    "/usr/lib",
    "/usr/lib64",
    "/usr/lib/tcltk",
    "/usr/local/share",
    "/usr/local/lib",
)


def _get_settings_safely():
    """Safely import Settings instance, handling potential circular imports."""
    try:
        from .settings import Settings

        return Settings()
    except ImportError as e:
        # Handle circular import during module loading.
        # This was previously silent, which made it indistinguishable from
        # "Settings loaded fine but the user just didn't configure overlay
        # colors" - log it so a misconfigured overlay is diagnosable instead
        # of quietly falling back to defaults.
        logger.warning(
            f"Could not import real Settings (circular import?); overlay is "
            f"using hardcoded defaults and ignoring user configuration: {e}"
        )
        # Return a dict-like object with default values

        class FallbackSettings(dict):
            def get(self, key, default=None):
                # Handle nested key access like ("overlay", "enabled")
                if isinstance(key, tuple) and len(key) == 2:
                    return dict.get(dict.get(self, key[0], {}), key[1], default)
                return dict.get(self, key, default)

            def __getitem__(self, key):
                # Handle nested key access like ("overlay", "enabled")
                if isinstance(key, tuple) and len(key) == 2:
                    return dict.get(dict.get(self, key[0], {}), key[1])
                return dict.get(self, key)

        # Provide sensible defaults
        fallback = FallbackSettings()
        fallback["overlay"] = {
            "enabled": True,
            "font_size": 48,
            "color": "white",
            "bg_color": "black",
            "opacity": 0.8,
            # Pixel height of the timer digits. None means "derive from
            # font_size" (see compute_overlay_metrics below).
            "timer_font_size": None,
            "subtitle_font_size": None,
        }
        return fallback


def find_tcl_dir(filename: str) -> Optional[str]:
    """Find directory containing target Tcl/Tk configuration file."""
    env_var = ENV_TCL_LIBRARY if filename == TCL_INIT_FILE else ENV_TK_LIBRARY
    existing_path = os.environ.get(env_var)
    if existing_path and os.path.exists(os.path.join(existing_path, filename)):
        return existing_path

    prefixes = [sys.base_prefix, sys.prefix]
    for p in prefixes:
        lib_dir = os.path.join(p, "lib")
        if not os.path.exists(lib_dir):
            continue

        for entry in os.listdir(lib_dir):
            target = os.path.join(lib_dir, entry)
            if os.path.isdir(target) and os.path.exists(os.path.join(target, filename)):
                return target

    for base_dir in TCL_SEARCH_PATHS:
        if not os.path.exists(base_dir):
            continue

        try:
            for entry in os.listdir(base_dir):
                target = os.path.join(base_dir, entry)
                if not os.path.isdir(target):
                    continue

                if os.path.exists(os.path.join(target, filename)):
                    return target

                for sub in os.listdir(target):
                    sub_target = os.path.join(target, sub)
                    if os.path.isdir(sub_target) and os.path.exists(
                        os.path.join(sub_target, filename)
                    ):
                        return sub_target
        except OSError:
            continue

    return None


def setup_tcl_env() -> None:
    """Ensure TCL_LIBRARY and TK_LIBRARY env vars point to valid locations."""
    tcl_dir = find_tcl_dir(TCL_INIT_FILE)
    if tcl_dir:
        os.environ[ENV_TCL_LIBRARY] = tcl_dir

    tk_dir = find_tcl_dir(TK_INIT_FILE)
    if tk_dir:
        os.environ[ENV_TK_LIBRARY] = tk_dir


def detect_monitors() -> list[tuple[int, int, int, int]]:
    """Detect geometry for all active monitors (w, h, x, y)."""
    monitors: list[tuple[int, int, int, int]] = []
    try:
        res = subprocess.run(
            ["xrandr", "--current"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in res.stdout.splitlines():
            if " connected" not in line:
                continue

            match = re.search(r"(\d+)x(\d+)\+(\d+)\+(\d+)", line)
            if match:
                w, h, x, y = map(int, match.groups())
                monitors.append((w, h, x, y))
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        logger.debug(f"xrandr query failed: {e}")

    return monitors


DIGIT_SEGMENTS = {
    "0": (1, 1, 1, 1, 1, 1, 0),
    "1": (0, 1, 1, 0, 0, 0, 0),
    "2": (1, 1, 0, 1, 1, 0, 1),
    "3": (1, 1, 1, 1, 0, 0, 1),
    "4": (0, 1, 1, 0, 0, 1, 1),
    "5": (1, 0, 1, 1, 0, 1, 1),
    "6": (1, 0, 1, 1, 1, 1, 1),
    "7": (1, 1, 1, 0, 0, 0, 0),
    "8": (1, 1, 1, 1, 1, 1, 1),
    "9": (1, 1, 1, 1, 0, 1, 1),
}


DEFAULT_DIGIT_W = 90
DEFAULT_DIGIT_H = 160
DEFAULT_THICKNESS = 18
DEFAULT_GAP = 8
DEFAULT_SPACING = 16
INACTIVE_SEGMENT_COLOR = "#181D24"
SUBTITLE_TEXT_COLOR = "#888888"

# Digit-clock proportions, all derived from a single "digit height" so that
# width, stroke thickness, segment gaps, and the colon dots all scale
# together instead of drifting out of proportion with each other.
DIGIT_W_TO_H_RATIO = 0.5625  # matches the original 90x160 digit design
THICKNESS_DIVISOR = 9
GAP_DIVISOR = 20
SPACING_DIVISOR = 10
# How far each colon dot sits above/below center, as a fraction of digit
# height. Previously this was a constant 0, which put both dots on top of
# each other so the colon rendered as a single dot.
COLON_DOT_OFFSET_RATIO = 0.17

# The timer digits are the focal point of the overlay, so by default they're
# rendered noticeably larger than the title text rather than being derived
# from it. Users can pin an exact pixel size via Settings
# ("overlay", "timer_font_size").
TIMER_FONT_SCALE = 2.8
MIN_TIMER_DIGIT_H = 140


def compute_overlay_metrics(
    overlay_font_size: int,
    timer_digit_h: Optional[int] = None,
    subtitle_font_size: Optional[int] = None,
) -> dict:
    """Derive every overlay size/offset from a couple of Settings-driven inputs.

    Centralizing this calculation is what keeps the Hyprland and X11 render
    paths in sync. Previously each path scaled digit size and text offsets
    independently, which both made the timer render much smaller than
    intended and made it possible for the title/subtitle to overlap the
    digits depending on configured font size. Here, offsets are always
    derived from the *actual* rendered digit height and text sizes, so
    overlap can't happen regardless of what's configured.
    """
    title_font_size = overlay_font_size
    effective_subtitle_font_size = (
        subtitle_font_size
        if subtitle_font_size is not None
        else max(12, overlay_font_size // 3)
    )

    digit_h = (
        timer_digit_h
        if timer_digit_h is not None
        else max(MIN_TIMER_DIGIT_H, int(overlay_font_size * TIMER_FONT_SCALE))
    )
    digit_w = int(digit_h * DIGIT_W_TO_H_RATIO)
    thickness = max(3, digit_h // THICKNESS_DIVISOR)
    gap = max(1, digit_h // GAP_DIVISOR)
    spacing = max(4, digit_h // SPACING_DIVISOR)

    title_offset_y = digit_h // 2 + title_font_size + 20
    subtitle_offset_y = digit_h // 2 + effective_subtitle_font_size + 20

    return {
        "title_font_size": title_font_size,
        "subtitle_font_size": effective_subtitle_font_size,
        "digit_w": digit_w,
        "digit_h": digit_h,
        "thickness": thickness,
        "gap": gap,
        "spacing": spacing,
        "title_offset_y": title_offset_y,
        "subtitle_offset_y": subtitle_offset_y,
    }


def draw_vector_clock(
    canvas: tk.Canvas,
    text: str,
    cx: float,
    cy: float,
    tag: str = "clock_digits",
    digit_w: int = DEFAULT_DIGIT_W,
    digit_h: int = DEFAULT_DIGIT_H,
    thickness: int = DEFAULT_THICKNESS,
    gap: int = DEFAULT_GAP,
    spacing: int = DEFAULT_SPACING,
    color: str = DEFAULT_OVERLAY_ACCENT,
    inactive_color: str = INACTIVE_SEGMENT_COLOR,
) -> None:
    """Render smooth vector 7-segment digital alarm clock digits on a Canvas."""
    canvas.delete(tag)

    colon_w = thickness
    widths = [colon_w if ch == ":" else digit_w for ch in text]
    total_w = sum(widths) + spacing * (len(text) - 1)
    x = cx - total_w / 2.0

    for char in text:
        w_i = colon_w if char == ":" else digit_w

        # Draw colon separator (two dots, vertically separated so it reads
        # as a colon rather than collapsing into a single dot).
        if char == ":":
            dot_sz = thickness
            dot_x = x
            colon_offset = digit_h * COLON_DOT_OFFSET_RATIO
            canvas.create_oval(
                dot_x,
                cy - colon_offset - dot_sz / 2,
                dot_x + dot_sz,
                cy - colon_offset + dot_sz / 2,
                fill=color,
                outline="",
                tags=tag,
            )
            canvas.create_oval(
                dot_x,
                cy + colon_offset - dot_sz / 2,
                dot_x + dot_sz,
                cy + colon_offset + dot_sz / 2,
                fill=color,
                outline="",
                tags=tag,
            )
            x += w_i + spacing
            continue

        segs = DIGIT_SEGMENTS.get(char, (0, 0, 0, 0, 0, 0, 0))
        t = thickness
        g = gap
        half_h = digit_h / 2

        # A: top segment
        c0 = color if segs[0] else inactive_color
        canvas.create_polygon(
            x + g,
            cy - half_h,
            x + digit_w - g,
            cy - half_h,
            x + digit_w - g - t / 2,
            cy - half_h + t,
            x + g + t / 2,
            cy - half_h + t,
            fill=c0,
            outline="",
            tags=tag,
        )

        # B: top right segment
        c1 = color if segs[1] else inactive_color
        canvas.create_polygon(
            x + digit_w,
            cy - half_h + g,
            x + digit_w,
            cy - g / 2,
            x + digit_w - t,
            cy - g / 2 - t / 2,
            x + digit_w - t,
            cy - half_h + g + t / 2,
            fill=c1,
            outline="",
            tags=tag,
        )

        # C: bottom right segment
        c2 = color if segs[2] else inactive_color
        canvas.create_polygon(
            x + digit_w,
            cy + g / 2,
            x + digit_w,
            cy + half_h - g,
            x + digit_w - t,
            cy + half_h - g - t / 2,
            x + digit_w - t,
            cy + g / 2 + t / 2,
            fill=c2,
            outline="",
            tags=tag,
        )

        # D: bottom segment
        c3 = color if segs[3] else inactive_color
        canvas.create_polygon(
            x + g + t / 2,
            cy + half_h - t,
            x + digit_w - g - t / 2,
            cy + half_h - t,
            x + digit_w - g,
            cy + half_h,
            x + g,
            cy + half_h,
            fill=c3,
            outline="",
            tags=tag,
        )

        # E: bottom left segment
        c4 = color if segs[4] else inactive_color
        canvas.create_polygon(
            x,
            cy + g / 2,
            x + t,
            cy + g / 2 + t / 2,
            x + t,
            cy + half_h - g - t / 2,
            x,
            cy + half_h - g,
            fill=c4,
            outline="",
            tags=tag,
        )

        # F: top left segment
        c5 = color if segs[5] else inactive_color
        canvas.create_polygon(
            x,
            cy - half_h + g,
            x + t,
            cy - half_h + g + t / 2,
            x + t,
            cy - g / 2 - t / 2,
            x,
            cy - g / 2,
            fill=c5,
            outline="",
            tags=tag,
        )

        # G: middle segment
        c6 = color if segs[6] else inactive_color
        canvas.create_polygon(
            x + g,
            cy,
            x + g + t / 2,
            cy - t / 2,
            x + digit_w - g - t / 2,
            cy - t / 2,
            x + digit_w - g,
            cy,
            x + digit_w - g - t / 2,
            cy + t / 2,
            x + g + t / 2,
            cy + t / 2,
            fill=c6,
            outline="",
            tags=tag,
        )

        x += w_i + spacing


def draw_overlay_frame(
    canvas: tk.Canvas,
    title: str,
    time_str: str,
    accent: str,
    cx: float | None = None,
    cy: float | None = None,
    title_font_size: int = 26,
    subtitle_font_size: int = 16,
    title_color: str | None = None,
    subtitle_color: str | None = None,
    digit_w: int = DEFAULT_DIGIT_W,
    digit_h: int = DEFAULT_DIGIT_H,
    thickness: int = DEFAULT_THICKNESS,
    gap: int = DEFAULT_GAP,
    spacing: int = DEFAULT_SPACING,
    title_offset_y: int | None = None,
    subtitle_offset_y: int | None = None,
    clear_all: bool = True,
    digit_tag: str = "clock_digits",
) -> None:
    """Draw title, clock digits, and subtitle, laid out so they never overlap.

    This is the single drawing path used for both Hyprland (one canvas per
    monitor) and X11 (one shared canvas, multiple centers). For the X11
    case, pass clear_all=False with a unique digit_tag per monitor so
    repeated calls on the same canvas don't erase each other's output.
    """
    text_tag = f"{digit_tag}_text"
    if clear_all:
        canvas.delete("all")
    else:
        canvas.delete(digit_tag)
        canvas.delete(text_tag)

    w = canvas.winfo_width()
    h = canvas.winfo_height()

    if cx is None:
        cx = (w / 2.0) if w > 1 else 960.0
    if cy is None:
        cy = (h / 2.0) if h > 1 else 540.0

    effective_title_color = title_color if title_color is not None else accent
    effective_subtitle_color = (
        subtitle_color if subtitle_color is not None else SUBTITLE_TEXT_COLOR
    )

    # Fall back to offsets derived from the supplied sizes if the caller
    # didn't compute them explicitly (e.g. compute_overlay_metrics), so this
    # function still lays out sensibly on its own.
    effective_title_offset_y = (
        title_offset_y
        if title_offset_y is not None
        else digit_h // 2 + title_font_size + 20
    )
    effective_subtitle_offset_y = (
        subtitle_offset_y
        if subtitle_offset_y is not None
        else digit_h // 2 + subtitle_font_size + 20
    )

    canvas.create_text(
        cx,
        cy - effective_title_offset_y,
        text=f"{title.upper()}",
        font=("DejaVu Sans", title_font_size, "bold"),
        fill=effective_title_color,
        tags=text_tag,
    )
    draw_vector_clock(
        canvas,
        time_str,
        cx,
        cy,
        tag=digit_tag,
        color=accent,
        digit_w=digit_w,
        digit_h=digit_h,
        thickness=thickness,
        gap=gap,
        spacing=spacing,
    )
    canvas.create_text(
        cx,
        cy + effective_subtitle_offset_y,
        text=SUBTITLE_TEXT,
        font=("DejaVu Sans", subtitle_font_size),
        fill=effective_subtitle_color,
        tags=text_tag,
    )


def run_standalone_overlay(
    break_title: str,
    initial_remaining_s: int,
    accent_color: str,
) -> None:
    """Run fullscreen overlay covering all monitors."""
    # Get settings safely to handle potential circular imports
    settings = _get_settings_safely()

    setup_tcl_env()
    is_hyprland = bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))

    # Get overlay settings from Settings singleton
    overlay_enabled = settings.get("overlay", {}).get("enabled", True)
    if not overlay_enabled:
        return  # Overlay is disabled, exit early

    overlay_font_size = settings.get("overlay", {}).get("font_size", 48)
    overlay_color = settings.get("overlay", {}).get("color", "white")
    overlay_bg_color = settings.get("overlay", {}).get("bg_color", "black")
    overlay_opacity = settings.get("overlay", {}).get("opacity", 0.8)
    # Optional explicit overrides. None means "derive automatically" (see
    # compute_overlay_metrics).
    overlay_timer_font_size = settings.get("overlay", {}).get("timer_font_size", None)
    overlay_subtitle_font_size = settings.get("overlay", {}).get(
        "subtitle_font_size", None
    )

    metrics = compute_overlay_metrics(
        overlay_font_size,
        timer_digit_h=overlay_timer_font_size,
        subtitle_font_size=overlay_subtitle_font_size,
    )

    # Store start time for local timer calculation
    start_time = time.time()

    canvases: list[tk.Canvas] = []
    x11_centers: list[tuple[float, float]] = []

    if is_hyprland:
        try:
            res = subprocess.run(
                ["hyprctl", "-j", "monitors"],
                capture_output=True,
                text=True,
                check=True,
            )
            hypr_monitors = json.loads(res.stdout)
        except Exception:
            hypr_monitors = []

        if not hypr_monitors:
            hypr_monitors = [{"name": "0"}]

        root = tk.Tk(className="pomlock-overlay-0")
        root.configure(takefocus=False)
        root.title("pomlock-overlay-0")
        root.overrideredirect(True)
        root.configure(bg=overlay_bg_color)
        root.config(cursor="none")
        root.attributes("-alpha", overlay_opacity)  # Set window opacity
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", lambda: None)

        windows: list[tk.Tk | tk.Toplevel] = [root]
        for i in range(1, len(hypr_monitors)):
            top = tk.Toplevel(root, class_=f"pomlock-overlay-{i}")
            top.title(f"pomlock-overlay-{i}")
            top.overrideredirect(True)
            top.configure(bg=overlay_bg_color)
            top.config(cursor="none")
            top.attributes("-alpha", overlay_opacity)  # Set window opacity
            top.attributes("-topmost", True)
            top.protocol("WM_DELETE_WINDOW", lambda: None)
            windows.append(top)

        for win in windows:
            canvas = tk.Canvas(win, bg=overlay_bg_color, highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            canvases.append(canvas)

        root.update()

        # Set geometry for each window directly using monitor data
        for i, (win, m) in enumerate(zip(windows, hypr_monitors)):
            # Hyprland monitor dict contains: x, y, width, height
            x = m.get("x", 0)
            y = m.get("y", 0)
            w = m.get("width", 0)
            h = m.get("height", 0)
            if w > 0 and h > 0:
                win.geometry(f"{w}x{h}+{x}+{y}")

        root.update()  # Ensure geometry is applied

        # Use hyprctl to properly set window position and fullscreen state
        for i, (win, m) in enumerate(zip(windows, hypr_monitors)):
            subprocess.run(
                ["hyprctl", "dispatch", "focuswindow", f"title:{win.title()}"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if m.get("name"):
                subprocess.run(
                    ["hyprctl", "dispatch", "movewindow", f"mon:{m.get('name')}"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            subprocess.run(
                ["hyprctl", "dispatch", "fullscreen", "0"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        root.update()

        def _on_hypr_resize(event: tk.Event | None, c: tk.Canvas) -> None:
            # Calculate current remaining time based on elapsed time
            elapsed = time.time() - start_time
            current_remaining = max(0, initial_remaining_s - elapsed)
            mins, secs = divmod(int(current_remaining), 60)
            time_str = f"{mins:02d}:{secs:02d}"
            draw_overlay_frame(
                c,
                break_title,
                time_str,
                accent_color,
                title_font_size=metrics["title_font_size"],
                subtitle_font_size=metrics["subtitle_font_size"],
                title_color=overlay_color,
                subtitle_color=overlay_color,
                digit_w=metrics["digit_w"],
                digit_h=metrics["digit_h"],
                thickness=metrics["thickness"],
                gap=metrics["gap"],
                spacing=metrics["spacing"],
                title_offset_y=metrics["title_offset_y"],
                subtitle_offset_y=metrics["subtitle_offset_y"],
            )

        for c in canvases:
            c.bind("<Configure>", lambda e, target=c: _on_hypr_resize(e, target))
            # Initial draw
            _on_hypr_resize(None, c)
        root.update()
    else:
        monitors = detect_monitors()
        root = tk.Tk()
        root.configure(takefocus=False)

        if not monitors:
            monitors = [(root.winfo_screenwidth(), root.winfo_screenheight(), 0, 0)]

        min_x = min(x for _, _, x, _ in monitors)
        min_y = min(y for _, _, _, y in monitors)
        max_x = max(x + w for w, _, x, _ in monitors)
        max_y = max(y + h for _, h, _, y in monitors)

        total_w = max(root.winfo_screenwidth(), max_x - min_x)
        total_h = max(root.winfo_screenheight(), max_y - min_y)

        root.overrideredirect(True)
        root.geometry(f"{total_w}x{total_h}+{min_x}+{min_y}")
        root.configure(bg=overlay_bg_color)
        root.attributes("-alpha", overlay_opacity)  # Set window opacity
        root.attributes("-topmost", True)
        root.config(cursor="none")
        root.protocol("WM_DELETE_WINDOW", lambda: None)
        root.lift()

        canvas = tk.Canvas(
            root,
            width=total_w,
            height=total_h,
            bg=overlay_bg_color,
            highlightthickness=0,
        )
        canvas.pack(fill="both", expand=True)
        canvases.append(canvas)

        for w, h, x, y in monitors:
            cx = float(x - min_x + (w // 2))
            cy = float(y - min_y + (h // 2))
            x11_centers.append((cx, cy))

        def _redraw_x11(time_str: str | None = None) -> None:
            if time_str is None:
                elapsed = time.time() - start_time
                current_remaining = max(0, initial_remaining_s - elapsed)
                mins, secs = divmod(int(current_remaining), 60)
                time_str = f"{mins:02d}:{secs:02d}"

            canvas.delete("all")
            for i, (mx, my) in enumerate(x11_centers):
                draw_overlay_frame(
                    canvas,
                    break_title,
                    time_str,
                    accent_color,
                    cx=mx,
                    cy=my,
                    title_font_size=metrics["title_font_size"],
                    subtitle_font_size=metrics["subtitle_font_size"],
                    title_color=overlay_color,
                    subtitle_color=overlay_color,
                    digit_w=metrics["digit_w"],
                    digit_h=metrics["digit_h"],
                    thickness=metrics["thickness"],
                    gap=metrics["gap"],
                    spacing=metrics["spacing"],
                    title_offset_y=metrics["title_offset_y"],
                    subtitle_offset_y=metrics["subtitle_offset_y"],
                    clear_all=False,
                    digit_tag=f"clock_digits_{i}",
                )

        _redraw_x11()
        root.update_idletasks()

    def _poll_stdin() -> None:
        nonlocal start_time
        try:
            while select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline()
                if not line:
                    root.destroy()
                    return

                cmd = line.strip()
                if cmd == CMD_STOP:
                    root.destroy()
                    return

                try:
                    # Handle external updates (like skipping break)
                    remaining = int(cmd)
                    # Reset our timer based on external input
                    # If remaining is less than what we currently show, adjust start_time
                    elapsed_so_far = time.time() - start_time
                    expected_remaining = max(0, initial_remaining_s - elapsed_so_far)

                    # Only adjust if the external command indicates a significant change
                    # (like skipping to 0 or manually setting a new time)
                    if (
                        abs(remaining - expected_remaining) > 1
                    ):  # More than 1 second difference
                        start_time = time.time() - (initial_remaining_s - remaining)
                except ValueError:
                    pass
        except Exception:
            pass

        root.after(POLL_INTERVAL_MS, _poll_stdin)

    # Timer update function for smooth display
    def _update_timer_display() -> None:
        # Calculate current remaining time based on elapsed time
        elapsed = time.time() - start_time
        current_remaining = max(0, initial_remaining_s - elapsed)

        if current_remaining <= 0:
            # Time's up - close the overlay
            root.destroy()
            return

        mins, secs = divmod(int(current_remaining), 60)
        time_str = f"{mins:02d}:{secs:02d}"

        if is_hyprland:
            for c in canvases:
                _on_hypr_resize(None, c)
        else:
            _redraw_x11(time_str)

        # Schedule next update (4 times per second for smooth display)
        root.after(250, _update_timer_display)

    # Start the timer updates
    root.after(250, _update_timer_display)

    root.after(POLL_INTERVAL_MS, _poll_stdin)

    try:
        root.mainloop()
    except Exception as e:
        logger.debug(f"Tkinter mainloop error: {e}")


def main() -> None:
    """CLI entry point for overlay process."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="Break")
    parser.add_argument("--remaining", type=int, default=300)
    parser.add_argument("--accent", default=DEFAULT_OVERLAY_ACCENT)
    args = parser.parse_args()

    run_standalone_overlay(
        break_title=args.title,
        initial_remaining_s=args.remaining,
        accent_color=args.accent,
    )


if __name__ == "__main__":
    main()


class BreakOverlayManager:
    """Manages full-screen break overlay windows across all monitors via subprocess."""

    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self._is_active: bool = False

    def start_overlay(
        self,
        break_title: str,
        initial_remaining_s: int,
        accent_color: str = DEFAULT_OVERLAY_ACCENT,
    ) -> None:
        """Start overlay windows in an isolated child subprocess."""
        if self._is_active:
            return

        self._is_active = True
        cmd = [
            sys.executable,
            "-c",
            "from pomlock.ui.break_overlay import main; main()",
            "--title",
            break_title,
            "--remaining",
            str(initial_remaining_s),
            "--accent",
            accent_color,
        ]

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            logger.debug(f"Failed to spawn break overlay subprocess: {e}")
            self._is_active = False

    def update_timer(self, remaining_s: int) -> None:
        """Post remaining seconds to the overlay process."""
        # This method is kept for compatibility but is no longer used.
        # The overlay process now uses its own local timer and listens for commands via stdin.
        if not self._is_active or not self._proc or not self._proc.stdin:
            return

        try:
            self._proc.stdin.write(f"{remaining_s}\n")
            self._proc.stdin.flush()
        except Exception:
            pass

    def stop_overlay(self) -> None:
        """Stop and close all overlay windows."""
        if not self._is_active:
            return

        self._is_active = False

        if self._proc:
            if self._proc.stdin:
                try:
                    self._proc.stdin.write(f"{CMD_STOP}\n")
                    self._proc.stdin.flush()
                except Exception:
                    pass
                try:
                    self._proc.stdin.close()
                except Exception:
                    pass

            try:
                self._proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    self._proc.kill()

        self._proc = None

