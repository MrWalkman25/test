from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.database import add_task, get_tasks


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("My Tasks")
        self.resize(640, 520)

        central_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title_label = QLabel("My Tasks")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_label.setObjectName("titleLabel")

        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Введіть назву задачі...")

        self.add_button = QPushButton("Додати")
        self.add_button.clicked.connect(self.handle_add_task)
        self.task_input.returnPressed.connect(self.handle_add_task)

        self.tasks_list = QListWidget()

        layout.addWidget(title_label)
        layout.addWidget(self.task_input)
        layout.addWidget(self.add_button)
        layout.addWidget(self.tasks_list)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.apply_styles()
        self.load_tasks()

    def handle_add_task(self) -> None:
        title = self.task_input.text().strip()
        if not title:
            return

        add_task(title)
        self.tasks_list.insertItem(0, title)
        self.task_input.clear()

    def load_tasks(self) -> None:
        self.tasks_list.clear()
        for title in get_tasks():
            self.tasks_list.addItem(title)

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #121417;
            }
            QLabel#titleLabel {
                color: #F2F5F7;
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 6px;
            }
            QLineEdit {
                background-color: #1A1F24;
                border: 1px solid #2C333B;
                border-radius: 10px;
                color: #E6EBF0;
                padding: 10px 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #3D8BFF;
            }
            QPushButton {
                background-color: #2D6CDF;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3A78E8;
            }
            QPushButton:pressed {
                background-color: #2258BB;
            }
            QListWidget {
                background-color: #171B20;
                border: 1px solid #2C333B;
                border-radius: 10px;
                color: #E6EBF0;
                padding: 6px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 8px 6px;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background-color: #25364F;
            }
            """
        )
