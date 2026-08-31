# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup
- Install dependencies: `uv sync` (if using uv for development) or `pip install -e .` for editable install
- The project uses `uv` as the primary package manager (`uv.lock` present)

### Running the Application
- Start with default settings: `pomlock`
- Use a timer preset: `pomlock --timer ultradian` (90/20 cycle)
- Set custom timer: `pomlock --timer "45 15 30 3"` (45min work, 15min short break, 30min long break after 3 cycles)
- Tag activity: `pomlock --activity coding`
- Run without input blocking (safe for testing): `pomlock --no-block-input`
- List activities: `pomlock --show-activities`

### Testing
- Run all tests: `python -m unittest discover tests` or `python -m pytest`
- Run specific test module: `python -m unittest tests.test_timer_engine`
- Tests use Python's built-in `unittest` framework with `unittest.mock` for isolation
- Tests create temporary directories and database files for isolation

### Building and Publishing
- Build distributions: `uv build` (creates sdist and wheel in `dist/` directory)
- Publish to PyPI: `uv publish` (requires PyPI credentials)
- GitHub Actions workflow handles automated releases via release-please:
  - Pushes to `main` trigger version bumps
  - Workflow builds, publishes to PyPI and AUR (Arch User Repository)

### Development Utilities
- Waybar integration: `src/pomlock/waybar.py` provides JSON status output for status bars
- State file: `/tmp/pomlock.json` contains current timer state for polling integrations
- Callback system: Use `--callback /path/to/script.sh` for event-driven integrations

## Code Architecture

### Core Components
1. **Timer Engine (`src/pomlock/timer_engine.py`)**:
   - State machine (`TimerEngine`) managing pomodoro/break cycles
   - Handles timing, phase transitions, persistence via `HistoryStore`
   - Features: start/pause/resume/reset/skip, automatic phase advancement

2. **Persistence Layer**:
   - `src/pomlock/db.py`: SQLite database layer (`pomlock.db`)
   - `src/pomlock/history_store.py`: CRUD operations and analytics (daily/weekly/monthly/yearly views)
   - Automatic activity creation when new activities are encountered
   - Goal tracking with multi-period objectives

3. **User Interface (`src/pomlock/ui/`)**:
   - **Textual-based main interface** (`app.py`, `screens/`):
     - Main screen: timer, cycle info, activity tagging, goals display
     - Stats screen: historical data in multiple timeframes
     - Settings screen: preference configuration
   - **Break overlay system** (`break_overlay.py`):
     - Fullscreen Tkinter windows spanning all monitors
     - Vector-rendered 7-segment display with countdown
     - Multi-monitor support via X11/Hyprland detection
     - Communicates via subprocess with stdin commands for updates

4. **Input Blocking (`src/pomlock/input_handler.py`)**:
   - Three-tier fallback system:
     1. Direct evdev kernel access (most reliable)
     2. Hyprland-specific controls (if running Hyprland)
     3. X11/xinput fallback (traditional Linux desktop)
   - Graceful cleanup on application exit or interruption

5. **Configuration (`src/pomlock/__init__.py` Settings class)**:
   - Hierarchical configuration: Defaults → Config File → CLI Arguments
   - Rich argument parsing with help formatting
   - Runtime validation of all settings (positive numbers, valid ranges)
   - Dynamic preset and activity management

### Key Design Patterns
- **State Machine**: TimerEngine uses explicit states (STOPPED, RUNNING, PAUSED) and session kinds (POMODORO, SHORT_BREAK, LONG_BREAK)
- **Dependency Injection**: Components receive dependencies via constructor (e.g., TimerEngine gets HistoryStore)
- **Configuration Layering**: Settings loaded in order: defaults → config file → CLI args (CLI wins)
- **Modular UI**: Textual screens and widgets separated for maintainability
- **Safe Blocking**: Input handler with fallbacks and guaranteed cleanup mechanisms

### Data Flow
1. CLI arguments parsed and merged with config file defaults
2. TimerEngine initialized with settings and HistoryStore
3. UI starts, displaying current state from TimerEngine
4. Timer ticks update engine state, which persists to database via HistoryStore
5. Break triggers input blocking and overlay display
6. Break completion advances phase, potentially blocking input again
7. Application exit restores input devices and cleans up state file

### Safety Features
- Automatic input device restoration on exit (normal or via Ctrl+C)
- Non-blocking mode (`--no-block-input`) for safe testing
- Force-quit mechanism: `pkill -f pomlock` restores input devices
- State file (`/tmp/pomlock.json`) for external status monitoring (e.g., Waybar integration)

### Testing Approach
- Unit tests in `tests/` directory using `unittest`
- Heavy use of mocking (`unittest.mock.patch`) for time, subprocess, and system calls
- Temporary directories and database files ensure test isolation
- Tests cover state transitions, timing accuracy, persistence, and edge cases