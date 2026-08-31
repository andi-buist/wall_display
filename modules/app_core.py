from PySide6 import QtCore, QtWidgets
from websocket import *

from modules.data_manager import *
from modules.widgets.buttons import *
from modules.widgets.viewer import *
from modules.widgets.views.astronomy import *
from modules.widgets.views.map import *
from modules.widgets.views.weather import *
from modules.widgets.views.strava import *
from modules.widgets.infoboxes.strava import *
from modules.widgets.spinners import *
from modules.widgets.terminal import *
import theme

import json
with open("tokens.json") as f: 
    token_config = json.load(f)

HOME_COORDINATES = (token_config['home_coordinates']['longitude'],
                    token_config['home_coordinates']['latitude'])

HASS_WS_URL = token_config['hass_config']['url']
HASS_WS_TOKEN = token_config['hass_config']['secret']

ASTRONOMY_API_USER_ID = token_config['astronomy_config']['id']
ASTRONOMY_API_USER_SECRET = token_config['astronomy_config']['secret']

MET_OFFICE_API_ORDER_ID = token_config['met_office_atmospheric_models_config']['order_id']
MET_OFFICE_API_FILE_IDS = token_config['met_office_atmospheric_models_config']['file_id']
MET_OFFICE_API_USER_SECRET = token_config['met_office_atmospheric_models_config']['secret']

STRAVA_API_CLIENT_ID = token_config['strava_config']['client_id']
STRAVA_API_CLIENT_SECRET = token_config['strava_config']['client_secret']
STRAVA_API_REFRESH_TOKEN = token_config['strava_config']['refresh_token']

class HomeApp(QtWidgets.QApplication):
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

        # Create DataManagers -----------------------------------------------------------------
        self.hass_data_manager = HASSDataManager(HASS_WS_URL, 
                                                 HASS_WS_TOKEN, 
                                                 refresh_rate = 60000)
        self.hass_data_manager.data_event.connect(self.on_entity_state_changed)

        self.astro_data_manager = AstronomyDataManager(ASTRONOMY_API_USER_ID, 
                                                       ASTRONOMY_API_USER_SECRET, 
                                                       HOME_COORDINATES, 
                                                       refresh_rate = 60000)
        
        self.weather_data_managers = {
            'precipitation': MetOfficeDataManager(MET_OFFICE_API_ORDER_ID,
                                                  MET_OFFICE_API_FILE_IDS['precipitation'],
                                                  MET_OFFICE_API_USER_SECRET,
                                                  HOME_COORDINATES, 
                                                  'precipitation',
                                                  refresh_rate = 3600000),
            'temperature': MetOfficeDataManager(MET_OFFICE_API_ORDER_ID,
                                                  MET_OFFICE_API_FILE_IDS['temperature'],
                                                  MET_OFFICE_API_USER_SECRET,
                                                  HOME_COORDINATES, 
                                                  'temperature',
                                                  refresh_rate = 3600000),
            'cloud': MetOfficeDataManager(MET_OFFICE_API_ORDER_ID,
                                          MET_OFFICE_API_FILE_IDS['cloud'],
                                          MET_OFFICE_API_USER_SECRET,
                                          HOME_COORDINATES, 
                                          'cloud',
                                          refresh_rate = 3600000)}
        
        self.strava_data_manager = StravaDataManager(STRAVA_API_CLIENT_ID,
                                                     STRAVA_API_CLIENT_SECRET,
                                                     STRAVA_API_REFRESH_TOKEN,
                                                     refresh_rate=3600000)
        # --------------------------------------------------------------------------------------

        # TODO: worth converting to its own LightingPanel widget maybe? could have options for RGB, Temp, cute icon
        slider_test = QtWidgets.QWidget()
        slider_test_layout = QtWidgets.QHBoxLayout(slider_test)
        slider_test_layout.addWidget(RGBSpinner(self.hass_data_manager,'light.bedside_lamp', 'vertical'))
        slider_test_layout.addWidget(VSpinner(self.hass_data_manager,'light.bedside_lamp', 'horizontal'))

        # widgets
        self.widget_store = [
            {'label': "Calendar",
             'widget': QtWidgets.QCalendarWidget()},
            {'label': "Light Switch",
             'widget': HASSEntityButton(self.hass_data_manager, 
                                          "light.floor_lamp")},
            {'label': "Spinner",
             'widget': slider_test},
            {'label': "Map",
             'widget': Viewer(self.kiosk_controller,
                              view_options = {
                                  "map": (MapView,{"data_manager": self.hass_data_manager}),
                                  "astronomy": (AstronomyView, {"data_manager": self.astro_data_manager, "kiosk_controller": self.kiosk_controller}),
                                  "weather: precipitation": (WeatherView, {"data_manager": self.weather_data_managers['precipitation']}),
                                  "weather: temperature": (WeatherView, {"data_manager": self.weather_data_managers['temperature']}),
                                  "weather: cloud": (WeatherView, {"data_manager": self.weather_data_managers['cloud']}),
                                  "strava": (StravaView, {"data_manager": self.strava_data_manager, "kiosk_controller": self.kiosk_controller})
                                  },
                                  infobox_options = {
                                  "strava": (StravaInfoBox, {"data_manager": self.strava_data_manager, "kiosk_controller": self.kiosk_controller})
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

    def on_entity_state_changed(self, entity):
        # Update only the widget(s) for this entity
        # TODO: change to logging.logger
        print(f"Heard data update, {entity['entity_id']} [state: {entity['state']}]")