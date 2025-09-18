import theme

import os
from websocket import *
import tkinter as tk
from tkinter import ttk

from modules.hass_app import *
from modules.caching import *
from modules.websocket_defs import *
from modules.entity_widgets.entity_blueprint import *
from modules.entity_widgets.entity_button import *
from modules.entity_widgets.entity_mapsnap import *
from modules.entity_widgets.entity_rgb_spinner import *
from modules.entity_widgets.entity_slider import *

#establish local sending socket
local_ws = ThreadedWebsocket(2)

""""
Main App Functions
"""

"""
App Definition
"""
window = HASSApp()
window.title("Example")
window.geometry("800x480")

style = theme.CreateStyle()

notebook = ttk.Notebook(window)

blueprint_menu = ttk.Frame(notebook, style = 'EntityWidget.TFrame')
light_menu = ttk.Frame(notebook, style = 'EntityWidget.TFrame')
map_menu = ttk.Frame(notebook, style = 'EntityWidget.TFrame')

notebook.add(blueprint_menu)
notebook.add(map_menu)
notebook.tab(0, text = "Home")
notebook.tab(1, text = "Map")
notebook.pack(side = tk.RIGHT,
              fill = 'y')

"""Floor 1 Geometry"""
hallway_poly = [(60,0),(510,0),(510,100),(200,100),(200,140),(60,140)]
lounge_poly = [(60,140),(200,140),(200,100),(510,100),(510,450),(60,450),(60,380),(0,380),(0,250),(60,250)]
kitchen_poly = [(510,0),(820,0),(820,230),(750,230),(820,230),(820,450),(510,450),(510,230),(580,230),(510,230)]

hallway_decor = {
     "h_cabinet": [(80,140),(80,100),(180,100),(180,140)],
     "f1_stairs": [(290,0),(510,0),(510,100),(290,100)]
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

stair_up_arrow = [(290,30),(450,30),(450,0),(510,50),(450,100),(450,70),(290,70)]

"""Floor 2 Geometry"""
landing_poly = [(310,0),(590,0),(590,180),(270,180),(270,100),(310,100)]
landing_decor = [(310,0),(510,0),(510,100),(310,100)]
bathroom_poly = [(590,0),(770,0),(770,180),(590,180)]
office_poly = [(520,180),(770,180),(770,450),(430,450),(430,250),(520,250)]
bedroom_poly = [(270,180),(270,200),(0,200),(0,450),(360,450),(360,180)]
spareroom_poly = [(0,0),(310,0),(310,100),(270,100),(270,200),(0,200)]

stair_down_arrow = [(310,50),(370,0),(370,30),(510,30),(510,70),(370,70),(370,100)]

#blueprint widgets
blueprint_f1 = EntityBlueprint(blueprint_menu, border = 10, size = 400, state_channel = "blueprint_f1", initial_state = True)
blueprint_f2 = EntityBlueprint(blueprint_menu, border = 10, size = 400, state_channel = "blueprint_f2", initial_state = False)

#first floor
blueprint_f1.add_body("hallway", hallway_poly)
for k,v in hallway_decor.items(): blueprint_f1.add_body(k, v, type = 'decor')
blueprint_f1.add_body("lounge", lounge_poly)
for k,v in lounge_decor.items(): blueprint_f1.add_body(k, v, type = 'decor')
blueprint_f1.add_body("kitchen", kitchen_poly)
for k,v in kitchen_decor.items(): blueprint_f1.add_body(k, v, type = 'decor')

blueprint_f1.add_body("blueprint_f2", stair_up_arrow, type = 'navigate')

blueprint_f1.grid(row = 0)

#second floor
blueprint_f2.add_body("landing", landing_poly)
blueprint_f2.add_body("f2_stairs", landing_decor, type = 'decor')
blueprint_f2.add_body("bathroom", bathroom_poly)
blueprint_f2.add_body("office", office_poly)
blueprint_f2.add_body("bedroom", bedroom_poly)
blueprint_f2.add_body("spareroom", spareroom_poly)

blueprint_f2.add_body("blueprint_f1", stair_down_arrow, type = 'navigate')

blueprint_f2.grid(row = 0)

#blueprint switches
def light_switchboard(master, entity_id: str, state_channel: str):
    out = ttk.Frame(master)
    out.grid_columnconfigure(0, weight = 1)
    out.grid_columnconfigure(1, weight = 4)

    EntityButton(out, local_ws, EntityButton.light_switch, entity_id = entity_id, state_channel = state_channel, initial_state = False).grid(row = 0, columnspan = 2)
    EntitySlider(out, local_ws, entity_id = entity_id, state_channel = state_channel, initial_state = False, orient = 'vertical').grid(row = 1, column = 0)
    EntityRGBSpinners(out, local_ws, entity_id = entity_id, state_channel = state_channel, initial_state = False).grid(row = 1, column = 1)

    return(out)

light_switchboard(blueprint_menu, 'light.floor_lamp', "lounge").grid(row = 1)
light_switchboard(blueprint_menu, 'light.kitchen_light', "kitchen").grid(row = 1)
light_switchboard(blueprint_menu, 'light.desk_light', "office").grid(row = 1)
light_switchboard(blueprint_menu, 'light.bedside_lamp', "bedroom").grid(row = 1)

map_snap = EntityMapSnap(map_menu, ['person', 'zone'], size = 400)
map_snap.pack()

window.state_change_periodic_check(100)

window.mainloop()