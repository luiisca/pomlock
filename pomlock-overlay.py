#!/usr/bin/env python3
import sys
import time
import subprocess
from tkinter import Tk, Label, font

# Default overlay configuration
config = {
    'font_size': 48,
    'color': 'white',
    'bg_color': 'black',
    'opacity': 0.8,
    'notify': True,
    'notify_msg': 'Time for a break!'
}

# TODO: parse duration fn
def parse_args():
    args = sys.argv[1:]
    duration = 300
    if args and args[0].isdigit():
        duration = int(args[0])
        args = args[1:]
    
    for arg in args:
        if '=' in arg:
            key, value = arg.split('=', 1)
            key = key.lstrip('-').replace('-', '_')
            if key in config:
                if key in ['font_size', 'opacity']:
                    config[key] = float(value)
                else:
                    config[key] = value
    return duration

DURATION = parse_args()

if config['notify']:
    subprocess.Popen(['notify-send', config['notify_msg']])

root = Tk()
root.attributes('-fullscreen', True)
root.attributes('-alpha', config['opacity'])
root.configure(background=config['bg_color'])
root.attributes('-topmost', True)

label_font = font.Font(family="Helvetica", size=int(config['font_size']))
Label(root, text="", fg=config['color'], bg=config['bg_color'], font=label_font).pack(expand=True)
label = Label(root, text="", fg='white', bg='black', font=label_font)
label.pack(expand=True)

start_time = time.time()

def update_timer():
    remaining = DURATION - (time.time() - start_time)
    if remaining <= 0:
        root.destroy()
        return
    mins, secs = divmod(int(remaining), 60)
    label.config(text=f"BREAK TIME\n{mins:02}:{secs:02}")
    root.after(1000, update_timer)

update_timer()
root.mainloop()
