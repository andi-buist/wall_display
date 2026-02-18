from PySide6 import QtCore, QtWebSockets
from PySide6.QtNetwork import QAbstractSocket
from typing import Literal
from modules.api import get_data
import json
import base64
import requests
import datetime
import time
import pandas as pd

# Met Office
from urllib.parse import quote
from PIL import Image
import xarray as xr
import os
import numpy as np

class DataManager(QtCore.QObject):
    '''
    A generic data management object that subscribes to signals to keep an internal entity dictionary updated.
    Can be set up to do a complete refresh at a scheduled rate (ms).
    '''
    data_update = QtCore.Signal()  # signal triggered by data refreshing
    data_event = QtCore.Signal(dict)  # signal triggered by a heard pubsub event

    def __init__(self,
                 url: str = None,
                 auth_token: str = None,
                 refresh_rate: int = None,
                 connection_type: Literal['ws','api'] = 'ws'):
        """
        Instantiate a new generic DataManager

        :param url: WebSocket URL
        :type url: str
        :param auth_token: WebSocket authorisation token
        :type auth_token: str
        :param refresh_rate: Number of milliseconds between complete entity dictionary refreshes
        :type refresh_rate: int
        :param connection_type: Whether to establish a maintained WebSocket connection or perform routine API fetches
        :type connection_type: Literal['ws', 'api']
        """
        super().__init__(parent = None)
        self.connection_type = connection_type
        self.data: dict | list
        
        match self.connection_type:
            case 'ws':
                # Connection settings
                self.connection_settings = {'url': url,
                                            'auth_token': auth_token}

                # Message ID tracking
                self._message_id = 2
                self._get_states_id = None  # Track the last get_states message id

                #WebSocket
                self.ws = QtWebSockets.QWebSocket()

                # Self-check timer for WebSocket diagnostics, connection timeout, etc.
                self._check_timer = QtCore.QTimer(self)
                self._check_timer.setInterval(30000)
                self._check_timer.timeout.connect(self._ws_self_check)

                # Connect signals
                self.ws.connected.connect(self._ws_on_connected)
                self.ws.textMessageReceived.connect(self._ws_on_message)

                # Start connection
                self._ws_open_connection()
            case 'api':
                # Initial data fetch, _schedule_timer will take over from then.
                self._send_data_request()
        
        # Timer for periodic data request
        if refresh_rate:
            self._schedule_timer = QtCore.QTimer(self)
            self._schedule_timer.setInterval(refresh_rate)
            self._schedule_timer.timeout.connect(self._send_data_request)
            # After a delay, start the timer. Longer to permit WS connection setup to complete
            QtCore.QTimer.singleShot(10000, self._schedule_timer.start)
    
    def _ws_open_connection(self) -> None:
        self.ws.open(QtCore.QUrl(self.connection_settings['url']))

    # Initial connection on ws.connected, send authentication token
    def _ws_on_connected(self) -> None:
        # Authenticate
        self.ws.sendTextMessage(json.dumps({"type": "auth", "access_token": self.connection_settings['auth_token']}))
        # After a short delay, send get_states and subscribe to events
        QtCore.QTimer.singleShot(1000, self._ws_post_auth_setup)

    # First data fetch, stock self & subscribe to state changes
    def _ws_post_auth_setup(self) -> None:
        self._send_data_request() # initial request
        self._ws_subscribe() # subscribe to state changes
        self._check_timer.start()

    # Regular internal check for closed connection re-establishment
    def _ws_self_check(self) -> None:
        if self.ws.state() == QAbstractSocket.SocketState.ConnectedState:
            self.ws.ping()
        else:
            print(str(self) + " WebSocket connection is offline. Attempting restart...")
            self._ws_open_connection()
    
    # Event subscription 
    def _ws_subscribe(self) -> None:
        """
        Overwrite in subclass
        """
        pass
    
    # Respond to incoming message
    def _ws_on_message(self, message) -> None:
        """
        Overwrite in subclass
        """
        pass

    # Get data 
    def _send_data_request(self) -> None:
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
                 refresh_rate: int = None):
        super().__init__(url = url, 
                         auth_token = auth_token, 
                         refresh_rate = refresh_rate,
                         connection_type = 'ws')
    
    def _send_data_request(self):
        print(str(self) + " refreshing all data")
        self._message_id += 1
        self._get_states_id = self._message_id
        self.ws.sendTextMessage(json.dumps({"id": self._message_id, "type": "get_states"}))
    
    def _ws_subscribe(self) -> None:
        self._message_id += 1
        self.ws.sendTextMessage(json.dumps({
            "id": self._message_id,
            "type": "subscribe_events",
            "event_type": "state_changed"
        }))
    
    def _ws_on_message(self, message) -> None:
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

