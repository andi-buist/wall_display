import json

from .core import *

class EntityButton(EntityWidget):
    def __init__(self, master,
                 command: callable, 
                 entity_type: str | list[str] = None, entity_id: str | list[str] = None, 
                 initial_state: bool = True,
                 state_channel: str | list[str] = [],
                 **kwargs):
        EntityWidget.__init__(self = self, master = master, widget_name = "entity_button",
                              entity_type = entity_type, entity_id = entity_id, 
                              initial_state = initial_state,
                              state_channel = state_channel,
                              **kwargs)

        try: self.command = command
        except: raise KeyError("EntityButton requires a command to perform on click")
    
    def construct_widget(self, entity_id: str, entity: dict):
        return ttk.Button(self,
                          text = entity['attributes']['friendly_name'],
                          command = lambda: self.command(self, entity_id),
                          width = 30)