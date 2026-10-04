import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pomlock.settings as settings_module
from pomlock.settings import Settings


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conf_path = Path(self.temp_dir.name) / "test.conf"
        self.conf_path.write_text("[general]\ntimer = ultradian\nblock_input = false\n")

        Settings.reset()
        self._conf_patcher = patch.object(
            settings_module, "DEFAULT_CONFIG_FILE", self.conf_path
        )
        self._conf_patcher.start()

    def tearDown(self):
        Settings.reset()
        self._conf_patcher.stop()
        self.temp_dir.cleanup()

    def test_cli_standard_preset(self):
        # CLI -t standard must override config timer = ultradian
        with patch("sys.argv", ["pomlock", "-t", "standard"]):
            settings = Settings()
            self.assertEqual(settings.get("general", {}).get("timer"), "standard")

    def test_cli_long_timer_arg(self):
        # CLI --timer standard must override config timer = ultradian
        with patch("sys.argv", ["pomlock", "--timer", "standard"]):
            settings = Settings()
            self.assertEqual(settings.get("general", {}).get("timer"), "standard")

    def test_cli_custom_preset(self):
        # CLI -t fifty_ten overrides config
        with patch("sys.argv", ["pomlock", "-t", "fifty_ten"]):
            settings = Settings()
            self.assertEqual(settings.get("general", {}).get("timer"), "fifty_ten")

    def test_config_timer_default(self):
        # Without CLI arg, timer should use config value
        with patch("sys.argv", ["pomlock"]):
            settings = Settings()
            self.assertEqual(settings.get("general", {}).get("timer"), "ultradian")

    def test_cli_custom_values(self):
        # Custom timer values passed via CLI
        with patch("sys.argv", ["pomlock", "-t", "25 5 15 4"]):
            settings = Settings()
            self.assertEqual(settings.get("general", {}).get("timer"), "25 5 15 4")

    def test_cli_block_input_flag(self):
        # CLI flag overrides config boolean
        with patch("sys.argv", ["pomlock", "--block-input"]):
            settings = Settings()
            self.assertTrue(settings.get("general", {}).get("block_input"))
