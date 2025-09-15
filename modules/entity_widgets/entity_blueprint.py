import tkinter as tk
from tkinter import ttk
from io import BytesIO
import datetime
from PIL import Image, ImageDraw, ImageOps, ImageTk, ImageEnhance
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from adjustText import adjust_text
import cartopy
from cartopy import crs as ccrs
from cartopy.io import img_tiles as ctiles
import math
from typing import Literal

from config import *
from .core import *
from ..caching import *

from .core import *

class EntityBlueprint(EntityWidget):
    def __init__(self, master, client, entity_type: str | list[str] = None, entity_id: str | list[str] = None, **kwargs):
        EntityWidget.__init__(self, master, "entity_blueprint", client, entity_type, entity_id, foreach = False, **kwargs)
        self.body_dict = {}
        
    def construct_widget(self, entity_id: str, entity: dict):
        #find the max x,y
        coord_data_flat = [x['coords'] for x in self.body_dict.values()]
        extent = (max(x for group in coord_data_flat for x, _ in group),
                  max(y for group in coord_data_flat for _, y  in group))
        
        #get border, else 0
        if self.kwargs.get('border') is not None: border = self.kwargs.get('border')
        else: border = 0

        #convert the desired size to a scale, else just remove borders ((e - 2b) / e)
        #this can be thought of as the scale of the inner image in comparison to the source coords
        #adding borders * 2 = full image size (for parent Image extent)
        if self.kwargs.get('size') is not None:
            inner_scale = (self.kwargs.get('size') - (border * 2))/max(extent)
        else: 
            inner_scale = 1 - ((border * 2)/max(extent))

        outer_extent = tuple(int(x * inner_scale) + (border  * 2) for x in extent)

        """First image creation"""
        bg_image = Image.new("L", outer_extent, "#ffffff")
        bg_draw = ImageDraw.Draw(bg_image)

        # for each body, draw polygon using accompanying 'style' and 'selection' as choice.
        for current_body in self.body_dict.values():
            bg_draw.polygon([tuple((y * inner_scale) + border for y in x) for x in current_body['coords']], **current_body['style'][current_body['selected']])
        
        bg_image = bg_image.convert('1')

        self.photo_image = ImageTk.PhotoImage(bg_image)

        """Make the canvas, using first image as background"""
        widget = tk.Canvas(self, width = outer_extent[0], height = outer_extent[1])
        widget.create_image(0, 0, anchor = 'nw', image = self.photo_image)

        for id, current_body in self.body_dict.items():
            if current_body['type'] == "room":
                self.body_dict[id]['poly'] = widget.create_polygon([[(y * inner_scale) + border for y in x] for x in current_body['coords']], fill = "")
                widget.tag_bind(
                    self.body_dict[id]['poly'],
                    '<Button-1>',
                    lambda e, id = id: self.select_room(id))

        return widget
    
    def add_body(self, id: str, coords: list[tuple], command: callable = None, type: Literal["room","decor"] = "room"):
        room = dict(outline = "#000000", fill = "#ffffff")
        selected_room = dict(outline = "#000000", fill = "#999999")

        decor = dict(outline = "#000000", fill = "#666666")

        match type:
            case "room":
                style = dict(yes = selected_room, no = room)
            case "decor":
                style = dict(no = decor)
            case _:
                raise KeyError("str type not recognised")

        if command is None:
            command = print

        self.body_dict[id] = dict(type = type, coords = coords, style = style, command = command, selected = 'no')
    
    def select_room(self, id: str):
        for _id, current_body in self.body_dict.items():
            if _id == id and current_body['selected'] == "no":
                current_body['selected'] = "yes"
            else:
                current_body['selected'] = "no"
        self.event_generate(self.widget_virtual_event)

        self.build()
