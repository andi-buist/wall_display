import tkinter as tk
from tkinter import ttk

import paho.mqtt.client as mqtt
import json

window = tk.Tk()
window.title("Example")
window.geometry("480x300")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect('192.168.0.180')
client.subscribe("system-def")
client.loop_start()

entity_dict = {}

def on_system_def(client, userdata, msg):
    msg_json = json.loads(msg.payload)
    for entity in msg_json:
        key = entity["entity_id"]

        if key not in entity_dict.keys():
            make_button(key, entity)

        entity_dict[key] = entity

def make_button(key, entity):
    _button = ttk.Button(master = window, text = entity["attributes"]["friendly_name"], command = lambda x = key: function1(x))
    _button.pack()

client.on_message = on_system_def

client.publish("system-def-request", '{"entity_type": "light"}')

def function1(key):
    client.publish("system-def-request", '{"entity_type": "light"}')

    entity = entity_dict[key]

    if entity["state"] == "on":
        action = "light.turn_off"
        #entity_dict[key]["state"] = "off"
    else:
        action = "light.turn_on"
        #entity_dict[key]["state"] = "on"

    msg_dict = {"action": action, "entity_id": entity["entity_id"]}
    client.publish("lights",json.dumps(msg_dict))

window.mainloop()