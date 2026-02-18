from PySide6 import QtCore, QtWebSockets
from PySide6.QtNetwork import QAbstractSocket
import json

# TODO: Continue with subclassing

class DataManager(QtCore.QObject):
    '''
    A generic data management object that subscribes to signals to keep an internal entity dictionary updated.
    Can also be set up to do a complete refresh at a scheduled rate (ms).
    '''
    data_update = QtCore.Signal()  # signal triggered by data refreshing
    data_event = QtCore.Signal(dict)  # signal triggered by a heard pubsub event

    def __init__(self,
                 url: str,
                 auth_token: str,
                 scheduled_refresh_rate: int = None,
                 parent=None):
        '''
        Docstring for __init__
        
        :param url: Pubsub URL
        :type url: str
        :param auth_token: Pubsub authorisation token
        :type auth_token: str
        :param scheduled_refresh_rate: Number of milliseconds between complete entity dictionary refreshes
        :type scheduled_refresh_rate: int
        '''
        super().__init__(parent)

        # Single websocket
        self.ws = QtWebSockets.QWebSocket()

        # Connection settings
        self.connection_settings = {'url': url,
                                    'auth_token': auth_token}

        # Self-check timer for diagnostics, connection timeout, etc.
        self._check_timer = QtCore.QTimer(self)
        self._check_timer.setInterval(30000)
        self._check_timer.timeout.connect(self._self_check)

        # Timer for periodic data request
        if scheduled_refresh_rate:
            self._schedule_timer = QtCore.QTimer(self)
            self._schedule_timer.setInterval(scheduled_refresh_rate)
            self._schedule_timer.timeout.connect(self._send_data_request)

        # Connect signals
        self.ws.connected.connect(self._on_connected)
        self.ws.textMessageReceived.connect(self._on_message)

        # Start connection
        self._open_connection()

        self._message_id = 2
        self._get_states_id = None  # Track the last get_states message id
    
    def _open_connection(self):
        self.ws.open(QtCore.QUrl(self.connection_settings['url']))

    # Initial connection on ws.connected, send authentication token
    def _on_connected(self):
        # Authenticate
        self.ws.sendTextMessage(json.dumps({"type": "auth", "access_token": self.connection_settings['auth_token']}))
        # After a short delay, send get_states and subscribe to events
        QtCore.QTimer.singleShot(1000, self._post_auth_setup)

    # handles all incoming traffic - this is the automatic response to any action or update
    def _on_message(self, message):
        pass
    
    # First data fetch, stock self & subscribe to state changes
    def _post_auth_setup(self):
        self._send_data_request() # initial request
        self._subscribe() # subscribe to state changes
        self._check_timer.start()

        # If scheduled, restart schedule timer
        if hasattr(self, "_schedule_timer"):
            self._schedule_timer.start()

    # Regular internal check for closed connection re-establishment
    def _self_check(self):
        if self.ws.state() == QAbstractSocket.SocketState.ConnectedState:
            self.ws.ping()
        else:
            print(str(self) + " WebSocket connection is offline. Attempting restart...")
            self._open_connection()

    # Get data 
    def _send_data_request(self):
        """
        Overwrite in subclass
        """
        pass

    # Event subscription 
    def _subscribe(self):
        """
        Overwrite in subclass
        """
        pass
    
    # handles any outgoing traffic the user wants to orchestrate - use this to send messages to the websocket
    def send_command(self, msg):
        self._message_id += 1
        msg['id'] = self._message_id
        self.ws.sendTextMessage(json.dumps(msg))

class HASSDataManager(DataManager):
    def __init__(self, 
                 url: str,
                 auth_token: str,
                 scheduled_refresh_rate: int = None, 
                 parent = None):
        super().__init__(url, auth_token, scheduled_refresh_rate, parent)

        self.data: dict = {}
    
    def _on_message(self, message):
        msg_dict = json.loads(message)

        # if type is "result", fetched all (direct request from timer)
        if msg_dict.get('type') == "result" and msg_dict.get('id') == self._get_states_id:
            self.data = {x['entity_id']: x for x in msg_dict['result']}
            self.data_update.emit()
        # if type is "event", is result of a subscribed state change
        elif msg_dict.get('type') == "event" and msg_dict.get('event', {}).get('event_type') == "state_changed":
            new_state = msg_dict['event']['data']['new_state']
            self.data[new_state['entity_id']] = new_state
            self.data_update.emit()
            self.data_event.emit(new_state)
    
    def _send_data_request(self):
        print(str(self) + " refreshing all data")
        self._message_id += 1
        self._get_states_id = self._message_id
        self.ws.sendTextMessage(json.dumps({"id": self._message_id, "type": "get_states"}))
    
    def _subscribe(self):
        self._message_id += 1
        self.ws.sendTextMessage(json.dumps({
            "id": self._message_id,
            "type": "subscribe_events",
            "event_type": "state_changed"
        }))