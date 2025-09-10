import tkinter as tk
from tkinter import ttk
from tkinter.colorchooser import askcolor

import webcolors
import colorsys

from PIL import Image, ImageTk, ImageFilter, ImageDraw
import requests
from io import BytesIO

import numpy as np

import paho.mqtt.client as mqtt
import json

global_font = ('Nintendo DS BIOS',12)

class HASSRenderer(ttk.Frame):
    """Defines a top-level ttk.Frame element containing sub elements at an appropriate entity-level. Re-rendered when system-entities is messaged."""

    def __init__(self, parent, interactive_element: ttk.Frame | tk.Frame, entity_type: str | list[str] = None, entity_id: str | list[str] = None, **kwargs):
        ttk.Frame.__init__(self, parent)

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.connect("192.168.0.180")
        self.client.subscribe("system-entities")
        self.client.loop_start()

        self.kwargs = kwargs
        self.entity_type = entity_type
        self.entity_id = entity_id

        self.interactive_element = interactive_element

        self.client.on_message = self.__on_refresh

        #initial publish to stock
        self.client.publish("system-entities-request")

 
    def __on_refresh(self, _client, userdata, msg):
        """Generic function to destroy and repack whatever is defined in __add_elements()."""

        #get incoming json msg.payload
        msg_json = json.loads(msg.payload)

        #create sub-array from all the desired items in payload
        if self.entity_type is not None:
            msg_json = [i for i in msg_json if i['entity_id'].split(".")[0] in self.entity_type]
        if self.entity_id is not None:
            msg_json = [i for i in msg_json if i['entity_id'] in self.entity_id]

        #erase existing children
        for child in self.winfo_children():
            child.destroy()

        #add new child for each relevant in msg
        for entity in msg_json:
            self.__add_elements(entity)
    
    def __add_elements(self, entity):
        """Creates a tkinter-compatible element at an entity-level, packing them in the parent ttk.Frame."""
        #attempt to pass kwargs if class accepts them, otherwise don't
        try:
            _interactive =  self.interactive_element(self, entity, **self.kwargs)
        except TypeError:
            _interactive =  self.interactive_element(self, entity)
        _interactive.pack()

class EntityButton(ttk.Frame):
    def __init__(self, parent: HASSRenderer, entity):
        ttk.Frame.__init__(self, parent)

        #set own client attribute to that of parent (HASSRenderer)
        self.client = parent.client
        self.entity = entity

        if self.entity['state'] == "on":
            _button_style = "Active.TButton"
        else:
            _button_style = "Inactive.TButton"

        _interactive = ttk.Button(self,
                                 text = entity['attributes']['friendly_name'],
                                 command = lambda: self.interactive_function(),
                                 width = 30)
        _interactive.pack()
    
    def interactive_function(self):
        """The function used by default when the element created by make_interactive() is called."""

        #get current state in order to perform toggle (not needed in most other scenarios)
        self.client.publish("system-entities-request")

        if self.entity['state'] == "on":
            msg_dict = {'action': "light.turn_off", 'entity_id': self.entity['entity_id']}
        else:
            msg_dict = {'action': "light.turn_on", 'entity_id': self.entity['entity_id'], 'data': {'brightness': 255}}

        self.client.publish("lights",json.dumps(msg_dict))

class EntitySlider(ttk.Frame):
    def __init__(self, parent: HASSRenderer, entity, **kwargs):
        ttk.Frame.__init__(self, parent)

        #pull parent into self to send cache before death
        self.parent = parent

        #set own client attribute to that of parent (HASSRenderer)
        self.client = parent.client
        self.entity = entity

        self.interactive = ttk.Scale(self,
                                 from_ = 255,
                                 to = 0,
                                 orient = (kwargs.get('orient')),
                                 length = 70)
        
        if hasattr(parent, "cached_value"):
            _init_value = parent.cached_value
        else:
            _init_value = entity['attributes']['brightness']
        
        if _init_value is None:
            _init_value = 255

        print(_init_value)
        self.interactive.set(_init_value)
        self.interactive.bind("<ButtonRelease-1>", self.interactive_function)
        self.interactive.pack(fill = 'y')

    def interactive_function(self, event):
        """The function used by default when the element created by make_interactive() is called."""

        #get current state in order to perform toggle (not needed in most other scenarios)
        self.client.publish("system-entities-request")

        action = 'light.turn_on'
        value = int(self.interactive.get())

        self.parent.cached_value = value

        msg_dict = {'action': action, 'entity_id': self.entity['entity_id'], 'data': {'brightness': value}}
        self.client.publish("lights",json.dumps(msg_dict))

