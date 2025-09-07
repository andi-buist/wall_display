import tkinter as tk
from tkinter import ttk

import paho.mqtt.client as mqtt
import json

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect('192.168.0.180')
client.subscribe("system-def")
client.loop_start()

def on_system_def(client, userdata, msg):
    msg_json = json.loads(msg.payload)
    for entity in msg_json:
        _button = ttk.Button(master = window, text = entity["attributes"]["friendly_name"], command = lambda x = entity: function1(x))
        _button.pack()

client.on_message = on_system_def

client.publish("system-def-request", '{"entity_type": "light"}')

def function1(entity):
    if entity["state"] == "on":
        action = "light.turn_off"
    else:
        action = "light.turn_on"

    msg_dict = {"action": action, "entity_id": entity["entity_id"]}
    print(json.dumps(msg_dict))
    client.publish("lights",json.dumps(msg_dict))

window = tk.Tk()
window.title("Example")
window.geometry("480x300")



window.mainloop()