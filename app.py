import tkinter as tk
from tkinter import ttk

import requests
from io import BytesIO

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

#cartopy setup
resol = '10m'
global_cartopy_features = {
        'bodr': cfeature.NaturalEarthFeature(category='cultural',
                                                   name='admin_0_boundary_lines_land',
                                                   scale=resol,
                                                   facecolor='none',
                                                   alpha=0.7),
        'land': cfeature.NaturalEarthFeature('physical',
                                                   'land',
                                                   scale=resol,
                                                   edgecolor='k',
                                                   facecolor=cfeature.COLORS['land']),
        'ocean': cfeature.NaturalEarthFeature('physical',
                                                    'ocean',
                                                    scale=resol,
                                                    edgecolor='none',
                                                    facecolor=cfeature.COLORS['water']),
        'lakes': cfeature.NaturalEarthFeature('physical',
                                                    'lakes',
                                                    scale=resol,
                                                    edgecolor='b',
                                                    facecolor=cfeature.COLORS['water']),
        'rivers': cfeature.NaturalEarthFeature('physical',
                                                     'rivers_lake_centerlines',
                                                     scale=resol,
                                                     edgecolor='b',
                                                     facecolor='none')
}

with BytesIO(requests.get("https://xkcd.com/color/rgb.txt").content) as file:
    #remove 1st entry as this is the title, license, etc.
    xkcd_colours = dict([tuple(line.decode('utf-8').split("\t")[0:2]) for line in file][1:])

def entity_cache_write(entity_id: str, key: str, value):
    """Assigns the specified value to the key of an entity_id dictionary in the global_entity_cache."""
    if entity_id in global_entity_cache.keys():
        global_entity_cache[entity_id][key] = value
    else:
        global_entity_cache[entity_id] = {key: value}

def entity_cache_read(entity_id: str, key: str, fallback):
    """Gets the value of the specified key from the entity_id dictionary of the global_entity_cache. If there's nothing there, it returns fallback."""
    #pull cached value if exists
    if entity_id in global_entity_cache.keys():
        return global_entity_cache[entity_id][key]
    else:
        return fallback

class HASSRenderer(ttk.Frame):
    """Defines a top-level ttk.Frame element containing sub elements at an appropriate entity-level. Re-rendered when system-entities is messaged."""

    def __init__(self, parent, interactive_element: ttk.Frame | tk.Frame, entity_type: str | list[str] = None, entity_id: str | list[str] = None, for_each: bool = True, **kwargs):
        ttk.Frame.__init__(self, parent)

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.connect("192.168.0.180")
        self.client.subscribe("system-entities")
        self.client.loop_start()

        self.kwargs = kwargs
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.for_each = for_each

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
        if self.for_each:
            for entity in msg_json:
                self.__add_elements(entity)
        else:
            self.__add_elements(msg_json)
    
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

        #set own client attribute to that of parent (HASSRenderer)
        self.client = parent.client
        self.entity = entity

        self.interactive = ttk.Scale(self,
                                 from_ = 255,
                                 to = 0,
                                 orient = (kwargs.get('orient')),
                                 length = 70)
        
        #pull cached value if exists
        _init_value = entity_cache_read(self.entity['entity_id'], 'value', entity['attributes']['brightness'])
        
        if _init_value is None:
            _init_value = 255

        self.interactive.set(_init_value)
        self.interactive.bind("<ButtonRelease-1>", self.interactive_function)
        self.interactive.pack(fill = 'y')

    def interactive_function(self, event):
        """The function used by default when the element created by make_interactive() is called."""

        #get current state in order to perform toggle (not needed in most other scenarios)
        self.client.publish("system-entities-request")

        action = 'light.turn_on'
        value = int(self.interactive.get())

        #if entity in cache, overwrite value, else make entity dict
        entity_cache_write(self.entity['entity_id'], 'value', value)

        msg_dict = {'action': action, 'entity_id': self.entity['entity_id'], 'data': {'brightness': value}}
        self.client.publish("lights",json.dumps(msg_dict))

class EntityRGBSpinners(ttk.Frame):
    def __init__(self, parent: HASSRenderer, entity):
        ttk.Frame.__init__(self, parent)

        #set own client attribute to that of parent (HASSRenderer)
        self.client = parent.client
        self.entity = entity

        if entity['state'] == "on":
            self.rgb = tuple(round(x/255 * 7) for x in entity['attributes']['rgb_color'])

            _init_value = entity_cache_read(self.entity['entity_id'], 'value', entity['attributes']['brightness'])

            _value_adjusted_colour =  self.__get_value_adjusted_colour(self.rgb, _init_value)

            self.label_text = entity['attributes']['friendly_name'] + ": " + self.__get_colour_name(_value_adjusted_colour).upper()
        else:
            self.rgb = (0,0,0)
            self.value = 0

            self.label_text = entity['attributes']['friendly_name'] + " is offline..."

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
            #open rgb 
            _rgb = list(self.rgb)
            #tick up/down by amount, clamp to 0-7
            _rgb[channel] = min(max(self.rgb[channel] + amount, 0),7)

            #set class rgb
            self.rgb = tuple(_rgb)

            _value_adjusted_colour = self.__get_value_adjusted_colour(self.rgb, self.entity['attributes']['brightness'])

            #set parent frame bg and change text
            self.top_label['text'] = self.entity['attributes']['friendly_name'] + ": " + self.__get_colour_name(_value_adjusted_colour).upper()
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
    
    def __get_value_adjusted_colour(self, rgb, value):
        return tuple(round(x/(max(rgb)) * value) if max(rgb) else 0 for x in rgb)

    def __get_colour_name(self, requested_colour):
        distances = {}
        for name in xkcd_colours.keys():
            r_c, g_c, b_c = webcolors.hex_to_rgb(xkcd_colours[name])
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
        if kwargs.get('circle'):
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

