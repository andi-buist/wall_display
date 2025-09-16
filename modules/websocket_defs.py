from websocket import *
from threading import *
import tkinter as tk
import json
import time
import threading

HASS_WS_URL = "ws://192.168.0.180:8123/api/websocket"
with open(".secrets/hass.txt") as f: 
    TOKEN = f.read()

#define some helper functions that do things on connection - then, make connection, point to helpers, run forever **on thread**.
#note: i suppose this could be where we diversify? start_connect could all be the same, but then the target lambda different dependent on use-case
def state_change_socket(socket_uid: int, action: callable):
    def on_open(ws: WebSocket):
        ws.send(json.dumps({"type": "auth", "access_token": TOKEN}).encode('utf-8'))
        print("state_change_socket opened:", ws)
        ws.send(json.dumps({"id": socket_uid, "type": "subscribe_events", "event_type": "state_changed"}).encode('utf-8'))
    
    def on_message(ws: WebSocket, message):
        msg_dict: dict = json.loads(message)
        print("state_change_socket message:", ws, msg_dict['event']['data']['new_state']['entity_id'])
        action(msg_dict)
        
    def on_error(ws: WebSocket, error):
        print("state_change_socket error:", ws, error)

    def on_close(ws: WebSocket, *args):
        print("state_change_socket closed:", *args)

    """The main, looping functionality of the connect_to_socket function. Called at end of def."""
    def main():
        #enableTrace(True) # useful for watching events pass by. maybe print this to a live console? that would be quite cool!
        ws = WebSocketApp(HASS_WS_URL,
                        on_open = on_open, 
                        on_message = on_message, 
                        on_error = on_error, 
                        on_close = on_close)
        
        # #attach a call to shut down threads when window closes, then close
        # def on_window_close():
        #     ws.close()
        # window.protocol("WM_DELETE_WINDOW", on_window_close)

        #runs forever on the thread!
        ws.run_forever()
    
    main()

#define some helper functions that do things on connection - then, make connection, point to helpers, run forever **on thread**.
#note: i suppose this could be where we diversify? start_connect could all be the same, but then the target lambda different dependent on use-case
def all_entities_socket(socket_uid: int, action: callable):
    def on_open(ws: WebSocket):
        def periodic_send():
            message_id = 2
            while True:
                message_id += 1
                ws.send(json.dumps({"id": message_id,"type": "get_states"}).encode('utf-8'))
                time.sleep(60)
        
        ws.send(json.dumps({"type": "auth", "access_token": TOKEN}).encode('utf-8'))
        print("all_entities_socket opened:", ws)

        threading.Thread(target = periodic_send).start()
    
    def on_message(ws: WebSocket, message: dict):
        print("all_entities_socket messaged:", ws) # don't print message, too large
        msg_dict: dict = json.loads(message)
        action(msg_dict)
        
    def on_error(ws: WebSocket, error):
        print("all_entities_socket error:", ws, error)

    def on_close(ws: WebSocket, *args):
        print("all_entities_socket closed:", *args)

    """The main, looping functionality of the connect_to_socket function. Called at end of def."""
    def main():
        #enableTrace(True) # useful for watching events pass by. maybe print this to a live console? that would be quite cool!
        ws = WebSocketApp(HASS_WS_URL,
                        on_open = on_open, 
                        on_message = on_message, 
                        on_error = on_error, 
                        on_close = on_close)
        
        ws.run_forever()

    main()

class ThreadedWebsocket:
    def __init__(self, socket_uid: int):
        self.ws =  WebSocketApp(HASS_WS_URL,
                        on_open = self.on_open,
                        on_message = self.on_message,
                        on_error = self.on_error, 
                        on_close = self.on_close)
        self.message_id = 2
        self.permanent_thread = threading.Thread(target = self.ws.run_forever, daemon = True)
        self.permanent_thread.start()

    def on_open(self, ws):
        self.ws.send(json.dumps({"type": "auth", "access_token": TOKEN}).encode('utf-8'))
        print("local_socket opened:", ws)
    
    def on_message(self, ws, message):
        print("local_socket messaged:", ws, message)

    def on_error(self, ws, error):
        print("local_socket error:", ws, error)

    def on_close(self, ws, *args):
        print("local_socket closed:", ws, *args)
    
    def send(self, message: dict):
        message['id'] = self.message_id
        self.ws.send(json.dumps(message).encode('utf-8'))
        self.message_id += 1
