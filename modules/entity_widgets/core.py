import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import paho.mqtt.client as mqtt
import traceback
from pubsub import *

class EntityWidget(tk.Widget):
    def __init__(self, master, widget_name, client: mqtt.Client,
                 entity_type: str | list[str] = None, entity_id: str | list[str] = None, 
                 initial_state: bool = True,
                 foreach: bool = True, state_channel: str | list[str] = [],
                 **kwargs):
        ttk.Frame.__init__(self, master)
        #pass alongs
        self.kwargs = kwargs
        self.foreach = foreach

        #the mqtt client
        self.client = client

        #pubsub messaging system - state
        if not isinstance(state_channel, list):
            state_channel = [state_channel]
        for channel in state_channel:
            print(channel)
            pub.subscribe(self.state_listener, channel)

        #the latest message set by MQTTWindow
        self.latest_msg = None
        #the initial entity types and ids
        self.entity_type = entity_type
        self.entity_id = entity_id
        #the up-to-date entity dictionary
        self.entity_dict = {}

        #the widget to be instanced
        self.widget: tk.Misc = None

        #is the widget visible?
        self.state: bool = initial_state

        #note: __init__ should not explicitly call build(). build() is coordinated 
        # by the HASSEngine in what's called "lazy loading", 
        # only making the resource once entity_dict is available

    def update_entity_dict(self):
        self.entity_dict = self.get_target_entities()
    
    #creates the object described in construct widget, assigns it to attr in self, then packs
    #will destroy stale widgets and instance new ones based on data in self
    #this should be called in all cases where self needs refresh but not necessarily everything does
    def build(self, **kwargs):
        """Rebuilds this widget without erasing its attributes! kwargs will happily pass to construct_widget()"""
        try:
            for child in self.winfo_children():
                child.destroy()
            
            if len(self.entity_dict) > 0:
                if self.state:
                    if self.foreach:
                        for entity_id, entity in self.entity_dict.items():
                            widget = self.construct_widget(entity_id, entity, **kwargs)
                            widget.pack()
                    else:
                        widget = self.construct_widget(None, self.entity_dict, **kwargs)
                        widget.pack()
            else:
                ttk.Label(self, text="Loading...").pack()
        except Exception as e:
            #create and format debug image, add details to label, pack in place of broken widget
            debug_image = Image.open("./theme/ui/img/ill_capy.png")
            debug_image = debug_image.resize((300,300), resample= Image.Resampling.NEAREST)
            debug_image = debug_image.convert('1')
            debug_image = ImageTk.PhotoImage(debug_image)

            debug_placeholder = ttk.Label(self, image=debug_image)
            debug_placeholder.image = debug_image
            debug_placeholder.pack()

            debug_label = ttk.Label(self, text="Something went wrong...\nError Details: " + traceback.format_exc() +"\nRaised by: " + str(self))
            debug_label.pack()
            
    
    def construct_widget(self, entity_id: str, entity: dict):
        return ttk.Label(self,
                         text = entity['attributes']['friendly_name'])

    def get_target_entities(self):
        msg_json = self.latest_msg

        #create sub-array from all the desired items in payload
        if self.entity_type is not None:
            msg_json = [i for i in msg_json if i['entity_id'].split(".")[0] in self.entity_type]
        if self.entity_id is not None:
            msg_json = [i for i in msg_json if i['entity_id'] in self.entity_id]
        
        msg_json = dict(zip([x['entity_id'] for x in msg_json], msg_json))

        return msg_json
    
    #will set the state of the EntityWidget to the 'state' value of the incoming message, then rebuild
    def state_listener(self, state: bool):
        self.state = state
        self.build()