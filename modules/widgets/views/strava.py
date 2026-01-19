from modules.widgets.views.base import *
from PySide6 import QtWidgets

from io import BytesIO
import dateutil
from PIL import Image
import matplotlib.pyplot as plt
from adjustText import adjust_text

class StravaView(View):
    def __init__(self, data_manager: HASSDataManager):
        super().__init__(data_manager)
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
    
    def _on_entities_updated(self, entities):
        self.update_view()

    def get_data(self):
        data = get_strava_map_data(period = (datetime.datetime.today() - datetime.timedelta(days=30), datetime.datetime.now()))
        data = self.kiosk_select_data(data, start_unselected=False)
        kiosk_data = data['data'][data['kiosk_selected']]

        # compute extent
        if data["kiosk_selected"]:
            extent = calculate_extent(kiosk_data['polyline'])
        else:
            coords = []
            for v in data['data'].values():
                coords.extend(v['polyline'])
            extent = calculate_extent(coords)

        return {
            "extent": extent,
            "data": data
        }

    def update_view(self):
        # main call to image generator
        view_data = self.get_data()
        QtCore.QTimer.singleShot(0, lambda: self._deferred_render_visuals(view_data))
    
    def _deferred_render_visuals(self, view_data: dict):
        try: 
            image = self.render_visuals(view_data)
            if image:
                pixmap = image_to_formatted_pixmap(image, self.label_size)
                self.view_label.setPixmap(pixmap)
            else:
                self.view_label.setText("Loading...")
        except Exception as e:
            # generic image as a placeholder (when no data)
            image = Image.open(theme.filestore['ui']['img']['bug'])
            pixmap = image_to_formatted_pixmap(image, self.label_size)
            self.view_label.setPixmap(pixmap)
            self.view_label_info.setText(str(e))

    def render_visuals(self, view_data: dict) -> Image.Image:
        # map plot setup ----
        plt.rcParams['font.family'] = "Nintendo DS BIOS"

        self.label_size = int(min(self.view_label.width(), self.view_label.height()))
        
        data = view_data['data']
        kiosk_data = data['data'][data['kiosk_selected']]

        if data["kiosk_selected"]:
            extent = calculate_extent(kiosk_data['polyline'])
        else:
            coord_list = []
            for value in data['data'].values():
                coord_list = coord_list + [x for x in value['polyline']]
            extent = calculate_extent(coord_list)

        map_bg =  get_map_image(self.label_size, extent['extent'], extent['dimension'], extent['min_dimension'], 128, 1)

        fig, ax = plt_make(extent)
        ax.imshow(map_bg, extent = extent['extent'])

        plt_add_strava_view(ax, data)

        time_str = kiosk_data['start_date'].strftime('%A %d %b, %H:%M')
        run_length = str(round(kiosk_data['distance']/1000,1)) + "k"

        self.view_label_info.setText(f"{time_str}: {run_length}")

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
    if len(data['data'].values()) > 0:
        if not data['kiosk_selected']:
            for value in data['data'].values():
                    ax.plot([x[0] for x in value['polyline']],
                            [x[1] for x in value['polyline']],
                            color = "#000",
                            linewidth = 5,
                            linestyle = 'solid',
                            zorder = 1)
        else:
            poly = data['data'][data['kiosk_selected']]['polyline']
            ax.plot([x[0] for x in poly],
                    [x[1] for x in poly],
                    color = "#000",
                    linewidth = 5,
                    linestyle = 'solid',
                    zorder = 1)