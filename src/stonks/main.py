import ctypes
import ctypes.util
import platform
import signal
import sys
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from stonks.config import APP_NAME, APP_VERSION, DB_PATH
from stonks.models.database import init_db
from stonks.ui.main_window import MainWindow
from stonks.ui.style import DARK_STYLE
from stonks.ui.workers import wait_for_closing_workers

# Relies on source tree layout; distributed builds embed the icon at build time.
_ICON_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "com.stonks.Stonks.svg"


def _set_process_name(name: str):
    if platform.system() == "Darwin":
        try:
            libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("c"))
            libc.setprogname(name.encode())
        except (OSError, AttributeError):
            pass


def main():
    _set_process_name(APP_NAME)

    pg.setConfigOptions(antialias=True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setDesktopFileName("com.stonks.Stonks")
    app.setStyleSheet(DARK_STYLE)
    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))

    # Restore default SIGINT so Ctrl+C works; QTimer gives Python a chance to see it.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    sigint_timer = QTimer()
    sigint_timer.start(200)
    sigint_timer.timeout.connect(lambda: None)

    conn = init_db(DB_PATH)
    window = MainWindow(conn)
    window.show()

    ret = app.exec()
    wait_for_closing_workers()
    sys.exit(ret)


if __name__ == "__main__":
    main()
