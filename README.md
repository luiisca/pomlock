# Pomlock - Break Enforcement System

> "The productivity tool that _actually_ makes you take breaks"

![Demo Preview](demo-preview.gif)

A Linux utility that enforces regular breaks by temporarily blocking input devices. Perfect for developers, writers, and anyone who needs help stepping away from the keyboard.

## Features

- ⏲️ **Preset Timers**: Built-in Pomodoro intervals (25/5, 40/10) + custom schedules
- ⌨️ **Input Blocking**: Physically disables keyboard/mouse during breaks
- 📝 **Activity Logging**: Simple timestamped work/break tracking
- 🎨 **Custom Overlay**: Adjustable full-screen break timer display
- 🔄 **Safe Mode**: Optional monitoring without input blocking (`--enable-input`)

## Installation

```bash
git clone https://github.com/yourusername/pomlock.git
cd pomlock
chmod +x pomlock.sh pomlock-overlay.py
# cp pomlock.conf.example ~/.config/pomlock.conf
```

## Basic Usage

```bash
# Start with standard 25/5 Pomodoro
./pomlock.sh --preset standard

# Custom work/break schedule (45min work, 15min breaks)
./pomlock.sh --preset custom 2700 900 1800 3

# Monitor without blocking input
./pomlock.sh --enable-input
```

<!-- ## Configuration -->
<!---->
<!-- Edit `~/.config/pomlock.conf`: -->
<!-- ```ini -->
<!-- # Core timing (seconds) -->
<!-- WORK_DURATION=1500     # 25 minutes -->
<!-- SHORT_BREAK=300        # 5 minutes -->
<!-- LONG_BREAK=900         # 15 minutes -->
<!-- CYCLES_BEFORE_LONG=4   # Long break after 4 work sessions -->
<!---->
<!-- # Display settings -->
<!-- FONT_SIZE=48 -->
<!-- COLOR="white" -->
<!-- BG_COLOR="black" -->
<!-- OPACITY=0.8 -->
<!-- ``` -->

## Log Format

Plain text format compatible with most time trackers:
```
2023-07-20 14:25:00 WORK_START 1500
2023-07-20 14:50:00 BREAK_START 300
2023-07-20 14:55:00 WORK_START 1500
```

## Safety

- Input automatically restores when program exits
- Use `--enable-input` for non-blocking monitoring
- Force stop at any time with:
```bash
pkill -f pomlock.sh && pkill -f pomlock-overlay.py
```

## Roadmap

- [ ] udev rules for secure device control
- [ ] Systemd service integration
- [ ] Graphical configuration UI
