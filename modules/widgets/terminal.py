from PySide6 import QtCore, QtWidgets
import sys
import datetime
from html import escape

class EmittingStream(QtCore.QObject):
    text_written = QtCore.Signal(str)

    def __init__(self, original_stream):
        super().__init__()
        self.original_stream = original_stream

    def write(self, text):
        if text.strip():
            # permit object.__str__ printing, among others
            text = escape(text)
            timestamp = str(datetime.datetime.now().replace(microsecond=0))
            self.text_written.emit(
                f"<b><u>{timestamp}:</u></b>&nbsp;&nbsp;{text}"
            )
        self.original_stream.write(text)

    def flush(self):
        self.original_stream.flush()

class Terminal(QtWidgets.QTextEdit):
    def __init__(self):
        super().__init__(readOnly=True)
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr

        self.stdout_stream = EmittingStream(self._orig_stdout)
        self.stderr_stream = EmittingStream(self._orig_stderr)

        self.stdout_stream.text_written.connect(self.append)
        self.stderr_stream.text_written.connect(self.append)

        sys.stdout = self.stdout_stream
        sys.stderr = self.stderr_stream
