import argparse
import json
import os
import re
import select
import subprocess
import sys
import tkinter as tk
from typing import Optional

from ..constants import DEFAULT_OVERLAY_ACCENT
from ..logger import logger

POLL_INTERVAL_MS = 50
SUBTITLE_TEXT = "Step away from the screen. Input is locked."
FONT_FAMILY_FALLBACK = "DejaVu Sans Mono"
CMD_STOP = "STOP"


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
TITLE_OFFSET_Y = 140
SUBTITLE_OFFSET_Y = 140
COLON_DOT_OFFSET_Y = 35
INACTIVE_SEGMENT_COLOR = "#181D24"
SUBTITLE_TEXT_COLOR = "#888888"


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

        # Draw colon separator
        if char == ":":
            dot_sz = thickness
            dot_x = x
            canvas.create_oval(
                dot_x,
                cy - COLON_DOT_OFFSET_Y - dot_sz / 2,
                dot_x + dot_sz,
                cy - COLON_DOT_OFFSET_Y + dot_sz / 2,
                fill=color,
                outline="",
                tags=tag,
            )
            canvas.create_oval(
                dot_x,
                cy + COLON_DOT_OFFSET_Y - dot_sz / 2,
                dot_x + dot_sz,
                cy + COLON_DOT_OFFSET_Y + dot_sz / 2,
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
            x + g, cy - half_h,
            x + digit_w - g, cy - half_h,
            x + digit_w - g - t / 2, cy - half_h + t,
            x + g + t / 2, cy - half_h + t,
            fill=c0, outline="", tags=tag,
        )

        # B: top right segment
        c1 = color if segs[1] else inactive_color
        canvas.create_polygon(
            x + digit_w, cy - half_h + g,
            x + digit_w, cy - g / 2,
            x + digit_w - t, cy - g / 2 - t / 2,
            x + digit_w - t, cy - half_h + g + t / 2,
            fill=c1, outline="", tags=tag,
        )

        # C: bottom right segment
        c2 = color if segs[2] else inactive_color
        canvas.create_polygon(
            x + digit_w, cy + g / 2,
            x + digit_w, cy + half_h - g,
            x + digit_w - t, cy + half_h - g - t / 2,
            x + digit_w - t, cy + g / 2 + t / 2,
            fill=c2, outline="", tags=tag,
        )

        # D: bottom segment
        c3 = color if segs[3] else inactive_color
        canvas.create_polygon(
            x + g + t / 2, cy + half_h - t,
            x + digit_w - g - t / 2, cy + half_h - t,
            x + digit_w - g, cy + half_h,
            x + g, cy + half_h,
            fill=c3, outline="", tags=tag,
        )

        # E: bottom left segment
        c4 = color if segs[4] else inactive_color
        canvas.create_polygon(
            x, cy + g / 2,
            x + t, cy + g / 2 + t / 2,
            x + t, cy + half_h - g - t / 2,
            x, cy + half_h - g,
            fill=c4, outline="", tags=tag,
        )

        # F: top left segment
        c5 = color if segs[5] else inactive_color
        canvas.create_polygon(
            x, cy - half_h + g,
            x + t, cy - half_h + g + t / 2,
            x + t, cy - g / 2 - t / 2,
            x, cy - g / 2,
            fill=c5, outline="", tags=tag,
        )

        # G: middle segment
        c6 = color if segs[6] else inactive_color
        canvas.create_polygon(
            x + g, cy,
            x + g + t / 2, cy - t / 2,
            x + digit_w - g - t / 2, cy - t / 2,
            x + digit_w - g, cy,
            x + digit_w - g - t / 2, cy + t / 2,
            x + g + t / 2, cy + t / 2,
            fill=c6, outline="", tags=tag,
        )

        x += w_i + spacing


def draw_overlay_frame(
    canvas: tk.Canvas,
    title: str,
    time_str: str,
    accent: str,
    cx: float | None = None,
    cy: float | None = None,
) -> None:
    """Draw title, clock digits, and subtitle dynamically centered on canvas."""
    canvas.delete("all")
    w = canvas.winfo_width()
    h = canvas.winfo_height()

    if cx is None:
        cx = (w / 2.0) if w > 1 else 960.0
    if cy is None:
        cy = (h / 2.0) if h > 1 else 540.0

    canvas.create_text(
        cx,
        cy - TITLE_OFFSET_Y,
        text=f"{title.upper()}",
        font=("DejaVu Sans", 26, "bold"),
        fill=accent,
    )
    draw_vector_clock(canvas, time_str, cx, cy, color=accent)
    canvas.create_text(
        cx,
        cy + SUBTITLE_OFFSET_Y,
        text=SUBTITLE_TEXT,
        font=("DejaVu Sans", 16),
        fill=SUBTITLE_TEXT_COLOR,
    )


