from modules.widgets.views.base import *
from PySide6 import QtWidgets

from io import BytesIO
import dateutil
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import math

class AstronomyView(View):
    def __init__(self, data_manager: AstronomyDataManager, kiosk_controller: KioskController, parent=None):
        super().__init__(data_manager, kiosk_controller, parent)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.view_label = QtWidgets.QLabel()
        self.view_label.setAlignment(QtCore.Qt.AlignCenter)
        self.view_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        layout.addWidget(self.view_label)

        self.view_label_info = QtWidgets.QLabel()
        self.view_label_info.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.view_label_info)
    
    def get_latest_data(self):
        plot_params = calculate_plot_params([self.data_manager.lon_lat])
        
        # External astronomy data
        astro = get_astronomy_map_data(self.data_manager.data, self.data_manager.lon_lat, plot_params['extent'], (plot_params['dimension'] / 2) + (plot_params['buffer'] / 2))
        astro = self.kiosk_select_data(astro) 
        
        return {
            "plot_params": plot_params,
            "data": astro
            }

    def render(self):
        # Determine label size
        self.label_size = int(min(self.view_label.width(), self.view_label.height()))

        latest_data = self.get_latest_data()

        # If no data yet, show placeholder
        if not latest_data["plot_params"]:
            self.view_label.setText("Loading...")
            return
        
        try: 
            image = self.render_visuals(latest_data)
            pixmap = image_to_formatted_pixmap(image, self.label_size)
            self.view_label.setPixmap(pixmap)
            self.view_label_info.clear()
        except Exception as e: 
            fallback = Image.open(theme.filestore['ui']['img']['bug'])
            pixmap = image_to_formatted_pixmap(fallback, self.label_size)
            self.view_label.setPixmap(pixmap)
            self.view_label_info.setText(str(e))

    def render_visuals(self, latest_data: dict) -> Image.Image:
        # map plot setup ----
        plt.rcParams['font.family'] = "Nintendo DS BIOS"
        
        plot_params = latest_data['plot_params']
        data = latest_data['data']

        fig, ax = plt_make(plot_params['extent'])
        self.plt_add_astronomy(data, ax, plot_params) # +map buffer would have circle perfectly fit square, but we want some allowance for icons

        self.view_label_info.clear()

        image_buffer = BytesIO()
        fig.savefig(image_buffer, format = 'png', bbox_inches='tight', pad_inches = 0)
        plt.close()

        image = Image.open(image_buffer)
        image = image.resize((self.label_size, self.label_size), resample= Image.Resampling.NEAREST)
        image = image.convert('1')

        return image
    
    # plotting function

    def plt_add_astronomy(self, data: dict, ax: plt.Axes, plot_params: dict) -> None:

        lon_lat = plot_params['centre']
        extent = plot_params['extent']
        max_radius = (plot_params['dimension']/2) + (plot_params['buffer']/2)
        
        map_bg = get_map_image(self.label_size, plot_params['extent'], plot_params['dimension'], plot_params['min_dimension'], 128, 1)
        ax.imshow(map_bg, extent=extent)

        if len(data) > 0: 
            # plot crosshair
            ax.axvline(x = lon_lat[0], color = "#000000")
            ax.axhline(y = lon_lat[1], color = "#000000")
            ax.add_patch(patches.Circle(lon_lat, max_radius, edgecolor = "#000000", facecolor = "none"))

            legend_text = ""

            # index-wise plotting due to kiosk
            astro_markers = []
            for key, value in data['data'].items():

                # screen space coordinates
                position_conversion = alt_az_to_viewport(value['position'], lon_lat, extent, max_radius)
                history_conversion = [alt_az_to_viewport(position, lon_lat, extent, max_radius) for position in value['history']]

                if not data["kiosk_selected"]:
                    is_focus = False
                    zoom_level = 0.2
                    focused_str = "   "
                    line_color = "#666666"
                    line_width = 2
                elif key == data["kiosk_selected"]:
                    is_focus = True
                    zoom_level = 0.35
                    focused_str = "<<<"
                    line_color = "#2a2a2a"
                    line_width = 3
                else:
                    is_focus = False
                    zoom_level = 0.1
                    focused_str = "   "
                    line_color = "#999999"
                    line_width = 1

                # plot history trails
                ax.plot(*zip(*history_conversion),
                    color = line_color,
                    linewidth = line_width,
                    zorder = 1)

                astro_icon_image = OffsetImage(value['icon'], zoom = zoom_level, interpolation = 'bicubic')
                astro_marker = AnnotationBbox(astro_icon_image, position_conversion, frameon = False, annotation_clip = True)
                astro_marker.set_clip_on(True)

                # add markers to list to render later
                if is_focus:
                    astro_markers.append(astro_marker) # push to back, render last
                else:
                    astro_markers.insert(0, astro_marker) # push to front, render... not last.

                if len(legend_text) > 0: 
                    legend_text = legend_text + "\n" # separate lines
                legend_text = f"{legend_text}{value['name']}: {round((180/math.pi) * value['position'][0],1)},{round((180/math.pi) * value['position'][1],1)}{focused_str}"

            # render marker list
            for astro_marker in astro_markers:
                ax.add_artist(astro_marker)

            # add legend
            legend_bbox = dict(alpha = 1, edgecolor = "#000000", facecolor = "#ffffff")
            ax.text(0.025, 
                    0.975, 
                    legend_text, 
                    transform = ax.transAxes, 
                    fontsize = 24, 
                    verticalalignment = 'top',
                    bbox = legend_bbox)
        else:
            # no astro data to plot, show placeholder
            legend_text = "Nothing's in the sky right now... \nCheck back later!"
            legend_bbox = dict(alpha = 1, edgecolor = "#000000", facecolor = "#ffffff")
            ax.text(0.5, 
                    0.5, 
                    legend_text, 
                    transform = ax.transAxes, 
                    fontsize = 24, 
                    verticalalignment = 'center',
                    horizontalalignment = 'center',
                    bbox = legend_bbox)

