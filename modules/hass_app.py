from websocket import *
import threading
import tkinter as tk
import queue

from modules.websocket_defs import *
from modules.entity_widgets.core import *

class HASSApp(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.state_change_queue = queue.Queue()
        
        #start connections to sockets, UIDS 2,3
        threading.Thread(target = lambda socket_uid = 2: all_entities_socket(socket_uid, self.entity_dict_refresh)).start()
        threading.Thread(target = lambda socket_uid = 2: state_change_socket(socket_uid, self.queue_state_changes)).start()
    
    """-----Heavy Refresh Functions-----"""
    #the "heavy" refresh on_message, as opposed to the "light" refresh
    def entity_dict_refresh(self, message: dict):
        for child in self.get_all_children(self):
            if isinstance(child, EntityWidget):
                child.entity_dict_handler(message['result'])
        # #then update
        self.update()
    """-----End-----"""

    """-----Light Refresh Functions-----"""
    #called by the init connection to push state changes into state_change_queue on_message
    def queue_state_changes(self, message):
        if message['type'] == "event":
            self.state_change_queue.put(message['event']['data']['new_state'])
    
    #periodic check of the state_change_queue
    def state_change_periodic_check(self, period: int):
        try:
            self.state_refresh(self.state_change_queue.get(False)) # non-blocking
        except queue.Empty:
            pass
        finally:
            self.after(period, self.state_change_periodic_check, period)
    
    #the "light" refresh on_message, as opposed to the "heavy" refresh
    def state_refresh(self, message: dict):
        for child in self.get_all_children(self):
            if isinstance(child, EntityWidget):
                child.state_change_handler(message)
        #then update
        self.update()
    """-----End-----"""
    
    def get_all_children(self, widget, finList=None):
        finList = finList or []
        children = widget.winfo_children()
        for item in children:
            finList.append(item)
            self.get_all_children(item, finList)
        return finList