from PySide6 import QtCore, QtWidgets
from websocket import *

from modules.websocket_defs import *
from modules.widgets.buttons import *
from modules.widgets.viewer import *
from modules.widgets.views.astronomy import *
from modules.widgets.views.map import *
from modules.widgets.views.weather import *
from modules.widgets.views.strava import *
from modules.widgets.infoboxes.strava import *
from modules.widgets.rgb_spinner import *
from modules.widgets.terminal import *
import theme

class HASSApp(QtWidgets.QApplication):
    def __init__(self, resolution: tuple[int] = (800,480)):
        QtWidgets.QApplication.__init__(self)
        self.kiosk_controller = KioskController()

        #apply the global qss to self (and all children of application)
        style_file = QtCore.QFile(theme.global_qss)
        style_file.open(QtCore.QFile.OpenModeFlag.ReadOnly)
        self.setStyleSheet(style_file.readAll().toStdString())

        self.setFont(theme.global_font)

        # create main window
        self.window = QtWidgets.QMainWindow()
        even_margin = 2
        self.window.setContentsMargins(*([even_margin] * 4))

        self.window.setFixedWidth(resolution[0])
        self.window.setFixedHeight(resolution[1])

        central_widget = QtWidgets.QWidget(self.window)
        self.window.setCentralWidget(central_widget)
        layout = QtWidgets.QHBoxLayout(central_widget)

        # create a data manager
        self.data_manager = HASSDataManager()
        self.data_manager.entities_updated.connect(self.on_entities_updated)
        self.data_manager.entity_state_changed.connect(self.on_entity_state_changed)

        # widgets
        self.widget_store = [
            {'label': "Calendar",
             'widget': QtWidgets.QCalendarWidget()},
            {'label': "Light Switch",
             'widget': HASSEntityButton(self.data_manager, 
                                          "light.floor_lamp", 
                                          HASSEntityButton.light_switch)},
            {'label': "Spinner",
             'widget': ChannelSpinner(self.data_manager, font_scale=3)},
            {'label': "Map",
             'widget': Viewer(self.data_manager,
                              self.kiosk_controller,
                              view_options = {
                                  "map": (MapView,{}),
                                  "astronomy": (AstronomyView, {"kiosk_controller": self.kiosk_controller}),
                                  "weather: precipitation": (WeatherView, {"overlay_type": 'precipitation'}),
                                  "weather: temperature": (WeatherView, {"overlay_type": 'temperature'}),
                                  "weather: cloud": (WeatherView, {"overlay_type": 'cloud'}),
                                  "strava": (StravaView, {"kiosk_controller": self.kiosk_controller})
                                  },
                                  infobox_options = {
                                    "strava": (StravaInfoBox, {"kiosk_controller": self.kiosk_controller})
                                  }
                                  )},
            {'label': "Terminal",
             'widget': Terminal()}
                         ]

        # button layout
        button_layout_parent = QtWidgets.QWidget()
        button_layout_parent.setFixedWidth(int(resolution[0] * (2/8)))
        layout.addWidget(button_layout_parent)
        button_layout = QtWidgets.QVBoxLayout(button_layout_parent)

        # grouping buttons to have single signal endpoint
        self.buttongroup = QtWidgets.QButtonGroup()
        self.buttongroup.buttonClicked.connect(self.slot)

        # stacking widgets to be displayed in the same slot
        self.stack = QtWidgets.QStackedWidget()
        self.stack.setObjectName("stackWidget1")
        self.stack.setStyleSheet("QWidget#stackWidget1 { border: 1px solid #000 }")
        layout.addWidget(self.stack)

        self.button_store = []
        for idx, choice in enumerate(self.widget_store):
            self.button_store.append(QtWidgets.QRadioButton(choice['label']))
            if idx == 0:
                self.button_store[idx].setChecked(True)
            button_layout.addWidget(self.button_store[idx])
            self.buttongroup.addButton(self.button_store[idx])
            self.stack.addWidget(choice['widget'])

        # show window
        self.window.show()
    
    # points radio button to correct item
    def slot(self, button):
        idx = self.button_store.index(button)
        self.stack.setCurrentIndex(idx)
    
    # these are mostly here for debug. can be removed/deactivated and run silently in widgets
    def on_entities_updated(self, entities):
        # Update all widgets with new entities dict
        print(f"Scheduled data refresh, {str(len(entities))} entities found")

    def on_entity_state_changed(self, entity):
        # Update only the widget(s) for this entity
        print(f"Heard data update, {entity['entity_id']} [state: {entity['state']}]")