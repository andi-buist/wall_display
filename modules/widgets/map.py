from PySide6 import QtWidgets
from PySide6.QtGui import QPixmap, QImage

from io import BytesIO
import dateutil
from PIL import Image, ImageEnhance, ImageOps
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from adjustText import adjust_text
import cartopy
from cartopy import crs as ccrs
from cartopy.io import img_tiles as ctiles
import math
from typing import Literal
from scipy import ndimage
import numpy as np
from scipy.spatial.distance import cdist
from collections import defaultdict
import networkx as nx
import polyline
import starplot

from .widget_core import *
from ..caching import *
from ..api.get_data import *

with open("tokens.json") as f: 
    token_config = json.load(f)

matplotlib.use('agg')
cartopy.config['cache_dir'] = "./.cache/cartopy/"

class HASSMap(HASSWidget):
    def __init__(self, data_manager, parent=None):
        super().__init__(data_manager, entity_types=["person", "zone"], entity_ids=None, parent=parent)
        self.label_size = None

        self.map_focus = "all"
        self.view = "map"

        self.zones = {}
        self.people = {}

        # "kiosk" things can be latched to to slowly change visuals over time
        self.kiosk_index = 0
        self.kiosk_timer = QtCore.QTimer(self)
        self.kiosk_timer.setInterval(10000)
        self.kiosk_timer.timeout.connect(self.on_kiosk_timer_next)

        """Qt Setup"""

        layout = QtWidgets.QVBoxLayout(self)
        view_layout = QtWidgets.QHBoxLayout()
        button_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(view_layout)
        layout.addLayout(button_layout)

        # View label - Left
        view_panel_left = QtWidgets.QVBoxLayout()
        view_layout.addLayout(view_panel_left)

        dummy_button = QtWidgets.QPushButton("dummy")
        view_panel_left.addWidget(dummy_button)

        # View label -Right
        view_panel_right = QtWidgets.QVBoxLayout()
        view_panel_right.setAlignment(QtCore.Qt.AlignRight)
        view_layout.addLayout(view_panel_right)

        self.view_label = QtWidgets.QLabel()
        self.view_label.setAlignment(QtCore.Qt.AlignCenter)
        view_panel_right.addWidget(self.view_label)
        self.view_label_info = QtWidgets.QLabel()
        self.view_label_info.setAlignment(QtCore.Qt.AlignCenter)
        view_panel_right.addWidget(self.view_label_info)

        # Focus and view buttons
        self.focus_button = QtWidgets.QPushButton("Focus: All")
        self.focus_button.clicked.connect(self.toggle_focus)
        button_layout.addWidget(self.focus_button)

        self.view_button = QtWidgets.QPushButton("View: Map")
        self.view_button.clicked.connect(self.toggle_view)
        button_layout.addWidget(self.view_button)

        # Initial map render
        self.update_label()

    def on_entities_update(self, entities):
        # Update zones and people lists, then redraw map
        self.zones = {id: entity for id, entity in entities.items() if 'zone' in id}
        self.people = {id: entity for id, entity in entities.items() if 'person' in id}
        self.update_label()
    
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
        self.update_label()

    # Command invoked to toggle map focus (person)
    def toggle_focus(self):
        focus_options = ["all"] + sorted(list(self.people.keys()))

        idx = focus_options.index(self.map_focus) if self.map_focus in focus_options else 0
        self.map_focus = focus_options[(idx + 1) % len(focus_options)]

        # if focus is a valid person, get their name, else just nicely format the focus name
        if self.map_focus in self.people.keys():
            self.focus_button.setText(f"Focus: {self.people[self.map_focus]['attributes']['friendly_name']}")
        else:
            self.focus_button.setText(f"Focus: {self.map_focus.title()}")
        self.update_label()

    # Command invoked to toggle map view
    def toggle_view(self):
        view_options = ["map", "astronomy", "cloud", "temperature", "precipitation", "strava"]
        idx = view_options.index(self.view)
        self.view = view_options[(idx + 1) % len(view_options)]
        self.view_button.setText(f"View: {self.view.title()}")

        # kiosk timer controls
        match self.view:
            case "astronomy" | "strava":
                self.kiosk_index = 0
                self.kiosk_timer.setInterval(10000)
                self.kiosk_timer.start()
            case _:
                self.kiosk_index = 0
                self.kiosk_timer.stop()

        self.update_label()

    def update_label(self):
        try:
            self.label_size = int(min((self.window().width(), self.window().height())) * 0.8)

            # main call to image generator
            image = self.get_visuals()

            if image:
                image = image.crop((1, 1, image.width - 1, image.height - 1))
                image = ImageOps.expand(image, 1, fill = "#000000")

                data = BytesIO()
                image.save(data, format="PNG")
                qimg = QImage.fromData(data.getvalue())
                pixmap = QPixmap.fromImage(qimg)
                self.view_label.setPixmap(pixmap)
            else:
                self.view_label.setText("Loading...")
        except Exception as e:
            # generic image as a placeholder (when no data)
            image = Image.open(theme.filestore['ui']['img']['bug'])
            image = image.resize((self.label_size, self.label_size), resample= Image.Resampling.NEAREST)
            image = image.convert('1')
            
            image = image.crop((1, 1, image.width - 1, image.height - 1))
            image = ImageOps.expand(image, 1, fill = "#000000")

            data = BytesIO()
            image.save(data, format="PNG")
            qimg = QImage.fromData(data.getvalue())
            pixmap = QPixmap.fromImage(qimg)
            self.view_label.setPixmap(pixmap)
            self.view_label_info.setText(str(e))

    """Getter Functions"""
    def get_visuals(self, **kwargs) -> Image.Image:
        if len(self.zones) == 0 and len(self.people) == 0:
            return None
        
        # copy self.zones/people to filter to needed
        filtered_zones = self.zones
        filtered_people = self.people

        # if focus is a person, filter people to that person
        if self.map_focus in self.entities.keys():
           filtered_people = {entity_id: entity for entity_id, entity in filtered_people.items() if  self.map_focus in entity_id}

        # map plot setup ----
        plt.rcParams['font.family'] = "Nintendo DS BIOS"

        label_store = []
        
        """Match case for the current display mode"""
        match self.view:
            case "map":
                extent = self.calculate_extent([(entity['attributes']['longitude'], entity['attributes']['latitude']) for entity in filtered_people.values()])
                map_bg = self.get_map_image(self.label_size, extent['extent'], extent['dimension'], extent['min_dimension'], 128, 1)

                filtered_zones = self.filter_entities_to_extent(filtered_zones, extent['extent']) # remove zones out of view

                fig, ax = self.plt_make(extent)
                ax.imshow(map_bg, extent = extent['extent'])

                data = self.get_people_movement_data()
                label_store = self.plt_add_zones(ax, filtered_zones, -extent['buffer'], label_store)
                label_store = self.plt_add_people(ax, filtered_people, data, extent['buffer'], label_store)

                self.view_label_info.clear()
            case "astronomy":
                extent = self.calculate_extent([(entity['attributes']['longitude'], entity['attributes']['latitude']) for entity in filtered_people.values()])
                map_bg = self.get_map_image(self.label_size, extent['extent'], extent['dimension'], extent['min_dimension'], 128, 1)

                fig, ax = self.plt_make(extent)
                ax.imshow(map_bg, extent = extent['extent'])

                data = self.get_astronomy_map_data(token_config["astronomy_lon_lat"], extent['extent'], (extent['dimension']/2) + (extent['buffer']/2))
                data = self.kiosk_select_data(data)
                self.plt_add_astronomy(data, ax, extent['centre'], extent['extent'], (extent['dimension']/2) + (extent['buffer']/2)) # +map buffer would have circle perfectly fit square, but we want some allowance for icons

                self.view_label_info.clear()
            case "cloud"|"temperature"|"precipitation":
                extent = self.calculate_extent([(entity['attributes']['longitude'], entity['attributes']['latitude']) for entity in filtered_people.values()], extent_dimension = 2.25)
                map_bg = self.get_map_image(self.label_size, extent['extent'], extent['dimension'], extent['min_dimension'], 128, 1)

                fig, ax = self.plt_make(extent)
                ax.imshow(map_bg, extent = extent['extent'])

                self.plt_add_met_office_view(ax, extent['extent'], type = self.view)

                self.view_label_info.clear()
            case "strava":
                data = self.get_strava_map_data(period = (datetime.datetime.today() - datetime.timedelta(days=30), datetime.datetime.now()))
                data = self.kiosk_select_data(data, start_unselected=False)

                if data["kiosk_selected"]:
                    extent = self.calculate_extent(data['data'][data['kiosk_selected']]['polyline'])
                else:
                    coord_list = []
                    for value in data['data'].values():
                        coord_list = coord_list + [x for x in value['polyline']]
                    extent = self.calculate_extent(coord_list)

                map_bg = self.get_map_image(self.label_size, extent['extent'], extent['dimension'], extent['min_dimension'], 128, 1)

                fig, ax = self.plt_make(extent)
                ax.imshow(map_bg, extent = extent['extent'])

                self.plt_add_strava_view(ax, data)

                time_str = data['data'][data['kiosk_selected']]['start_date'].strftime('%A %d %b, %H:%M')
                run_length = str(round(data['data'][data['kiosk_selected']]['distance']/1000,1)) + "k"

                self.view_label_info.setText(f"{time_str}: {run_length}")
            case _:
                raise KeyError(f"The view {self.view} was not found")
    
        # TODO: bundle into plt_add_zones/people? would remove need for plt functions to ingest & spit out label_store, too
        adjust_text(label_store, arrowprops=dict(arrowstyle = '-', color = "#000000", linewidth = 3, zorder = 2))
        """---End of second plot cycle---"""

        image_buffer = BytesIO()
        fig.savefig(image_buffer, format = 'png', bbox_inches='tight', pad_inches = 0)
        plt.close()

        image = Image.open(image_buffer)
        image = image.resize((self.label_size, self.label_size), resample= Image.Resampling.NEAREST)
        image = image.convert('1')

        return image

    # TODO: feed ax into here to imshow in function
    def get_map_image(self, size: int, extent: list, aspect: float, min_aspect: float, brightness: float, contrast: float) -> Image.Image:
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
        map_bg = ImageEnhance.Contrast(Image.merge(map_bg.mode, [x.point(lambda i: i + ((1 - (i/255)) * brightness)) for x in map_bg.split()])).enhance(contrast)
        return map_bg
    
    def get_people_movement_data(self) -> dict:
        data = {}
        for entity_id, entity in self.people.items():
            #get position history if present, else make, trim to most recent N and append current
            position_history = localcache_read("./data/person_position_log.json", entity_id)
            _current_position = [entity['attributes']['longitude'], entity['attributes']['latitude']]

            if len(position_history) > 0:
                _latest_parsed_datetime = max(position_history.keys())
                _latest_position = position_history[_latest_parsed_datetime]
            else:
                _latest_position = None

            if len(position_history) == 0 or _current_position != _latest_position:
                localcache_write("./data/person_position_log.json",
                                 entity_id,
                                 dateutil.parser.parse(entity['last_updated']).timestamp(),
                                 _current_position,
                                 12) # assign back
            data[entity_id] = position_history
        return data

    def get_astronomy_map_data(self, lon_lat: tuple, extent: dict, max_radius: float) -> dict:
        # create a list of permitted celestial bodies
        allowed_bodies = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune']
                    
        # data fetch from api
        astro_data = get_astro_data(lon_lat)
        astro_data = [body for body in astro_data if body['id'] in allowed_bodies]
        
        data = {}

        # convert altitude & azimuth to radians (added rounding because it was overly-specific)
        for body in astro_data:
            position = (round(math.radians(float(body['position']['horizontal']['altitude']['degrees'])), 2),
                        round(math.radians(float(body['position']['horizontal']['azimuth']['degrees'])), 2))
            
            if position[0] > 0: # filter to above horizon
                data[body['id']] = {"position": position, "timestamp": body['date'], "name": body['name'], "extraInfo": body['extraInfo']}

        # read/write position history
        for body_id, body_data in data.items():
            position_history = localcache_read("./data/astro_position_log.json", body_id)

            if len(position_history) > 0:
                _latest_parsed_datetime = max(position_history.keys())
                _latest_position = position_history[_latest_parsed_datetime]
            else:
                _latest_position = None

            if len(position_history) == 0 or list(body_data['position']) != _latest_position: # json will not return a tuple back, only list
                localcache_write("./data/astro_position_log.json",
                                    body_id,
                                    dateutil.parser.parse(body_data['timestamp']).timestamp(),
                                    body_data['position'],
                                    24) # assign back
        
            # read position history
            position_history = localcache_read("./data/astro_position_log.json", body_id).values()
            position_history = sorted(position_history, key=lambda x: x[1]) # sort by azimuth (prevents line joining across discontinuity)
            position_history = [self.alt_az_to_viewport(position, lon_lat, extent, max_radius) for position in position_history]

            data[body_id]['history'] = position_history
        
        for body_id in data.keys():
            match body_id:
                case 'moon':
                    try:
                        # moon phase icon fetch
                        data[body_id]["icon"] = plt.imread(theme.filestore['ui']['icons']['astro']["moon_" + data[body_id]['extraInfo']['phase']['string'].replace(" ", "_").lower()])
                    except:
                        # api returned unknown phase, show the confused moon!
                        data[body_id]["icon"] = plt.imread(theme.filestore['ui']['icons']['astro']["moon_bug"])
                case _:
                    data[body_id]["icon"] = plt.imread(theme.filestore['ui']['icons']['astro'][body_id])
        return {"data": data, "kiosk_selected": None}

    def get_strava_map_data(self, type: str = None, 
                            period: tuple[datetime.datetime, datetime.datetime] = (datetime.datetime.today() - datetime.timedelta(days = 30), datetime.datetime.now()),
                            cache_frequency: datetime.timedelta = datetime.timedelta(hours=1),
                            cache_filepath: Path = Path("./data/strava_data_cache.json")) -> dict:
        data = get_strava_data(period = period, cache_frequency = cache_frequency, cache_filepath=cache_filepath)

        for key, value in data['data'].items():
            data['data'][key]['start_date'] = datetime.datetime.fromtimestamp(value['start_date'])

        return data

    """Plotter Functions"""
    def plt_make(self, extent: dict = None):
        fig, ax = plt.subplots(figsize = (8,8))
        plt.axis('off')
        if extent:
            ax.set_xlim(extent['extent'][0], extent['extent'][1])
            ax.set_ylim(extent['extent'][2], extent['extent'][3])
        return fig, ax

    def plt_add_zones(self, ax: plt.Axes, zones: dict, label_offset: float, label_store: list) -> list:
        label_store = label_store
        for entity in zones.values():
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
    
    def plt_add_people(self, ax: plt.Axes, people: dict, data: dict, label_offset: float, label_store: list) -> list:
        label_store = label_store
        for entity in people.values():
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
            ax.plot(*zip(*data[entity['entity_id']].values()),
                    color = "#444444",
                    linewidth = 3,
                    linestyle = 'dotted',
                    zorder = 1)
        return label_store
    
    def plt_add_astronomy(self, data: dict, ax: plt.Axes, lon_lat: tuple, extent: list, max_radius: float) -> None:
        if len(data) > 0: 
            # plot crosshair
            ax.axvline(x = lon_lat[0], color = "#000000")
            ax.axhline(y = lon_lat[1], color = "#000000")
            ax.add_patch(patches.Circle(lon_lat, max_radius, edgecolor = "#000000", facecolor = "none"))

            legend_text = ""

            # index-wise plotting due to kiosk
            astro_markers = []
            for key, value in data['data'].items():
                conversion = self.alt_az_to_viewport(value['position'], lon_lat, extent, max_radius)

                if not data["kiosk_selected"]:
                    is_focus = False
                    zoom_level = 0.2
                    focused_str = "   "
                    line_color = "#666666"
                    line_width = 2
                elif key == data["kiosk_selected"]:
                    is_focus = True
                    zoom_level = 0.35
                    focused_str = "<<<"
                    line_color = "#2a2a2a"
                    line_width = 3
                else:
                    is_focus = False
                    zoom_level = 0.1
                    focused_str = "   "
                    line_color = "#999999"
                    line_width = 1

                ax.plot(*zip(*value['history']),
                    color = line_color,
                    linewidth = line_width,
                    zorder = 1)

                astro_icon_image = OffsetImage(value['icon'], zoom = zoom_level, interpolation = 'bicubic')
                astro_marker = AnnotationBbox(astro_icon_image, conversion, frameon = False, annotation_clip = True)
                astro_marker.set_clip_on(True)

                # add markers to list to render later
                if is_focus:
                    astro_markers.append(astro_marker) # push to back, render last
                else:
                    astro_markers.insert(0, astro_marker) # push to front, render... not last.

                if len(legend_text) > 0: legend_text = legend_text + "\n" # separate lines
                legend_text = f"{legend_text}{value['name']}: {round((180/math.pi)  *value['position'][0],1)},{round((180/math.pi) * value['position'][1],1)}{focused_str}"

            # render marker list
            for astro_marker in astro_markers:
                ax.add_artist(astro_marker)

            # add legend
            legend_bbox = dict(alpha = 1, edgecolor = "#000000", facecolor = "#ffffff")
            ax.text(0.025, 
                    0.975, 
                    legend_text, 
                    transform = ax.transAxes, 
                    fontsize = 24, 
                    verticalalignment = 'top',
                    bbox = legend_bbox)
        else:
            # no astro data to plot, show placeholder
            legend_text = "Nothing's in the sky right now... \nCheck back later!"
            legend_bbox = dict(alpha = 1, edgecolor = "#000000", facecolor = "#ffffff")
            ax.text(0.5, 
                    0.5, 
                    legend_text, 
                    transform = ax.transAxes, 
                    fontsize = 24, 
                    verticalalignment = 'center',
                    horizontalalignment = 'center',
                    bbox = legend_bbox)
            
    def plt_add_strava_view(self, ax: plt.Axes, data: dict) -> None:
        if len(data['data'].values()) > 0:
            if not data['kiosk_selected']:
                for value in data['data'].values():
                        ax.plot([x[0] for x in value['polyline']],
                                [x[1] for x in value['polyline']],
                                color = "#000",
                                linewidth = 5,
                                linestyle = 'solid',
                                zorder = 1)
            else:
                poly = data['data'][data['kiosk_selected']]['polyline']
                ax.plot([x[0] for x in poly],
                        [x[1] for x in poly],
                        color = "#000",
                        linewidth = 5,
                        linestyle = 'solid',
                        zorder = 1)

    # met office data is just images with some internal data (value meaning, ranges) so there's no getter for this
    def plt_add_met_office_view(self, ax: plt.Axes, extent: tuple[float, float, float, float], type: str = Literal["cloud", "precipitation", "temperature"]) -> None:
            result = get_met_office_grib(file_id=token_config['met_office_atmospheric_models_config']['file_id'][type])
            view: Image.Image = result['image'].convert('L')

            # calculations to crop view to map extent
            view_extent = token_config['met_office_atmospheric_models_config']['extent']
            # scales - pixels per degree
            h_scale = view.width / (view_extent[1] - view_extent[0])
            v_scale = view.height / (view_extent[3] - view_extent[2])

            #degree differences
            left_border = extent[0] - view_extent[0]
            right_border = extent[1] - view_extent[0]
            bottom_border = extent[2] - view_extent[2]
            top_border = extent[3] - view_extent[2]

            # extent in pixels
            new_extent = (
                int(left_border * h_scale),
                view.height - int(top_border * v_scale),
                int(right_border * h_scale),
                view.height - int(bottom_border * v_scale)
            )

            # crop
            view = view.crop(new_extent)
            view = view.resize((int(view.size[0]/2), int(view.size[1]/2)), resample= Image.Resampling.BICUBIC)
            view = view.resize((self.label_size, self.label_size), resample= Image.Resampling.BICUBIC)
            
            # calculate contour label positions, values, etc.
            arr = np.array(view)

            quantization_bin = 32
            arr = (arr // quantization_bin) * quantization_bin

            # add view to ax
            view = Image.fromarray(255 - arr)
            view.putalpha(196)
            ax.imshow(view, extent=extent)

            view_text = []

            unique_values = np.unique(arr)

            if len(unique_values) != 1: # 0 (shouldn't happen) or >1, add labels foreach
                for value in unique_values:
                    mask = arr == value # TODO: add masks to a list and use kiosk to highlight each in turn? Add to ax in separate passes...
                    if mask.any():
                        label_arr, n_labels = ndimage.label(mask)
                        for idx in range(1, n_labels + 1):
                            mask_image = label_arr == idx
                            if mask_image.sum() > 32 and mask_image.sum() < ((self.label_size ** 2) - 32): # number of valid pixels
                                y,x = ndimage.center_of_mass(mask_image) # row, col
                                x = float(x)/self.label_size
                                y = (self.label_size - float(y))/self.label_size # coords are from top left
                                view_text.append({"coords": (x,y), "value": value})
            else: # 1 value, add central label
                view_text.append({"coords": (0.5,0.5), "value": unique_values[0]})

            view_text = self.snap_labels(view_text, 0.25)

            #legends, labels
            legend_bbox = dict(alpha = 1, edgecolor = "#000000", facecolor = "#ffffff")

            #add contour labels
            match self.view:
                case "cloud"|"precipitation":
                    [x.update(value = str(int((x['value']/255) * 100)) + "%") for x in view_text]
                case "temperature":
                    [x.update(value = str(int(result['value_range'][0] + ((x['value']/255) *  (result['value_range'][1] - result['value_range'][0])) - 273.15)) + "c") for x in view_text] # kelvin to c


            for label in view_text:
                ax.text(label['coords'][0],
                        label['coords'][1],
                        label['value'],
                        transform = ax.transAxes,
                        fontsize = 24,
                        verticalalignment = 'center',
                        horizontalalignment = 'center',
                        bbox = legend_bbox,
                        clip_on= True)
            
            # Add timestamp
            ax.text(0.5, 
                    0.975, 
                    f"Updated: {result['timestamp'].strftime('%A %d %H:%M')}", 
                    transform = ax.transAxes, 
                    fontsize = 24, 
                    verticalalignment = 'top',
                    horizontalalignment = 'center',
                    bbox = legend_bbox)

    """Tool Functions (for getter/plotter)"""
    def kiosk_select_data(self, data: dict, start_unselected: bool = True) -> dict:
        if len(data['data']) > 0:
            # reset kiosk index if past final set
            match start_unselected:
                case True: kiosk_start_point = 1
                case False: kiosk_start_point = 0

            self.kiosk_index = self.kiosk_index % (len(data['data']) + kiosk_start_point)

            if start_unselected and self.kiosk_index == 0:
                data["kiosk_selected"] = None
            else:
                data["kiosk_selected"] = list(data['data'].keys())[self.kiosk_index - kiosk_start_point]
        
        return data

    def calculate_extent(self, lon_lat: list[tuple[float,float]], buffer_amount: float = 0.1, extent_dimension: float = None, min_dimension: float = 0.0015) -> dict:
        lon_values = [x[0] for x in lon_lat]
        lat_values = [x[1] for x in lon_lat]
        
        lonlat_diff = (max(lon_values) - min(lon_values),
                        max(lat_values) - min(lat_values))
        lonlat_centre = (min(lon_values) + (lonlat_diff[0]/2),
                            min(lat_values) + (lonlat_diff[1]/2))
        
        if not extent_dimension:
            extent_dimension = max(max(lonlat_diff), min_dimension) # don't zoom in past target

        extent_buffer = extent_dimension * buffer_amount

        return {"extent": (
            lonlat_centre[0] - (extent_dimension/2) - extent_buffer,
            lonlat_centre[0] + (extent_dimension/2) + extent_buffer,
            lonlat_centre[1] - (extent_dimension/2) - extent_buffer,
            lonlat_centre[1] + (extent_dimension/2) + extent_buffer
            ),
            "centre": lonlat_centre,
            "buffer": extent_buffer,
            "dimension": extent_dimension,
            "min_dimension": min_dimension
            }

    def filter_entities_to_extent(self, entities: dict, extent: list) -> list:
        return {entity_id: entity for entity_id, entity in entities.items() if 
            entity['attributes']['longitude'] >= extent[0] and 
            entity['attributes']['longitude'] <= extent[1] and
            entity['attributes']['latitude'] >= extent[2] and 
            entity['attributes']['latitude'] <= extent[3]}

    def alt_az_to_viewport(self, alt_az: tuple, lon_lat: tuple, extent: list, max_radius: float) -> tuple[int,int]:
            #convert to lon lat at origin where circle bounds viewport square
            conversion = [math.sin(alt_az[1]), math.cos(alt_az[1])] 
            conversion = [x * (1 - (alt_az[0]/math.radians(90))) * max_radius for x in conversion]

            #move from origin to viewport centre
            conversion = [sum(x) for x in zip(lon_lat, conversion)]
            #clamp to within viewport square
            conversion = (min(max(conversion[0], extent[0]), extent[1]), min(max(conversion[1], extent[2]), extent[3]))

            return conversion
    
    def snap_labels(self, label_list: list[dict], grouping_threshold: float = 0.1) -> list[dict]:
        # snapping together close-by labels
        label_coord_list = [x['coords'] for x in label_list]
        label_value_list = [x['value'] for x in label_list]
        pairwise_distances = cdist(label_coord_list, label_coord_list)

        # label value: indices of value group members
        label_groups = defaultdict(list)
        for idx, value in enumerate(label_value_list):
            label_groups[value].append(idx)

        label_clustering_results = {}

        # graph-based clustering
        for id, indices in label_groups.items():
            if(len(indices) > 1):
                sub = pairwise_distances[np.ix_(indices, indices)]
                graph = nx.Graph()
                graph.add_nodes_from(indices)

                for i_local, i_global in enumerate(indices):
                    for j_local, j_global in enumerate(indices):
                        if i_local < j_local and sub[i_local, j_local] < grouping_threshold:
                            graph.add_edge(i_global, j_global)

                label_clustering_results[id] = [list(comp) for comp in nx.connected_components(graph)]

        new_labels = []
        labels_to_remove = []
        for grouping in [x for xs in label_clustering_results.values() for x in xs if len(x) > 1]:
            new_labels.append({"coords": tuple(map(np.mean, zip(*[p['coords'] for p in [label_list[q] for q in grouping]]))), "value": label_list[grouping[0]]['value']})
            labels_to_remove = labels_to_remove + grouping

        output_label_list = [x for idx, x in enumerate(label_list) if idx not in labels_to_remove]
        return output_label_list + new_labels
    
    # deprecated
    """
    def plt_sky_view(self, ax: plt.Axes, lon_lat: tuple[float, float]) -> None:
    # reset kiosk index if past final set
    if self.kiosk_index > 3:
        self.kiosk_index = 0
    
    dir = self.kiosk_index * 90

    style = starplot.PlotStyle(
        constellation_labels = starplot.LabelStyle(font_size=32, font_weight=starplot.FontWeightEnum.NORMAL, zorder=starplot.ZOrderEnum.LAYER_3),
        constellation_lines = starplot.LineStyle(color="#444444", width = 8, zorder=starplot.ZOrderEnum.LAYER_3),
        star = starplot.ObjectStyle(marker=starplot.MarkerStyle(fill=starplot.FillStyleEnum.FULL, zorder=starplot.ZOrderEnum.LAYER_3, size=40, edge_color=None))
    )
    observer = starplot.Observer(dt = datetime.datetime.now(tz = datetime.timezone.utc),
                                    lon = lon_lat[0],
                                    lat = lon_lat[1]) 
    plot = starplot.HorizonPlot(altitude = (0,90),
                                azimuth = (dir-45,dir+45),
                                observer=observer,
                                style=style,
                                show_compass=False,
                                show_grid=False,
                                show_axes=False,
                                show_labels=False,
                                padding=0,
                                margin=0,
                                resolution = 256,
                                autoscale=True)

    plot.constellations()
    plot.stars(where=[starplot._.magnitude < 5],
                where_labels=[False])
    plot.constellation_labels()
    
    buffer = BytesIO()
    plot.fig.savefig(buffer, format="png", dpi=plot.fig.dpi, bbox_inches="tight", pad_inches=0)
    buffer.seek(0) 
    image = Image.open(buffer)
    ax.imshow(image)
    """