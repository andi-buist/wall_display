from PySide6 import QtCore, QtWidgets, QtGui
from websocket import *

from modules.websocket_defs import *
from modules.widgets.buttons import *
from modules.widgets.map import *
from modules.widgets.terminal import *
import theme

class HASSApp(QtWidgets.QApplication):
    def __init__(self, resolution: tuple[int] = (800,480)):
        QtWidgets.QApplication.__init__(self)

        self.setFont(theme.global_font)

        self.data_manager = HASSDataManager()

        self.window = QtWidgets.QMainWindow()

        self.window.setFixedWidth(resolution[0])
        self.window.setFixedHeight(resolution[1])

        self.data_manager.entities_updated.connect(self.on_entities_updated)
        self.data_manager.entity_state_changed.connect(self.on_entity_state_changed)

        central_widget = QtWidgets.QWidget(self.window)
        self.window.setCentralWidget(central_widget)
        layout = QtWidgets.QHBoxLayout(central_widget)

        # Widgets!
        light_switch = SingleEntityButton(self.data_manager, 
                                          "light.floor_lamp", 
                                          SingleEntityButton.light_switch)
        map = HASSMap(self.data_manager)
        terminal = Terminal()

        self.widget_store = [
            {'label': "Calendar",
             'widget': QtWidgets.QCalendarWidget()},
            {'label': "Light Switch",
             'widget': SingleEntityButton(self.data_manager, 
                                          "light.floor_lamp", 
                                          SingleEntityButton.light_switch)},
            {'label': "Map",
             'widget': HASSMap(self.data_manager)},
            {'label': "Terminal",
             'widget': Terminal()}
                         ]

        # Button layout
        button_layout_parent = QWidget()
        button_layout_parent.setFixedWidth(int(resolution[0] * (3/8)))
        layout.addWidget(button_layout_parent)
        button_layout = QtWidgets.QVBoxLayout(button_layout_parent)

        # Grouping buttons to have single signal endpoint
        self.buttongroup = QtWidgets.QButtonGroup()
        self.buttongroup.buttonClicked.connect(self.slot)

        # Stacking widgets to be displayed in the same slot
        self.stack = QtWidgets.QStackedWidget()
        self.stack.setFixedWidth(int(resolution[0] * (5/8)))
        layout.addWidget(self.stack)

        self.button_store = []
        for idx, choice in enumerate(self.widget_store):
            self.button_store.append(QtWidgets.QRadioButton(choice['label']))
            if idx == 0:
                self.button_store[idx].setChecked(True)
            button_layout.addWidget(self.button_store[idx])
            self.buttongroup.addButton(self.button_store[idx])
            self.stack.addWidget(choice['widget'])

        # Show window
        self.window.show()
    
    # These are mostly here for debug. Can be removed/deactivated and run silently in widgets
    def on_entities_updated(self, entities):
        # Update all widgets with new entities dict
        print("∎∎∎" + str(datetime.datetime.now().replace(microsecond=0)) + "∎∎∎ : " + str(len(entities)) + " entities refreshed")

    def on_entity_state_changed(self, entity):
        # Update only the widget(s) for this entity
        print("∎∎∎" + str(datetime.datetime.now().replace(microsecond=0)) + "∎∎∎ : " + entity['entity_id'] + " refreshed")
    
    # TODO: if options are all in a bit dict/list... we could just marry them to IDs!
    def slot(self, button):
        idx = self.button_store.index(button)
        self.stack.setCurrentIndex(idx)