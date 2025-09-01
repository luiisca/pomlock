#!/usr/bin/env python3

import logging
import json
import subprocess
import sys
import time
from pathlib import Path

# This path must match the one in pomlock/constants.py
STATE_FILE = Path("/tmp/pomlock.json")


LOG_FILE = Path("/tmp/pomlock_waybar.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_state():
    """Reads the current state from the state file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}


def handle_click(button):
    """Handles left and right clicks from Waybar."""
    if button == "left":
        cmd = ["pomlock"]
        subprocess.Popen(cmd)
        logger.debug(f"Executed: {' '.join(cmd)}")
    elif button == "right":
        logger.debug("Opening rofi menu for preset selection.")
        try:
            cmd_presets = ["pomlock", "--show-presets"]
            logger.debug(f"Executing: {' '.join(cmd_presets)}")
            presets_str = subprocess.check_output(
                cmd_presets).decode("utf-8").strip()

            cmd_rofi = ["rofi", "-dmenu", "-p", "Select Preset"]
            logger.debug(f"Executing: {' '.join(cmd_rofi)} with input: {
                         presets_str[:50]}...")
            selected = subprocess.check_output(
                cmd_rofi,
                input=presets_str.encode('utf-8'),  # rofi expects bytes
                text=False  # text=True implies input/output are strings, but input needs to be bytes
            ).decode("utf-8").strip()

            if selected:
                preset_name = selected.split(':')[0].strip()
                cmd_pomlock = ["pomlock", "-t", preset_name]
                subprocess.Popen(cmd_pomlock)
                logger.debug(f"Executed: {' '.join(cmd_pomlock)}")
        except FileNotFoundError as e:
            logger.error(f"Command not found: {
                         e.filename}. Is rofi installed and in PATH?")
        except subprocess.CalledProcessError as e:
            logger.error(f"Subprocess failed with exit code {
                         e.returncode}: {e.stderr.decode('utf-8')}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")


def print_waybar_json(state):
    """Calculates and prints the JSON output for Waybar."""
    if not state or "start_time" not in state:
        # No active timer, show default text
        print(json.dumps(
            {"text": "pomlock", "tooltip": "Click to start a session"}))
        return

    elapsed = time.time() - state["start_time"]
    remaining_s = (state["time"] * 60) - elapsed

    if remaining_s <= 0:
        # Timer is done, show default text. pomlock will send the next state or exit.
        print(json.dumps({"text": "pomlock", "tooltip": "Session ended"}))
        return

    mins, secs = divmod(int(remaining_s), 60)
    time_str = f"{mins:02d}:{secs:02d}"

    action = state.get("action", "pomodoro")
    if action == "pomodoro":
        action_icon = "󰚜"
    elif action == "short_break":
        action_icon = "󰽙"
    else:  # long_break
        action_icon = "󰽞"

    cycle_str = ""
    if state.get("crr_cycle") and state.get("total_cycles"):
        cycle_str = f" - {state['crr_cycle']}/{state['total_cycles']}"

    tooltip = f"Current: {action.replace('_', ' ').title()}"

    print(json.dumps({
        "text": f"{action_icon} {time_str}{cycle_str}",
        "tooltip": tooltip
    }))


def main():
    """Main script entry point."""
    # Check for click handlers passed from Waybar's on-click
    if len(sys.argv) > 1 and sys.argv[1] in ["left", "right"]:
        handle_click(sys.argv[1])
        return

    # Otherwise, it's a regular poll from Waybar's interval
    state = get_state()
    print_waybar_json(state)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