def run_standalone_overlay(
    break_title: str,
    initial_remaining_s: int,
    accent_color: str,
) -> None:
    """Run fullscreen overlay covering all monitors."""
    is_hyprland = bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))
    mins, secs = divmod(initial_remaining_s, 60)
    current_time: list[str] = [f"{mins:02d}:{secs:02d}"]
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
        root.title("pomlock-overlay-0")
        root.configure(bg="black")
        root.config(cursor="none")
        root.protocol("WM_DELETE_WINDOW", lambda: None)

        windows: list[tk.Tk | tk.Toplevel] = [root]
        for i in range(1, len(hypr_monitors)):
            top = tk.Toplevel(root, class_=f"pomlock-overlay-{i}")
            top.title(f"pomlock-overlay-{i}")
            top.configure(bg="black")
            top.config(cursor="none")
            top.protocol("WM_DELETE_WINDOW", lambda: None)
            windows.append(top)

        for win in windows:
            canvas = tk.Canvas(win, bg="black", highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            canvases.append(canvas)

        root.update()

        for i, m in enumerate(hypr_monitors):
            mname = m.get("name", "")
            wtitle = f"pomlock-overlay-{i}"
            subprocess.run(
                ["hyprctl", "dispatch", "focuswindow", f"title:{wtitle}"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if mname:
                subprocess.run(
                    ["hyprctl", "dispatch", "movewindow", f"mon:{mname}"],
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

        def _on_hypr_resize(event: tk.Event, c: tk.Canvas) -> None:
            draw_overlay_frame(c, break_title, current_time[0], accent_color)

        for c in canvases:
            c.bind("<Configure>", lambda e,
                   target=c: _on_hypr_resize(e, target))
            draw_overlay_frame(c, break_title, current_time[0], accent_color)
    else:
        monitors = detect_monitors()
        root = tk.Tk()

        if not monitors:
            monitors = [(root.winfo_screenwidth(),
                         root.winfo_screenheight(), 0, 0)]

        min_x = min(x for _, _, x, _ in monitors)
        min_y = min(y for _, _, _, y in monitors)
        max_x = max(x + w for w, _, x, _ in monitors)
        max_y = max(y + h for _, h, _, y in monitors)

        total_w = max(root.winfo_screenwidth(), max_x - min_x)
        total_h = max(root.winfo_screenheight(), max_y - min_y)

        root.overrideredirect(True)
        root.geometry(f"{total_w}x{total_h}+{min_x}+{min_y}")
        root.configure(bg="black")
        root.attributes("-topmost", True)
        root.config(cursor="none")
        root.protocol("WM_DELETE_WINDOW", lambda: None)
        root.lift()

        canvas = tk.Canvas(root, width=total_w, height=total_h,
                           bg="black", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        canvases.append(canvas)

        for w, h, x, y in monitors:
            cx = float(x - min_x + (w // 2))
            cy = float(y - min_y + (h // 2))
            x11_centers.append((cx, cy))

        def _redraw_x11() -> None:
            canvas.delete("all")
            for cx, cy in x11_centers:
                canvas.create_text(
                    cx,
                    cy - TITLE_OFFSET_Y,
                    text=f"{break_title.upper()}",
                    font=("DejaVu Sans", 26, "bold"),
                    fill=accent_color,
                )
                draw_vector_clock(
                    canvas, current_time[0], cx, cy, color=accent_color)
                canvas.create_text(
                    cx,
                    cy + SUBTITLE_OFFSET_Y,
                    text=SUBTITLE_TEXT,
                    font=("DejaVu Sans", 16),
                    fill=SUBTITLE_TEXT_COLOR,
                )

        _redraw_x11()
        root.update_idletasks()

    def _poll_stdin() -> None:
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
                    remaining = int(cmd)
                    m, s = divmod(remaining, 60)
                    current_time[0] = f"{m:02d}:{s:02d}"

                    if is_hyprland:
                        for c in canvases:
                            draw_overlay_frame(
                                c, break_title, current_time[0], accent_color)
                    else:
                        _redraw_x11()
                except ValueError:
                    pass
        except Exception:
            pass

        root.after(POLL_INTERVAL_MS, _poll_stdin)

    root.after(POLL_INTERVAL_MS, _poll_stdin)

    try:
        root.mainloop()
    except Exception as e:
        logger.debug(f"Tkinter mainloop error: {e}")


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
