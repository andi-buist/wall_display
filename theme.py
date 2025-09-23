import tkinter as tk
import tkinter.ttk as ttk

global_font = ('Nintendo DS BIOS', 12)

def CreateStyle():
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('.',  font = global_font)
    style.configure('.', fg = "#000000", bg = "#ffffff")
    
    style.configure('EntityWidget.TFrame',
                    foreground = "#000000",
                    background = "#ffffff",
                    expand = True)
    
    style.configure('EntityWidget.TButton',
                    foreground = "#000000",
                    background = "#ffffff")
    
    style.configure('EntityWidget.Vertical.TScale',
                    foreground = "#000000",
                    troughcolor = "#555555",
                    background = "#ffffff")
    style.configure('EntityWidget.Horizontal.TScale',
                    foreground = "#000000",
                    background = "#ffffff")
    
    style.configure('EntityWidget.TLabel',
                    foreground = "#000000",
                    background = "#ffffff")
    
    style.configure('AppStyle.TNotebook',
                    foreground = "#000000",
                    background = "#ffffff",
                    bordercolor = "#000000",
                    tabmargins = [0,0,0,0])
    style.configure('AppStyle.TNotebook.Tab',
                    bordercolor = "#000000")
    style.map('AppStyle.TNotebook.Tab',
              foreground=[("selected", "#ffffff"),("", "#000000")],
              background=[("selected", "#000000"),("", "#ffffff")])

    style.configure('ContextFrame.TNotebook',
                    foreground = "#000000",
                    background = "#ffffff",
                    bordercolor = "#ffffff",
                    relief = 'flat')
    style.layout('ContextFrame.TNotebook.Tab', [])

    return style