class EntityRGBSpinners(ttk.Frame):
    def __init__(self, parent: HASSRenderer, entity):
        ttk.Frame.__init__(self, parent)

        #set own client attribute to that of parent (HASSRenderer)
        self.client = parent.client
        self.entity = entity

        if entity['state'] == "on":
            self.rgb = tuple(round(7 * x/255) for x in entity['attributes']['rgb_color'])
            self.label_text = self.__get_colour_name(tuple(round(255 * x/7) for x in self.rgb))
        else:
            self.rgb = (0,0,0)
            self.label_text = entity['attributes']['friendly_name'].lower() + " is offline..."

        _interactive = ttk.Frame(self)
        
        self.top_label = ttk.Label(_interactive,
                                    text = self.label_text)

        self.red_channel = tk.Frame(_interactive, bg = self.rgb_to_bg(0), width = 64, height = 64)
        self.green_channel = tk.Frame(_interactive, bg = self.rgb_to_bg(1), width = 64, height = 64)
        self.blue_channel = tk.Frame(_interactive, bg = self.rgb_to_bg(2), width = 64, height = 64)
        
        self.top_label.grid(row=0, columnspan=3)
        self.red_channel.grid(column=0,row=2)
        self.green_channel.grid(column=1,row=2)
        self.blue_channel.grid(column=2,row=2)

        ttk.Button(_interactive, command = lambda x=1: self.increment_channel(0,x)).grid(column=0,row=1)
        ttk.Button(_interactive, command = lambda x=-1: self.increment_channel(0,x)).grid(column=0,row=3)
        ttk.Button(_interactive, command = lambda x=1: self.increment_channel(1,x)).grid(column=1,row=1)
        ttk.Button(_interactive, command = lambda x=-1: self.increment_channel(1,x)).grid(column=1,row=3)
        ttk.Button(_interactive, command = lambda x=1: self.increment_channel(2,x)).grid(column=2,row=1)
        ttk.Button(_interactive, command = lambda x=-1: self.increment_channel(2,x)).grid(column=2,row=3)
        
        _interactive.pack()
        
    def increment_channel(self, channel: int, amount: int):
        if self.entity['state'] == "on":
            _rgb = list(self.rgb)
            _rgb[channel] = min(max(self.rgb[channel] + amount, 0),7)

            #set class rgb
            self.rgb = tuple(_rgb)

            #set parent frame bg and change text
            self.top_label['text'] = self.__get_colour_name(tuple(round(255 * x/7) for x in self.rgb))
            match channel:
                case 0: self.red_channel['bg'] = self.rgb_to_bg(channel)
                case 1: self.green_channel['bg'] = self.rgb_to_bg(channel)
                case 2: self.blue_channel['bg'] = self.rgb_to_bg(channel)
            
            self.change_entity_colour()

    def change_entity_colour(self):
        action = 'light.turn_on'
        target_colour = self.rgb
        msg_dict = {'action': action, 'entity_id': self.entity['entity_id'], 'data': {'rgb_color': target_colour}}
        self.client.publish("lights",json.dumps(msg_dict))

    def rgb_to_bg(self, index:int = None):
        if index is not None:
            _fraction = self.rgb[index]/7
            _channel_strength = 255 - round(255 * _fraction)
            return '#%02x%02x%02x' % (_channel_strength, _channel_strength, _channel_strength)
        else:
            _channel_strength = tuple(round(255 * x/7) for x in self.rgb)
            return '#%02x%02x%02x' % _channel_strength
    
    def __get_colour_name(self, requested_colour):
        distances = {}
        for name in webcolors.names():
            r_c, g_c, b_c = webcolors.name_to_rgb(name)
            rd = (r_c - requested_colour[0]) ** 2
            gd = (g_c - requested_colour[1]) ** 2
            bd = (b_c - requested_colour[2]) ** 2
            distances[name] = rd + gd + bd
        return min(distances, key=distances.get)

class EntityImage(ttk.Frame):
    def __init__(self, parent: HASSRenderer, entity, **kwargs):
        ttk.Frame.__init__(self, parent)

        #set own client attribute to that of parent (HASSRenderer)
        self.client = parent.client
        self.entity = entity

        _size = kwargs.get('size')
        if _size is None: raise KeyError("kwarg 'size' expected for class EntityImage")

        image = Image.open(BytesIO(requests.get("http://192.168.0.180:8123" + entity['attributes']['entity_picture']).content))
        image = image.resize((_size, _size), resample= Image.Resampling.NEAREST)
        image = image.convert('1')
        image = self.crop_to_circle(image)

        photo_image = ImageTk.PhotoImage(image)
        _interactive = ttk.Label(self, image = photo_image)
        _interactive.image = photo_image
        _interactive.pack()
    
    def crop_to_circle(self, image: Image.Image):
        mask = Image.new('L', image.size)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0,0, image.size[0], image.size[1]), fill=255)

        return Image.composite(image, Image.new('RGBA', image.size, (255,255,255,0)), mask)

"""
App Definition
"""
window = tk.Tk()
window.title("Example")
window.geometry("480x300")

style = ttk.Style()
#must come before .configure
style.theme_use('default')

#configure style
style.configure('.',  font = global_font)
style.configure('Active.TButton', relief = 'sunken')
style.configure('Inactive.TButton', relief = 'raised')

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect("192.168.0.180")
client.subscribe("system-entities")
client.loop_start()

notebook = ttk.Notebook(master = window)

light_menu = ttk.Frame(style = 'Wrapper.TFrame')
map_menu = ttk.Labelframe()

notebook.add(light_menu)
notebook.add(map_menu)
notebook.tab(0, text = "Lighting")
notebook.tab(1, text = "Map")
notebook.pack(side = tk.RIGHT,
              fill = 'y')

lights = HASSRenderer(light_menu, EntityButton, entity_type='light')
lights.grid(row = 0, columnspan = 2)

brightness = HASSRenderer(light_menu, EntitySlider, entity_id = 'light.desk_light', orient = 'vertical')
brightness.grid(column = 0, row = 1, ipadx = 10)
rgb = HASSRenderer(light_menu, EntityRGBSpinners, entity_id = 'light.desk_light')
rgb.grid(column = 1, row = 1)

im = HASSRenderer(map_menu, EntityImage, entity_id='person.josh', size = 128)
im.place(relx = 0.5, rely = 0.5, anchor = 'center')

window.mainloop()