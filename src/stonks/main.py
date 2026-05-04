import sys

from PySide6.QtWidgets import QApplication

from stonks.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Stonks")
    app.setDesktopFileName("com.stonks.Stonks")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
