from PySide6.QtWidgets import QLabel, QMainWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stonks")
        self.setMinimumSize(900, 600)
        self.setCentralWidget(QLabel("Hello Stonks"))
