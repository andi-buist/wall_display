from PySide6 import QtCore, QtWidgets, QtGui
from typing import Literal
import requests
from io import BytesIO
from PIL import Image
import webcolors

from modules.widgets.widget_core import *

global xkcd_colours

with BytesIO(requests.get("https://xkcd.com/color/rgb.txt").content) as file:
#remove 1st entry as this is the title, license, etc.
    xkcd_colours = dict([tuple(line.decode('utf-8').split("\t")[0:2]) for line in file][1:])

class Spinner(QtWidgets.QWidget):
    """
    A widget containing two buttons, used to increment an internal value, and a display panel used to represent the internal value.
    Contains a signal, value_changed, that can be latched to on internal value change.
    """
    value_changed = QtCore.Signal(int)
    def __init__(self, 
                 orientation: Literal["vertical", "horizontal"] = "vertical", 
                 bits: int = 8, 
                 parent=None):
        """
        Create a new ValueSpinner

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

        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

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

class VSpinner(HASSWidget):
    def __init__(self, 
                 data_manager: HASSDataManager, 
                 entity_id: str=None, 
                 orientation: Literal["vertical", "horizontal"] = "vertical", 
                 bits: int = 8,  
                 parent = None):
        super().__init__(data_manager, entity_ids=entity_id, parent = parent)

        match orientation:
            case 'horizontal':
                layout = QtWidgets.QHBoxLayout(self)
                self.spinner = Spinner(orientation = 'vertical', bits = bits)
            case 'vertical':
                layout = QtWidgets.QVBoxLayout(self) 
                self.spinner = Spinner(orientation = 'horizontal', bits = bits)

        layout.addWidget(self.spinner)
        self.spinner.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.spinner.value_changed.connect(lambda value: self.change_value(value))
        layout.setStretch(0, 1)

    def change_value(self, value: int):
        '''
        Sets the RGB value for relevant entities
        
        :param self: RGBSpinner class
        :param value: Emitted value from Spinner class signal
        :type value: int
        :param channel: Channel signal source
        :type channel: Literal['r', 'g', 'b']
        '''
        brightness = int(255 * value/(self.spinner.bits - 1))
        
        for entity_id in self.entity_ids:
            msg_template = dict(type = "call_service",
                                domain = "light",
                                target = dict(entity_id = entity_id))
            #for messages that would return a response, include return_response = True
            msg_template['service'] = "turn_on"
            msg_template['service_data'] = dict(brightness = brightness)

            self.data_manager.send_command(msg_template)


class RGBSpinner(HASSWidget):
    '''
    A HASSWidet used to control an entity with RGB values (lights, bulbs)
    '''
    def __init__(self, 
                 data_manager: HASSDataManager, 
                 entity_id: str=None, 
                 orientation: Literal["vertical", "horizontal"] = "vertical", 
                 bits: int = 8,  
                 parent = None):
        super().__init__(data_manager, entity_ids=entity_id, parent = parent)

        self.spinners: dict[str: Spinner] = {}

        match orientation:
            case 'horizontal':
                layout = QtWidgets.QHBoxLayout(self)
            case 'vertical':
                layout = QtWidgets.QVBoxLayout(self)

        for channel in ['r','g','b']:
            match orientation:
                case 'horizontal':
                    spinner = Spinner(orientation = 'vertical', bits = bits)
                case 'vertical':
                    spinner = Spinner(orientation = 'horizontal', bits = bits)
            self.spinners[channel] = spinner
            layout.addWidget(self.spinners[channel])
            self.spinners[channel].setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
            self.spinners[channel].value_changed.connect(lambda value, ch = channel: self.change_rgb(value, ch))

        # make all children evenly sized
        for index in range(layout.count()):
            layout.setStretch(index, 1)
    
    def change_rgb(self, value: int, channel: Literal['r','g','b']):
        '''
        Sets the RGB value for relevant entities
        
        :param self: RGBSpinner class
        :param value: Emitted value from Spinner class signal
        :type value: int
        :param channel: Channel signal source
        :type channel: Literal['r', 'g', 'b']
        '''
        rgb = tuple(int(255 * s.value/(s.bits - 1)) for s in self.spinners.values())
        
        for entity_id in self.entity_ids:
            entity = self.data[entity_id]
            adj_rgb = rgb = get_value_adjusted_rgb(rgb, entity['attributes']['brightness'])

            #print(get_colour_name(adj_rgb))

            msg_template = dict(type = "call_service",
                                domain = "light",
                                target = dict(entity_id = entity_id))
            #for messages that would return a response, include return_response = True
            msg_template['service'] = "turn_on"
            msg_template['service_data'] = dict(rgb_color = adj_rgb)

            self.data_manager.send_command(msg_template)
    

def get_value_adjusted_rgb(rgb: tuple[int, int, int], value) -> tuple[int, int, int]:
    '''
    Converts an RGB tuple (0-255) to the appropriate brightness, given a specified brightness value.
    
    :param rgb: RGB values
    :type rgb: tuple[int, int, int]
    :param value: Brightness value
    :return: Scaled RGB values
    :rtype: tuple[int, int, int]
    '''
    # case for when the colour is black but brightness > 0
    if(rgb == (0, 0, 0)):
        rgb = (1,1,1)
    return tuple(int(x/(max(*rgb, 1)) * value) for x in rgb)

def get_colour_name(rgb: tuple[int, int, int]) -> str:
    '''
        Gets the XKCD colour name from an input RGB by minimum Euclidean distance
    
    :param rgb: RGB values
    :type rgb: tuple[int, int, int]
    :return: A colour name from the XKCD data
    :rtype: str
    '''
    distances = {}
    for name in xkcd_colours.keys():
        xkcd_rgb = tuple(webcolors.hex_to_rgb(xkcd_colours[name]))
        distances[name] = sum((xkcd_rgb[i] - rgb[i]) ** 2 for i in range(3))
    return min(distances, key=distances.get)