class EntityMapSnap(ttk.Frame):
    def __init__(self, parent: HASSRenderer, entity_list, **kwargs):
        ttk.Frame.__init__(self, parent)

        #set own client attribute to that of parent (HASSRenderer)
        self.client = parent.client
        self.entity_list = entity_list

        zones = [x for x in entity_list if 'zone' in x['entity_id']]
        people = [x for x in entity_list if 'person' in x['entity_id']]

        _size = kwargs.get('size')
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
            case 0: _zoom_level = 18
            case 1: _zoom_level = 17
            case 2: _zoom_level = 16
            case 3: _zoom_level = 15
            case 4: _zoom_level = 14
            case 5: _zoom_level = 13
            case 6: _zoom_level = 12
            case 7: _zoom_level = 11
            case 8: _zoom_level = 10
            case 9: _zoom_level = 9
            case 10: _zoom_level = 8
            case 11: _zoom_level = 7
            case 12: _zoom_level = 6 
            case _: _zoom_level = 5

        ax.add_image(tiles, _zoom_level)

        _text_objects = []
        for entity in zones:
            if len(entity['attributes']['persons']) > 0:
                # label stem
                ax.plot(*zip(*[(entity['attributes']['longitude'], entity['attributes']['latitude']),
                            (entity['attributes']['longitude'], entity['attributes']['latitude'] - _lonlat_buffer)]), # little spacing to hover below point
                        color = "#000000",
                        linewidth = 3)
                # label
                _text_objects.append(
                    ax.text(
                        entity['attributes']['longitude'],
                        entity['attributes']['latitude'] - _lonlat_buffer, # little spacing to hover below point
                        entity['attributes']['friendly_name'],
                        fontsize = 20,
                        color = "#ffffff",
                        horizontalalignment = 'center',
                        bbox = dict(facecolor = "#000000", edgecolor = "#000000", linewidth = 1.5)
                        ))
            #point
            ax.plot(entity['attributes']['longitude'], 
                    entity['attributes']['latitude'],
                    markersize = 4,
                    marker = 'o',
                    color = "#000000",
                    mfc = "#444444")
        
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

            # position history
            ax.plot(*zip(*position_history),
                    color = "#444444",
                    linewidth = 4)
            # label stem
            ax.plot(*zip(*[(entity['attributes']['longitude'], entity['attributes']['latitude']),
                           (entity['attributes']['longitude'], entity['attributes']['latitude'] + _lonlat_buffer)]), # little spacing to hover above point
                    color = "#000000",
                    linewidth = 3)
            # label
            _text_objects.append(
                ax.text(
                    entity['attributes']['longitude'],
                    entity['attributes']['latitude'] + _lonlat_buffer, # little spacing to hover above point
                    entity['attributes']['friendly_name'],
                    fontsize = 20,
                    horizontalalignment = 'center',
                    bbox = dict(facecolor = "#ffffff", edgecolor = "#000000", linewidth = 1.5)
                    ))
            # point
            ax.plot(entity['attributes']['longitude'], 
                    entity['attributes']['latitude'],
                    markersize = 8,
                    marker = 'o',
                    color = "#000000",
                    mfc = "#ffffff")
        with open("./data/person_position_log.json", 'w') as file_write:
            json.dump(movement_history, file_write)
        
        adjust_text(_text_objects, arrowprops=dict(arrowstyle = '-', color = "#000000", linewidth = 3))
        
        image_buffer = BytesIO()
        fig.savefig(image_buffer, format = 'png', bbox_inches='tight', pad_inches = 0)
        image = Image.open(image_buffer)
        image = image.resize((_size, _size), resample= Image.Resampling.NEAREST)
        image = image.convert('1')

        photo_image = ImageTk.PhotoImage(image)

        _interactive = ttk.Label(self, image = photo_image)
        _interactive.image = photo_image
        _interactive.pack()

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

# im = HASSRenderer(map_menu, EntityImage, entity_id='person.josh', size = 128)
# im.place(relx = 0.5, rely = 0.5, anchor = 'center')

map = HASSRenderer(map_menu, EntityMapSnap, entity_type = ['person', 'zone'], for_each = False, size = 480)
map.pack()

window.mainloop()