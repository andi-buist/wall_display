from PySide6 import QtWidgets

from modules.widgets.widget_core import *
from modules.caching import *
from modules.api.get_data import *
from modules.widgets.kiosk import *
from modules.data_manager import DataManager

class InfoBox(QtWidgets.QWidget):
    def __init__(self, 
                 data_manager: DataManager, 
                 kiosk_controller: KioskController, 
                 parent=None):
        super().__init__(parent)
        self.data_manager = data_manager

        if kiosk_controller:
            self.kiosk_index = 0
            kiosk_controller.tick.connect(self.on_kiosk_timer_next)

        data_manager.data_update.connect(self._on_data_update)
        data_manager.data_event.connect(self._on_data_event)

        QtCore.QTimer.singleShot(0, self._apply_initial_data_snapshot)
    
    def _apply_initial_data_snapshot(self): 
        if self.data_manager.data: 
            self._on_data_update(self.data_manager.data)

    def _on_data_update(self):
        self.update_ui()
    
    def _on_data_event(self, event):
        self.update_ui()
    
    def kiosk_select_data(self, data: dict, start_unselected: bool = True) -> dict:
        if len(data['data']) > 0:
            # reset kiosk index if past final set
            match start_unselected:
                case True: kiosk_start_point = 1
                case False: kiosk_start_point = 0

            self.kiosk_index = self.kiosk_index % (len(data['data']) + kiosk_start_point)

            if start_unselected and self.kiosk_index == 0:
                data["kiosk_selected"] = None
            else:
                data["kiosk_selected"] = list(data['data'].keys())[self.kiosk_index - kiosk_start_point]
        
        return data
    
    def on_kiosk_timer_next(self, index: int):
        self.kiosk_index = index
        self.update_ui()

    def update_ui(self):
        print(f"{self} is still using the base.py update_ui() function. Are you sure your subclass is set up correctly?")
        pass
