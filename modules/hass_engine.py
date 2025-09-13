import paho.mqtt.client as mqtt
import tkinter as tk
import json

from .entity_widgets.core import *

class HASSEngine():
    """Defines a class that can be queried for entity info & used to update the window."""
    def __init__(self, client: mqtt.Client, window: tk.Tk):
        self.client = client
        self.window = window

        self.client.loop_start()
        self.client.on_message = self.__on_refresh

        #initial publish to stock
        self.client.publish("system-entities-request")

    #refresh which updates latest_msg and then calls refresh, triggered by subscription messages
    def __on_refresh(self, _client, userdata, msg):
        """Generic function to destroy and repack"""
        #get incoming json msg.payload
        msg_json = json.loads(msg.payload)
        self.latest_msg = msg_json
        self.refresh()
    
    #refresh
    #note: probably never needs calling directly? try widget's build() first...
    def refresh(self):
        #erase existing children
        for child in self.get_all_children(self.window):
            if isinstance(child, EntityWidget):
                #cascade latest message to children
                child.latest_msg = self.latest_msg
                child.update_entity_dict()
                child.build()
        
        self.window.update()
    
    def get_all_children(self, widget, finList=None):
        finList = finList or []
        children = widget.winfo_children()
        for item in children:
            finList.append(item)
            self.get_all_children(item, finList)
        return finList