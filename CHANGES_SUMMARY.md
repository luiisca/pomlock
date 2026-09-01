# Summary of Changes

## Fixed missing scrollbar in settings page
- Modified `src/pomlock/ui/screens/settings_screen.py` to wrap the entire content in a `VerticalScroll` widget.
- Changed the layout of the main container to `Horizontal` to place Activity and Timer columns side by side.
- Moved the General Settings section inside the scrollable area.

## Ensured settings page edits .conf file and vice versa
- Added new settings fields in the settings screen:
  - break_notify_msg
  - long_break_notify_msg
  - pomo_notify_msg
  - callback
  - overlay_font_size
  - overlay_color
  - overlay_bg_color
  - overlay_opacity
- Updated the `on_save_general_pressed` method to save these settings to the config file.
- Ensured that the settings screen loads these values from the app settings (which are loaded from the config file on startup).

## Provided one-to-one options with config file and flags
- Each setting in the settings screen corresponds directly to a key in the `[general]` section of the config file.
- The config file keys are:
  - overlay
  - block_input
  - notify
  - break_notify_msg
  - long_break_notify_msg
  - pomo_notify_msg
  - callback
  - overlay_font_size
  - overlay_color
  - overlay_bg_color
  - overlay_opacity
- The settings screen updates the app settings dictionary, which is then written to the config file.
- On startup, the app settings are loaded from the config file (via the Settings class) and used to initialize the UI.

## Wrote tests for 100% compatibility
- Updated `tests/test_settings_screen.py`:
  - Fixed the test `test_settings_general_settings_load_and_save` to include a config file path and corrected the button press handler by adding the missing `@on(Button.Pressed, "#btn-save-general")` decorator.
  - Removed debug print statements from the test.
  - Ensured the test verifies that the app settings and config file are updated correctly.
  - The test `test_settings_general_settings_defaults` was left unchanged but continues to pass.
- All tests pass, including the existing test suite.

## Files Modified
1. `src/pomlock/ui/screens/settings_screen.py`
2. `tests/test_settings_screen.py`

## Test Results
All 53 tests pass.