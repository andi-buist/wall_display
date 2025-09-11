import tkinter as tk
from tkinter import ttk

import requests
from io import BytesIO

import threading

from PIL import Image, ImageTk, ImageDraw

import webcolors

import matplotlib
matplotlib.use('agg') # permits starting matplotlib contexts in classes (EntityMapSnap)
import matplotlib.pyplot as plt

from adjustText import adjust_text

from cartopy import crs as ccrs
from cartopy import feature as cfeature
from cartopy.io import img_tiles as ctiles

import math

import paho.mqtt.client as mqtt
import json

global_font = ('Nintendo DS BIOS',12)

global_entity_cache = {}

def entity_cache_write(entity_id: str, key: str, value):
    """Assigns the specified value to the key of an entity_id dictionary in the global_entity_cache."""
    if entity_id in global_entity_cache.keys():
        global_entity_cache[entity_id][key] = value
    else:
        global_entity_cache[entity_id] = {key: value}

def entity_cache_read(entity_id: str, key: str, fallback):
    """Gets the value of the specified key from the entity_id dictionary of the global_entity_cache. If there's nothing there, it returns fallback."""
    #pull cached value if exists
    if entity_id in global_entity_cache.keys() and key in global_entity_cache[entity_id]:
        return global_entity_cache[entity_id][key]
    else:
        return fallback

with BytesIO(requests.get("https://xkcd.com/color/rgb.txt").content) as file:
    #remove 1st entry as this is the title, license, etc.
    xkcd_colours = dict([tuple(line.decode('utf-8').split("\t")[0:2]) for line in file][1:])

class HASSEngine():
    """Defines a class that can be queried for entity info & used to update the window."""
    def __init__(self, client: mqtt.Client, window: tk.Tk):
        self.client = client
        self.window = window

        self.client.loop_start()
        self.client.on_message = self.__on_refresh

        #initial publish to stock
        self.client.publish("system-entities-request")
        #threading.Event().wait(1)

 
    def __on_refresh(self, _client, userdata, msg):
        """Generic function to destroy and repack"""
        #get incoming json msg.payload
        msg_json = json.loads(msg.payload)

        #erase existing children
        for child in self.get_all_children(self.window):
            if isinstance(child, EntityWidget):
                child.latest_msg = msg_json
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

class EntityWidget(tk.Widget):
    def __init__(self, master, widget_name, client: mqtt.Client, entity_type: str | list[str] = None, entity_id: str | list[str] = None, foreach: bool = True, **kwargs):
        ttk.Frame.__init__(self, master)
        #pass alongs
        self.kwargs = kwargs
        self.foreach = foreach

        #the mqtt client
        self.client = client

        #the latest message set by HASSEngine
        self.latest_msg = None

        #the initial entity types and ids
        self.entity_type = entity_type
        self.entity_id = entity_id

        #the up-to-date entity dictionary
        self.entity_dict = {}

        #the widget to be instanced
        self.widget: tk.Misc = None

        self.build()

    def update_entity_dict(self):
        self.entity_dict = self.get_target_entities()
    
    def build(self):
        for child in self.winfo_children():
            child.destroy()
        
        if len(self.entity_dict) > 0:
            if self.foreach:
                for entity_id, entity in self.entity_dict.items():
                    widget = self.construct_widget(entity_id, entity)
                    widget.pack()
            else:
                widget = self.construct_widget(None, self.entity_dict)
                widget.pack()
    
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

class EntityButton(EntityWidget):
    def __init__(self, master, client, entity_type: str | list[str] = None, entity_id: str | list[str] = None, **kwargs):
        EntityWidget.__init__(self, master, "entity_button", client, entity_type, entity_id, **kwargs)
    
    def construct_widget(self, entity_id: str, entity: dict):
        return ttk.Button(self,
                          text = entity['attributes']['friendly_name'],
                          command = lambda: self.interactive_function(entity_id),
                          width = 30)
    
    def interactive_function(self, entity_id):
        """The function used by default when the element is called."""
        entity = self.entity_dict[entity_id]

        if entity['state'] == "on":
            msg_dict = {'action': "light.turn_off", 'entity_id': entity_id}
        else:
            msg_dict = {'action': "light.turn_on", 'entity_id': entity_id, 'data': {'brightness': 255}}

        self.client.publish("lights",json.dumps(msg_dict))

class EntitySlider(EntityWidget):
    def __init__(self, master, client, entity_type: str | list[str] = None, entity_id: str | list[str] = None, **kwargs):
        EntityWidget.__init__(self, master, "entity_slider", client, entity_type, entity_id, **kwargs)
    
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

        action = 'light.turn_on'
        value = int(event.widget.get())

        #if entity in cache, overwrite value, else make entity dict
        entity_cache_write(entity_id, 'value', value)

        msg_dict = {'action': action, 'entity_id': entity_id, 'data': {'brightness': value}}
        self.client.publish("lights",json.dumps(msg_dict))

