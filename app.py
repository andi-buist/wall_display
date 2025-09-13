import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageEnhance
import paho.mqtt.client as mqtt

from modules.caching import *
from modules.entity_widgets.entity_button import *
from modules.entity_widgets.entity_mapsnap import *
from modules.entity_widgets.entity_rgb_spinner import *
from modules.entity_widgets.entity_slider import *
from modules.hass_engine import *

global_font = ('Nintendo DS BIOS',12)

"""
App Definition
"""
window = tk.Tk()
window.title("Example")
window.geometry("800x480")

style = ttk.Style()
#must come before .configure
style.theme_use('default')

#configure style
style.configure('.',  font = global_font)
style.configure('Active.TButton', backgroundcolor = "#333333")
style.configure('Inactive.TButton', backgroundcolor = "#dddddd")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect("192.168.0.180")
client.subscribe("system-entities")

h = HASSEngine(client, window)

notebook = ttk.Notebook(window)

light_menu = ttk.Frame()
map_menu = ttk.Labelframe()

notebook.add(light_menu)
notebook.add(map_menu)
notebook.tab(0, text = "Lighting")
notebook.tab(1, text = "Map")
notebook.pack(side = tk.RIGHT,
              fill = 'y')

def light_switch(self, entity_id):
        entity = self.entity_dict[entity_id]

        if entity['state'] == "on":
            msg_dict = {'action': "light.turn_off", 'entity_id': entity_id}
        else:
            msg_dict = {'action': "light.turn_on", 'entity_id': entity_id, 'data': {'brightness': 255}}

        self.client.publish("lights",json.dumps(msg_dict))

light_switches = EntityButton(light_menu, client, light_switch, 'light')
light_switches.grid(row = 0, columnspan = 2)

light_sliders = EntitySlider(light_menu, client, entity_id = 'light.desk_light', orient = 'vertical')
light_sliders.grid(column = 0, row = 1, ipadx = 10)

light_rgb = EntityRGBSpinners(light_menu, client, entity_id = 'light.desk_light')
light_rgb.grid(column = 1, row = 1)

map_snap = EntityMapSnap(map_menu, client, ['person', 'zone'], size = 400)
map_snap.pack()

window.mainloop()