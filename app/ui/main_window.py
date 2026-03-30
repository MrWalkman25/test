from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.database import add_task, get_task_by_id, get_tasks, update_task


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.current_task_id: int | None = None

        self.setWindowTitle("My Tasks")
        self.resize(960, 620)

        self._build_ui()
        self.apply_styles()
        self.load_tasks()

    def _build_ui(self) -> None:
        central_widget = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        title_label = QLabel("My Tasks")
        title_label.setObjectName("titleLabel")

        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)

        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        create_group = QGroupBox("Нова задача")
        create_form = QFormLayout()
        create_form.setSpacing(8)

        self.task_title_input = QLineEdit()
        self.task_title_input.setPlaceholderText("Назва (обов'язково)")

        self.task_description_input = QTextEdit()
        self.task_description_input.setPlaceholderText("Опис (опційно)")
        self.task_description_input.setFixedHeight(90)

        self.task_deadline_input = QLineEdit()
        self.task_deadline_input.setPlaceholderText("YYYY-MM-DD (опційно)")

        create_form.addRow("Назва", self.task_title_input)
        create_form.addRow("Опис", self.task_description_input)
        create_form.addRow("Дедлайн", self.task_deadline_input)

        self.add_button = QPushButton("Додати")
        self.add_button.clicked.connect(self.handle_add_task)

        create_layout = QVBoxLayout()
        create_layout.addLayout(create_form)
        create_layout.addWidget(self.add_button)
        create_group.setLayout(create_layout)

        self.tasks_list = QListWidget()
        self.tasks_list.currentItemChanged.connect(self.on_task_selected)

        left_layout.addWidget(create_group)
        left_layout.addWidget(self.tasks_list)
        left_panel.setLayout(left_layout)

        details_group = QGroupBox("Деталі задачі")
        details_layout = QVBoxLayout()

        details_form = QFormLayout()
        details_form.setSpacing(8)

        self.details_title_input = QLineEdit()
        self.details_description_input = QTextEdit()
        self.details_description_input.setFixedHeight(110)
        self.details_deadline_input = QLineEdit()
        self.details_deadline_input.setPlaceholderText("YYYY-MM-DD")

        self.created_at_label = QLabel("—")
        self.created_at_label.setObjectName("mutedLabel")

        details_form.addRow("Назва", self.details_title_input)
        details_form.addRow("Опис", self.details_description_input)
        details_form.addRow("Дедлайн", self.details_deadline_input)
        details_form.addRow("Створено", self.created_at_label)

        self.save_button = QPushButton("Зберегти")
        self.save_button.clicked.connect(self.handle_save_task)

        details_layout.addLayout(details_form)
        details_layout.addStretch()
        details_layout.addWidget(self.save_button)
        details_group.setLayout(details_layout)

        content_layout.addWidget(left_panel, 2)
        content_layout.addWidget(details_group, 2)

        root_layout.addWidget(title_label)
        root_layout.addLayout(content_layout)

        central_widget.setLayout(root_layout)
        self.setCentralWidget(central_widget)

        self.set_details_enabled(False)

    def handle_add_task(self) -> None:
        title = self.task_title_input.text().strip()
        if not title:
            return

        description = self.task_description_input.toPlainText().strip() or None
        deadline = self._normalize_deadline(self.task_deadline_input.text())

        task_id = add_task(title=title, description=description, deadline=deadline)

        item = QListWidgetItem(title)
        item.setData(Qt.ItemDataRole.UserRole, task_id)
        self.tasks_list.insertItem(0, item)
        self.tasks_list.setCurrentItem(item)

        self.task_title_input.clear()
        self.task_description_input.clear()
        self.task_deadline_input.clear()

    def load_tasks(self) -> None:
        self.tasks_list.clear()
        tasks = get_tasks()

        for task in tasks:
            item = QListWidgetItem(task["title"])
            item.setData(Qt.ItemDataRole.UserRole, task["id"])
            self.tasks_list.addItem(item)

        if self.tasks_list.count() > 0:
            self.tasks_list.setCurrentRow(0)
        else:
            self.show_empty_details()

    def on_task_selected(self, current: QListWidgetItem | None) -> None:
        if current is None:
            self.show_empty_details()
            return

        task_id = current.data(Qt.ItemDataRole.UserRole)
        selected_task = get_task_by_id(task_id)

        if selected_task is None:
            self.show_empty_details()
            return

        self.current_task_id = selected_task["id"]
        self.set_details_enabled(True)

        self.details_title_input.setText(selected_task["title"] or "")
        self.details_description_input.setPlainText(selected_task["description"] or "")
        self.details_deadline_input.setText(selected_task["deadline"] or "")
        self.created_at_label.setText(self._format_datetime(selected_task["created_at"]))

    def handle_save_task(self) -> None:
        if self.current_task_id is None:
            return

        title = self.details_title_input.text().strip()
        if not title:
            return

        description = self.details_description_input.toPlainText().strip() or None
        deadline = self._normalize_deadline(self.details_deadline_input.text())

        update_task(
            task_id=self.current_task_id,
            title=title,
            description=description,
            deadline=deadline,
        )

        current_item = self.tasks_list.currentItem()
        if current_item is not None:
            current_item.setText(title)

    def set_details_enabled(self, enabled: bool) -> None:
        self.details_title_input.setEnabled(enabled)
        self.details_description_input.setEnabled(enabled)
        self.details_deadline_input.setEnabled(enabled)
        self.save_button.setEnabled(enabled)

    def show_empty_details(self) -> None:
        self.current_task_id = None
        self.details_title_input.clear()
        self.details_description_input.clear()
        self.details_deadline_input.clear()
        self.created_at_label.setText("—")
        self.set_details_enabled(False)

    def _normalize_deadline(self, value: str) -> str | None:
        cleaned = value.strip()
        return cleaned or None

    def _format_datetime(self, value: str | None) -> str:
        if not value:
            return "—"

        try:
            parsed = datetime.fromisoformat(value)
            return parsed.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background-color: #121417; }
            QLabel, QGroupBox { color: #EAF0F5; }
            QLabel#titleLabel { font-size: 24px; font-weight: 700; }
            QLabel#mutedLabel { color: #A8B4C0; }
            QGroupBox {
                border: 1px solid #2B323A;
                border-radius: 10px;
                margin-top: 8px;
                padding: 10px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLineEdit, QTextEdit, QListWidget {
                background-color: #1B2026;
                border: 1px solid #323B45;
                border-radius: 8px;
                color: #EAF0F5;
                padding: 8px;
            }
            QPushButton {
                background-color: #2D6CDF;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #3B79E8; }
            QPushButton:pressed { background-color: #245BBE; }
            QListWidget::item { padding: 8px 6px; }
            QListWidget::item:selected { background-color: #28415D; }
            """
        )
