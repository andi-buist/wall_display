from .core import *
from ..caching import *
from ..websocket_defs import ThreadedWebsocket

class EntitySlider(EntityWidget):
    def __init__(self, master, local_ws: ThreadedWebsocket,
                 entity_type: str | list[str] = None, entity_id: str | list[str] = None, 
                 state_channel: str | list[str] = [],
                 **kwargs):
        EntityWidget.__init__(self=self, master=master, widget_name="entity_slider",
                              entity_type=entity_type, entity_id=entity_id, 
                              state_channel=state_channel,
                              **kwargs)
        self.local_ws = local_ws
    
    def construct_widget(self, entity_id: str, entity: dict):
        slider = ttk.Scale(self,
                           from_ = 255,
                           to = 0,
                           orient = (self.kwargs.get('orient')),
                           length = 70)
        
        #pull cached value if exists
        _init_value = entity_cache_read(entity_id, 'value', entity['attributes']['brightness'] if entity['state'] == "on" else 0)
        
        if _init_value is None:
            _init_value = 255

        slider.set(_init_value)
        slider.bind("<ButtonRelease-1>", lambda event, entity_id = entity_id: self.interactive_function(event, entity_id))
        return slider

    def interactive_function(self, event, entity_id):
        """The function used by default when the element created by make_interactive() is called."""
        value = int(event.widget.get())

        #if entity in cache, overwrite value, else make entity dict
        entity_cache_write(entity_id, 'value', value)

        msg_template = dict(type = "call_service",
                            domain = "light",
                            service = "turn_on",
                            service_data = dict(brightness = value),
                            target = dict(entity_id = entity_id))

        self.local_ws.send(msg_template)