class EntityRGBSpinners(EntityWidget):
    def __init__(self, master, client, entity_type: str | list[str] = None, entity_id: str | list[str] = None, **kwargs):
        EntityWidget.__init__(self, master, "entity_slider", client, entity_type, entity_id, **kwargs)

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

        widget = ttk.Frame(self)
        
        self.top_label = ttk.Label(widget,
                                    text = self.label_text)

        self.red_channel = tk.Frame(widget, bg = self.rgb_to_bg(0), width = 64, height = 64)
        self.green_channel = tk.Frame(widget, bg = self.rgb_to_bg(1), width = 64, height = 64)
        self.blue_channel = tk.Frame(widget, bg = self.rgb_to_bg(2), width = 64, height = 64)
        
        self.top_label.grid(row=0, columnspan=3)
        self.red_channel.grid(column=0,row=2)
        self.green_channel.grid(column=1,row=2)
        self.blue_channel.grid(column=2,row=2)

        ttk.Button(widget, command = lambda x=1, entity_id = entity_id, entity = entity: self.increment_channel(0,x, entity_id, entity)).grid(column=0,row=1)
        ttk.Button(widget, command = lambda x=-1, entity_id = entity_id, entity = entity: self.increment_channel(0,x, entity_id, entity)).grid(column=0,row=3)
        ttk.Button(widget, command = lambda x=1, entity_id = entity_id, entity = entity: self.increment_channel(1,x, entity_id, entity)).grid(column=1,row=1)
        ttk.Button(widget, command = lambda x=-1, entity_id = entity_id, entity = entity: self.increment_channel(1,x, entity_id, entity)).grid(column=1,row=3)
        ttk.Button(widget, command = lambda x=1, entity_id = entity_id, entity = entity: self.increment_channel(2,x, entity_id, entity)).grid(column=2,row=1)
        ttk.Button(widget, command = lambda x=-1, entity_id = entity_id, entity = entity: self.increment_channel(2,x, entity_id, entity)).grid(column=2,row=3)
        
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
        action = 'light.turn_on'
        target_colour = tuple(round(x/7 * 255) for x in self.rgb)

        msg_dict = {'action': action, 'entity_id': entity_id, 'data': {'rgb_color': target_colour, 'brightness': max(target_colour)}}
        self.client.publish("lights",json.dumps(msg_dict))

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

