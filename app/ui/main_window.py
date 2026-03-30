from datetime import datetime

from PySide6.QtCore import QDate, QDateTime, QSettings, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
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
    QTabBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.database import (
    add_task,
    delete_task,
    get_due_reminders,
    get_task_by_id,
    get_tasks,
    mark_reminder_shown,
    update_task,
)
from app.notifications import send_desktop_notification


class MainWindow(QMainWindow):
    STATUS_OPTIONS = ["inbox", "in_progress", "done"]
    PRIORITY_OPTIONS = ["low", "normal", "high"]
    FILTER_KEYS = ["all", "today", "overdue", "no_deadline", "done"]
    FILTER_LABELS = ["All", "Today", "Overdue", "No deadline", "Done"]

    EMPTY_DATE = QDate(2000, 1, 1)
    EMPTY_DATETIME = QDateTime(2000, 1, 1, 0, 0)

    def __init__(self) -> None:
        super().__init__()

        self.settings = QSettings("LocalTaskManager", "MyTasks")
        self.current_task_id: int | None = None
        self._loading_details = False
        self.active_filter = "all"

        self.setWindowTitle("My Tasks")
        self.resize(1080, 720)

        self._build_ui()
        self._apply_saved_theme()
        self.load_tasks()
        self._start_reminder_timer()

    def _build_ui(self) -> None:
        central_widget = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        top_row = QHBoxLayout()
        title_label = QLabel("My Tasks")
        title_label.setObjectName("titleLabel")
        top_row.addWidget(title_label)
        top_row.addStretch()

        self.test_notification_button = QPushButton("Тест сповіщення")
        self.test_notification_button.clicked.connect(self.handle_test_notification)
        top_row.addWidget(self.test_notification_button)

        top_row.addWidget(QLabel("Theme:"))
        self.theme_selector = QComboBox()
        self.theme_selector.addItems(["Dark", "Light"])
        self.theme_selector.currentTextChanged.connect(self.on_theme_changed)
        top_row.addWidget(self.theme_selector)

        self.filter_tabs = QTabBar()
        self.filter_tabs.setDrawBase(False)
        for label in self.FILTER_LABELS:
            self.filter_tabs.addTab(label)
        self.filter_tabs.currentChanged.connect(self.on_filter_tab_changed)

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
        self.task_description_input.setFixedHeight(70)

        self.task_tag_input = QLineEdit()
        self.task_tag_input.setPlaceholderText("Тег (опційно)")

        self.create_priority_combo = QComboBox()
        self.create_priority_combo.addItems(self.PRIORITY_OPTIONS)
        self.create_priority_combo.setCurrentText("normal")

        self.task_deadline_input = self._build_optional_date_edit()
        self.task_deadline_clear = QPushButton("Очистити")
        self.task_deadline_clear.clicked.connect(lambda: self._clear_date_edit(self.task_deadline_input))

        create_deadline_row = QHBoxLayout()
        create_deadline_row.addWidget(self.task_deadline_input)
        create_deadline_row.addWidget(self.task_deadline_clear)

        self.task_reminder_input = self._build_optional_datetime_edit()
        self.task_reminder_clear = QPushButton("Очистити")
        self.task_reminder_clear.clicked.connect(
            lambda: self._clear_datetime_edit(self.task_reminder_input)
        )

        create_reminder_row = QHBoxLayout()
        create_reminder_row.addWidget(self.task_reminder_input)
        create_reminder_row.addWidget(self.task_reminder_clear)

        create_form.addRow("Назва", self.task_title_input)
        create_form.addRow("Опис", self.task_description_input)
        create_form.addRow("Тег", self.task_tag_input)
        create_form.addRow("Пріоритет", self.create_priority_combo)
        create_form.addRow("Дедлайн", create_deadline_row)
        create_form.addRow("Нагадування", create_reminder_row)

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

        self.details_tag_input = QLineEdit()
        self.details_tag_input.setPlaceholderText("Тег (опційно)")

        self.details_status_combo = QComboBox()
        self.details_status_combo.addItems(self.STATUS_OPTIONS)
        self.details_status_combo.currentTextChanged.connect(self.handle_status_changed)

        self.details_priority_combo = QComboBox()
        self.details_priority_combo.addItems(self.PRIORITY_OPTIONS)

        self.details_deadline_input = self._build_optional_date_edit()
        self.details_deadline_clear = QPushButton("Очистити")
        self.details_deadline_clear.clicked.connect(
            lambda: self._clear_date_edit(self.details_deadline_input)
        )

        details_deadline_row = QHBoxLayout()
        details_deadline_row.addWidget(self.details_deadline_input)
        details_deadline_row.addWidget(self.details_deadline_clear)

        self.details_reminder_input = self._build_optional_datetime_edit()
        self.details_reminder_clear = QPushButton("Очистити")
        self.details_reminder_clear.clicked.connect(
            lambda: self._clear_datetime_edit(self.details_reminder_input)
        )

        details_reminder_row = QHBoxLayout()
        details_reminder_row.addWidget(self.details_reminder_input)
        details_reminder_row.addWidget(self.details_reminder_clear)

        self.created_at_label = QLabel("—")
        self.created_at_label.setObjectName("mutedLabel")

        details_form.addRow("Назва", self.details_title_input)
        details_form.addRow("Опис", self.details_description_input)
        details_form.addRow("Тег", self.details_tag_input)
        details_form.addRow("Статус", self.details_status_combo)
        details_form.addRow("Пріоритет", self.details_priority_combo)
        details_form.addRow("Дедлайн", details_deadline_row)
        details_form.addRow("Нагадування", details_reminder_row)
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
        root_layout.addWidget(self.filter_tabs)
        root_layout.addLayout(content_layout)

        central_widget.setLayout(root_layout)
        self.setCentralWidget(central_widget)

        self.set_details_enabled(False)
        self.filter_tabs.setCurrentIndex(0)

    def _build_optional_date_edit(self) -> QDateEdit:
        editor = QDateEdit()
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("yyyy-MM-dd")
        editor.setSpecialValueText("—")
        editor.setMinimumDate(self.EMPTY_DATE)
        editor.setDate(self.EMPTY_DATE)
        return editor

    def _build_optional_datetime_edit(self) -> QDateTimeEdit:
        editor = QDateTimeEdit()
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("yyyy-MM-dd HH:mm")
        editor.setSpecialValueText("—")
        editor.setMinimumDateTime(self.EMPTY_DATETIME)
        editor.setDateTime(self.EMPTY_DATETIME)
        return editor

    def _clear_date_edit(self, editor: QDateEdit) -> None:
        editor.setDate(self.EMPTY_DATE)

    def _clear_datetime_edit(self, editor: QDateTimeEdit) -> None:
        editor.setDateTime(self.EMPTY_DATETIME)

    def _start_reminder_timer(self) -> None:
        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(30_000)
        self.reminder_timer.timeout.connect(self.check_due_reminders)
        self.reminder_timer.start()
        self.check_due_reminders()

    def check_due_reminders(self) -> None:
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M")
        due_tasks = get_due_reminders(now_iso)

        for task in due_tasks:
            message = "Час виконати задачу."
            if task["description"]:
                message = f"Час виконати задачу: {task['description'][:80]}"

            sent = send_desktop_notification(task["title"], message)
            if sent:
                mark_reminder_shown(task["id"])

    def handle_test_notification(self) -> None:
        send_desktop_notification(
            "Test notification",
            "Це тестове сповіщення з застосунку",
        )

    def on_filter_tab_changed(self, index: int) -> None:
        if index < 0 or index >= len(self.FILTER_KEYS):
            return
        self.active_filter = self.FILTER_KEYS[index]
        self.load_tasks()

    def handle_add_task(self) -> None:
        title = self.task_title_input.text().strip()
        if not title:
            return

        description = self.task_description_input.toPlainText().strip() or None
        tag = self.task_tag_input.text().strip() or None
        priority = self.create_priority_combo.currentText()

        deadline = self._date_value_or_none(self.task_deadline_input)
        reminder_at = self._datetime_value_or_none(self.task_reminder_input)

        task_id = add_task(
            title=title,
            description=description,
            tag=tag,
            deadline=deadline,
            reminder_at=reminder_at,
            priority=priority,
        )

        self.task_title_input.clear()
        self.task_description_input.clear()
        self.task_tag_input.clear()
        self.create_priority_combo.setCurrentText("normal")
        self._clear_date_edit(self.task_deadline_input)
        self._clear_datetime_edit(self.task_reminder_input)

        self.load_tasks(select_task_id=task_id)

    def load_tasks(self, select_task_id: int | None = None) -> None:
        self.tasks_list.clear()
        tasks = self._apply_filter(get_tasks())

        for task in tasks:
            text = task["title"]
            if task.get("tag"):
                text = f"[{task['tag']}] {text}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, task["id"])
            self._style_task_item(item, task)
            self.tasks_list.addItem(item)

        if self.tasks_list.count() == 0:
            self.show_empty_details()
            return

        if select_task_id is not None:
            for i in range(self.tasks_list.count()):
                item = self.tasks_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == select_task_id:
                    self.tasks_list.setCurrentRow(i)
                    return

        self.tasks_list.setCurrentRow(0)

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
        self._loading_details = True
        self.set_details_enabled(True)

        self.details_title_input.setText(selected_task["title"] or "")
        self.details_description_input.setPlainText(selected_task["description"] or "")
        self.details_tag_input.setText(selected_task["tag"] or "")
        self.details_status_combo.setCurrentText(selected_task["status"] or "inbox")
        self.details_priority_combo.setCurrentText(selected_task["priority"] or "normal")

        deadline = selected_task["deadline"]
        if deadline:
            parsed_date = QDate.fromString(deadline, "yyyy-MM-dd")
            if parsed_date.isValid():
                self.details_deadline_input.setDate(parsed_date)
            else:
                self._clear_date_edit(self.details_deadline_input)
        else:
            self._clear_date_edit(self.details_deadline_input)

        reminder_at = selected_task["reminder_at"]
        if reminder_at:
            parsed_datetime = QDateTime.fromString(reminder_at, "yyyy-MM-dd HH:mm")
            if parsed_datetime.isValid():
                self.details_reminder_input.setDateTime(parsed_datetime)
            else:
                self._clear_datetime_edit(self.details_reminder_input)
        else:
            self._clear_datetime_edit(self.details_reminder_input)

        self.created_at_label.setText(self._format_datetime(selected_task["created_at"]))
        self._loading_details = False

    def handle_status_changed(self) -> None:
        if self._loading_details or self.current_task_id is None:
            return
        self.handle_save_task()

    def handle_save_task(self) -> None:
        if self.current_task_id is None:
            return

        title = self.details_title_input.text().strip()
        if not title:
            return

        update_task(
            task_id=self.current_task_id,
            title=title,
            description=self.details_description_input.toPlainText().strip() or None,
            tag=self.details_tag_input.text().strip() or None,
            status=self.details_status_combo.currentText(),
            priority=self.details_priority_combo.currentText(),
            deadline=self._date_value_or_none(self.details_deadline_input),
            reminder_at=self._datetime_value_or_none(self.details_reminder_input),
        )

        self.load_tasks(select_task_id=self.current_task_id)

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
        self.current_task_id = None
        self.load_tasks()

    def _date_value_or_none(self, editor: QDateEdit) -> str | None:
        if editor.date() <= self.EMPTY_DATE:
            return None
        return editor.date().toString("yyyy-MM-dd")

    def _datetime_value_or_none(self, editor: QDateTimeEdit) -> str | None:
        if editor.dateTime() <= self.EMPTY_DATETIME:
            return None
        return editor.dateTime().toString("yyyy-MM-dd HH:mm")

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
        if theme_name == "Light":
            self.setStyleSheet(self._light_stylesheet())
        else:
            self.setStyleSheet(self._dark_stylesheet())

    def set_details_enabled(self, enabled: bool) -> None:
        self.details_title_input.setEnabled(enabled)
        self.details_description_input.setEnabled(enabled)
        self.details_tag_input.setEnabled(enabled)
        self.details_status_combo.setEnabled(enabled)
        self.details_priority_combo.setEnabled(enabled)
        self.details_deadline_input.setEnabled(enabled)
        self.details_deadline_clear.setEnabled(enabled)
        self.details_reminder_input.setEnabled(enabled)
        self.details_reminder_clear.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    def show_empty_details(self) -> None:
        self.current_task_id = None
        self.details_title_input.clear()
        self.details_description_input.clear()
        self.details_tag_input.clear()
        self.details_status_combo.setCurrentText("inbox")
        self.details_priority_combo.setCurrentText("normal")
        self._clear_date_edit(self.details_deadline_input)
        self._clear_datetime_edit(self.details_reminder_input)
        self.created_at_label.setText("—")
        self.set_details_enabled(False)

    def _apply_filter(self, tasks: list[dict]) -> list[dict]:
        today = QDate.currentDate().toString("yyyy-MM-dd")

        if self.active_filter == "all":
            return tasks
        if self.active_filter == "done":
            return [task for task in tasks if task.get("status") == "done"]
        if self.active_filter == "today":
            return [task for task in tasks if task.get("deadline") == today]
        if self.active_filter == "no_deadline":
            return [task for task in tasks if not task.get("deadline")]
        if self.active_filter == "overdue":
            return [
                task
                for task in tasks
                if task.get("deadline")
                and task["deadline"] < today
                and task.get("status") != "done"
            ]

        return tasks

    def _style_task_item(self, item: QListWidgetItem, task: dict) -> None:
        priority = task.get("priority", "normal")
        if priority == "high":
            item.setForeground(QColor("#ff9b9b"))
        elif priority == "low":
            item.setForeground(QColor("#9aa4af"))

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
        QLineEdit, QTextEdit, QDateEdit, QDateTimeEdit, QComboBox, QListWidget, QTabBar::tab {
            background-color: #1B2026;
            border: 1px solid #323B45;
            border-radius: 8px;
            color: #EAF0F5;
            padding: 7px;
        }
        QTabBar::tab:selected {
            background: #2D6CDF;
            border-color: #2D6CDF;
            color: #FFFFFF;
        }
        QPushButton {
            background-color: #2D6CDF;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 7px 10px;
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
        QLabel, QGroupBox { color: #1A2026; }
        QLabel#titleLabel { font-size: 24px; font-weight: 700; }
        QLabel#mutedLabel { color: #5F6D7A; }
        QGroupBox {
            border: 1px solid #D5DDE5;
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
        QLineEdit, QTextEdit, QDateEdit, QDateTimeEdit, QComboBox, QListWidget, QTabBar::tab {
            background-color: white;
            border: 1px solid #CFD8E2;
            border-radius: 8px;
            color: #1A2026;
            padding: 7px;
        }
        QTabBar::tab:selected {
            background: #2D6CDF;
            border-color: #2D6CDF;
            color: #FFFFFF;
        }
        QPushButton {
            background-color: #2D6CDF;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 7px 10px;
            font-weight: 600;
        }
        QPushButton:hover { background-color: #3B79E8; }
        QPushButton:pressed { background-color: #245BBE; }
        QPushButton#dangerButton { background-color: #B33A3A; }
        QPushButton#dangerButton:hover { background-color: #C24A4A; }
        QListWidget::item { padding: 8px 6px; }
        QListWidget::item:selected { background-color: #DCE9F8; }
        """
