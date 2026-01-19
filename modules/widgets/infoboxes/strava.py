from modules.widgets.infoboxes.base import *
from PySide6 import QtWidgets, QtGui, QtCore
from PIL import ImageQt
from typing import Literal
from pathlib import Path
import textwrap

import theme


class StravaInfoBox(InfoBox): 
    def __init__(self, view_data: dict): 
        super().__init__() 
        self.vbox = QtWidgets.QVBoxLayout(self)
        self.achievement_count: int = 0

        data = view_data['data']
        kiosk_data = data['data'][data['kiosk_selected']]

        self.add_kcal(kiosk_data['calories'])

        for achievement in kiosk_data['achievements'].values():
            for a in achievement['achievements']:
                self.add_achievement("\n".join(textwrap.wrap(achievement['name'], 32)), a['rank'])

    def add_kcal(self, kcals: int|float):
        kcal_title_bar = QtWidgets.QLabel("Calories:")
        kcal_title_bar.setStyleSheet("font-weight: bold")
        kcal_title_bar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.vbox.addWidget(kcal_title_bar)

        hbox = QtWidgets.QHBoxLayout()
        hbox.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        icon = QtWidgets.QLabel(pixmap = QtGui.QPixmap.fromImage(ImageQt.ImageQt(theme.filestore['ui']['icons']['misc']['fire'])))
        icon.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)
        label = QtWidgets.QLabel(f"{kcals}")
        label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        hbox.addWidget(icon) 
        hbox.addWidget(label)
        self.vbox.addLayout(hbox)


    def add_achievement(self, text: str = None, rank: Literal[1,2,3] = 1):
        if self.achievement_count == 0:
            self.achievement_title_bar = QtWidgets.QLabel("No achievements")
            self.achievement_title_bar.setStyleSheet("font-weight: bold")
            self.achievement_title_bar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.vbox.addWidget(self.achievement_title_bar)

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
        self.vbox.addLayout(hbox)