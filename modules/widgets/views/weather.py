from modules.widgets.views.base import *
from PySide6 import QtWidgets

from io import BytesIO
from PIL import Image
import matplotlib.pyplot as plt
from adjustText import adjust_text
from typing import Literal
from scipy import ndimage
import numpy as np

class WeatherView(View):
    def __init__(self, data_manager: HASSDataManager, overlay_type: Literal["cloud", "temperature", "precipitation"], parent=None):
        super().__init__(data_manager, parent = parent)
        self.overlay_type = overlay_type

        self.people = {}

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
    
    def set_data(self, entities):
        self.people = {id: e for id, e in entities.items() if 'person' in id}
        
        super().set_data(entities) # triggers render() + data_ready
    
    def prepare_data(self):
        # Compute params
        plot_params = calculate_plot_params([(p['attributes']['longitude'], p['attributes']['latitude']) for p in self.people.values()], extent_dimension = 2.25)
        
        return {
            "plot_params": plot_params
            }
    
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

        self.label_size = int(min(self.view_label.width(), self.view_label.height()))

        if len(self.people) == 0: # loading
            return None
        
        plot_params = prepared_data['plot_params']
        map_bg = get_map_image(self.label_size, plot_params['extent'], plot_params['dimension'], plot_params['min_dimension'], 128, 1)

        fig, ax = plt_make(plot_params['extent'])
        ax.imshow(map_bg, extent = plot_params['extent'])

        self.plt_add_met_office_view(ax, plot_params['extent'], type = self.overlay_type)

        self.view_label_info.clear()

        image_buffer = BytesIO()
        fig.savefig(image_buffer, format = 'png', bbox_inches='tight', pad_inches = 0)
        plt.close()

        image = Image.open(image_buffer)
        image = image.resize((self.label_size, self.label_size), resample= Image.Resampling.NEAREST)
        image = image.convert('1')

        return image
    
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

        view_text = snap_labels(view_text, 0.25)

        #legends, labels
        legend_bbox = dict(alpha = 1, edgecolor = "#000000", facecolor = "#ffffff")

        #add contour labels
        match self.overlay_type:
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