def get_astronomy_map_data(astro_data:list, lon_lat: tuple, extent: dict, max_radius: float) -> dict:
        # create a list of permitted celestial bodies
        allowed_bodies = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune']

        astro_data = [body for body in astro_data if body['id'] in allowed_bodies]
        
        data = {}

        # convert altitude & azimuth to radians (added rounding because it was overly-specific)
        for body in astro_data:
            position = (round(math.radians(float(body['position']['horizontal']['altitude']['degrees'])), 2),
                        round(math.radians(float(body['position']['horizontal']['azimuth']['degrees'])), 2))
            
            if position[0] > 0: # filter to above horizon
                data[body['id']] = {"position": position, "timestamp": body['date'], "name": body['name'], "extraInfo": body['extraInfo']}

        # read/write position history
        for body_id, body_data in data.items():
            position_history = localcache_read("./data/astro_position_log.json", body_id)

            if len(position_history) > 0:
                _latest_parsed_datetime = max(position_history.keys())
                _latest_position = position_history[_latest_parsed_datetime]
            else:
                _latest_position = None

            if len(position_history) == 0 or list(body_data['position']) != _latest_position: # json will not return a tuple back, only list
                localcache_write("./data/astro_position_log.json",
                                    body_id,
                                    dateutil.parser.parse(body_data['timestamp']).timestamp(),
                                    data[body_id]['position'],
                                    24) # assign back
        
            # read position history
            position_history = localcache_read("./data/astro_position_log.json", body_id).values()
            position_history = sorted(position_history, key=lambda x: x[1]) # sort by azimuth (prevents line joining across discontinuity)

            data[body_id]['history'] = position_history
        
        for body_id in data.keys():
            match body_id:
                case 'moon':
                    try:
                        # moon phase icon fetch
                        data[body_id]["icon"] = plt.imread(theme.filestore['ui']['icons']['astro']["moon_" + data[body_id]['extraInfo']['phase']['string'].replace(" ", "_").lower()])
                    except:
                        # api returned unknown phase, show the confused moon!
                        data[body_id]["icon"] = plt.imread(theme.filestore['ui']['icons']['astro']["moon_bug"])
                case _:
                    data[body_id]["icon"] = plt.imread(theme.filestore['ui']['icons']['astro'][body_id])
        return {"data": data, "kiosk_selected": None}

def alt_az_to_viewport(alt_az: tuple, lon_lat: tuple, extent: list, max_radius: float) -> tuple[int,int]:
        #convert to lon lat at origin where circle bounds viewport square
        conversion = [math.sin(alt_az[1]), math.cos(alt_az[1])] 
        conversion = [x * (1 - (alt_az[0]/math.radians(90))) * max_radius for x in conversion]

        #move from origin to viewport centre
        conversion = [sum(x) for x in zip(lon_lat, conversion)]
        #clamp to within viewport square
        conversion = (min(max(conversion[0], extent[0]), extent[1]), min(max(conversion[1], extent[2]), extent[3]))

        return conversion