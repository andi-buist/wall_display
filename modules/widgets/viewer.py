from PySide6 import QtWidgets

from PIL import Image
import matplotlib
import matplotlib.pyplot as plt
import cartopy
from typing import Callable

from modules.widgets.widget_core import *
from modules.caching import *
from modules.api.get_data import *
from modules.widgets.kiosk import KioskController
from modules.widgets.infoboxes.base import InfoBox
from modules.widgets.views.base import View

with open("tokens.json") as f: 
    token_config = json.load(f)

matplotlib.use('agg')
cartopy.config['cache_dir'] = "./.cache/cartopy/"

class Viewer(HASSWidget):
    def __init__(self, data_manager: DataManager, kiosk_controller: KioskController, view_options: dict[str, Callable[[], View]], infobox_options: dict[str, Callable[[], InfoBox]] = None):
        super().__init__(data_manager)
        self.kiosk_controller = kiosk_controller

        self.view_options = view_options
        self.infobox_options = infobox_options

        self.view = None
        self.infobox = None

        self.view_choice = list(view_options.keys())[0]

        # Qt Setup:
        # Self
        # ┌─────────────────────────────────────┐
        # │Layout                               │
        # │┌───────────────────────────────────┐│
        # ││View Layout                        ││
        # ││┌───────────────┐┌────────────────┐││
        # │││View Panel Left││View Panel Right│││
        # ││└───────────────┘└────────────────┘││
        # │└───────────────────────────────────┘│
        # │┌───────────────────────────────────┐│
        # ││Button Layout                      ││
        # │└───────────────────────────────────┘│
        # └─────────────────────────────────────┘
        
        layout = QtWidgets.QVBoxLayout(self)
        view_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(view_layout)
        button_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(button_layout)

        # left panel
        self.view_panel_left = QtWidgets.QWidget()
        self.view_panel_left.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)

        self.view_panel_left_layout = QtWidgets.QVBoxLayout()
        self.view_panel_left_layout.setAlignment(QtCore.Qt.AlignCenter)
        self.view_panel_left.setLayout(self.view_panel_left_layout)
        view_layout.addWidget(self.view_panel_left)

        # right panel (viewer)
        self.view_panel_right = QtWidgets.QWidget()
        self.view_panel_right.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

        self.view_panel_right_layout = QtWidgets.QVBoxLayout()
        self.view_panel_right_layout.setAlignment(QtCore.Qt.AlignCenter)
        self.view_panel_right.setLayout(self.view_panel_right_layout)
        view_layout.addWidget(self.view_panel_right)

        self.view_button = QtWidgets.QPushButton("View: Map")
        self.view_button.clicked.connect(self.toggle_view)
        button_layout.addWidget(self.view_button)

        self.rebuild_viewer()

    # Command invoked to toggle view
    def toggle_view(self):
        self.kiosk_controller.reset()

        view_options = list(self.view_options.keys())
        idx = view_options.index(self.view_choice)
        self.view_choice = view_options[(idx + 1) % len(view_options)]
        self.view_button.setText(f"View: {self.view_choice.title()}")

        self.rebuild_viewer()

    def rebuild_viewer(self):
        self.clear_panels()

        # add infobox if needed
        if self.view_choice in self.infobox_options.keys():
            cls, kwargs = self.infobox_options[self.view_choice]
            self.infobox = cls(data_manager = self.data_manager, parent = self.view_panel_left, **kwargs)
            self.view_panel_left_layout.addWidget(self.infobox)
        
        # add view if needed
        if self.view_choice in self.view_options.keys():
            cls, kwargs = self.view_options[self.view_choice]
            self.view = cls(data_manager = self.data_manager, parent = self.view_panel_right, **kwargs)
            self.view_panel_right_layout.addWidget(self.view)
    
    def clear_panels(self):
        for layout in (self.view_panel_left_layout, self.view_panel_right_layout):
            while (item := layout.takeAt(0)) is not None:
                if item.widget():
                    item.widget().deleteLater()