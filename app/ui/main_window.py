from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("My Tasks")
        self.resize(600, 500)

        central_widget = QWidget()
        layout = QVBoxLayout()

        title_label = QLabel("My Tasks")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Введіть назву задачі...")

        self.add_button = QPushButton("Додати")

        self.tasks_list = QListWidget()

        layout.addWidget(title_label)
        layout.addWidget(self.task_input)
        layout.addWidget(self.add_button)
        layout.addWidget(self.tasks_list)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
