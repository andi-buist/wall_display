from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt

from io import BytesIO
import dateutil
from PIL import Image, ImageEnhance
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
from .widget_core import *
from ..caching import *
from ..api.astronomy import *

matplotlib.use('agg')
cartopy.config['cache_dir'] = "./.cache/cartopy/"

class HASSMap(HASSWidget):
    def __init__(self, data_manager, parent=None):
        super().__init__(data_manager, entity_types=["person", "zone"], entity_ids=None, parent=parent)

        self.map_focus = "all"
        self.overlay = "none"

        self.mapsize = None
        self.zones = []
        self.people = []

        # "kiosk" things can be latched to to slowly change visuals over time
        self.kiosk_index = 0
        self.kiosk_timer = QtCore.QTimer(self)
        self.kiosk_timer.setInterval(10000)
        self.kiosk_timer.timeout.connect(self.on_kiosk_timer_next)

        """Qt Setup"""

        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        # Map image label
        self.map_label = QLabel(self)
        self.layout.addWidget(self.map_label)

        # Focus and overlay buttons
        btn_layout = QHBoxLayout()
        self.focus_button = QPushButton("Focus: All", self)
        self.focus_button.clicked.connect(self.toggle_focus)
        btn_layout.addWidget(self.focus_button)

        self.overlay_button = QPushButton("Overlay: None", self)
        self.overlay_button.clicked.connect(self.toggle_overlay)
        btn_layout.addWidget(self.overlay_button)

        self.layout.addLayout(btn_layout)

        # Initial map render
        self.update_map()

    def on_entities_update(self, entities):
        # Update zones and people lists, then redraw map
        self.zones = [entity for id, entity in entities.items() if 'zone' in id]
        self.people = [entity for id, entity in entities.items() if 'person' in id]
        self.astro_data =  self.get_astronomy_data(astronomy_lon_lat) # uses known location to fetch to prevent weird drift in cached logs
        self.update_map()

    def on_entity_update(self, entity):
        # Update a single entity and redraw map if relevant
        self.on_entities_update(self.entities)
    
    # hijacking show/hide to start/stop the kiosk timer
    def showEvent(self, event):
        self.kiosk_index = 0
        self.kiosk_timer.start()
        super().showEvent(event)
    
    def hideEvent(self, event):
        self.kiosk_index = 0
        self.kiosk_timer.stop()
        super().hideEvent(event)

    # when kiosk timer triggers, tick index up, update map
    def on_kiosk_timer_next(self):
        self.kiosk_index += 1
        self.update_map()

    # Command invoked to toggle map focus (person)
    def toggle_focus(self):
        focus_options = ["all"] + [x['entity_id'] for x in self.people]
        idx = focus_options.index(self.map_focus) if self.map_focus in focus_options else 0
        self.map_focus = focus_options[(idx + 1) % len(focus_options)]
        self.focus_button.setText(f"Focus: {self.map_focus.title() if self.map_focus != 'all' else 'All'}")
        self.update_map()

    # Command invoked to toggle map overlay
    def toggle_overlay(self):
        overlay_options = ["none", "astro"]
        idx = overlay_options.index(self.overlay)
        self.overlay = overlay_options[(idx + 1) % len(overlay_options)]
        self.overlay_button.setText(f"Overlay: {self.overlay.title()}")

        if self.overlay == "astro":
            self.kiosk_index = 0
            self.kiosk_timer.start()
        else:
            self.kiosk_index = 0
            self.kiosk_timer.stop()

        self.update_map()

    def update_map(self):
        parent = self.parentWidget()
        if parent:
            self.mapsize = int(min((parent.width(), parent.height())) * 0.8)
        else:
            self.mapsize = 128

        pil_img = self.generate_map()

        if not pil_img:
            # generic image as a placeholder (when no data)
            image = Image.open(common_image_paths["globe"])
            image = image.resize((self.mapsize, self.mapsize), resample= Image.Resampling.NEAREST)
            image = image.convert('1')
            pil_img = image

        data = BytesIO()
        pil_img.save(data, format="PNG")
        qimg = QImage.fromData(data.getvalue())
        pixmap = QPixmap.fromImage(qimg)
        self.map_label.setPixmap(pixmap)
    
    def generate_map(self, **kwargs) -> Image:
        zones = self.zones
        people = self.people

        if len(zones) == 0 and len(people) == 0:
            return None

        # if focus is a person, filter people to that person, else (probably "All"), do nothing
        if self.map_focus in self.entities.keys():
            people = [entity for id, entity in self.entities.items() if self.map_focus in id]

        
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
        map_bg = self.get_map_image(self.mapsize, extent, map_dimension, _minimum_aspect, 128, 1)
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
                self.plt_add_astronomy(self.astro_data, fig, ax, lonlat_centroid, extent, (map_dimension/2) + (map_buffer/2)) # +map buffer would have circle perfectly fit square, but we want some allowance for icons
    
        adjust_text(label_store, arrowprops=dict(arrowstyle = '-', color = "#000000", linewidth = 3, zorder = 2))
        """---End of second plot cycle---"""

        image_buffer = BytesIO()
        fig.savefig(image_buffer, format = 'png', bbox_inches='tight', pad_inches = 0)
        plt.close()

        image = Image.open(image_buffer)
        image = image.resize((self.mapsize, self.mapsize), resample= Image.Resampling.NEAREST)
        image = image.convert('1')

        return image
    
    def get_map_image(self, size: int, extent: list, aspect: float, min_aspect: float, brightness: float, contrast: float) -> Image:
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
    
    def plt_add_zones(self, ax: plt.Axes, zones: list[dict], label_offset: float, label_store: list) -> list:
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
    
    def plt_add_people(self, ax: plt.Axes, people: list[dict], label_offset: float, label_store: list) -> list:
        label_store = label_store
        for entity in people:
            # TODO: separate out the person tracking & caching logic from the plotting logic so it is always running - same as what's done for astro

            #get position history if present, else make, trim to most recent N and append current
            position_history = localcache_read("./data/person_position_log.json", entity['entity_id'])
            _current_position = [entity['attributes']['longitude'], entity['attributes']['latitude']]

            if len(position_history) > 0:
                _latest_parsed_datetime = max(position_history.keys())
                _latest_position = position_history[_latest_parsed_datetime]
            else:
                _latest_position = None

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
    
    def get_astronomy_data(self, lon_lat: tuple):
        print(datetime.datetime.now(), " got astro data!")

        # create a list of permitted celestial bodies
        allowed_bodies = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune']
                    
        # data fetch from api
        astro_data = get_astro_data(lon_lat, astronomy_config["id"], astronomy_config["secret"])
        astro_data = [body for body in astro_data if body['id'] in allowed_bodies]

        # convert altitude & azimuth to radians (added rounding because it was overly-specific)
        astro_data = [{**body, 
                       "alt_az": 
                       (round(math.radians(float(body['position']['horizontal']['altitude']['degrees'])), 2), 
                        round(math.radians(float(body['position']['horizontal']['azimuth']['degrees'])), 2))
                        } for body in astro_data]
        
        # filter to above horizon
        astro_data = [body for body in astro_data if body['alt_az'][0] > 0]

        # read/write position history
        for body in astro_data:
            position_history = localcache_read("./data/astro_position_log.json", body['id'])

            if len(position_history) > 0:
                _latest_parsed_datetime = max(position_history.keys())
                _latest_position = position_history[_latest_parsed_datetime]
            else:
                _latest_position = None

            if len(position_history) == 0 or list(body['alt_az']) != _latest_position: # json will not return a tuple back, only list
                print(body['id'], ": ", body['alt_az'])
                localcache_write("./data/astro_position_log.json",
                                    body['id'],
                                    dateutil.parser.parse(body['date']).timestamp(),
                                    body['alt_az'],
                                    24) # assign back
            else:
                print(body['id'], ": no changes...")
        return astro_data

    def plt_add_astronomy(self, astro_data: list[dict], fig: plt.Figure, ax: plt.Axes, lon_lat: tuple, extent: list, max_radius: float) -> None:
        # reset kiosk index if past final set
        if self.kiosk_index >= (len(astro_data) + 1):
            self.kiosk_index = 0

        # mods for kiosk plotting
        astro_data = [{**e, 
                       "kiosk_selected":
                       True if idx == (self.kiosk_index - 1)
                       else False,
                       } for idx, e in enumerate(astro_data)]

        # plot crosshair
        ax.axvline(x = lon_lat[0], color = "#000000")
        ax.axhline(y = lon_lat[1], color = "#000000")
        ax.add_patch(patches.Circle(lon_lat, max_radius, edgecolor = "#000000", facecolor = "none"))

        legend_text = ""

        astro_markers = []

        for idx, body in enumerate(astro_data):
            conversion = self.alt_az_to_viewport(body['alt_az'], lon_lat, extent, max_radius)

            if self.kiosk_index == 0:
                is_focus = False
                zoom_level = 0.2
                focused_str = "   "
            elif self.kiosk_index == (idx + 1):
                is_focus = True
                zoom_level = 0.35
                focused_str = "<<<"
            else:
                is_focus = False
                zoom_level = 0.1
                focused_str = "   "
            
            # read position history
            position_history = localcache_read("./data/astro_position_log.json", body['id'])
            position_history = [self.alt_az_to_viewport(alt_az, lon_lat, extent, max_radius) for alt_az in position_history.values()]

            ax.plot(*zip(*position_history),
                color = "#2a2a2a",
                linewidth = 2,
                zorder = 1)

            match body['id']:
                case 'moon':
                    try:
                        # moon phase icon fetch
                        astro_icon = plt.imread("./theme/ui/icons/astro/moon_" + body['extraInfo']['phase']['string'].replace(" ", "_").lower() + ".png")
                    except:
                        # api returned unknown phase, show the confused moon!
                        astro_icon = plt.imread("./theme/ui/icons/astro/moon_bug.png")
                case _:
                    astro_icon = plt.imread("./theme/ui/icons/astro/" + body['id'] + ".png")

            astro_icon_image = OffsetImage(astro_icon, zoom = zoom_level, interpolation = 'bicubic')
            astro_marker = AnnotationBbox(astro_icon_image, conversion, frameon = False, annotation_clip = True)
            astro_marker.set_clip_on(True)

            # add markers to list to render later - focal element last
            if is_focus:
                astro_markers.append(astro_marker)
            else:
                astro_markers.insert(0, astro_marker)

            if len(legend_text) > 0: legend_text = legend_text + "\n"
            legend_text = legend_text + body['name'] + ": " + str(round(float(body['position']['horizontal']['altitude']['degrees']), 1)) + ", " + str(round(float(body['position']['horizontal']['azimuth']['degrees']), 1)) + focused_str

        # render marker list
        for astro_marker in astro_markers:
            ax.add_artist(astro_marker)

        props = dict(alpha = 1, edgecolor = "#000000", facecolor = "#ffffff")
        ax.text(0.025, 
                0.975, 
                legend_text, 
                transform = ax.transAxes, 
                fontsize = 24, 
                verticalalignment = 'top',
                bbox = props)

    def alt_az_to_viewport(self, alt_az: tuple, lon_lat: tuple, extent: list, max_radius: float):
                #convert to lon lat at origin where circle bounds viewport square
                conversion = [math.sin(alt_az[1]), math.cos(alt_az[1])] 
                conversion = [x * (1 - (alt_az[0]/math.radians(90))) * max_radius for x in conversion]

                #move from origin to viewport centre
                conversion = [sum(x) for x in zip(lon_lat, conversion)]
                #clamp to within viewport square
                conversion = (min(max(conversion[0], extent[0]), extent[1]), min(max(conversion[1], extent[2]), extent[3]))

                return conversion
    
    def filter_entities_to_extent(self, entity_list: list[dict], extent: list):
        return [x for x in entity_list if 
         x['attributes']['longitude'] >= extent[0] and 
         x['attributes']['longitude'] <= extent[1] and
         x['attributes']['latitude'] >= extent[2] and 
         x['attributes']['latitude'] <= extent[3]]