import sys
from tkinter import *
from time import sleep, time


class Fullscreen_Window:

    def __init__(self):
        self.tk = Tk()
        self.tk.attributes("-fullscreen", True)
        # This just maximizes it so we can see the window. It's nothing to do with fullscreen.
        self.frame = Frame(self.tk)
        self.frame.pack()
        self.state = False
        self.tk.bind("<F11>", self.toggle_fullscreen)
        # self.tk.bind("<Escape>", self.end_fullscreen)

    def toggle_fullscreen(self):
        self.tk.attributes("-fullscreen", True)
        return "break"

    def end_fullscreen(self, event=None):
        self.state = False
        self.tk.attributes("-fullscreen", False)
        return "break"


if __name__ == '__main__':
    w = Fullscreen_Window()
    # w.tk.after(10, w.toggle_fullscreen)
    w.tk.mainloop()
