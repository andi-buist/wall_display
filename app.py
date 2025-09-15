import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageEnhance
import paho.mqtt.client as mqtt

from modules.caching import *
from modules.entity_widgets.entity_button import *
from modules.entity_widgets.entity_mapsnap import *
from modules.entity_widgets.entity_rgb_spinner import *
from modules.entity_widgets.entity_slider import *
from modules.entity_widgets.entity_blueprint import *
from modules.mqtt_window import *

global_font = ('Nintendo DS BIOS',12)

"""
App Definition
"""
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect("192.168.0.180")
client.subscribe("system-entities")

window = MQTTWindow(client = client)
window.title("Example")
window.geometry("800x480")

style = ttk.Style()
#must come before .configure
style.theme_use('default')

#configure style
style.configure('.',  font = global_font)

notebook = ttk.Notebook(window)

blueprint_menu = ttk.Frame()
light_menu = ttk.Frame()
map_menu = ttk.Frame()

notebook.add(blueprint_menu)
notebook.add(light_menu)
notebook.add(map_menu)
notebook.tab(0, text = "Home")
notebook.tab(1, text = "Lighting")
notebook.tab(2, text = "Map")
notebook.pack(side = tk.RIGHT,
              fill = 'y')

def light_switch(self, entity_id):
        entity = self.entity_dict[entity_id]

        if entity['state'] == "on":
            msg_dict = {'action': "light.turn_off", 'entity_id': entity_id}
        else:
            msg_dict = {'action': "light.turn_on", 'entity_id': entity_id, 'data': {'brightness': 255}}

        self.client.publish("lights",json.dumps(msg_dict))

hallway_poly = [(60,0),(510,0),(510,100),(200,100),(200,140),(60,140)]
lounge_poly = [(60,140),(200,140),(200,100),(510,100),(510,450),(60,450),(60,380),(0,380),(0,250),(60,250)]
kitchen_poly = [(510,0),(820,0),(820,230),(750,230),(820,230),(820,450),(510,450),(510,230),(580,230),(510,230)]

hallway_decor = {
     "h_cabinet": [(80,140),(80,100),(180,100),(180,140)],
     "stairs": [(290,0),(510,0),(510,100),(290,100)]
     }
lounge_decor = {
     "sofa": [(510,450),(290,450),(290,380),(440,380),(440,290),(510,290)],
     "footstool": [(340,350),(340,280),(410,280),(410,350)],
     "l_cabinet": [(90,450),(90,400),(270,400),(270,450)],
     "seat": [(0,370),(0,260),(50,260),(50,370)]
     }
kitchen_decor = {
     "counters": [(510,230),(570,230),(570,390),(760,390),(760,230),(820,230),(820,450),(510,450)],
     "k_chair1": [(600,40),(650,40),(650,90),(600,90)],
     "k_chair2": [(680,40),(730,40),(730,90),(680,90)],
     "k_chair3": [(600,120),(650,120),(650,170),(600,170)],
     "k_chair4": [(680,120),(730,120),(730,170),(680,170)],
     "k_table": [(590,70),(740,70),(740,140),(590,140)]
}

text_output = ttk.Label(window, text = "...")
text_output.pack()

blueprint_f1 = EntityBlueprint(blueprint_menu, client, border = 10, size = 400)

def print_out(current_room: dict):
     text_output['text'] = current_room

blueprint_f1.add_body("hallway", hallway_poly, print_out)
for k,v in hallway_decor.items(): blueprint_f1.add_body(k, v, type = 'decor')
blueprint_f1.add_body("lounge", lounge_poly, print_out)
for k,v in lounge_decor.items(): blueprint_f1.add_body(k, v, type = 'decor')
blueprint_f1.add_body("kitchen", kitchen_poly, print_out)
for k,v in kitchen_decor.items(): blueprint_f1.add_body(k, v, type = 'decor')
blueprint_f1.grid()

# TODO: Investigate whether parentage allows for us to pass variables down from e.g. blueprint -> light switches? Good test case: new light switch parent of blueprint, check if children in room, else set child active = False
# if no pleasant way to do this, another route could be doing wo_getinfo on master? Or maybe a separate context field so blueprint can be however many layers deep, and then fetch children of context?

## doesn't work
#test_switch = EntityButton(blueprint_f1, client, light_switch, entity_id = 'light.desk_light')
#test_switch.pack()

light_switches = EntityButton(light_menu, client, light_switch, 'light')
light_switches.grid(row = 0, columnspan = 2)

light_sliders = EntitySlider(light_menu, client, entity_id = 'light.desk_light', orient = 'vertical')
light_sliders.grid(column = 0, row = 1, ipadx = 10)

light_rgb = EntityRGBSpinners(light_menu, client, entity_id = 'light.desk_light')
light_rgb.grid(column = 1, row = 1)

map_snap = EntityMapSnap(map_menu, client, ['person', 'zone'], size = 400)
map_snap.pack()

window.mainloop()