# Pomlock - Break Enforcement System

> "The productivity tool that _actually_ makes you take breaks"

![Demo Preview](demo-preview.gif)

A Linux utility that enforces regular breaks by temporarily blocking input devices. Perfect for developers, writers, and anyone who needs help stepping away from the keyboard.

## Features

- ⏲️ **Preset Timers**: Built-in Pomodoro intervals (25/5, 40/10) + custom schedules
- ⌨️ **Input Blocking**: Physically disables keyboard/mouse during breaks
- 📝 **Activity Logging**: Simple timestamped work/break tracking
- 🎨 **Custom Overlay**: Adjustable full-screen break timer display
- 🔄 **Safe Mode**: Optional monitoring without input blocking (`--enable-input-during-break`)

## Installation

```bash
git clone https://github.com/yourusername/pomlock.git
cd pomlock
chmod +x py-pomlock.py
```

## Basic Usage

```bash
# Start with standard 25/5 Pomodoro
./py-pomlock.py --timer standard

# Custom work/break schedule (45min work, 15min short breaks, 30min long breaks, after 3 cycles)
./py-pomlock.py --timer "45 15 30 3"

# Monitor without blocking input
./py-pomlock.py --enable-input-during-break
```

## Configuration

Edit `~/.config/pomlock/pomlock.conf`:
```ini
[pomodoro]
pomodoro = 25
short_break = 5
long_break = 20
cycles_before_long = 4
enable_input_during_break = false

[overlay]
font_size = 48
color = white
bg_color = black
opacity = 0.8
notify = true
notify_msg = Time for a break!

[presets]
standard = 25 5 20 4
extended = 60 10 20 3
```

## Log Format

Plain text format compatible with most time trackers:
```
2023-07-20 14:25:00 - INFO - Pomodoro started (25 minutes).
2023-07-20 14:50:00 - INFO - Pomodoro completed (Duration: 25m) (Cycle: 1)
2023-07-20 14:50:00 - INFO - Short break started (Duration: 5m) (Cycle: 1)
2023-07-20 14:55:00 - INFO - Break completed (Cycle: 1)
```

## Safety

- Input automatically restores when program exits
- Use `--enable-input-during-break` for non-blocking monitoring
- Force stop at any time with:
```bash
pkill -f py-pomlock.py
```

## Roadmap

- [ ] udev rules for secure device control
- [ ] Systemd service integration
- [ ] Graphical configuration UI
