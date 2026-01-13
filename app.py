import theme

import os
from websocket import *

from modules.hass_qt import *
from modules.caching import *
from modules.websocket_defs import *

from PySide6 import QtCore, QtWidgets, QtGui

app = HASSApp()
app.exec()