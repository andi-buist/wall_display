from modules.widgets.views.base import *
from PySide6 import QtWidgets

from io import BytesIO
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

class StravaView(View):
    def __init__(self, data_manager: DataManager, kiosk_controller: KioskController, parent=None):
        super().__init__(data_manager, kiosk_controller, parent)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        # view label
        self.view_label = QtWidgets.QLabel()
        self.view_label.setAlignment(QtCore.Qt.AlignCenter)
        self.view_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        layout.addWidget(self.view_label)

        # label below viewer (text etc)
        self.view_label_info = QtWidgets.QLabel()
        self.view_label_info.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.view_label_info)
    
    def _on_data_update(self): # in Views like strava, this is sort of overkill since no data is extracted, but it's an available timer
        super()._on_data_update()

    def get_latest_data(self):
        data = get_strava_map_data(period = (datetime.datetime.today() - datetime.timedelta(days=30), datetime.datetime.now()))
        data = self.kiosk_select_data(data, start_unselected=False)

        plot_params = get_map_traits(data['data'][data['kiosk_selected']]['polyline'])

        return {
            "plot_params": plot_params,
            "data": data
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
            image = self.generate_plot_vis(latest_data)
            pixmap = image_to_formatted_pixmap(image, self.label_size)
            self.view_label.setPixmap(pixmap)
            
            kiosk_data = latest_data['data']['data'][latest_data['data']['kiosk_selected']]
            time_str = kiosk_data['start_date'].strftime('%A %d %b, %H:%M')
            run_length = str(round(kiosk_data['distance']/1000,1)) + "k"
            self.view_label_info.setText(f"{time_str}: {run_length}")
        except Exception as e: 
            fallback = Image.open(theme.filestore['ui']['img']['bug'])
            pixmap = image_to_formatted_pixmap(fallback, self.label_size)
            self.view_label.setPixmap(pixmap)
            self.view_label_info.setText(str(e))

    def generate_plot_vis(self, latest_data: dict) -> Image.Image:
        # map plot setup ----
        plt.rcParams['font.family'] = "Nintendo DS BIOS"

        self.label_size = int(min(self.view_label.width(), self.view_label.height()))
        
        data = latest_data['data']
        kiosk_data = data['data'][data['kiosk_selected']]

        plot_params = latest_data['plot_params']

        map_bg =  get_map_image(self.label_size, plot_params['extent'], plot_params['aspect'], 128, 1)

        fig, ax = plt_make(plot_params['extent'])
        ax.imshow(map_bg, extent = plot_params['extent'])

        plt_add_strava_view(ax, kiosk_data)

        image_buffer = BytesIO()
        fig.savefig(image_buffer, format = 'png', bbox_inches='tight', pad_inches = 0)
        plt.close()

        image = Image.open(image_buffer)
        image = image.resize((self.label_size, self.label_size), resample= Image.Resampling.NEAREST)
        image = image.convert('1')

        return image
    
def get_strava_map_data(type: str = None,
                        period: tuple[datetime.datetime, datetime.datetime] = (datetime.datetime.today() - datetime.timedelta(days = 30), datetime.datetime.now()),
                        cache_frequency: datetime.timedelta = datetime.timedelta(hours=1),
                        cache_filepath: Path = Path("./data/strava_data_cache.json")) -> dict:
    data = get_strava_data(period = period, cache_frequency = cache_frequency, cache_filepath=cache_filepath)

    for key, value in data['data'].items():
        data['data'][key]['start_date'] = datetime.datetime.fromtimestamp(value['start_date'])
    return data

def plt_add_strava_view(ax: plt.Axes, data: dict) -> None:
    if len(data['polyline']) > 0:
        ax.plot([x[0] for x in data['polyline']],
                [x[1] for x in data['polyline']],
                color = "#000",
                linewidth = 5,
                linestyle = 'solid',
                zorder = 1)

        flag_icon_image = OffsetImage(plt.imread(theme.filestore['ui']['icons']['misc']['checkered_flag']), zoom = 2, interpolation = 'nearest')
        flag_marker = AnnotationBbox(flag_icon_image, (data['polyline'][-1][0], data['polyline'][-1][1]), frameon = False, annotation_clip = True, box_alignment=(1,0))
        flag_marker.set_clip_on(True)
        ax.add_artist(flag_marker)
        
    else:
        # no activity data to plot, show placeholder
        legend_text = "No recent activity... \nCheck back later!"
        legend_bbox = dict(alpha = 1, edgecolor = "#000000", facecolor = "#ffffff")
        ax.text(0.5, 
                0.5, 
                legend_text, 
                transform = ax.transAxes, 
                fontsize = 24, 
                verticalalignment = 'center',
                horizontalalignment = 'center',
                bbox = legend_bbox)