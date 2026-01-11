from tkinter import ttk
from io import BytesIO
import dateutil
from PIL import Image, ImageTk, ImageEnhance
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from adjustText import adjust_text
import cartopy
from cartopy import crs as ccrs
from cartopy.io import img_tiles as ctiles
import math

from config import *
from .core import *
from ..caching import *
from ..api.astronomy import *

matplotlib.use('agg')
cartopy.config['cache_dir'] = "./.cache/cartopy/"

class EntityMapSnap(EntityWidget):
    def __init__(self, master, 
                 entity_type: str | list[str] = None, entity_id: str | list[str] = None, 
                 state_channel: str | list[str] = [],
                 **kwargs):
        EntityWidget.__init__(self=self, master=master, widget_name="entity_mapsnap",
                              entity_type=entity_type, entity_id=entity_id,
                              state_channel=state_channel,
                              foreach = False,
                              **kwargs)
        self.map_focus = "all"
        self.overlay = "none"


    def construct_widget(self, entity_id: str, entity_dict: dict, **kwargs):
        widget = ttk.Frame(self)

        if self.kwargs.get('size') is not None:
            self.mapsize = self.kwargs.get('size')
        else: raise KeyError("kwarg 'size' expected for class EntityMapSnap")

        self.zones = [entity for id, entity in entity_dict.items() if 'zone' in id]
        self.people = [entity for id, entity in entity_dict.items() if 'person' in id]

        photo_image = self.generate_map(entity_id, entity_dict, **kwargs)

        map_widget = ttk.Label(widget, image = photo_image)
        map_widget.image = photo_image
        map_widget.grid(column=0, row=0, columnspan=2)

        focus_choice_list = ["all"] + [x for x in entity_dict.keys() if 'person' in x]
        focus_choice_list_names = ["All"] + [x['attributes']['friendly_name'] for k,x in entity_dict.items() if 'person' in k]

        focus_button = ttk.Button(widget,
                                   command = lambda attr = 'map_focus', options = focus_choice_list: self.toggle_attr(attr, options),
                                   text = "Focus: " + focus_choice_list_names[focus_choice_list.index(self.map_focus)])
        focus_button.grid(column = 0, row = 1, sticky = 'nsew')

        overlay_choice_list = ["none", "astro"]
        overlay_choice_names = ["None", "Astronomy"]

        debug_button = ttk.Button(widget,
                                   command = lambda attr = 'overlay', options = overlay_choice_list: self.toggle_attr(attr, options),
                                   text = "Overlay: " + overlay_choice_names[overlay_choice_list.index(self.overlay)])
        debug_button.grid(column = 1, row = 1, sticky = 'nsew')

        return widget
    
    # get length of current people list, iterate through looping back to 0 at end, set as current focus
    def toggle_attr(self, attr: str, options: list[str]):
        new_option_index = (options.index(getattr(self, attr)) + 1) % len(options)
        setattr(self, attr, options[new_option_index])
        self.build()
    
    def generate_map(self, entity_id: str, entity_dict: dict, **kwargs):
        zones = self.zones
        people = self.people
        _size = self.mapsize

        #if focus is a person
        if self.map_focus in entity_dict.keys():
            people = [entity for id, entity in entity_dict.items() if self.map_focus in id]

        
        """Calculating map extent"""
        _minimum_aspect = 0.0015
        _map_buffer_amount = 0.1

        match self.map_focus:
            case _:
                _lonlat_diff = (max([x['attributes']['longitude'] for x in people]) - min([x['attributes']['longitude'] for x in people]),
                                max([x['attributes']['latitude'] for x in people]) - min([x['attributes']['latitude'] for x in people]))
                map_dimension = max(max(_lonlat_diff), _minimum_aspect) # don't zoom in past target
                lonlat_centroid = (min([x['attributes']['longitude'] for x in people]) + (_lonlat_diff[0]/2),
                                    min([x['attributes']['latitude'] for x in people]) + (_lonlat_diff[1]/2))
        map_buffer = map_dimension * _map_buffer_amount

        extent = [
            lonlat_centroid[0] - (map_dimension/2) - map_buffer,
            lonlat_centroid[0] + (map_dimension/2) + map_buffer,
            lonlat_centroid[1] - (map_dimension/2) - map_buffer,
            lonlat_centroid[1] + (map_dimension/2) + map_buffer,
            ]
        
        #filter to ensure not rendering tile content out of bounds
        zones = self.filter_entities_to_extent(zones, extent)
        people = self.filter_entities_to_extent(people, extent)

        # map plot setup ----
        plt.rcParams['font.family'] = "Nintendo DS BIOS"
        
        """---First plot cycle: used to fetch tiles, apply enhancements, save to image. Used as bg of second plot cycle---"""
        map_bg = self.get_map_image(_size, extent, map_dimension, _minimum_aspect, 96, 0.75)
        """---End of first plot cycle---"""

        """---Second plot cycle---"""
        fig, ax = plt.subplots(figsize = (8,8))
        plt.axis('off')
        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim(extent[2], extent[3])
        ax.imshow(map_bg, extent = extent)

        label_store = []

        """Match case for the current display mode"""
        match self.overlay:
            case "none":
                label_store = self.plt_add_zones(ax, zones, -map_buffer, label_store)
                label_store = self.plt_add_people(ax, people, map_buffer, label_store)
            case "astro":
                self.plt_add_astronomy(fig, ax, lonlat_centroid, extent, (map_dimension/2) + (map_buffer/2)) # +map buffer would have circle perfectly fit square, but we want some allowance for icons
    
        adjust_text(label_store, arrowprops=dict(arrowstyle = '-', color = "#000000", linewidth = 3, zorder = 2))
        """---End of second plot cycle---"""

        image_buffer = BytesIO()
        fig.savefig(image_buffer, format = 'png', bbox_inches='tight', pad_inches = 0)
        plt.close()

        image = Image.open(image_buffer)
        image = image.resize((_size, _size), resample= Image.Resampling.NEAREST)
        image = image.convert('1')

        photo_image = ImageTk.PhotoImage(image)

        return photo_image
    
    def get_map_image(self, size: int, extent: list, aspect: float, min_aspect: float, brightness: float, contrast: float):
        match math.floor(math.log2(aspect / min_aspect)):
            case 0: _zoom_level = 17
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

        crs = ccrs.PlateCarree()
        tiles = ctiles.StadiaMapsTiles(apikey = "5d0de9f8-8302-49a6-811c-086d733500c4",
                                       style = "stamen_toner_background",
                                       cache = True)

        fig, ax = plt.subplots(figsize = (8,8), subplot_kw=dict(projection=crs))
        ax.margins(x = 0, y = 0)
        ax.autoscale(False)
        ax.set_extent(extent, crs = crs)

        ax.add_image(tiles, _zoom_level)

        #create a file buffer object, save map view
        buffer = BytesIO()
        fig.savefig(buffer, format = 'png', bbox_inches='tight', pad_inches = 0)
        plt.close()

        #open as image, resize
        map_bg = Image.open(buffer)
        map_bg = map_bg.resize((size, size), resample= Image.Resampling.NEAREST)

        #pull up brightness by mapping [0,255] -> [n,255]
        return ImageEnhance.Contrast(Image.merge(map_bg.mode, [x.point(lambda i: i + ((1 - (i/255)) * brightness)) for x in map_bg.split()])).enhance(contrast)
    
    def plt_add_zones(self, ax: plt.Axes, zones: list[dict], label_offset: float, label_store: list):
        label_store = label_store
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
                label_store.append(
                    ax.text(
                        entity['attributes']['longitude'],
                        entity['attributes']['latitude'] + label_offset, # little spacing to hover below point
                        entity['attributes']['friendly_name'],
                        fontsize = 24,
                        color = "#ffffff",
                        horizontalalignment = 'center',
                        bbox = dict(facecolor = "#000000", edgecolor = "#000000", linewidth = 1.5),
                        zorder = 4))
                # label stem
                ax.plot(*zip(*[(entity['attributes']['longitude'], entity['attributes']['latitude']),
                            (entity['attributes']['longitude'], entity['attributes']['latitude'] + label_offset)]), # little spacing to hover below point
                        color = "#000000",
                        linewidth = 3,
                        zorder = 2)
        return label_store
    
    def plt_add_people(self, ax: plt.Axes, people: list[dict], label_offset: float, label_store: list):
        label_store = label_store
        for entity in people:
            #get position history if present, else make, trim to most recent N and append current
            position_history = localcache_read("./data/person_position_log.json", entity['entity_id'])
            _current_position = [entity['attributes']['longitude'], entity['attributes']['latitude']]

            if len(position_history) > 0:
                _latest_parsed_datetime = max(position_history.keys())
                _latest_position = position_history[_latest_parsed_datetime]

            if len(position_history) == 0 or _current_position != _latest_position:
                localcache_write("./data/person_position_log.json",
                                 entity['entity_id'],
                                 dateutil.parser.parse(entity['last_updated']).timestamp(),
                                 _current_position,
                                 12) # assign back
            
            # point
            ax.plot(entity['attributes']['longitude'], 
                    entity['attributes']['latitude'],
                    markersize = 8,
                    marker = 'o',
                    color = "#000000",
                    mfc = "#ffffff",
                    zorder = 3)
            # label
            label_store.append(
                ax.text(
                    entity['attributes']['longitude'],
                    entity['attributes']['latitude'] + label_offset, # little spacing to hover above point
                    entity['attributes']['friendly_name'],
                    fontsize = 24,
                    horizontalalignment = 'center',
                    bbox = dict(facecolor = "#ffffff", edgecolor = "#000000", linewidth = 1.5),
                    zorder = 4))
            # label stem
            ax.plot(*zip(*[(entity['attributes']['longitude'], entity['attributes']['latitude']),
                           (entity['attributes']['longitude'], entity['attributes']['latitude'] + label_offset)]), # little spacing to hover above point
                    color = "#000000",
                    linewidth = 3,
                    zorder = 2)
            # position history
            ax.plot(*zip(*position_history.values()),
                    color = "#444444",
                    linewidth = 3,
                    linestyle = 'dotted',
                    zorder = 1)
        return label_store
    
    def plt_add_astronomy(self, fig: plt.Figure, ax: plt.Axes, lon_lat: tuple, extent: list, max_radius: float):
        def alt_az_to_viewport(alt_az: tuple):
            #convert to lon lat at origin where circle bounds viewport square
            conversion = [math.sin(alt_az[1]), math.cos(alt_az[1])] 
            conversion = [x * (1 - (alt_az[0]/math.radians(90))) * max_radius for x in conversion]

            #move from origin to viewport centre
            conversion = [sum(x) for x in zip(lon_lat, conversion)]
            #clamp to within viewport square
            conversion = (min(max(conversion[0], extent[0]), extent[1]), min(max(conversion[1], extent[2]), extent[3]))

            return conversion

        astro_data = get_astro_data(lon_lat, astronomy_config["id"], astronomy_config["secret"])

        ax.axvline(x = lon_lat[0], color = "#000000")
        ax.axhline(y = lon_lat[1], color = "#000000")
        ax.add_patch(patches.Circle(lon_lat, max_radius, edgecolor = "#000000", facecolor = "none"))

        legend_text = ""

        for body in astro_data:
            if body['id'] in ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune']:
                #get altitude and azimuth

                alt_az = (math.radians(float(body['position']['horizontal']['altitude']['degrees'])), 
                        math.radians(float(body['position']['horizontal']['azimuth']['degrees'])))
                
                # above/on horizon
                if alt_az[0] >= 0:
                    conversion = alt_az_to_viewport(alt_az)

                    astro_icon = OffsetImage(plt.imread("./theme/ui/icons/astro/" + body['id'] + ".png"), zoom = 1.5, interpolation = 'nearest')
                    astro_marker = AnnotationBbox(astro_icon, conversion, frameon = False, annotation_clip = True)
                    astro_marker.set_clip_on(True)
                    ax.add_artist(astro_marker)

                    if len(legend_text) > 0: legend_text = legend_text + "\n"
                    legend_text = legend_text + body['name'] + ": " + str(round(float(body['position']['horizontal']['altitude']['degrees']), 1)) + ", " + str(round(float(body['position']['horizontal']['azimuth']['degrees']), 1))

        props = dict(alpha = 1, edgecolor = "#000000", facecolor = "#ffffff")
        ax.text(0.025, 
                0.975, 
                legend_text, 
                transform = ax.transAxes, 
                fontsize = 24, 
                verticalalignment = 'top',
                bbox = props)

    def filter_entities_to_extent(self, entity_list: list[dict], extent: list):
        return [x for x in entity_list if 
         x['attributes']['longitude'] >= extent[0] and 
         x['attributes']['longitude'] <= extent[1] and
         x['attributes']['latitude'] >= extent[2] and 
         x['attributes']['latitude'] <= extent[3]]