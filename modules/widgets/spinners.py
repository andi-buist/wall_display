from PySide6 import QtCore, QtWidgets, QtGui
from typing import Literal
import requests
from io import BytesIO
from PIL import Image
import webcolors

from .widget_core import *
from theme import *
from ..caching import *

global xkcd_colours

with BytesIO(requests.get("https://xkcd.com/color/rgb.txt").content) as file:
#remove 1st entry as this is the title, license, etc.
    xkcd_colours = dict([tuple(line.decode('utf-8').split("\t")[0:2]) for line in file][1:])
    
"""
class HASSEntityRGBSpinner(HASSWidget):
    def __init__(self, data_manager, entity_id, parent=None):
        super().__init__(data_manager, entity_ids=entity_id, parent=parent)
        layout = QtWidgets.QVBoxLayout(self)

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

        widget = ttk.Frame(self, style = 'EntityWidget.TFrame')
        
        self.top_label = ttk.Label(widget,
                                    text = self.label_text,
                                    style = 'EntityWidget.TLabel')

        self.red_channel = tk.Frame(widget, bg = self.rgb_to_bg(0), width = 64, height = 64)
        self.green_channel = tk.Frame(widget, bg = self.rgb_to_bg(1), width = 64, height = 64)
        self.blue_channel = tk.Frame(widget, bg = self.rgb_to_bg(2), width = 64, height = 64)
        
        self.top_label.grid(row=0, columnspan=3)
        self.red_channel.grid(column=0,row=2)
        self.green_channel.grid(column=1,row=2)
        self.blue_channel.grid(column=2,row=2)

        ttk.Button(widget, style = 'EntityWidget.TButton', command = lambda x=1, entity_id = entity_id, entity = entity: self.increment_channel(0,x, entity_id, entity)).grid(column=0,row=1)
        ttk.Button(widget, style = 'EntityWidget.TButton', command = lambda x=-1, entity_id = entity_id, entity = entity: self.increment_channel(0,x, entity_id, entity)).grid(column=0,row=3)
        ttk.Button(widget, style = 'EntityWidget.TButton', command = lambda x=1, entity_id = entity_id, entity = entity: self.increment_channel(1,x, entity_id, entity)).grid(column=1,row=1)
        ttk.Button(widget, style = 'EntityWidget.TButton', command = lambda x=-1, entity_id = entity_id, entity = entity: self.increment_channel(1,x, entity_id, entity)).grid(column=1,row=3)
        ttk.Button(widget, style = 'EntityWidget.TButton', command = lambda x=1, entity_id = entity_id, entity = entity: self.increment_channel(2,x, entity_id, entity)).grid(column=2,row=1)
        ttk.Button(widget, style = 'EntityWidget.TButton', command = lambda x=-1, entity_id = entity_id, entity = entity: self.increment_channel(2,x, entity_id, entity)).grid(column=2,row=3)
        
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
        target_colour = tuple(round(x/7 * 255) for x in self.rgb)

        msg_template = dict(type = "call_service",
                            domain = "light",
                            service = "turn_on",
                            service_data = dict(rgb_color = target_colour, brightness = max(target_colour)),
                            target = dict(entity_id = entity_id))

        self.local_ws.send(msg_template)

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
"""
class ValueSpinner(QtWidgets.QWidget):
    """
    A widget containing two buttons, used to increment an internal value, and a display panel used to represent the internal value.
    Contains a signal, value_changed, that can be latched to on internal value change.
    """
    value_changed = QtCore.Signal(int)
    def __init__(self, orientation: Literal["vertical", "horizontal"] = "vertical", bits: int = 8, parent=None):
        """
        Create a new ValueSpinner

        :param data_manager: The app's DataManager
        :param orientation: Orientation of the spinner
        :type orientation: Literal["vertical", "horizontal"]
        :param bits: Values 0 -> n-1 the spinner can represent
        :type bits: int
        """
        super().__init__(parent=parent)
        self.value = 0
        self.bits = bits
        self.label_min_size = 32
        self.orientation = orientation

        self.value_label = QtWidgets.QLabel(alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        self.value_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.value_label.setMinimumSize(self.label_min_size,self.label_min_size)
        self.value_label.setStyleSheet(f"background: #fff; border: 1px solid #000")

        self.pos_button = QtWidgets.QPushButton()
        self.pos_button.clicked.connect(lambda: self.increment_channel(1))
        self.neg_button = QtWidgets.QPushButton()
        self.neg_button.clicked.connect(lambda: self.increment_channel(-1))

        match self.orientation:
            case "horizontal":
                layout = QtWidgets.QHBoxLayout(self)
                self.pos_button.setIcon(QtGui.QPixmap(theme.filestore['ui']['icons']['general']['arrow_right']))
                self.neg_button.setIcon(QtGui.QPixmap(theme.filestore['ui']['icons']['general']['arrow_left']))

                self.pos_button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
                self.neg_button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)

                layout.addWidget(self.neg_button)
                layout.addWidget(self.value_label)
                layout.addWidget(self.pos_button)
            case "vertical":
                layout = QtWidgets.QVBoxLayout(self)
                self.pos_button.setIcon(QtGui.QPixmap(theme.filestore['ui']['icons']['general']['arrow_up']))
                self.neg_button.setIcon(QtGui.QPixmap(theme.filestore['ui']['icons']['general']['arrow_down']))

                self.pos_button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
                self.neg_button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)

                layout.addWidget(self.pos_button)
                layout.addWidget(self.value_label)
                layout.addWidget(self.neg_button)

        self.increment_channel(-1)
        
    def increment_channel(self, value: int):
        self.value = min(max((self.value + value), 0), self.bits-1)
        _fraction = self.value/(self.bits-1)
        _channel_strength = 255 - round(255 * _fraction)
        _hex_code = '#%02x%02x%02x' % (_channel_strength, _channel_strength, _channel_strength)

        dither_image = Image.new('RGB', (self.value_label.width(), self.value_label.height()), _hex_code)
        dither_image = dither_image.convert('1')

        dither_image_data = BytesIO()
        dither_image.save(dither_image_data, format="PNG")
        dither_qimg = QtGui.QImage.fromData(dither_image_data.getvalue())
        self.value_label.setPixmap(QtGui.QPixmap.fromImage(dither_qimg))

        self.value_changed.emit(self.value)

class RGBSPinner(HASSWidget):
    """
    A HASSWidet used to control an entity with RGB values (lights, bulbs)
    """
    def __init__(self, data_manager: DataManager, orientation: Literal["vertical", "horizontal"] = "vertical", bits: int = 8,  parent = None):
        super().__init__(data_manager)

        match orientation:
            case 'horizontal':
                layout = QtWidgets.QHBoxLayout(self)
                self.R_spinner = ValueSpinner(orientation = 'vertical', bits = bits)
                self.G_spinner = ValueSpinner(orientation = 'vertical', bits = bits)
                self.B_spinner = ValueSpinner(orientation = 'vertical', bits = bits)
            case 'vertical':
                layout = QtWidgets.QVBoxLayout(self)
                self.R_spinner = ValueSpinner(orientation = 'horizontal', bits = bits)
                self.G_spinner = ValueSpinner(orientation = 'horizontal', bits = bits)
                self.B_spinner = ValueSpinner(orientation = 'horizontal', bits = bits)

        layout.addWidget(self.R_spinner)
        layout.addWidget(self.G_spinner)
        layout.addWidget(self.B_spinner)