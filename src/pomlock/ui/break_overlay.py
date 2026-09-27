import json
import multiprocessing as mp
import os
import re
import subprocess
import sys
import time
import tkinter as tk
from dataclasses import dataclass
from multiprocessing.synchronize import Event as MpEvent
from typing import Optional

from pomlock.settings import Settings

from ..logger import logger

POLL_INTERVAL_MS = 50
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


# Digit-clock proportions, all derived from a single "digit height" so that
# width, stroke thickness, segment gaps, and the colon dots all scale
# together instead of drifting out of proportion with each other.
DIGIT_W_TO_H_RATIO = 0.5625  # matches the original 90x160 digit design
THICKNESS_DIVISOR = 9
GAP_DIVISOR = 20
SPACING_DIVISOR = 10
# How far each colon dot sits above/below center, as a fraction of digit
# height. A constant 0 here would put both dots on top of each other so the
# colon would render as a single dot.
COLON_DOT_OFFSET_RATIO = 0.17

# The timer digits are the focal point of the overlay, so they're rendered
# noticeably larger than Settings["overlay"]["font_size"] itself rather than
# using that value as a literal pixel height.
TIMER_FONT_SCALE = 2.8
MIN_TIMER_DIGIT_H = 140


@dataclass(frozen=True)
class OverlayStyle:
    """Every Settings["overlay"] value, read once per overlay run.

    This is the single source of truth for overlay configuration: nothing
    downstream in this module should reach back into Settings, and nothing
    should re-thread individual setting values through function parameters.
    Functions that need overlay config take this object (and, where they
    need computed geometry, the `metrics` dict derived from it) instead of
    a hand-picked subset of fields.
    """

    enabled: bool
    bg_color: str
    opacity: float
    accent: str
    inactive_color: str
    title_color: str
    title_font_family: str
    title_font_size: int
    short_break_title: str
    long_break_title: str
    timer_font_size: int
    subtitle_text: str
    subtitle_color: str
    subtitle_font_family: str
    subtitle_font_size: int


def _load_overlay_style() -> OverlayStyle:
    overlay = Settings()["overlay"]
    return OverlayStyle(
        enabled=overlay["enabled"],
        bg_color=overlay["bg_color"],
        opacity=overlay["opacity"],
        accent=overlay["color"],
        inactive_color=overlay["inactive_segment_color"],
        title_color=overlay["title_color"],
        title_font_family=overlay["title_font_family"],
        title_font_size=overlay["title_font_size"],
        short_break_title=overlay["short_break_title"],
        long_break_title=overlay["long_break_title"],
        timer_font_size=overlay["font_size"],
        subtitle_text=overlay["msg"],
        subtitle_color=overlay["msg_color"],
        subtitle_font_family=overlay["msg_font_family"],
        subtitle_font_size=overlay["msg_font_size"],
    )


