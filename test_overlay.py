import subprocess
import sys
import time

# Simulate break overlay start
break_title = "Long Break"
initial_remaining_s = 20  # 20 seconds for test
accent_color = "#b48ead"

cmd = [
    sys.executable,
    "-c",
    "from pomlock.ui.break_overlay import main; main()",
    "--title",
    break_title,
    "--remaining",
    str(initial_remaining_s),
    "--accent",
    accent_color,
]

print("Starting overlay subprocess:", " ".join(cmd))
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True, bufsize=1)

try:
    # Simulate TimerEngine sending updates every 0.2 seconds
    start = time.time()
    while time.time() - start < 10:  # run for 10 seconds
        remaining = max(0, initial_remaining_s - int(time.time() - start))
        proc.stdin.write(f"{remaining}\n")
        proc.stdin.flush()
        time.sleep(0.2)
    print("Finished sending updates")
except Exception as e:
    print(f"Error: {e}")
finally:
    proc.stdin.close()
    proc.wait()
    print(f"Overlay subprocess exited with code {proc.returncode}")
