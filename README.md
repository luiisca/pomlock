# Pomlock - A pomodoro application for Linux

![Demo Preview](demo-preview.gif)

A Linux utility that enforces regular breaks by temporarily blocking input devices. Perfect for developers, writers, and anyone who needs help stepping away from the keyboard.

## Features

- **Flexible Timer System**: Supports multiple timer presets, including the classic Pomodoro, Ultradian Rhythm (90/20), and a 50/10 cycle. New presets can be defined in the configuration file, and a one-time custom timer can be passed as a command-line argument.
- **Input Blocking**: Disables all input devices during break periods to ensure you step away.
- **Customizable Overlay**: A full-screen display during breaks with configurable font, colors, and opacity.
- **Desktop Notifications**: Get native desktop notifications when a break starts.
- **Activity Logging**: Keeps a simple log of work and break cycles at `~/.local/share/pomlock/pomlock.log`.
- **Safe Mode**: Run the timer without input blocking using the `--enable-input-during-break` flag.
- **Smart Configuration**: Settings are loaded in a logical order: Defaults < Config File < CLI Arguments. CLI flags always have the final say.


## Installation

### pip
```bash
pip install pomlock
```

### uv
```bash
uv tool install pomlock
```

<!-- ### Arch Linux (AUR) -->
<!-- ```bash -->
<!-- yay -S pomlock -->
<!-- ``` -->
<!-- ```bash -->
<!-- paru -S pomlock -->
<!-- ``` -->
<!---->
<!-- ### Manual -->
<!---->
<!-- <!-- TODO: some ideas --> -->
<!-- options: -->
<!-- 1. curl command:  -->
<!-- [uv package manager](https://github.com/astral-sh/uv?tab=readme-ov-file#installation) -->
<!-- ```bash -->
<!-- curl -LsSf https://astral.sh/uv/install.sh | sh   -->
<!-- ``` -->
<!-- [yt-dlp](https://github.com/yt-dlp/yt-dlp/wiki/Installation#installing-the-release-binary) -->
<!-- ```bash -->
<!-- curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o ~/.local/bin/yt-dlp -->
<!-- chmod a+rx ~/.local/bin/yt-dlp  # Make executable -->
<!-- ``` -->
<!---->
<!-- 2. pip -->
<!-- [uv](https://github.com/astral-sh/uv?tab=readme-ov-file#installation) -->
<!-- ```bash -->
<!-- # With pip. -->
<!-- pip install uv -->
<!-- ``` -->
<!-- [yt-dlp](https://github.com/yt-dlp/yt-dlp/wiki/Installation#with-pip) -->
<!-- ```bash -->
<!-- python3 -m pip install -U "yt-dlp[default]" -->
<!-- ``` -->
<!---->
<!-- 3. pacman -->
<!-- [yt-dlp](https://github.com/yt-dlp/yt-dlp/wiki/Installation#pacman) -->
<!-- ```bash -->
<!-- sudo pacman -Syu yt-dlp -->
<!-- ``` -->


## Usage

```bash
# Start with the default 'standard' preset (25min work, 5min break)
pomlock

# Use the 'ultradian' preset for a long deep-work session (90min work, 20min break)
pomlock --timer ultradian

# Use the 'fifty_ten' preset for a 50/10 work-break cycle.
pomlock --timer fifty_ten

# Set a custom timer: 45min work, 15min short break, 30min long break after 3 cycles
pomlock --timer "45 15 30 3"

# Set a custom overlay text color for the session
pomlock --overlay-color "lime"

# Run without blocking input devices
pomlock --enable-input-during-break
```

## Configuration

You can create a custom configuration file at `~/.config/pomlock/pomlock.conf` to override the default settings. CLI arguments will always override settings from this file.

Here is an example configuration showing all available options:
```ini
# ~/.config/pomlock/pomlock.conf

[pomodoro]
# These values define the timer components when not using a preset.
# timer = 30 5 15 4
pomodoro = 30
short_break = 5
long_break = 15
cycles_before_long = 4
enable_input_during_break = false

[overlay]
# Customize the appearance of the break screen.
font_size = 64
color = red
bg_color = white
opacity = 0.5
notify = false
# notify_message = Time for a break!

[presets]
# Define your own custom timer presets.
# Format: "WORK SHORT_BREAK LONG_BREAK CYCLES"
standard = 25 5 20 4
ultradian = 90 20 20 1
fifty_ten = 50 10 10 1
```

## Log File

**Location**: `~/.local/share/pomlock/pomlock.log`

**Example Log Output**:
```log
2023-10-27 10:00:00 - INFO - Pomodoro started (25 minutes).
2023-10-27 10:25:00 - INFO - Pomodoro completed (Duration: 25m) (Cycle: 1)
2023-10-27 10:25:00 - INFO - Short break started (Duration: 5m) (Cycle: 1)
2023-10-27 10:30:00 - INFO - Break completed (Cycle: 1)
```

## Safety

- **Automatic Restoration**: Input devices are automatically re-enabled when the program exits cleanly or is interrupted (Ctrl+C).
- **Non-Blocking Mode**: Use `--enable-input-during-break` for safe, non-blocking monitoring.
- **Force Quit**: If the application becomes unresponsive, you can force it to close and restore input by running:
  ```bash
  pkill -f pomlock.py
  ```
