import tkinter as tk
from tkinter import ttk
import requests
from io import BytesIO
import webcolors
import json

from .widget_core import *
from ..caching import *
from modules.websocket_defs import ThreadedWebsocket

global xkcd_colours

with BytesIO(requests.get("https://xkcd.com/color/rgb.txt").content) as file:
#remove 1st entry as this is the title, license, etc.
    xkcd_colours = dict([tuple(line.decode('utf-8').split("\t")[0:2]) for line in file][1:])

class EntityRGBSpinners(HASSWidget):
    def __init__(self, master, local_ws: ThreadedWebsocket,
                 entity_type: str | list[str] = None, entity_id: str | list[str] = None, 
                 state_channel: str | list[str] = [],
                 **kwargs):
        HASSWidget.__init__(self=self, master=master, widget_name="entity_rgb_spinner",
                              entity_type=entity_type, entity_id=entity_id, 
                              state_channel=state_channel,
                              **kwargs)
        self.local_ws = local_ws

    def construct_widget(self, entity_id: str, entity: dict):
        if entity['state'] == "on":
            self.rgb = entity_cache_read(entity_id, 'rgb', tuple(round(x/255 * 7) for x in entity['attributes']['rgb_color']))

            _init_value = entity_cache_read(entity_id, 'value', entity['attributes']['brightness'])

            _value_adjusted_colour =  self.get_value_adjusted_colour(self.rgb, _init_value)
            self.label_text = entity['attributes']['friendly_name'] + ": " + self.get_colour_name(_value_adjusted_colour).upper()
        else:
            self.rgb = (0,0,0)
            self.value = 0

            self.label_text = entity['attributes']['friendly_name'] + " is offline..."

        widget = ttk.Frame(self, style = 'EntityWidget.TFrame')
        
        self.top_label = ttk.Label(widget,
                                    text = self.label_text,
                                    style = 'EntityWidget.TLabel')

        self.red_channel = tk.Frame(widget, bg = self.rgb_to_bg(0), width = 64, height = 64)
        self.green_channel = tk.Frame(widget, bg = self.rgb_to_bg(1), width = 64, height = 64)
        self.blue_channel = tk.Frame(widget, bg = self.rgb_to_bg(2), width = 64, height = 64)
        
        self.top_label.grid(row=0, columnspan=3)
        self.red_channel.grid(column=0,row=2)
        self.green_channel.grid(column=1,row=2)
        self.blue_channel.grid(column=2,row=2)

        ttk.Button(widget, style = 'EntityWidget.TButton', command = lambda x=1, entity_id = entity_id, entity = entity: self.increment_channel(0,x, entity_id, entity)).grid(column=0,row=1)
        ttk.Button(widget, style = 'EntityWidget.TButton', command = lambda x=-1, entity_id = entity_id, entity = entity: self.increment_channel(0,x, entity_id, entity)).grid(column=0,row=3)
        ttk.Button(widget, style = 'EntityWidget.TButton', command = lambda x=1, entity_id = entity_id, entity = entity: self.increment_channel(1,x, entity_id, entity)).grid(column=1,row=1)
        ttk.Button(widget, style = 'EntityWidget.TButton', command = lambda x=-1, entity_id = entity_id, entity = entity: self.increment_channel(1,x, entity_id, entity)).grid(column=1,row=3)
        ttk.Button(widget, style = 'EntityWidget.TButton', command = lambda x=1, entity_id = entity_id, entity = entity: self.increment_channel(2,x, entity_id, entity)).grid(column=2,row=1)
        ttk.Button(widget, style = 'EntityWidget.TButton', command = lambda x=-1, entity_id = entity_id, entity = entity: self.increment_channel(2,x, entity_id, entity)).grid(column=2,row=3)
        
        return widget
        
    def increment_channel(self, channel: int, amount: int, entity_id: str, entity: dict):
        if entity['state'] == "on":
            #open rgb 
            _rgb = list(self.rgb)
            #tick up/down by amount, clamp to 0-7
            _rgb[channel] = min(max(self.rgb[channel] + amount, 0),7)

            #set class rgb
            self.rgb = tuple(_rgb)

            _value_adjusted_colour = self.get_value_adjusted_colour(self.rgb, entity['attributes']['brightness'])

            #set parent frame bg and change text
            self.top_label['text'] = entity['attributes']['friendly_name'] + ": " + self.get_colour_name(_value_adjusted_colour).upper()
            match channel:
                case 0: self.red_channel['bg'] = self.rgb_to_bg(channel)
                case 1: self.green_channel['bg'] = self.rgb_to_bg(channel)
                case 2: self.blue_channel['bg'] = self.rgb_to_bg(channel)
            
            entity_cache_write(entity_id, 'rgb', self.rgb)
            self.change_entity_colour(entity_id)

    def change_entity_colour(self, entity_id: str):
        target_colour = tuple(round(x/7 * 255) for x in self.rgb)

        msg_template = dict(type = "call_service",
                            domain = "light",
                            service = "turn_on",
                            service_data = dict(rgb_color = target_colour, brightness = max(target_colour)),
                            target = dict(entity_id = entity_id))

        self.local_ws.send(msg_template)

    def rgb_to_bg(self, index:int = None):
        if index is not None:
            _fraction = self.rgb[index]/7
            _channel_strength = 255 - round(255 * _fraction)
            return '#%02x%02x%02x' % (_channel_strength, _channel_strength, _channel_strength)
        else:
            _channel_strength = tuple(round(255 * x/7) for x in self.rgb)
            return '#%02x%02x%02x' % _channel_strength
    
    def get_value_adjusted_colour(self, rgb, value):
        return tuple(round(x/(max(rgb)) * value) if max(rgb) else 0 for x in rgb)

    def get_colour_name(self, requested_colour):
        distances = {}
        for name in xkcd_colours.keys():
            r_c, g_c, b_c = webcolors.hex_to_rgb(xkcd_colours[name])
            rd = (r_c - requested_colour[0]) ** 2
            gd = (g_c - requested_colour[1]) ** 2
            bd = (b_c - requested_colour[2]) ** 2
            distances[name] = rd + gd + bd
        return min(distances, key=distances.get)