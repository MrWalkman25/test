from datetime import datetime

from PySide6.QtCore import QDate, QDateTime, QSettings, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCalendarWidget,
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
    QStackedWidget,
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

    PAGE_DETAILS = 0
    PAGE_CALENDAR = 1
    PAGE_NEW = 2

    def __init__(self) -> None:
        super().__init__()

        self.settings = QSettings("LocalTaskManager", "MyTasks")
        self.current_task_id: int | None = None
        self._loading_details = False
        self.active_filter = "all"

        self.new_deadline_active = False
        self.new_reminder_active = False
        self.details_deadline_active = False
        self.details_reminder_active = False

        self.setWindowTitle("My Tasks")
        self.resize(1140, 740)

        self._build_ui()
        self._apply_saved_theme()
        self.load_tasks()
        self._start_reminder_timer()

    def _build_ui(self) -> None:
        central_widget = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

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

        body = QHBoxLayout()
        body.setSpacing(12)

        left_panel = self._build_left_panel()
        self.right_stack = self._build_right_panel()

        body.addWidget(left_panel, 2)
        body.addWidget(self.right_stack, 3)

        root_layout.addLayout(top_row)
        root_layout.addLayout(body)

        central_widget.setLayout(root_layout)
        self.setCentralWidget(central_widget)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.filter_tabs = QTabBar()
        self.filter_tabs.setDrawBase(False)
        for label in self.FILTER_LABELS:
            self.filter_tabs.addTab(label)
        self.filter_tabs.currentChanged.connect(self.on_filter_tab_changed)
        layout.addWidget(self.filter_tabs)

        filters_row = QHBoxLayout()
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(["all_statuses", *self.STATUS_OPTIONS])
        self.status_filter_combo.currentTextChanged.connect(lambda _v: self.load_tasks())

        self.tag_filter_combo = QComboBox()
        self.tag_filter_combo.addItem("all_tags")
        self.tag_filter_combo.currentTextChanged.connect(lambda _v: self.load_tasks())

        filters_row.addWidget(QLabel("Status:"))
        filters_row.addWidget(self.status_filter_combo)
        filters_row.addWidget(QLabel("Tag:"))
        filters_row.addWidget(self.tag_filter_combo)
        layout.addLayout(filters_row)

        self.tasks_list = QListWidget()
        self.tasks_list.currentItemChanged.connect(self.on_task_selected)
        layout.addWidget(self.tasks_list)

        actions = QHBoxLayout()
        self.new_task_button = QPushButton("+ Нова задача")
        self.new_task_button.clicked.connect(lambda: self.open_right_page(self.PAGE_NEW))

        self.calendar_button = QPushButton("Календар")
        self.calendar_button.clicked.connect(lambda: self.open_right_page(self.PAGE_CALENDAR))

        actions.addWidget(self.new_task_button)
        actions.addWidget(self.calendar_button)
        layout.addLayout(actions)

        panel.setLayout(layout)
        return panel

    def _build_right_panel(self) -> QStackedWidget:
        stack = QStackedWidget()
        stack.addWidget(self._build_details_page())
        stack.addWidget(self._build_calendar_page())
        stack.addWidget(self._build_new_task_page())
        stack.setCurrentIndex(self.PAGE_DETAILS)
        return stack

    def _build_details_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()

        group = QGroupBox("Task details")
        form = QFormLayout()

        self.details_title_input = QLineEdit()
        self.details_description_input = QTextEdit()
        self.details_description_input.setFixedHeight(90)
        self.details_tag_input = QLineEdit()

        self.details_status_combo = QComboBox()
        self.details_status_combo.addItems(self.STATUS_OPTIONS)
        self.details_status_combo.currentTextChanged.connect(self.handle_status_changed)

        self.details_priority_combo = QComboBox()
        self.details_priority_combo.addItems(self.PRIORITY_OPTIONS)

        self.details_deadline_input = QDateEdit()
        self.details_deadline_input.setCalendarPopup(True)
        self.details_deadline_input.setDate(QDate.currentDate())
        self.details_deadline_input.setDisplayFormat("yyyy-MM-dd")
        self.details_deadline_input.dateChanged.connect(lambda _d: self._set_details_deadline_active(True))

        self.details_deadline_state = QLabel("Не задано")
        self.details_deadline_state.setObjectName("mutedLabel")
        self.details_deadline_today = QPushButton("Сьогодні")
        self.details_deadline_today.clicked.connect(self.set_details_deadline_today)
        self.details_deadline_clear = QPushButton("Очистити")
        self.details_deadline_clear.clicked.connect(self.clear_details_deadline)
        details_deadline_row = QHBoxLayout()
        details_deadline_row.addWidget(self.details_deadline_input)
        details_deadline_row.addWidget(self.details_deadline_today)
        details_deadline_row.addWidget(self.details_deadline_clear)

        self.details_reminder_input = QDateTimeEdit()
        self.details_reminder_input.setCalendarPopup(True)
        self.details_reminder_input.setDateTime(QDateTime.currentDateTime())
        self.details_reminder_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.details_reminder_input.dateTimeChanged.connect(
            lambda _dt: self._set_details_reminder_active(True)
        )

        self.details_reminder_state = QLabel("Не задано")
        self.details_reminder_state.setObjectName("mutedLabel")
        self.details_reminder_today = QPushButton("Сьогодні")
        self.details_reminder_today.clicked.connect(self.set_details_reminder_now)
        self.details_reminder_clear = QPushButton("Очистити")
        self.details_reminder_clear.clicked.connect(self.clear_details_reminder)
        details_reminder_row = QHBoxLayout()
        details_reminder_row.addWidget(self.details_reminder_input)
        details_reminder_row.addWidget(self.details_reminder_today)
        details_reminder_row.addWidget(self.details_reminder_clear)

        self.created_at_label = QLabel("—")
        self.created_at_label.setObjectName("mutedLabel")

        form.addRow("Назва", self.details_title_input)
        form.addRow("Опис", self.details_description_input)
        form.addRow("Тег", self.details_tag_input)
        form.addRow("Статус", self.details_status_combo)
        form.addRow("Пріоритет", self.details_priority_combo)
        form.addRow("Дедлайн", details_deadline_row)
        form.addRow("Стан дедлайну", self.details_deadline_state)
        form.addRow("Нагадування", details_reminder_row)
        form.addRow("Стан нагадування", self.details_reminder_state)
        form.addRow("Створено", self.created_at_label)

        buttons = QHBoxLayout()
        self.save_button = QPushButton("Зберегти")
        self.save_button.clicked.connect(self.handle_save_task)

        self.delete_button = QPushButton("Видалити")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self.handle_delete_task)

        buttons.addWidget(self.save_button)
        buttons.addWidget(self.delete_button)

        group_layout = QVBoxLayout()
        group_layout.addLayout(form)
        group_layout.addLayout(buttons)
        group.setLayout(group_layout)

        layout.addWidget(group)
        layout.addStretch()
        page.setLayout(layout)
        return page

    def _build_new_task_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()

        group = QGroupBox("New task")
        form = QFormLayout()

        self.new_title_input = QLineEdit()
        self.new_description_input = QTextEdit()
        self.new_description_input.setFixedHeight(90)
        self.new_tag_input = QLineEdit()

        self.new_priority_combo = QComboBox()
        self.new_priority_combo.addItems(self.PRIORITY_OPTIONS)
        self.new_priority_combo.setCurrentText("normal")

        self.new_deadline_input = QDateEdit()
        self.new_deadline_input.setCalendarPopup(True)
        self.new_deadline_input.setDate(QDate.currentDate())
        self.new_deadline_input.setDisplayFormat("yyyy-MM-dd")
        self.new_deadline_input.dateChanged.connect(lambda _d: self._set_new_deadline_active(True))

        self.new_deadline_state = QLabel("Не задано")
        self.new_deadline_state.setObjectName("mutedLabel")
        self.new_deadline_today = QPushButton("Сьогодні")
        self.new_deadline_today.clicked.connect(self.set_new_deadline_today)
        self.new_deadline_clear = QPushButton("Очистити")
        self.new_deadline_clear.clicked.connect(self.clear_new_deadline)
        new_deadline_row = QHBoxLayout()
        new_deadline_row.addWidget(self.new_deadline_input)
        new_deadline_row.addWidget(self.new_deadline_today)
        new_deadline_row.addWidget(self.new_deadline_clear)

        self.new_reminder_input = QDateTimeEdit()
        self.new_reminder_input.setCalendarPopup(True)
        self.new_reminder_input.setDateTime(QDateTime.currentDateTime())
        self.new_reminder_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.new_reminder_input.dateTimeChanged.connect(lambda _dt: self._set_new_reminder_active(True))

        self.new_reminder_state = QLabel("Не задано")
        self.new_reminder_state.setObjectName("mutedLabel")
        self.new_reminder_today = QPushButton("Сьогодні")
        self.new_reminder_today.clicked.connect(self.set_new_reminder_now)
        self.new_reminder_clear = QPushButton("Очистити")
        self.new_reminder_clear.clicked.connect(self.clear_new_reminder)
        new_reminder_row = QHBoxLayout()
        new_reminder_row.addWidget(self.new_reminder_input)
        new_reminder_row.addWidget(self.new_reminder_today)
        new_reminder_row.addWidget(self.new_reminder_clear)

        form.addRow("Назва", self.new_title_input)
        form.addRow("Опис", self.new_description_input)
        form.addRow("Тег", self.new_tag_input)
        form.addRow("Пріоритет", self.new_priority_combo)
        form.addRow("Дедлайн", new_deadline_row)
        form.addRow("Стан дедлайну", self.new_deadline_state)
        form.addRow("Нагадування", new_reminder_row)
        form.addRow("Стан нагадування", self.new_reminder_state)

        self.create_task_button = QPushButton("Створити задачу")
        self.create_task_button.clicked.connect(self.handle_add_task)

        group_layout = QVBoxLayout()
        group_layout.addLayout(form)
        group_layout.addWidget(self.create_task_button)
        group.setLayout(group_layout)

        layout.addWidget(group)
        layout.addStretch()
        page.setLayout(layout)
        return page

    def _build_calendar_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()

        group = QGroupBox("Calendar view")
        group_layout = QVBoxLayout()

        self.calendar_widget = QCalendarWidget()
        self.calendar_widget.setSelectedDate(QDate.currentDate())
        self.calendar_widget.selectionChanged.connect(self.refresh_calendar_list)

        self.calendar_tasks_list = QListWidget()

        group_layout.addWidget(self.calendar_widget)
        group_layout.addWidget(QLabel("Задачі на обрану дату:"))
        group_layout.addWidget(self.calendar_tasks_list)
        group.setLayout(group_layout)

        layout.addWidget(group)
        page.setLayout(layout)
        return page

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

    def open_right_page(self, page_index: int) -> None:
        self.right_stack.setCurrentIndex(page_index)
        if page_index == self.PAGE_CALENDAR:
            self.refresh_calendar_list()

    def on_filter_tab_changed(self, index: int) -> None:
        if index < 0 or index >= len(self.FILTER_KEYS):
            return
        self.active_filter = self.FILTER_KEYS[index]
        self.load_tasks()

    def _refresh_tag_filter_options(self, tasks: list[dict]) -> None:
        current = self.tag_filter_combo.currentText()
        tags = sorted({task["tag"] for task in tasks if task.get("tag")})

        self.tag_filter_combo.blockSignals(True)
        self.tag_filter_combo.clear()
        self.tag_filter_combo.addItem("all_tags")
        for tag in tags:
            self.tag_filter_combo.addItem(tag)
        if current in ["all_tags", *tags]:
            self.tag_filter_combo.setCurrentText(current)
        else:
            self.tag_filter_combo.setCurrentText("all_tags")
        self.tag_filter_combo.blockSignals(False)

    def handle_add_task(self) -> None:
        title = self.new_title_input.text().strip()
        if not title:
            return

        task_id = add_task(
            title=title,
            description=self.new_description_input.toPlainText().strip() or None,
            tag=self.new_tag_input.text().strip() or None,
            deadline=(
                self.new_deadline_input.date().toString("yyyy-MM-dd")
                if self.new_deadline_active
                else None
            ),
            reminder_at=(
                self.new_reminder_input.dateTime().toString("yyyy-MM-dd HH:mm")
                if self.new_reminder_active
                else None
            ),
            priority=self.new_priority_combo.currentText(),
        )

        self.new_title_input.clear()
        self.new_description_input.clear()
        self.new_tag_input.clear()
        self.new_priority_combo.setCurrentText("normal")
        self.clear_new_deadline()
        self.clear_new_reminder()

        self.load_tasks(select_task_id=task_id)
        self.open_right_page(self.PAGE_DETAILS)

    def load_tasks(self, select_task_id: int | None = None) -> None:
        all_tasks = get_tasks()
        self._refresh_tag_filter_options(all_tasks)
        tasks = self._apply_filter(all_tasks)

        self.tasks_list.clear()
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
            self.refresh_calendar_list()
            return

        if select_task_id is not None:
            for i in range(self.tasks_list.count()):
                item = self.tasks_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == select_task_id:
                    self.tasks_list.setCurrentRow(i)
                    self.refresh_calendar_list()
                    return

        self.tasks_list.setCurrentRow(0)
        self.refresh_calendar_list()

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

        deadline = selected_task.get("deadline")
        if deadline:
            parsed_date = QDate.fromString(deadline, "yyyy-MM-dd")
            self.details_deadline_input.setDate(parsed_date if parsed_date.isValid() else QDate.currentDate())
            self._set_details_deadline_active(True)
        else:
            self.clear_details_deadline()

        reminder_at = selected_task.get("reminder_at")
        if reminder_at:
            parsed_dt = QDateTime.fromString(reminder_at, "yyyy-MM-dd HH:mm")
            self.details_reminder_input.setDateTime(
                parsed_dt if parsed_dt.isValid() else QDateTime.currentDateTime()
            )
            self._set_details_reminder_active(True)
        else:
            self.clear_details_reminder()

        self.created_at_label.setText(self._format_datetime(selected_task["created_at"]))
        self._loading_details = False

        self.open_right_page(self.PAGE_DETAILS)

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
            deadline=(
                self.details_deadline_input.date().toString("yyyy-MM-dd")
                if self.details_deadline_active
                else None
            ),
            reminder_at=(
                self.details_reminder_input.dateTime().toString("yyyy-MM-dd HH:mm")
                if self.details_reminder_active
                else None
            ),
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

    def set_new_deadline_today(self) -> None:
        self.new_deadline_input.setDate(QDate.currentDate())
        self._set_new_deadline_active(True)

    def clear_new_deadline(self) -> None:
        self.new_deadline_input.setDate(QDate.currentDate())
        self._set_new_deadline_active(False)

    def _set_new_deadline_active(self, active: bool) -> None:
        self.new_deadline_active = active
        self.new_deadline_state.setText("Активно" if active else "Не задано")

    def set_new_reminder_now(self) -> None:
        self.new_reminder_input.setDateTime(QDateTime.currentDateTime())
        self._set_new_reminder_active(True)

    def clear_new_reminder(self) -> None:
        self.new_reminder_input.setDateTime(QDateTime.currentDateTime())
        self._set_new_reminder_active(False)

    def _set_new_reminder_active(self, active: bool) -> None:
        self.new_reminder_active = active
        self.new_reminder_state.setText("Активно" if active else "Не задано")

    def set_details_deadline_today(self) -> None:
        self.details_deadline_input.setDate(QDate.currentDate())
        self._set_details_deadline_active(True)

    def clear_details_deadline(self) -> None:
        self.details_deadline_input.setDate(QDate.currentDate())
        self._set_details_deadline_active(False)

    def _set_details_deadline_active(self, active: bool) -> None:
        self.details_deadline_active = active
        self.details_deadline_state.setText("Активно" if active else "Не задано")

    def set_details_reminder_now(self) -> None:
        self.details_reminder_input.setDateTime(QDateTime.currentDateTime())
        self._set_details_reminder_active(True)

    def clear_details_reminder(self) -> None:
        self.details_reminder_input.setDateTime(QDateTime.currentDateTime())
        self._set_details_reminder_active(False)

    def _set_details_reminder_active(self, active: bool) -> None:
        self.details_reminder_active = active
        self.details_reminder_state.setText("Активно" if active else "Не задано")

    def refresh_calendar_list(self) -> None:
        selected_date = self.calendar_widget.selectedDate().toString("yyyy-MM-dd")
        self.calendar_tasks_list.clear()
        for task in get_tasks():
            if task.get("deadline") == selected_date:
                self.calendar_tasks_list.addItem(task["title"])

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
        self.details_deadline_today.setEnabled(enabled)
        self.details_deadline_clear.setEnabled(enabled)
        self.details_reminder_input.setEnabled(enabled)
        self.details_reminder_today.setEnabled(enabled)
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
        self.clear_details_deadline()
        self.clear_details_reminder()
        self.created_at_label.setText("—")
        self.set_details_enabled(False)

    def _apply_filter(self, tasks: list[dict]) -> list[dict]:
        today = QDate.currentDate().toString("yyyy-MM-dd")
        status_filter = self.status_filter_combo.currentText()
        tag_filter = self.tag_filter_combo.currentText()

        filtered = tasks

        if self.active_filter == "done":
            filtered = [task for task in filtered if task.get("status") == "done"]
        elif self.active_filter == "today":
            filtered = [task for task in filtered if task.get("deadline") == today]
        elif self.active_filter == "no_deadline":
            filtered = [task for task in filtered if not task.get("deadline")]
        elif self.active_filter == "overdue":
            filtered = [
                task
                for task in filtered
                if task.get("deadline")
                and task["deadline"] < today
                and task.get("status") != "done"
            ]

        if status_filter != "all_statuses":
            filtered = [task for task in filtered if task.get("status") == status_filter]

        if tag_filter != "all_tags":
            filtered = [task for task in filtered if task.get("tag") == tag_filter]

        return filtered

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
        QLineEdit, QTextEdit, QDateEdit, QDateTimeEdit, QComboBox, QListWidget, QTabBar::tab, QCalendarWidget {
            background-color: #1B2026;
            border: 1px solid #323B45;
            border-radius: 8px;
            color: #EAF0F5;
            padding: 6px;
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
        QLineEdit, QTextEdit, QDateEdit, QDateTimeEdit, QComboBox, QListWidget, QTabBar::tab, QCalendarWidget {
            background-color: white;
            border: 1px solid #CFD8E2;
            border-radius: 8px;
            color: #1A2026;
            padding: 6px;
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
