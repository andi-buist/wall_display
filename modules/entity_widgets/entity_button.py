import json

from .core import *

class EntityButton(EntityWidget):
    def __init__(self, master, client, command: callable, entity_type: str | list[str] = None, entity_id: str | list[str] = None, **kwargs):
        EntityWidget.__init__(self, master, "entity_button", client, entity_type, entity_id, **kwargs)

        try: self.command = command
        except: raise KeyError("EntityButton requires a command to perform on click")
    
    def construct_widget(self, entity_id: str, entity: dict):
        return ttk.Button(self,
                          text = entity['attributes']['friendly_name'],
                          command = lambda: self.command(self, entity_id),
                          width = 30)