import sys

import pyqtgraph as pg
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

    conn = init_db(DB_PATH)
    window = MainWindow(conn)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
