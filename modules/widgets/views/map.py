from modules.widgets.views.base import *
from PySide6 import QtWidgets

from io import BytesIO
import dateutil
from PIL import Image
import matplotlib.pyplot as plt
from adjustText import adjust_text

class MapView(View):
    def __init__(self, data_manager: DataManager, parent=None):
        super().__init__(data_manager, parent = parent)
        self.map_focus = "all"
        self.people = {}
        self.people_filtered = {}
        self.people_movement_data = {}
        self.zones = {}

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        # view label
        self.view_label = QtWidgets.QLabel()
        self.view_label.setAlignment(QtCore.Qt.AlignCenter)
        self.view_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        layout.addWidget(self.view_label)

        # label below viewer (text etc)
        self.view_label_info = QtWidgets.QLabel()
        self.view_label_info.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.view_label_info)

        # buttons
        self.focus_button = QtWidgets.QPushButton("Focus: All")
        self.focus_button.clicked.connect(self.toggle_focus)
        layout.addWidget(self.focus_button)

    def set_data(self, entities):
        self.people = {id: e for id, e in entities.items() if 'person' in id}
        self.zones = {id: e for id, e in entities.items() if 'zone' in id}
        
        super().set_data(entities) # triggers render() + data_ready
    
    def prepare_data(self):
        # Determine focus
        if self.map_focus == "all":
            self.people_filtered = self.people
        else: 
            self.people_filtered = { k: v for k, v in self.people.items() if k == self.map_focus } 
            
        # If no people yet, return empty structure 
        if not self.people_filtered: 
            return {"plot_params": None, "data": {}}
        
        # Compute params
        coords = [(p['attributes']['longitude'], p['attributes']['latitude']) for p in self.people_filtered.values()]
        plot_params = calculate_plot_params(coords)
        
        # External astronomy data
        self.people_movement_data = get_people_movement_data(self.people_filtered)
        
        return {
            "plot_params": plot_params
            }
    
    def toggle_focus(self):
        focus_options = ["all"] + sorted(list(self.people.keys()))

        idx = focus_options.index(self.map_focus) if self.map_focus in focus_options else 0
        self.map_focus = focus_options[(idx + 1) % len(focus_options)]

        # if focus is a valid person, get their name, else just nicely format the focus name
        if self.map_focus in self.people.keys():
            self.focus_button.setText(f"Focus: {self.people[self.map_focus]['attributes']['friendly_name']}")
        else:
            self.focus_button.setText(f"Focus: {self.map_focus.title()}")
        
        self.render()

    def render(self):
        # Determine label size
        self.label_size = int(min(self.view_label.width(), self.view_label.height()))

        prepared = self.prepare_data()

        # If no data yet, show placeholder
        if not prepared["plot_params"]:
            self.view_label.setText("Loading...")
            return
        
        try: 
            image = self.render_visuals(prepared)
            pixmap = image_to_formatted_pixmap(image, self.label_size)
            self.view_label.setPixmap(pixmap)
            self.view_label_info.clear()
        except Exception as e: 
            fallback = Image.open(theme.filestore['ui']['img']['bug'])
            pixmap = image_to_formatted_pixmap(fallback, self.label_size)
            self.view_label.setPixmap(pixmap)
            self.view_label_info.setText(str(e))

    def render_visuals(self, prepared_data: dict) -> Image.Image:
        # map plot setup ----
        plt.rcParams['font.family'] = "Nintendo DS BIOS"
        
        label_store = []

        if len(self.zones) == 0 and len(self.people) == 0: # loading
            return None
        
        plot_params = prepared_data['plot_params']

        fig, ax = plt_make(plot_params['extent'])
        
        map_bg = get_map_image(self.label_size, plot_params['extent'], plot_params['dimension'], plot_params['min_dimension'], 128, 1)
        ax.imshow(map_bg, extent = plot_params['extent'])

        label_store = self.plt_add_zones(ax, -plot_params['buffer'], label_store)
        label_store = self.plt_add_people(ax, plot_params['buffer'], label_store)

        self.view_label_info.clear()

        adjust_text(label_store, arrowprops=dict(arrowstyle = '-', color = "#000000", linewidth = 3, zorder = 2))

        image_buffer = BytesIO()
        fig.savefig(image_buffer, format = 'png', bbox_inches='tight', pad_inches = 0)
        plt.close()

        image = Image.open(image_buffer)
        image = image.resize((self.label_size, self.label_size), resample= Image.Resampling.NEAREST)
        image = image.convert('1')

        return image
    
    # plotting functions

    def plt_add_zones(self, ax: plt.Axes, label_offset: float, label_store: list) -> list:
        label_store = label_store
        for entity in self.zones.values():
            if any(map(lambda v: v in self.people_filtered.keys(), entity['attributes']['persons'])): # only zones with a filtered person inside
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
    
    def plt_add_people(self, ax: plt.Axes, label_offset: float, label_store: list) -> list:
        label_store = label_store
        for entity in self.people_filtered.values():
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
            ax.plot(*zip(*self.people_movement_data[entity['entity_id']].values()),
                    color = "#444444",
                    linewidth = 3,
                    linestyle = 'dotted',
                    zorder = 1)
        return label_store

def get_people_movement_data(people: dict) -> dict:
    data = {}
    for entity_id, entity in people.items():
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