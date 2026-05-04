import sys

from PySide6.QtWidgets import QApplication

from stonks.config import DB_PATH
from stonks.models.database import init_db
from stonks.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Stonks")
    app.setDesktopFileName("com.stonks.Stonks")

    conn = init_db(DB_PATH)
    window = MainWindow(conn)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
