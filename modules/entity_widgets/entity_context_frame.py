from .core import *
from theme import *
from modules.websocket_defs import *

class ContextFrame(ttk.Frame):
    def __init__(self, master, **kwargs):
        ttk.Frame.__init__(self, master, **kwargs)
        
        self.notebook = ttk.Notebook(self, style = 'ContextFrame.TNotebook')

        self.tab_id: dict[str: int] = {}

    def add_widget(self, id: str, widget: EntityWidget):
        self.notebook.add(widget)
        self.tab_id[id] = len(self.notebook.tabs()) - 1
        pub.subscribe(self.select_listener, id)
    
    def select_listener(self, state: bool, context_id: str):
        if context_id is not None:
            self.notebook.select(self.tab_id[context_id])
        
        if state:
            self.notebook.pack()
        else:
            self.notebook.pack_forget()