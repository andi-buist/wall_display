import tkinter as tk
import tkinter.ttk as ttk

global_font = ('Nintendo DS BIOS', 12)

def CreateStyle():
    style = ttk.Style()
    style.configure('.',  font = global_font)
    style.configure('.', fg = "#000000", bg = "#ffffff")

    style.configure('EntityWidget.TFrame',
                    foreground = "#000000",
                    background = "#ffffff",
                    borderwidth = 10,
                    font = global_font)

    return style