class APIDataManager(DataManager):
    def __init__(self,
                 url: str = None,
                 params: dict = None,
                 headers: dict = None,
                 max_retries: int = 5,
                 refresh_rate: int = None):
        
        self.connection_settings = {"url": url,
                                    "params": params,
                                    "headers": headers,
                                    "max_retries": max_retries}

        super().__init__(refresh_rate = refresh_rate,
                         connection_type = 'api')
    
    def _send_data_request(self):
        for attempt in range(self.connection_settings['max_retries']):
            try:
                response = requests.get(url =self.connection_settings['url'],
                                        params = self.connection_settings['params'],
                                        headers = self.connection_settings['headers'])
                break
            except requests.exceptions.ConnectionError:
                time.sleep(2 ** attempt)
        return response

class AstronomyDataManager(APIDataManager):
    def __init__(self,
                 api_user_id: str,
                 api_user_secret: str,
                 lon_lat: tuple[float,float],
                 refresh_rate: int = None):
        
        self.lon_lat = lon_lat

        userpass = api_user_id + ":" + api_user_secret
        authString = base64.b64encode(userpass.encode()).decode()

        params = {"longitude": str(lon_lat[0]),
                  "latitude": str(lon_lat[1]),
                  "elevation": str(0),
                  "from_date": None,
                  "to_date": None,
                  "time": None}
        headers = {"Authorization": "Basic " + authString}

        super().__init__(url = "https://api.astronomyapi.com/api/v2/bodies/positions/",
                         params = params,
                         headers = headers,
                         refresh_rate = refresh_rate)

    def _send_data_request(self):
        print(str(self) + " refreshing all data")

        # update request time component in params
        dt = datetime.datetime.now(datetime.timezone.utc)
        self.connection_settings['params']['from_date'] = dt.date()
        self.connection_settings['params']['to_date'] = dt.date()
        self.connection_settings['params']['time'] = dt.strftime("%H:%M:%S")

        response = super()._send_data_request().json()
        self.data = [x[0] for x in pd.DataFrame.from_dict(response['data']['table']['rows'])['cells']]
        self.data_update.emit()

class MetOfficeDataManager(APIDataManager):
    def __init__(self,
                 api_order_id: str,
                 api_file_id: str,
                 api_user_secret: str,
                 lon_lat: tuple[float,float],
                 model_type: Literal['precipitation', 'temperature', 'cloud'],
                 refresh_rate: int = None):
        
        self.lon_lat = lon_lat
        self.model_type = model_type

        self.api_order_id = api_order_id
        self.api_file_id = api_file_id

        headers = {"apikey": api_user_secret,
                   "Accept": "*/*"}
        
        super().__init__(headers = headers,
                         refresh_rate = refresh_rate)
    
    def _send_data_request(self):
        print(str(self) + " refreshing all data")

        # update request time component in params
        current_file_id = quote(self.api_file_id + str(datetime.datetime.now().hour), safe="")
        url = f"https://data.hub.api.metoffice.gov.uk/atmospheric-models/1.0.0/orders/{self.api_order_id}/latest/{current_file_id}/data"

        self.connection_settings['url'] = url

        response = super()._send_data_request()

        # .grib parsing
        raw_path =".cache/met_office/grib_bytes_tmp.grib2"
        os.makedirs(os.path.dirname(raw_path), exist_ok=True)
        with open(raw_path, "wb") as f:
            f.write(response.content)

        data = xr.open_dataset(raw_path,
                            engine="cfgrib",
                            backend_kwargs={"indexpath": ""}) # prevent idx file gen
        # find name of primary data key
        primary_key = list(data.data_vars.keys())[0]

        # get values as array
        values = np.flip(data[primary_key].values,0)
        value_range = (values.min(), values.max())
        # normalise
        values = (((values - values.min())/(values.max() - values.min()))*255).astype(np.uint8)

        self.data = {"image": Image.fromarray(values),
                     "value_range": value_range,
                     "timestamp": datetime.datetime.now()}
        self.data_update.emit()
        