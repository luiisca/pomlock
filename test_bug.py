import subprocess
import time
import os
import sys
from pathlib import Path

# Function to send 's' key using evdev
def send_key_s():
    try:
        import evdev
        from evdev import uinput, ecodes
        # Find a keyboard device
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        for dev in devices:
            # Check if the device has the KEY_S capability
            if ecodes.KEY_S in dev.capabilities().get(ecodes.EV_KEY, []):
                print(f"Found keyboard device: {dev.path} ({dev.name})")
                # Open the device for writing
                with evdev.UInput.from_device(dev, name=f"virtual-{dev.name}") as ui:
                    # Key press
                    ui.write(ecodes.EV_KEY, ecodes.KEY_S, 1)  # value 1 for key press
                    ui.syn()
                    # Key release
                    ui.write(ecodes.EV_KEY, ecodes.KEY_S, 0)  # value 0 for key release
                    ui.syn()
                return
        print("No keyboard device found with KEY_S")
    except Exception as e:
        print(f"Failed to send key via evdev: {e}")
        raise

# Set environment variables to avoid lock file conflicts and set display
tmp_dir = Path("/tmp/pomlock_test")
tmp_dir.mkdir(exist_ok=True)
env = os.environ.copy()
env["XDG_RUNTIME_DIR"] = str(tmp_dir)
# Ensure we have a display (assuming :0)
env["DISPLAY"] = ":0"

# Start pomlock process using uv run to have the same environment
cmd = ["uv", "run", "pomlock"]
print(f"Starting pomlock with command: {cmd}")
proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

# Give it time to start
time.sleep(3)

# Now send the 's' key to skip
print("Sending 's' key to skip...")
try:
    send_key_s()
except Exception as e:
    print(f"Failed to send key: {e}")
    proc.terminate()
    proc.wait()
    sys.exit(1)

# Wait a bit to see if the bug occurs
print("Waiting 10 seconds to observe behavior...")
time.sleep(10)

# Terminate the process
print("Terminating pomlock...")
proc.terminate()
proc.wait()

# Print the output
print("\n=== Pomlock output ===")
if proc.stdout:
    for line in proc.stdout:
        print(line, end='')

# Dump the log file
log_file = Path.home() / ".local" / "share" / "pomlock" / "pomlock.log"
if log_file.exists():
    print("\n=== Log file ===")
    print(log_file.read_text())
else:
    print("\n=== Log file not found ===")
