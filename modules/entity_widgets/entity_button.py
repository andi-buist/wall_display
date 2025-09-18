import json

from .core import *
from modules.websocket_defs import *

class EntityButton(EntityWidget):
    def __init__(self, master, local_ws: ThreadedWebsocket,
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
        self.local_ws = local_ws

        try: self.command = command
        except: raise KeyError("EntityButton requires a command to perform on click")
    
    def construct_widget(self, entity_id: str, entity: dict):
        return ttk.Button(self,
                          text = entity['attributes']['friendly_name'],
                          command = lambda: self.command(self, entity_id),
                          width = 30)
    
    def light_switch(self, entity_id):
        entity = self.entity_dict[entity_id]

        msg_template = dict(type = "call_service",
                            domain = "light",
                            target = dict(entity_id = entity_id))
        #for messages that would return a response, include return_response = True

        if entity['state'] == "on":
            msg_template['service'] = "turn_off"
        else:
            msg_template['service'] = "turn_on"
            msg_template['service_data'] = dict(brightness = 255)

        self.local_ws.send(msg_template)