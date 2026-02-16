from .widget_core import HASSWidget
from PySide6.QtWidgets import QPushButton

class HASSEntityButton(HASSWidget):
    def __init__(self, data_manager, entity_id: str=None, command: callable=None, parent=None): #
        super().__init__(data_manager, entity_ids=entity_id, parent=parent)

        if not command:
            command = HASSEntityButton.light_switch

        self.button = QPushButton(self)
        self.button.clicked.connect(lambda: command(self, entity_id))
        # Layout setup, etc.

    def on_entity_update(self, entity):
        # Update button text, color, etc. based on entity state
        self.button.setText(entity['attributes'].get('friendly_name', entity['entity_id']))
        # Example: change color if light is on/off
        if entity['state'] == "on":
            self.button.setStyleSheet("background: yellow;")
        else:
            self.button.setStyleSheet("")
    
    def light_switch(self, entity_id):
        entity = self.entities[entity_id]

        msg_template = dict(type = "call_service",
                            domain = "light",
                            target = dict(entity_id = entity_id))
        #for messages that would return a response, include return_response = True

        if entity['state'] == "on":
            msg_template['service'] = "turn_off"
        else:
            msg_template['service'] = "turn_on"
            msg_template['service_data'] = dict(brightness = 255)

        self.data_manager.send_command(msg_template)