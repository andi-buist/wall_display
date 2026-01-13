from PySide6 import QtCore, QtWidgets, QtGui
from queue import Queue, Empty

from modules.websocket_defs import *
from modules.widgets.buttons import *
from modules.widgets.map import *

class HASSApp(QtWidgets.QMainWindow):
    def __init__(self, data_manager: HASSDataManager):
        QtWidgets.QMainWindow.__init__(self)

        self.data_manager = data_manager
        self.data_manager.entities_updated.connect(self.on_entities_updated)
        self.data_manager.entity_state_changed.connect(self.on_entity_state_changed)

        central_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QHBoxLayout(central_widget)

        light_switch = SingleEntityButton(self.data_manager, 
                                          "light.floor_lamp", 
                                          SingleEntityButton.light_switch)
        map = HASSMap(self.data_manager)

        self.buttongroup = QtWidgets.QButtonGroup()
        self.button1 = QtWidgets.QRadioButton("Light Switch")
        self.button2 = QtWidgets.QRadioButton("Map")
        self.buttongroup.addButton(self.button1)
        self.buttongroup.addButton(self.button2)
        self.buttongroup.buttonClicked.connect(self.slot)

        layout.addWidget(self.button1)
        layout.addWidget(self.button2)

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(light_switch)
        self.stack.addWidget(map)
        layout.addWidget(self.stack)
    
    # These are mostly here for debug. Can be removed/deactivated and run silently in widgets
    def on_entities_updated(self, entities):
        # Update all widgets with new entities dict
        print(str(len(entities)) + " entities refreshed")

    def on_entity_state_changed(self, entity):
        # Update only the widget(s) for this entity
        print(entity['entity_id'] + " refreshed")
    
    def slot(self, button):
        if button == self.button1:
            self.stack.setCurrentIndex(0)
        elif button == self.button2:
            self.stack.setCurrentIndex(1)