class EntityMapSnap(EntityWidget):
    def __init__(self, master, client, entity_type: str | list[str] = None, entity_id: str | list[str] = None, **kwargs):
        EntityWidget.__init__(self, master, "entity_slider", client, entity_type, entity_id, foreach = False, **kwargs)

    def construct_widget(self, entity_id: str, entity_dict: dict):
        zones = [entity for id, entity in entity_dict.items() if 'zone' in id]
        people = [entity for id, entity in entity_dict.items() if 'person' in id]

        _size = self.kwargs.get('size')
        if _size is None: raise KeyError("kwarg 'size' expected for class EntityMapSnap")
        
        # extent calculation ----
        _minimum_aspect = 0.0015

        _lonlat_diff = (max([x['attributes']['longitude'] for x in people]) - min([x['attributes']['longitude'] for x in people]),
                        max([x['attributes']['latitude'] for x in people]) - min([x['attributes']['latitude'] for x in people]))
        _square_aspect_diff = max(max(_lonlat_diff), _minimum_aspect) # don't zoom in past target
        _lonlat_centroid = (min([x['attributes']['longitude'] for x in people]) + (_lonlat_diff[0]/2),
                            min([x['attributes']['latitude'] for x in people]) + (_lonlat_diff[1]/2))
        _lonlat_buffer = _square_aspect_diff * 0.1

        extent = [
            _lonlat_centroid[0] - (_square_aspect_diff/2) - _lonlat_buffer,
            _lonlat_centroid[0] + (_square_aspect_diff/2) + _lonlat_buffer,
            _lonlat_centroid[1] - (_square_aspect_diff/2) - _lonlat_buffer,
            _lonlat_centroid[1] + (_square_aspect_diff/2) + _lonlat_buffer,
            ]
        
        # map plot setup ----
        plt.rcParams['font.family'] = "Nintendo DS BIOS"

        crs = ccrs.PlateCarree()
        tiles = ctiles.StadiaMapsTiles(apikey = "5d0de9f8-8302-49a6-811c-086d733500c4",
                                       style = "stamen_watercolor")

        fig, ax = plt.subplots(subplot_kw=dict(projection=crs), figsize = (8,8))
        ax.set_extent(extent, crs = crs)


        match math.floor(math.log2(_square_aspect_diff / _minimum_aspect)):
            case 0: _zoom_level = 16
            case 1: _zoom_level = 16
            case 2: _zoom_level = 15
            case 3: _zoom_level = 14
            case 4: _zoom_level = 13
            case 5: _zoom_level = 12
            case 6: _zoom_level = 11
            case 7: _zoom_level = 10
            case 8: _zoom_level = 9
            case 9: _zoom_level = 8
            case 10: _zoom_level = 7
            case 11: _zoom_level = 6
            case 12: _zoom_level = 5 
            case _: _zoom_level = 4

        ax.add_image(tiles, _zoom_level)

        _text_objects = []
        for entity in zones:
            if len(entity['attributes']['persons']) > 0:
                #point
                ax.plot(entity['attributes']['longitude'], 
                        entity['attributes']['latitude'],
                        markersize = 4,
                        marker = 'o',
                        color = "#000000",
                        mfc = "#444444",
                        zorder = 3)
                # label
                _text_objects.append(
                    ax.text(
                        entity['attributes']['longitude'],
                        entity['attributes']['latitude'] - _lonlat_buffer, # little spacing to hover below point
                        entity['attributes']['friendly_name'],
                        fontsize = 20,
                        color = "#ffffff",
                        horizontalalignment = 'center',
                        bbox = dict(facecolor = "#000000", edgecolor = "#000000", linewidth = 1.5),
                        zorder = 4))
                # label stem
                ax.plot(*zip(*[(entity['attributes']['longitude'], entity['attributes']['latitude']),
                            (entity['attributes']['longitude'], entity['attributes']['latitude'] - _lonlat_buffer)]), # little spacing to hover below point
                        color = "#000000",
                        linewidth = 3,
                        zorder = 2)
        
        with open("./data/person_position_log.json") as json_data:
            movement_history = json.load(json_data)
            json_data.close()

        for entity in people:
            #get position history if present, else make, trim to most recent N and append current
            position_history = movement_history[entity['entity_id']]
            _current_position = [entity['attributes']['longitude'], entity['attributes']['latitude']]

            if len(position_history) == 0 or _current_position != position_history[-1]:
                position_history.append(_current_position)
                position_history = position_history[-min(len(position_history), 100):] # trim
                movement_history[entity['entity_id']] = position_history # assign back
            
            # point
            ax.plot(entity['attributes']['longitude'], 
                    entity['attributes']['latitude'],
                    markersize = 8,
                    marker = 'o',
                    color = "#000000",
                    mfc = "#ffffff",
                    zorder = 3)
            # label
            _text_objects.append(
                ax.text(
                    entity['attributes']['longitude'],
                    entity['attributes']['latitude'] + _lonlat_buffer, # little spacing to hover above point
                    entity['attributes']['friendly_name'],
                    fontsize = 20,
                    horizontalalignment = 'center',
                    bbox = dict(facecolor = "#ffffff", edgecolor = "#000000", linewidth = 1.5),
                    zorder = 4))
            # label stem
            ax.plot(*zip(*[(entity['attributes']['longitude'], entity['attributes']['latitude']),
                           (entity['attributes']['longitude'], entity['attributes']['latitude'] + _lonlat_buffer)]), # little spacing to hover above point
                    color = "#000000",
                    linewidth = 3,
                    zorder = 2)
            # position history
            ax.plot(*zip(*position_history),
                    color = "#444444",
                    linewidth = 2,
                    zorder = 1)
        with open("./data/person_position_log.json", 'w') as file_write:
            json.dump(movement_history, file_write)
        
        adjust_text(_text_objects, arrowprops=dict(arrowstyle = '-', color = "#000000", linewidth = 3, zorder = 2))
        
        image_buffer = BytesIO()
        fig.savefig(image_buffer, format = 'png', bbox_inches='tight', pad_inches = 0)
        image = Image.open(image_buffer)
        image = image.resize((_size, _size), resample= Image.Resampling.NEAREST)
        image = image.convert('1')

        photo_image = ImageTk.PhotoImage(image)

        widget = ttk.Label(self, image = photo_image)
        widget.image = photo_image
        return widget

"""
App Definition
"""
window = tk.Tk()
window.title("Example")
window.geometry("800x480")

style = ttk.Style()
#must come before .configure
style.theme_use('default')

#configure style
style.configure('.',  font = global_font)
style.configure('Active.TButton', backgroundcolor = "#333333")
style.configure('Inactive.TButton', backgroundcolor = "#dddddd")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect("192.168.0.180")
client.subscribe("system-entities")

h = HASSEngine(client, window)

notebook = ttk.Notebook(window)

light_menu = ttk.Frame()
map_menu = ttk.Labelframe()

notebook.add(light_menu)
notebook.add(map_menu)
notebook.tab(0, text = "Lighting")
notebook.tab(1, text = "Map")
notebook.pack(side = tk.RIGHT,
              fill = 'y')

light_switches = EntityButton(light_menu, client, 'light')
light_switches.grid(row = 0, columnspan = 2)

light_sliders = EntitySlider(light_menu, client, 'light', orient = 'vertical')
light_sliders.grid(column = 0, row = 1, ipadx = 10)

light_rgb = EntityRGBSpinners(light_menu, client, entity_id = 'light.desk_light')
light_rgb.grid(column = 1, row = 1)

map = EntityMapSnap(map_menu, client, ['person', 'zone'], size = 480)
map.pack()

window.mainloop()