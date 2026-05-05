import signal
import sys

import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from stonks.config import DB_PATH
from stonks.models.database import init_db
from stonks.ui.main_window import MainWindow
from stonks.ui.style import DARK_STYLE


def main():
    pg.setConfigOptions(antialias=True)

    app = QApplication(sys.argv)
    app.setApplicationName("Stonks")
    app.setDesktopFileName("com.stonks.Stonks")
    app.setStyleSheet(DARK_STYLE)

    # Restore default SIGINT so Ctrl+C works; QTimer gives Python a chance to see it.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    sigint_timer = QTimer()
    sigint_timer.start(200)
    sigint_timer.timeout.connect(lambda: None)

    conn = init_db(DB_PATH)
    window = MainWindow(conn)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
