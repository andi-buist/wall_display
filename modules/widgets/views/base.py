from PySide6 import QtGui

from io import BytesIO
from PIL import Image, ImageEnhance, ImageOps
import matplotlib.pyplot as plt
from cartopy import crs as ccrs
from cartopy.io import img_tiles as ctiles
import math
import numpy as np
from scipy.spatial.distance import cdist
from collections import defaultdict
import networkx as nx

from modules.widgets.widget_core import *
from modules.caching import *
from modules.api.get_data import *
from modules.widgets.kiosk import *

class View(QtWidgets.QWidget):
    def __init__(self, data_manager: DataManager, kiosk_controller: KioskController = None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.latest_entity_data = {}

        if kiosk_controller:
            self.kiosk_index = 0
            kiosk_controller.tick.connect(self.on_kiosk_timer_next)

            self.kiosk_controller = kiosk_controller

        data_manager.entities_updated.connect(self.set_data)
        data_manager.entity_state_changed.connect(self.update_single)

        QtCore.QTimer.singleShot(0, self._apply_initial_data_snapshot)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.render()
    
    def _apply_initial_data_snapshot(self): 
        if self.data_manager.entities: 
            self.set_data(self.data_manager.entities)

    def set_data(self, entities):
        self.latest_entity_data = entities
        self.render()

    def update_single(self, entity):
        self.latest_entity_data[entity['entity_id']] = entity
        self.render()

    def kiosk_select_data(self, data: dict, start_unselected: bool = True) -> dict:
        if len(data['data']) > 0:
            match start_unselected:
                case True: kiosk_start_point = 1
                case False: kiosk_start_point = 0

            self.kiosk_index = self.kiosk_index % (len(data['data']) + kiosk_start_point)

            if start_unselected and self.kiosk_index == 0:
                data["kiosk_selected"] = None
            else:
                data["kiosk_selected"] = list(data['data'].keys())[self.kiosk_index - kiosk_start_point]
        
        return data
    
    # when kiosk timer triggers, tick index up, update map
    def on_kiosk_timer_next(self, index: int):
        self.kiosk_index = index
        self.render()

    def render(self):
        """Override in subclasses"""
        print(f"{self} is still using the base.py render() function. Are you sure your subclass is set up correctly?")
        pass
    
def plt_make(extent: tuple[float,float,float,float] = None):
    fig, ax = plt.subplots(figsize = (8,8))
    plt.axis('off')
    if extent:
        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim(extent[2], extent[3])
    return fig, ax

def get_map_image(size: int, extent: list, aspect: float, min_aspect: float, brightness: float, contrast: float) -> Image.Image:
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

def calculate_plot_params(lon_lat: list[tuple[float,float]], buffer_amount: float = 0.1, extent_dimension: float = None, min_dimension: float = 0.0015) -> dict:
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

def snap_labels(label_list: list[dict], grouping_threshold: float = 0.1) -> list[dict]:
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

def image_to_formatted_pixmap(image: Image.Image, size: int) -> QPixmap:
    image = image.resize((size, size), resample= Image.Resampling.NEAREST)
    image = image.convert('1')
    
    # add 1px border in image
    image = image.crop((1, 1, image.width - 1, image.height - 1))
    image = ImageOps.expand(image, 1, fill = "#000000")

    data = BytesIO()
    image.save(data, format="PNG")
    qimg = QtGui.QImage.fromData(data.getvalue())
    pixmap = QtGui.QPixmap.fromImage(qimg)
    return pixmap