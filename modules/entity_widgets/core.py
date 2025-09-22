import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import traceback
from pubsub import *
import pywinstyles

class EntityWidget(ttk.Frame):
    def __init__(self, master, widget_name,
                 entity_type: str | list[str] = None, entity_id: str | list[str] = None, 
                 initial_state: bool = True,
                 foreach: bool = True, state_channel: str | list[str] = [],
                 **kwargs):
        ttk.Frame.__init__(self, master, style = 'EntityWidget.TFrame')

        #pass alongs
        self.kwargs = kwargs
        self.foreach = foreach

        #pubsub messaging system - state
        if not isinstance(state_channel, list):
            state_channel = [state_channel]
        for channel in state_channel:
            pub.subscribe(self.state_listener, channel)

        #the initial entity types and ids
        self.entity_type = entity_type
        self.entity_id = entity_id
        #the up-to-date entity dictionary
        self.entity_dict_full = {}
        self.entity_dict = {}
        #is the widget visible?
        self.state: bool = initial_state

        #note: __init__ should never call build(). HassApp handles building.

    def entity_dict_handler(self, message:dict):
        self.entity_dict_full = {x['entity_id']: x for x in message}

        if self.entity_type is not None or self.entity_id is not None:
            filtered_messages = []
            for msg in self.entity_dict_full.values():
                prefix = msg['entity_id'].split(".")[0]
                if (self.entity_type is not None and prefix in self.entity_type) or (self.entity_id is not None and msg['entity_id'] in self.entity_id):
                    filtered_messages.append(msg)
            for msg in filtered_messages:
                self.entity_dict[msg['entity_id']] = msg
        else:
            self.entity_dict = self.entity_dict_full

        #if filtered_messages or (self.entity_type is None and self.entity_id is None):
        self.build()
    
    def state_change_handler(self, message: dict):
        if self.entity_type is not None and message['entity_id'].split(".")[0] in self.entity_type:
            self.entity_dict[message['entity_id']] = message
            self.build()
        elif self.entity_id is not None and message['entity_id'] in self.entity_id:
            self.entity_dict[message['entity_id']] = message
            self.build()
    
    #creates the object described in construct widget, assigns it to attr in self, then packs
    #will destroy stale widgets and instance new ones based on data in self
    #this should be called in all cases where self needs refresh but not necessarily everything does
    def build(self, **kwargs):
        """Rebuilds this widget without erasing its attributes! kwargs will happily pass to construct_widget()"""
        try:
            for child in self.winfo_children():
                child.destroy()
            
            widgets = []

            if len(self.entity_dict) > 0:
                #establish list of widgets
                if self.state:
                    if self.foreach:
                        for entity_id, entity in self.entity_dict.items():
                            widget = self.construct_widget(entity_id, entity, **kwargs)
                            widget.bind('<Button-3>', func = lambda event, s = self: print(event, s))
                            widgets.append(widget)
                    else:
                        widget = self.construct_widget(None, self.entity_dict, **kwargs)
                        widget.bind('<Button-3>', func = lambda event, s = self: print(event, s))
                        widgets.append(widget)
            
            for widget in widgets:
                widget.pack(fill = 'x', expand = True)
            

        except Exception as e:
            #create and format debug image, add details to label, pack in place of broken widget
            debug_image = Image.open("./theme/ui/img/broken_widget.png")
            debug_image = debug_image.resize((300,300), resample= Image.Resampling.NEAREST)
            debug_image = debug_image.convert('1')
            debug_image = ImageTk.PhotoImage(debug_image)

            debug_placeholder = ttk.Label(self, image=debug_image)
            debug_placeholder.image = debug_image
            debug_placeholder.pack()

            debug_label = ttk.Label(self, text="Something went wrong...\nError Details: " + traceback.format_exc() +"\nRaised by: " + str(self))
            debug_label.pack()

        # self.winfo_toplevel().update()
    
    def construct_widget(self, entity_id: str, entity: dict):
        return ttk.Label(self,
                         text = entity['attributes']['friendly_name'])
    
    #will set the state of the EntityWidget to the 'state' value of the incoming message, then rebuild
    def state_listener(self, state: bool, context_id: str):
        if state is not None:
            self.state = state
            self.build()
    