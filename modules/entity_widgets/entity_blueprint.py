import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
from typing import Literal

from config import *
from .core import *
from ..caching import *

from .core import *

class EntityBlueprint(EntityWidget):
    def __init__(self, master, 
                 entity_type: str | list[str] = None, entity_id: str | list[str] = None,
                 initial_state: bool = True,
                 state_channel: str | list[str] = [],
                 **kwargs):
        EntityWidget.__init__(self=self, master=master, widget_name="entity_blueprint",
                              entity_type=entity_type, entity_id=entity_id,
                              initial_state=initial_state,
                              state_channel = state_channel, 
                              foreach = False,
                              **kwargs)
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
            bg_draw.polygon([tuple((y * inner_scale) + border for y in x) for x in current_body['coords']], **current_body['style'][current_body['style_state']])
        
        bg_image = bg_image.convert('1')

        self.photo_image = ImageTk.PhotoImage(bg_image)

        """Make the canvas, using first image as background"""
        widget = tk.Canvas(self, width = outer_extent[0], height = outer_extent[1], bg = "#ffffff", highlightbackground = "#ffffff")
        widget.create_image(0, 0, anchor = 'nw', image = self.photo_image)

        #draw room interactives
        for id, current_body in self.body_dict.items():
            if current_body['type'] == "room":
                self.body_dict[id]['poly'] = widget.create_polygon([[(y * inner_scale) + border for y in x] for x in current_body['coords']], fill = "")
                widget.tag_bind(
                    self.body_dict[id]['poly'],
                    '<Button-1>',
                    lambda e, id = id: self.select_room(id))
        
        #draw navigate interactives
        for id, current_body in self.body_dict.items():
            if current_body['type'] == "navigate":
                self.body_dict[id]['poly'] = widget.create_polygon([[(y * inner_scale) + border for y in x] for x in current_body['coords']], fill = "")
                widget.tag_bind(
                    self.body_dict[id]['poly'],
                    '<Button-1>',
                    lambda e, id = id, select = False: self.change_room(id))

        return widget
    
    def add_body(self, id: str, coords: list[tuple], command: callable = None, type: Literal["room","decor","navigate"] = "room"):
        room = dict(outline = "#000000", fill = "#ffffff")
        active_room = dict(outline = "#000000", fill = "#cccccc")

        decor = dict(outline = "#000000", fill = "#999999")

        navigate = dict(outline = "#000000", fill = "#666666" )

        match type:
            case "room":
                style = dict(active = active_room, default = room)
            case "decor":
                style = dict(default = decor)
            case "navigate":
                style = dict(default = navigate)
            case _:
                raise KeyError("str type not recognised")

        self.body_dict[id] = dict(type = type, coords = coords, style = style, style_state = 'default')
    
    def select_room(self, id: str):
        """Sends a signal on the given ID."""
        #get state of body before deselect_all
        interacted_body_state = self.body_dict[id]['style_state']
        
        self.deselect_all()

        if interacted_body_state == "active":
            self.body_dict[id]['style_state'] = "default"
            pub.sendMessage(id, **dict(state = False, context_id = id))    
        else:
            self.body_dict[id]['style_state'] = "active"
            pub.sendMessage(id, **dict(state = True, context_id = id))    

        self.build()
    
    def deselect_all(self):
        for _id, current_body in self.body_dict.items():
            current_body['style_state'] = "default"
            pub.sendMessage(_id, **dict(state = False, context_id = None))
        self.build()
    
    def change_room(self, id: str):
        self.state = False
        self.deselect_all()
        pub.sendMessage(id, **dict(state = True, context_id = None))
