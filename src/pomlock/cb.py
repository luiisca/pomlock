#!/usr/bin/env python3
import sys
import json
import datetime
from pathlib import Path

# A simple log file in the same directory as the script
log_file_path = Path(__file__).parent / "cb.log"

with open(log_file_path, "a") as f:
    f.write(f"--- Callback triggered at {datetime.datetime.now()} ---\n")
    
    # The JSON data is the last argument
    if len(sys.argv) > 1:
        f.write("Arguments received:\n")
        f.write(sys.argv[1])
        f.write("\n")
        try:
            # You can also parse and use the data
            data = json.loads(sys.argv[1])
            f.write(f"Action: {data.get('action')}\n")
            f.write(f"Time: {data.get('time')} minutes\n")
        except json.JSONDecodeError:
            f.write("Error: Could not decode JSON data.\n")
    else:
        f.write("No arguments received.\n")
    
    f.write("--- END ---\n\n")