from .core import *
from theme import *
from modules.websocket_defs import *

class ContextFrame(ttk.Frame):
    def __init__(self, master, persistent: bool = False, **kwargs):
        ttk.Frame.__init__(self, master, style = 'EntityWidget.TFrame', **kwargs)
        
        self.persistent = persistent

        self.notebook = ttk.Notebook(self, style = 'ContextFrame.TNotebook')

        self.tab_id: dict[str: int] = {}

    def add_widget(self, id: str, widget: EntityWidget, selected: bool = False, **kwargs):
        self.notebook.add(widget, **kwargs)
        self.tab_id[id] = len(self.notebook.tabs()) - 1
        pub.subscribe(self.select_listener, id)

        if selected:
            self.notebook.select(self.tab_id[id])
            self.notebook.pack()
    
    def select_listener(self, state: bool, context_id: str):
        if context_id is not None and context_id in self.tab_id.keys():
            self.notebook.select(self.tab_id[context_id])
        
        if not self.persistent:
            if state:
                self.notebook.pack()
            else:
                self.notebook.pack_forget()