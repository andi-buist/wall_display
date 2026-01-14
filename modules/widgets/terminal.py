from .widget_core import HASSWidget
from PySide6 import QtCore, QtWidgets
import sys
import datetime

class EmittingStream(QtCore.QObject): 
    text_written = QtCore.Signal(str)

    def write(self, text): 
        if text.strip(): # ignore empty or newline-only writes
            timestamp = datetime.datetime.now().replace(microsecond=0)
            self.text_written.emit( f"<b><u>{timestamp}:</u></b>&nbsp;&nbsp;{text}") #HTML formatting, non-breaking spaces used

    def flush(self):
        pass

class Terminal(QtWidgets.QTextEdit):
    def __init__(self):
        super().__init__(readOnly=True)
        # Redirect stdout
        self.stdout_stream = EmittingStream()
        self.stdout_stream.text_written.connect(self.append)

        sys.stdout = self.stdout_stream
        sys.stderr = self.stdout_stream
