from PySide6 import QtCore, QtWebSockets
import json

with open("tokens.json") as f: 
    hass_config = json.load(f)["hass_config"]

HASS_WS_URL = hass_config['url']
TOKEN = hass_config['secret']

# TODO: i think this could be made more generic. we should be able to define a generic DataManager
# with subclasses for e.g. MetOfficeDataManager, StravaDataManager, etc.
# at the moment everything is tied to HASS data, even when HASS is not listened to
# passing an interval to _get_states_timer would be easy enough, and subclassable

class DataManager(QtCore.QObject):
    entities_updated = QtCore.Signal(dict)  # when all entities are refreshed
    entity_state_changed = QtCore.Signal(dict)  # when a single entity changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entities = {}
        self.entities_updated.emit(self.entities)

        # Single websocket
        self.ws = QtWebSockets.QWebSocket()

        # Timer for periodic get_states
        self._get_states_timer = QtCore.QTimer(self)
        self._get_states_timer.setInterval(60000)
        self._get_states_timer.timeout.connect(self.send_get_states)

        # Connect signals
        self.ws.connected.connect(self.on_connected)
        self.ws.textMessageReceived.connect(self.on_message)

        # Start connection
        self.ws.open(QtCore.QUrl(HASS_WS_URL))

        self._message_id = 2
        self._get_states_id = None  # Track the last get_states message id

    def on_connected(self):
        # Authenticate
        self.ws.sendTextMessage(json.dumps({"type": "auth", "access_token": TOKEN}))
        # After a short delay, send get_states and subscribe to events
        QtCore.QTimer.singleShot(1000, self.post_auth_setup)

    def post_auth_setup(self):
        self.send_get_states() # initial states fetch
        self.subscribe_state_changes() # subscribe to state changes

    def send_get_states(self):
        self._message_id += 1
        self._get_states_id = self._message_id
        self.ws.sendTextMessage(json.dumps({"id": self._message_id, "type": "get_states"}))
        self._get_states_timer.start()  # restart timer

    def subscribe_state_changes(self):
        self._message_id += 1
        self.ws.sendTextMessage(json.dumps({
            "id": self._message_id,
            "type": "subscribe_events",
            "event_type": "state_changed"
        }))
    
    # handles any outgoing traffic the user wants to orchestrate - use this to send messages to the websocket
    def send_command(self, msg):
        self._message_id += 1
        msg['id'] = self._message_id
        self.ws.sendTextMessage(json.dumps(msg))

    # handles all incoming traffic - this is the automatic response to any action or update
    def on_message(self, message):
        msg_dict = json.loads(message)

        # if type is "result", fetched all (direct request from timer)
        if msg_dict.get('type') == "result" and msg_dict.get('id') == self._get_states_id:
            self.entities = {x['entity_id']: x for x in msg_dict['result']}
            self.entities_updated.emit(self.entities)
        # if type is "event", is result of a subscribed state change
        elif msg_dict.get('type') == "event" and msg_dict.get('event', {}).get('event_type') == "state_changed":
            new_state = msg_dict['event']['data']['new_state']
            self.entities[new_state['entity_id']] = new_state
            self.entity_state_changed.emit(new_state)