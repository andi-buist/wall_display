import tkinter as tk
from tkinter import ttk
from io import BytesIO
import datetime
from PIL import Image, ImageTk, ImageEnhance
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
        if self.kwargs.get('size') is not None:
            size = self.kwargs.get('size')
        else: raise KeyError("kwarg 'size' expected for class EntityMapSnap")
        
        widget = tk.Canvas(self, width = size[0], height = size[1])

        coord_data_flat = [x['coords'] for x in self.body_dict.values()]
        scale = max(size)/max(max(x for group in coord_data_flat for x, _ in group),
                              max(y for group in coord_data_flat for _, y  in group))

        for id, current_body in self.body_dict.items():
            self.body_dict[id]['poly'] = widget.create_polygon([[y * scale for y in x] for x in current_body['coords']], **current_body['style'])
            widget.tag_bind(
                self.body_dict[id]['poly'],
                '<Button-1>',
                lambda e, id = id, current_body = current_body: self.body_dict[id]['command'](id))

        return widget
    
    def add_body(self, id: str, coords: list[tuple], command: callable = None, type: Literal["room","decor"] = "room", style: Literal["room","decor"] | dict = None):
        match style:
            case str():
                match style:
                    case "room":
                        style = dict(outline = "#000000", fill = "#ffffff", activestipple = 'gray25', activefill = "#000000")
                    case "decor":
                        style = dict(outline = "#000000", fill = "#000000", stipple = 'gray50')
                    case _:
                        raise KeyError("str style not recognised")
            case None:
                match type:
                    case "room":
                        style = dict(outline = "#000000", fill = "#ffffff", activestipple = 'gray25', activefill = "#000000")
                    case "decor":
                        style = dict(outline = "#000000", fill = "#000000", stipple = 'gray50')
                    case _:
                        raise KeyError("str type not recognised")
            case dict():
                style = style
            case _:
                raise KeyError("style must be one of str or dict")

        if command is None:
            command = print

        self.body_dict[id] = dict(type = type, coords = coords, style = style, command = command)