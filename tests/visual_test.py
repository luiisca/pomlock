#!/usr/bin/env python3
"""
Visual and interactive test for input blocking on Hyprland, Wayland, and X11.

Cycle:
1. Discovers input devices and displays them.
2. UNLOCKED (5s) - Type and move mouse to verify input works.
3. LOCKED (5s)   - All input devices are blocked. Try typing/clicking.
4. UNLOCKED (5s) - Input restored. Verify normal functionality.
"""

import sys
import time
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live

from pomlock.input_handler import (
    disable_input_devices,
    enable_input_devices,
    get_input_devices,
    _active_evdev_fds,
    _active_hypr_devs,
)
from pomlock.constants import SESSION_TYPE


def run_visual_test():
    console = Console()
    console.clear()

    # Banner
    console.print(
        Panel(
            "[bold cyan]Pomlock Input Blocking Visual Test[/bold cyan]\n"
            f"Session Type: [yellow]{SESSION_TYPE}[/yellow]",
            border_style="cyan",
        )
    )

    # Discovered devices
    devices = get_input_devices()
    table = Table(title="Discovered Input Devices", border_style="blue")
    table.add_column("Device Node", style="green")
    for dev in devices:
        table.add_row(dev)
    console.print(table)
    console.print()

    try:
        # Phase 1: Initial Unlocked Phase
        _countdown(console, "PHASE 1: UNLOCKED", "Input is active. Type or move mouse freely.", 5, "green")

        # Phase 2: Locked Phase
        disable_input_devices()
        grab_summary = f"{len(_active_evdev_fds)} evdev, {len(_active_hypr_devs)} Hyprland"
        _countdown(
            console,
            "PHASE 2: LOCKED (BLOCKING ACTIVE)",
            f"Blocked ({grab_summary}). Try typing and moving mouse - input should be frozen!",
            6,
            "red",
        )

        # Phase 3: Final Restored Phase
        enable_input_devices()
        _countdown(console, "PHASE 3: RESTORED", "Input is restored. Verify keyboard and mouse work again.", 5, "green")

        console.print(Panel("[bold green]Visual test completed successfully![/bold green]", border_style="green"))

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user. Cleaning up...[/yellow]")
    finally:
        enable_input_devices()
        console.print("[dim]Input devices safety check complete.[/dim]")


def _countdown(console: Console, title: str, subtitle: str, seconds: int, color: str):
    with Live(console=console, refresh_per_second=4) as live:
        for remaining in range(seconds, 0, -1):
            content = (
                f"[bold {color}]{title}[/bold {color}]\n"
                f"{subtitle}\n\n"
                f"[bold white]Time Remaining: [bold {color}]{remaining}[/bold {color}] seconds[/bold white]"
            )
            live.update(Panel(content, border_style=color, expand=False))
            time.sleep(1)


if __name__ == "__main__":
    run_visual_test()
