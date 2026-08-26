import json
import os
import unittest
from unittest.mock import MagicMock, call, mock_open, patch

import pomlock.input_handler as ih
from pomlock.input_handler import (
    DeviceState,
    disable_input_devices,
    enable_input_devices,
    get_input_devices,
)


MOCK_PROC_BUS_INPUT_DEVICES = """
I: Bus=0011 Vendor=0001 Product=0001 Version=ab83
N: Name="AT Translated Set 2 keyboard"
P: Phys=isa0060/serio0/input0
S: Sysfs=/devices/platform/i8042/serio0/input/input3
U: Uniq=
H: Handlers=sysrq kbd leds event3 
B: PROP=0
B: EV=120013
B: KEY=402000007 ff803078f800d001 feffffdfffcfffff fffffffffffffffe
B: MSC=10
B: LED=7

I: Bus=0019 Vendor=0000 Product=0001 Version=0000
N: Name="Power Button"
P: Phys=LNXPWRBN/button/input0
S: Sysfs=/devices/platform/LNXPWRBN:00/input/input2
U: Uniq=
H: Handlers=kbd event2 
B: PROP=0
B: EV=3
B: KEY=8000 10000000000000 0

I: Bus=0003 Vendor=046d Product=4054 Version=0111
N: Name="Logitech Wireless Mouse"
P: Phys=usb-0000:00:14.0-1/input1:2
S: Sysfs=/devices/pci0000:00/0000:00:14.0/usb1/1-1/1-1:1.1/0003:046D:C534.0002/0003:046D:4054.0005/input/input35
U: Uniq=00-00-00-00
H: Handlers=kbd event5 mouse0 
B: PROP=0
B: EV=1f
B: KEY=3f00733fff 0 0 483ffff17aff32d bfd4444600000000 ffff0001 130ff38b17d000 677bfad9415fed 19ed68000004400 10000002
B: REL=1943
B: ABS=100000000
B: MSC=10
"""


class TestInputHandler(unittest.TestCase):

    def setUp(self):
        ih._active_evdev_fds.clear()
        ih._active_hypr_devs.clear()

    def tearDown(self):
        ih._active_evdev_fds.clear()
        ih._active_hypr_devs.clear()

    def test_device_discovery(self):
        with patch("builtins.open", mock_open(read_data=MOCK_PROC_BUS_INPUT_DEVICES)):
            devices = get_input_devices()

        self.assertIn("/dev/input/event3", devices)
        self.assertIn("/dev/input/event5", devices)
        self.assertNotIn("/dev/input/event2", devices)

    @patch("pomlock.input_handler.os.open", return_value=42)
    @patch("pomlock.input_handler.fcntl.ioctl")
    @patch("pomlock.input_handler.get_input_devices", return_value=["/dev/input/event3"])
    def test_disable_evdev(self, mock_get_devs, mock_ioctl, mock_open_fd):
        disable_input_devices()
        self.assertEqual(len(ih._active_evdev_fds), 1)
        self.assertEqual(ih._active_evdev_fds[0], ("/dev/input/event3", 42))
        mock_ioctl.assert_called_once_with(42, ih.EVIOCGRAB, 1)

    @patch("pomlock.input_handler.os.close")
    @patch("pomlock.input_handler.fcntl.ioctl")
    def test_enable_evdev(self, mock_ioctl, mock_close):
        ih._active_evdev_fds.append(("/dev/input/event3", 42))
        enable_input_devices()
        self.assertEqual(len(ih._active_evdev_fds), 0)
        mock_ioctl.assert_called_once_with(42, ih.EVIOCGRAB, 0)
        mock_close.assert_called_once_with(42)

    @patch("pomlock.input_handler.subprocess.run")
    def test_hyprland_state(self, mock_subproc):
        devices = ["test-keyboard", "test-mouse"]
        ih._set_hypr_state(devices, DeviceState.DISABLE)
        mock_subproc.assert_has_calls([
            call(["hyprctl", "keyword", "device[test-keyboard]:enabled", "0"], capture_output=True, check=True),
            call(["hyprctl", "keyword", "device[test-mouse]:enabled", "0"], capture_output=True, check=True),
        ])


if __name__ == "__main__":
    unittest.main()
