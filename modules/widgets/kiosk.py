from PySide6 import QtCore

class KioskController(QtCore.QObject): 
    tick = QtCore.Signal(int) 
    def __init__(self, interval_ms=10000): 
        super().__init__() 
        self.index = 0 
        self.timer = QtCore.QTimer() 
        self.timer.setInterval(interval_ms) 
        self.timer.timeout.connect(self._on_tick) 
        self.timer.start() 

    def _on_tick(self):
        self.index += 1 
        self.tick.emit(self.index)
    
    def reset(self):
        #print(f"KioskController index reset")
        self.index = 0