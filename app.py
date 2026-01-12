import theme

import os
from websocket import *

from modules.hass_qt import *
from modules.caching import *
from modules.websocket_defs import *

from PySide6 import QtCore, QtWidgets, QtGui

app = QtWidgets.QApplication([])
app.setFont(theme.global_font)

data_manager = HASSDataManager()

window = HASSApp(data_manager)
#window.showFullScreen()
window.showMaximized()
app.exec()