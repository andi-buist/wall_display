from modules.widgets.infoboxes.base import *
from PySide6 import QtWidgets, QtGui, QtCore
from PIL import ImageQt
from typing import Literal
from pathlib import Path
import textwrap

import theme
from modules.widgets.views.base import get_map_traits


class StravaInfoBox(InfoBox): 
    def __init__(self, data_manager: StravaDataManager, kiosk_controller: KioskController, parent=None): 
        super().__init__(data_manager, kiosk_controller, parent)
        self.layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        self.achievement_count: int = 0
    
    def get_latest_data(self):
        data = self.data_manager.data
        data = self.kiosk_select_data(data, start_unselected=False)

        plot_params = get_map_traits(data['data'][data['kiosk_selected']]['polyline'])

        return {
            "plot_params": plot_params,
            "data": data
        }
    
    def update_ui(self):
        latest_data = self.get_latest_data()
        self.build_ui(latest_data)
    
    def build_ui(self, latest_data: dict):
        self.clear()

        data = latest_data['data']
        kiosk_data = data['data'][data['kiosk_selected']]

        self.add_kcal(kiosk_data['calories'])
        self.add_heartrate(kiosk_data['average_heartrate'])

        for achievement in kiosk_data['achievements'].values():
            for a in achievement['achievements']:
                self.add_achievement("\n".join(textwrap.wrap(achievement['name'], 32)), a['rank'])

    def add_kcal(self, kcals: int|float):
        kcal_title_bar = QtWidgets.QLabel("Calories:")
        kcal_title_bar.setStyleSheet("font-weight: bold")
        kcal_title_bar.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(kcal_title_bar)

        hbox = QtWidgets.QHBoxLayout()
        hbox.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        icon = QtWidgets.QLabel(pixmap = QtGui.QPixmap.fromImage(ImageQt.ImageQt(theme.filestore['ui']['icons']['misc']['fire'])))
        icon.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)
        label = QtWidgets.QLabel(f"{kcals}")
        label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        hbox.addWidget(icon) 
        hbox.addWidget(label)
        self.layout.addLayout(hbox)
    
    def add_heartrate(self, heartrate: int|float):
        hr_title_bar = QtWidgets.QLabel("Heart Rate:")
        hr_title_bar.setStyleSheet("font-weight: bold")
        hr_title_bar.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(hr_title_bar)

        hbox = QtWidgets.QHBoxLayout()
        hbox.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        icon = QtWidgets.QLabel(pixmap = QtGui.QPixmap.fromImage(ImageQt.ImageQt(theme.filestore['ui']['icons']['misc']['heart'])))
        icon.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)
        label = QtWidgets.QLabel(f"{heartrate}")
        label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        hbox.addWidget(icon) 
        hbox.addWidget(label)
        self.layout.addLayout(hbox)

    def add_achievement(self, text: str = None, rank: Literal[1,2,3] = 1):
        if self.achievement_count == 0:
            self.achievement_title_bar = QtWidgets.QLabel("No achievements")
            self.achievement_title_bar.setStyleSheet("font-weight: bold")
            self.achievement_title_bar.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.layout.addWidget(self.achievement_title_bar)

        self.achievement_count += 1
        self.achievement_title_bar.setText(f"Achievements: {self.achievement_count}")

        match rank:
            case 1:
                icon_path: Path = theme.filestore['ui']['icons']['misc']['medal_1']
            case 2:
                icon_path: Path = theme.filestore['ui']['icons']['misc']['medal_2']
            case 3:
                icon_path: Path = theme.filestore['ui']['icons']['misc']['medal_3']

        hbox = QtWidgets.QHBoxLayout()
        hbox.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        icon = QtWidgets.QLabel(pixmap = QtGui.QPixmap.fromImage(ImageQt.ImageQt(icon_path)))
        icon.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)
        label = QtWidgets.QLabel(text)
        label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        hbox.addWidget(icon) 
        hbox.addWidget(label)
        self.layout.addLayout(hbox)
    
    def clear(self):
        self.achievement_count = 0

        while (item := self.layout.takeAt(0)) is not None:
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._delete_layout(item.layout()) # start the looping logic
    
    def _delete_layout(self, layout):
        while (item := layout.takeAt(0)) is not None:
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._delete_layout(item.layout())

