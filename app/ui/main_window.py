from datetime import datetime

from PySide6.QtCore import QDate, Qt, QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.database import add_task, delete_task, get_task_by_id, get_tasks, update_task


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.settings = QSettings("LocalTaskManager", "MyTasks")
        self.current_task_id: int | None = None

        self.setWindowTitle("My Tasks")
        self.resize(980, 620)

        self._build_ui()
        self._apply_saved_theme()
        self.load_tasks()

    def _build_ui(self) -> None:
        central_widget = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        title_label = QLabel("My Tasks")
        title_label.setObjectName("titleLabel")

        top_row.addWidget(title_label)
        top_row.addStretch()

        self.theme_selector = QComboBox()
        self.theme_selector.addItems(["Dark", "Light"])
        self.theme_selector.currentTextChanged.connect(self.on_theme_changed)
        top_row.addWidget(QLabel("Theme:"))
        top_row.addWidget(self.theme_selector)

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
        self.task_description_input.setFixedHeight(80)

        self.task_deadline_checkbox = QCheckBox("Додати дедлайн")
        self.task_deadline_checkbox.toggled.connect(self.on_create_deadline_toggled)
        self.task_deadline_input = QDateEdit()
        self.task_deadline_input.setCalendarPopup(True)
        self.task_deadline_input.setDate(QDate.currentDate())
        self.task_deadline_input.setEnabled(False)

        create_form.addRow("Назва", self.task_title_input)
        create_form.addRow("Опис", self.task_description_input)
        create_form.addRow(self.task_deadline_checkbox, self.task_deadline_input)

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
        self.details_description_input.setFixedHeight(100)

        self.details_deadline_checkbox = QCheckBox("Є дедлайн")
        self.details_deadline_checkbox.toggled.connect(self.on_details_deadline_toggled)
        self.details_deadline_input = QDateEdit()
        self.details_deadline_input.setCalendarPopup(True)
        self.details_deadline_input.setDate(QDate.currentDate())
        self.details_deadline_input.setEnabled(False)

        self.created_at_label = QLabel("—")
        self.created_at_label.setObjectName("mutedLabel")

        details_form.addRow("Назва", self.details_title_input)
        details_form.addRow("Опис", self.details_description_input)
        details_form.addRow(self.details_deadline_checkbox, self.details_deadline_input)
        details_form.addRow("Створено", self.created_at_label)

        buttons_row = QHBoxLayout()
        self.save_button = QPushButton("Зберегти")
        self.save_button.clicked.connect(self.handle_save_task)

        self.delete_button = QPushButton("Видалити")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self.handle_delete_task)

        buttons_row.addWidget(self.save_button)
        buttons_row.addWidget(self.delete_button)

        details_layout.addLayout(details_form)
        details_layout.addStretch()
        details_layout.addLayout(buttons_row)
        details_group.setLayout(details_layout)

        content_layout.addWidget(left_panel, 2)
        content_layout.addWidget(details_group, 2)

        root_layout.addLayout(top_row)
        root_layout.addLayout(content_layout)

        central_widget.setLayout(root_layout)
        self.setCentralWidget(central_widget)

        self.set_details_enabled(False)

    def handle_add_task(self) -> None:
        title = self.task_title_input.text().strip()
        description = self.task_description_input.toPlainText().strip()
        if not title:
            return

        deadline = (
            self.task_deadline_input.date().toString("yyyy-MM-dd")
            if self.task_deadline_checkbox.isChecked()
            else None
        )

        task_id = add_task(
            title=title,
            description=description or None,
            deadline=deadline,
        )

        item = QListWidgetItem(title)
        item.setData(Qt.ItemDataRole.UserRole, task_id)
        self.tasks_list.insertItem(0, item)
        self.tasks_list.setCurrentItem(item)

        self.task_title_input.clear()
        self.task_description_input.clear()
        self.task_deadline_checkbox.setChecked(False)
        self.task_deadline_input.setDate(QDate.currentDate())

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

        deadline = selected_task["deadline"]
        if deadline:
            parsed_date = QDate.fromString(deadline, "yyyy-MM-dd")
            if parsed_date.isValid():
                self.details_deadline_checkbox.setChecked(True)
                self.details_deadline_input.setDate(parsed_date)
            else:
                self.details_deadline_checkbox.setChecked(False)
                self.details_deadline_input.setDate(QDate.currentDate())
        else:
            self.details_deadline_checkbox.setChecked(False)
            self.details_deadline_input.setDate(QDate.currentDate())

        self.created_at_label.setText(self._format_datetime(selected_task["created_at"]))

    def handle_save_task(self) -> None:
        if self.current_task_id is None:
            return

        title = self.details_title_input.text().strip()
        if not title:
            return

        description = self.details_description_input.toPlainText().strip() or None
        deadline = (
            self.details_deadline_input.date().toString("yyyy-MM-dd")
            if self.details_deadline_checkbox.isChecked()
            else None
        )

        update_task(self.current_task_id, title, description, deadline)

        current_item = self.tasks_list.currentItem()
        if current_item is not None:
            current_item.setText(title)

    def handle_delete_task(self) -> None:
        if self.current_task_id is None:
            return

        answer = QMessageBox.question(
            self,
            "Підтвердження",
            "Видалити цю задачу?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        delete_task(self.current_task_id)

        row = self.tasks_list.currentRow()
        self.tasks_list.takeItem(row)

        self.current_task_id = None
        if self.tasks_list.count() > 0:
            self.tasks_list.setCurrentRow(0)
        else:
            self.show_empty_details()

    def on_create_deadline_toggled(self, checked: bool) -> None:
        self.task_deadline_input.setEnabled(checked)

    def on_details_deadline_toggled(self, checked: bool) -> None:
        self.details_deadline_input.setEnabled(checked)

    def on_theme_changed(self, theme_name: str) -> None:
        self.settings.setValue("theme", theme_name)
        self.apply_theme(theme_name)

    def _apply_saved_theme(self) -> None:
        theme_name = str(self.settings.value("theme", "Dark"))
        self.theme_selector.blockSignals(True)
        self.theme_selector.setCurrentText(theme_name)
        self.theme_selector.blockSignals(False)
        self.apply_theme(theme_name)

    def apply_theme(self, theme_name: str) -> None:
        self.setStyleSheet(self._dark_stylesheet() if theme_name == "Dark" else self._light_stylesheet())

    def set_details_enabled(self, enabled: bool) -> None:
        self.details_title_input.setEnabled(enabled)
        self.details_description_input.setEnabled(enabled)
        self.details_deadline_checkbox.setEnabled(enabled)
        self.details_deadline_input.setEnabled(enabled and self.details_deadline_checkbox.isChecked())
        self.save_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    def show_empty_details(self) -> None:
        self.current_task_id = None
        self.details_title_input.clear()
        self.details_description_input.clear()
        self.details_deadline_checkbox.setChecked(False)
        self.details_deadline_input.setDate(QDate.currentDate())
        self.created_at_label.setText("—")
        self.set_details_enabled(False)

    def _format_datetime(self, value: str | None) -> str:
        if not value:
            return "—"

        try:
            parsed = datetime.fromisoformat(value)
            return parsed.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value

    def _dark_stylesheet(self) -> str:
        return """
        QMainWindow { background-color: #121417; }
        QLabel, QCheckBox, QGroupBox { color: #EAF0F5; }
        QLabel#titleLabel { font-size: 24px; font-weight: 700; }
        QLabel#mutedLabel { color: #A8B4C0; }
        QGroupBox {
            border: 1px solid #2B323A;
            border-radius: 10px;
            margin-top: 8px;
            padding: 10px;
            font-weight: 600;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        QLineEdit, QTextEdit, QDateEdit, QComboBox, QListWidget {
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
        QPushButton#dangerButton { background-color: #B33A3A; }
        QPushButton#dangerButton:hover { background-color: #C24A4A; }
        QListWidget::item { padding: 8px 6px; }
        QListWidget::item:selected { background-color: #28415D; }
        """

    def _light_stylesheet(self) -> str:
        return """
        QMainWindow { background-color: #F4F6F8; }
        QLabel, QCheckBox, QGroupBox { color: #1A2026; }
        QLabel#titleLabel { font-size: 24px; font-weight: 700; }
        QLabel#mutedLabel { color: #5F6D7A; }
        QGroupBox {
            border: 1px solid #D5DDE5;
            border-radius: 10px;
            margin-top: 8px;
            padding: 10px;
            font-weight: 600;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        QLineEdit, QTextEdit, QDateEdit, QComboBox, QListWidget {
            background-color: white;
            border: 1px solid #CFD8E2;
            border-radius: 8px;
            color: #1A2026;
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
        QPushButton#dangerButton { background-color: #B33A3A; }
        QPushButton#dangerButton:hover { background-color: #C24A4A; }
        QListWidget::item { padding: 8px 6px; }
        QListWidget::item:selected { background-color: #DCE9F8; }
        """