def compute_overlay_metrics(style: OverlayStyle) -> dict:
    """Derive every overlay geometry value from the style's font sizes.

    Centralizing this calculation is what keeps the Hyprland and X11 render
    paths in sync. Offsets are always derived from the *actual* rendered
    digit height and text sizes, so the title/subtitle can never overlap the
    timer digits regardless of what's configured.
    """
    digit_h = max(MIN_TIMER_DIGIT_H, int(style.timer_font_size * TIMER_FONT_SCALE))
    digit_w = int(digit_h * DIGIT_W_TO_H_RATIO)
    thickness = max(3, digit_h // THICKNESS_DIVISOR)
    gap = max(1, digit_h // GAP_DIVISOR)
    spacing = max(4, digit_h // SPACING_DIVISOR)

    title_offset_y = digit_h // 2 + style.title_font_size + 20
    subtitle_offset_y = digit_h // 2 + style.subtitle_font_size + 20

    return {
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
    tag: str,
    style: OverlayStyle,
    metrics: dict,
) -> None:
    """Render smooth vector 7-segment digital alarm clock digits on a Canvas."""
    canvas.delete(tag)

    color = style.accent
    inactive_color = style.inactive_color
    digit_w = metrics["digit_w"]
    digit_h = metrics["digit_h"]
    thickness = metrics["thickness"]
    gap = metrics["gap"]
    spacing = metrics["spacing"]

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
    style: OverlayStyle,
    metrics: dict,
    cx: float | None = None,
    cy: float | None = None,
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

    canvas.create_text(
        cx,
        cy - metrics["title_offset_y"],
        text=title.upper(),
        font=(style.title_font_family, style.title_font_size, "bold"),
        fill=style.title_color,
        tags=text_tag,
    )
    draw_vector_clock(canvas, time_str, cx, cy, tag=digit_tag, style=style, metrics=metrics)
    canvas.create_text(
        cx,
        cy + metrics["subtitle_offset_y"],
        text=style.subtitle_text,
        font=(style.subtitle_font_family, style.subtitle_font_size),
        fill=style.subtitle_color,
        tags=text_tag,
    )


def run_standalone_overlay(
    is_long_break: bool,
    initial_remaining_s: int,
    stop_event: MpEvent,
) -> None:
    """Run fullscreen overlay covering all monitors.

    Runs in a dedicated child process (see BreakOverlayManager). All display
    settings are read directly from Settings["overlay"] here.
    """
    style = _load_overlay_style()

    if not style.enabled:
        return  # Overlay is disabled, exit early

    setup_tcl_env()
    is_hyprland = bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))

    break_title = style.long_break_title if is_long_break else style.short_break_title
    metrics = compute_overlay_metrics(style)

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
        root.configure(bg=style.bg_color)
        root.config(cursor="none")
        root.attributes("-alpha", style.opacity)
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", lambda: None)

        windows: list[tk.Tk | tk.Toplevel] = [root]
        for i in range(1, len(hypr_monitors)):
            top = tk.Toplevel(root, class_=f"pomlock-overlay-{i}")
            top.title(f"pomlock-overlay-{i}")
            top.overrideredirect(True)
            top.configure(bg=style.bg_color)
            top.config(cursor="none")
            top.attributes("-alpha", style.opacity)
            top.attributes("-topmost", True)
            top.protocol("WM_DELETE_WINDOW", lambda: None)
            windows.append(top)

        for win in windows:
            canvas = tk.Canvas(win, bg=style.bg_color, highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            canvases.append(canvas)

        root.update()

        # Set geometry for each window directly using monitor data
        for win, m in zip(windows, hypr_monitors):
            # Hyprland monitor dict contains: x, y, width, height
            x = m.get("x", 0)
            y = m.get("y", 0)
            w = m.get("width", 0)
            h = m.get("height", 0)
            if w > 0 and h > 0:
                win.geometry(f"{w}x{h}+{x}+{y}")

        root.update()  # Ensure geometry is applied

        # Use hyprctl to properly set window position and fullscreen state
        for win, m in zip(windows, hypr_monitors):
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
            draw_overlay_frame(c, break_title, time_str, style, metrics)

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
        root.configure(bg=style.bg_color)
        root.attributes("-alpha", style.opacity)
        root.attributes("-topmost", True)
        root.config(cursor="none")
        root.protocol("WM_DELETE_WINDOW", lambda: None)
        root.lift()

        canvas = tk.Canvas(
            root,
            width=total_w,
            height=total_h,
            bg=style.bg_color,
            highlightthickness=0,
        )
        canvas.pack(fill="both", expand=True)
        canvases.append(canvas)

        for w, h, x, y in monitors:
            mx = float(x - min_x + (w // 2))
            my = float(y - min_y + (h // 2))
            x11_centers.append((mx, my))

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
                    style,
                    metrics,
                    cx=mx,
                    cy=my,
                    clear_all=False,
                    digit_tag=f"clock_digits_{i}",
                )

        _redraw_x11()
        root.update_idletasks()

    def _poll_stop_event() -> None:
        if stop_event.is_set():
            root.destroy()
            return
        root.after(POLL_INTERVAL_MS, _poll_stop_event)

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
    root.after(POLL_INTERVAL_MS, _poll_stop_event)

    try:
        root.mainloop()
    except Exception as e:
        logger.debug(f"Tkinter mainloop error: {e}")


class BreakOverlayManager:
    """Manages full-screen break overlay windows across all monitors via a subprocess."""

    def __init__(self):
        self._proc: Optional[mp.Process] = None
        self._stop_event: Optional[MpEvent] = None
        self._is_active: bool = False

    def start_overlay(self, is_long_break: bool, initial_remaining_s: int) -> None:
        """Start overlay windows in an isolated child process."""
        if self._is_active:
            return

        self._is_active = True
        self._stop_event = mp.Event()

        try:
            self._proc = mp.Process(
                target=run_standalone_overlay,
                args=(is_long_break, initial_remaining_s, self._stop_event),
                daemon=True,
            )
            self._proc.start()
        except Exception as e:
            logger.debug(f"Failed to spawn break overlay process: {e}")
            self._is_active = False
            self._proc = None
            self._stop_event = None

    def stop_overlay(self) -> None:
        """Stop and close all overlay windows."""
        if not self._is_active:
            return

        self._is_active = False

        if self._stop_event is not None:
            self._stop_event.set()

        if self._proc is not None:
            self._proc.join(timeout=0.5)
            if self._proc.is_alive():
                self._proc.terminate()
                self._proc.join(timeout=0.5)
                if self._proc.is_alive():
                    self._proc.kill()

        self._proc = None
        self._stop_event = None
