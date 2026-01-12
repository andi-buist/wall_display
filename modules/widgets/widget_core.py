from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QImage, QPixmap
from pubsub import pub
from PIL import Image
from ..websocket_defs import HASSDataManager
from theme import common_image_paths

class HASSWidget(QtWidgets.QWidget):
    def __init__(self,
                 data_manager: HASSDataManager,
                 entity_types: str | list[str] = None,
                 entity_ids: str | list[str] = None, 
                 parent = None,
                 **kwargs):
        super().__init__(parent)
        self.data_manager = data_manager

        if entity_types:
            if isinstance(entity_types, list):
                self.entity_types = entity_types
            else:
                self.entity_types = [entity_types]

        if entity_ids:
            if isinstance(entity_ids, list):
                self.entity_ids = entity_ids 
            else:
                self.entity_ids = [entity_ids]

        self.data_manager.entities_updated.connect(self._on_entities_updated)
        self.data_manager.entity_state_changed.connect(self._on_entity_state_changed)
        # Optionally, store current entity state(s)
        self.entities = {}

        self.error_label = None

    def _on_entities_updated(self, entities):
        # Filter for relevant entities

        if hasattr(self, "entity_types"):
            self.entity_ids = self._get_matching_entity_ids_by_type(entities)

        relevant = {eid: entities[eid] for eid in self.entity_ids if eid in entities}
        self.entities.update(relevant)
        self.on_entities_update(relevant)

    def _on_entity_state_changed(self, entity):
        if entity['entity_id'] in self.entity_ids:
            self.entities[entity['entity_id']] = entity
            self.on_entity_update(entity)

    def on_entities_update(self, entities):
        """Override in subclass: called when all entities are refreshed."""
        pass

    def on_entity_update(self, entity):
        """Override in subclass: called when a single entity changes."""
        pass

    def _get_matching_entity_ids_by_type(self, entities: dict):
        relevant_entities = []
        for type in self.entity_types:
            relevant_entities = relevant_entities + [id for id in entities.keys() if type in id]

        return relevant_entities
    
    def show_error(self, message):
        # Remove previous error label if present
        if self.error_label:
            self.error_label.deleteLater()
            self.error_label = None

        # Create error image and message label
        self.error_label = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(self.error_label)

        # Error image (use a built-in Qt icon or your own)
        error_image = QtWidgets.QLabel()
        pixmap = QPixmap(common_image_paths["bug"]).scaled(512,512, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        error_image.setPixmap(pixmap)
        error_image.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(error_image)

        # Error message
        error_msg = QtWidgets.QLabel(message)
        error_msg.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(error_msg)

        # Add to main layout
        self.error_label.setLayout(layout)
        self.error_label.show()
        self.error_label.setGeometry(0, 0, self.width(), self.height())
        self.error_label.raise_()