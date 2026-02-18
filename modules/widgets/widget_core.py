from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QImage, QPixmap
from ..data_manager import HASSDataManager
import theme

class HASSWidget(QtWidgets.QWidget):
    def __init__(self,
                 data_manager: HASSDataManager,
                 entity_types: str | list[str] = None,
                 entity_ids: str | list[str] = None, 
                 parent = None,
                 **kwargs):
        super().__init__(parent)
        self.data_manager = data_manager

        self.entity_types = []
        self.entity_ids = []

        match entity_types:
            case str():
                self.entity_types.append(entity_types)
            case list():
                self.entity_types = self.entity_types + entity_types
        match entity_ids:
            case str():
                self.entity_ids.append(entity_ids)
            case list():
                self.entity_ids = self.entity_ids + entity_ids

        self.data_manager.data_update.connect(self._on_data_update)
        self.data_manager.data_event.connect(self._on_data_event)

        self.data = {}

        self.error_label = None

    # TODO: I think there's quite a lot of redundancy here, partly so we have a generic response to
    # update/events that then calls a subclassable response, which is fine... but also why are we storing data
    # in the widget at all? surely easier just to fetch the data from the bundled datamanager. we're duping
    # remove this.

    def _on_data_update(self, data):
        # Filter for relevant data
        if len(self.entity_types) > 0:
            self.entity_ids = list(set(self.entity_ids + self._get_matching_entity_ids_by_type(data))) # if types specified, get valid ids and merge into entity_ids (unique)

        relevant = {}

        for eid in self.entity_ids:
            if eid in data:
                relevant[eid] = data[eid]

        self.data.update(relevant)
        self.on_entities_update(relevant)

    def _on_data_event(self, event):
        self.on_entity_update(event)

    def on_entities_update(self, data):
        """Override in subclass: called when all data are refreshed."""
        pass

    def on_entity_update(self, entity):
        """Override in subclass: called when a single entity changes."""
        pass

    def _get_matching_entity_ids_by_type(self, data: dict):
        relevant_entities = []
        if self.entity_types:
            for type in self.entity_types:
                relevant_entities = relevant_entities + [id for id in data.keys() if type in id]

        return relevant_entities
    
    def show_error(self, message):
        if self.error_label:
            self.error_label.deleteLater()
            self.error_label = None

        self.error_label = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(self.error_label)

        error_image = QtWidgets.QLabel()
        pixmap = QPixmap(theme.common_image_paths["bug"]).scaled(512,512, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        error_image.setPixmap(pixmap)
        error_image.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(error_image)

        error_msg = QtWidgets.QLabel(message)
        error_msg.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(error_msg)

        self.error_label.setLayout(layout)
        self.error_label.show()
        self.error_label.setGeometry(0, 0, self.width(), self.height())
        self.error_label.raise_()