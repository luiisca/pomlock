import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pomlock.instance_lock import InstanceLock, _focus_x11, read_status


class TestInstanceLock(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lock_path = Path(self.temp_dir.name) / "pomlock.lock"
        self.state_path = Path(self.temp_dir.name) / "pomlock.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_second_lock_is_rejected_until_owner_releases(self):
        owner = InstanceLock(self.lock_path)
        contender = InstanceLock(self.lock_path)

        self.assertTrue(owner.acquire())
        self.assertFalse(contender.acquire())

        owner.release()
        self.assertTrue(contender.acquire())
        contender.release()

    def test_lock_metadata_contains_owner_pid(self):
        lock = InstanceLock(self.lock_path)

        self.assertTrue(lock.acquire())
        metadata = json.loads(self.lock_path.read_text())

        self.assertEqual(metadata["pid"], lock.pid)
        lock.release()

    def test_read_status_returns_empty_for_invalid_state(self):
        self.state_path.write_text("not json")

        self.assertEqual(read_status(self.state_path), "")

    def test_read_status_formats_active_timer(self):
        self.state_path.write_text(json.dumps({
            "action": "pomodoro",
            "time": 25,
            "state": "running",
        }))

        self.assertEqual(read_status(self.state_path), "pomodoro: 25m (running)")

    @patch("pomlock.instance_lock._run")
    @patch("pomlock.instance_lock.shutil.which", return_value="/usr/bin/xdotool")
    def test_x11_focus_uses_matching_owner_window(self, _which, run):
        run.side_effect = ["42\n", ""]

        self.assertTrue(_focus_x11([123]))
        self.assertEqual(run.call_args_list[0].args, ("xdotool", "search", "--pid", "123"))
        self.assertEqual(run.call_args_list[1].args, ("xdotool", "windowactivate", "--sync", "42"))
