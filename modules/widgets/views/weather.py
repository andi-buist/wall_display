from modules.widgets.views.base import *
from PySide6 import QtWidgets

from io import BytesIO
from PIL import Image, ImageFilter, ImageChops
import matplotlib.pyplot as plt
from adjustText import adjust_text
from typing import Literal
from scipy import ndimage
import numpy as np

class WeatherView(View):
    def __init__(self, 
                 data_manager: MetOfficeDataManager, 
                 parent = None):
        super().__init__(data_manager, parent = parent)

        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)

        # view, info
        v_layout = QtWidgets.QVBoxLayout()
        layout.addLayout(v_layout)

        # view label
        self.view_label = QtWidgets.QLabel()
        self.view_label.setAlignment(QtCore.Qt.AlignCenter)
        self.view_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        v_layout.addWidget(self.view_label)

        # label below viewer (text etc)
        self.view_label_info = QtWidgets.QLabel()
        self.view_label_info.setAlignment(QtCore.Qt.AlignCenter)
        v_layout.addWidget(self.view_label_info)

        legend_gauge = QtWidgets.QLabel()
        legend_gauge.setFixedWidth(64)
        legend_gauge.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        layout.addWidget(legend_gauge)

    def _on_data_update(self):
        super()._on_data_update() # triggers render() + data_ready
    
    def render(self):
        # Determine label size
        self.label_size = int(min(self.view_label.width(), self.view_label.height()))

        data = self.data_manager.data

        plot_params = get_map_traits(lon_lat = [self.data_manager.lon_lat], zoom = 1/1000)

        # If no data yet, show placeholder
        if not plot_params:
            self.view_label.setText("Loading...")
            return
        
        try: 
            view_label_image = self.generate_met_office_image(data, plot_params)
            view_label_pixmap = image_to_formatted_pixmap(view_label_image, self.label_size)
            self.view_label.setPixmap(view_label_pixmap)
            self.view_label_info.clear()
        except Exception as e: 
            fallback = Image.open(theme.filestore['ui']['img']['bug'])
            view_label_pixmap = image_to_formatted_pixmap(fallback, self.label_size)
            self.view_label.setPixmap(view_label_pixmap)
            self.view_label_info.setText(str(e))
    
    def generate_met_office_image(self,
                                  data: dict,
                                  plot_params: dict) -> Image.Image:
        plt.rcParams['font.family'] = "Nintendo DS BIOS"

        self.label_size = int(min(self.view_label.width(), self.view_label.height()))
        
        map_bg = get_map_image(self.label_size, plot_params, 128, 1)
        map_bg = ImageChops.multiply(map_bg, map_bg.filter(ImageFilter.CONTOUR)) # enhance borders

        fig, ax = plt_make(plot_params['extent'])
        ax.imshow(map_bg, extent = plot_params['extent'])
        
        im: Image.Image = data['image'].convert('L')

        # calculations to crop im to map extent
        im_extent = token_config['met_office_atmospheric_models_config']['extent']
        # scales - pixels per degree
        h_scale = im.width / (im_extent[1] - im_extent[0])
        v_scale = im.height / (im_extent[3] - im_extent[2])

        #degree differences
        left_border =  plot_params['extent'][0] - im_extent[0]
        right_border =  plot_params['extent'][1] - im_extent[0]
        bottom_border =  plot_params['extent'][2] - im_extent[2]
        top_border =  plot_params['extent'][3] - im_extent[2]

        # extent in pixels
        new_extent = (
            int(left_border * h_scale),
            im.height - int(top_border * v_scale),
            int(right_border * h_scale),
            im.height - int(bottom_border * v_scale)
        )

        # crop
        im = im.crop(new_extent)
        im = im.resize((int(im.size[0]/2), int(im.size[1]/2)), resample= Image.Resampling.BICUBIC)
        im = im.resize((self.label_size, self.label_size), resample= Image.Resampling.BICUBIC)

        # image array - float (0,1)
        arr = np.array(im)
        # calculate the value range of the cropped image
        data['value_range'] = tuple(data['value_range'][0] + ((bound / 255) *  (data['value_range'][1] - data['value_range'][0])) for bound in (arr.min(), arr.max()))
        # normalise
        arr = (((arr - arr.min()) / (arr.max() - arr.min())) * 255).astype(np.uint8)

        quantization_bin = 64
        arr = (arr // quantization_bin) * quantization_bin
        unique_values = np.unique(arr)

        # invert if precip (dark = rainy)
        match self.data_manager.model_type:
            case "precipitation":
                view = Image.fromarray(255 - arr, mode = 'L')
            case _:
                view = Image.fromarray(arr, mode = 'L')

        view = ImageChops.multiply(view, view.filter(ImageFilter.CONTOUR)) # enhance borders

        # add view to ax
        view.putalpha(160)
        ax.imshow(view, extent = plot_params['extent'])

        # labels
        view_text = []
        # generate masks from arr unique values, create a label for contiguous area
        if len(unique_values) != 1: # 0 (shouldn't happen) or >1, add labels foreach
            for value in unique_values:
                mask = arr == value # TODO: add masks to a list and use kiosk to highlight each in turn? Add to ax in separate passes...
                if mask.any():
                    partition_arr, n_partitions = ndimage.label(mask,
                                                                structure = [[1,1,1],
                                                                             [1,1,1],
                                                                             [1,1,1]]) # partition each contiguous piece of the mask (include diags)
                    for idx in range(1, n_partitions + 1):
                        mask_partition = partition_arr == idx
                        if mask_partition.sum() > 32 and mask_partition.sum() < ((self.label_size ** 2) - 32): # number of valid pixels
                            y,x = ndimage.center_of_mass(mask_partition) # row, col
                            x = float(x)/self.label_size
                            y = (self.label_size - float(y))/self.label_size # coords are from top left
                            view_text.append({"coords": (x,y), "value": value})
        else: # 1 value, add central label
            view_text.append({"coords": (0.5,0.5), "value": unique_values[0]})

        view_text = snap_labels(view_text, 0.33)

        #legends, labels
        legend_bbox = dict(alpha = 1, edgecolor = "#000000", facecolor = "#ffffff")

        #add contour labels
        match self.data_manager.model_type:
            case "cloud"|"precipitation":
                [x.update(value = str(int((x['value']/255) * 100)) + "%") for x in view_text]
            case "temperature":
                [x.update(value = str(round(data['value_range'][0] + ((x['value']/255) *  (data['value_range'][1] - data['value_range'][0])) - 273.15, 1)) + "c") for x in view_text] # kelvin to c


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
                f"Updated: {data['timestamp'].strftime('%A %d %H:%M')}", 
                transform = ax.transAxes, 
                fontsize = 24, 
                verticalalignment = 'top',
                horizontalalignment = 'center',
                bbox = legend_bbox)
        
        image_buffer = BytesIO()
        fig.savefig(image_buffer, format = 'png', bbox_inches='tight', pad_inches = 0)
        plt.close()

        image = Image.open(image_buffer)
        image = image.resize((self.label_size, self.label_size), resample= Image.Resampling.NEAREST)
        image = image.convert('1')

        return image