from datetime import datetime, timedelta

from PySide6.QtCore import QDate, QDateTime, QSettings, QTimer, Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.database import (
    STATUS_CANCELLED,
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    STATUS_NEW,
    STATUS_OVERDUE,
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
    MANUAL_STATUS_OPTIONS = [STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_CANCELLED]
    PRIORITY_OPTIONS = ["low", "normal", "high"]
    FILTER_KEYS = ["all", "today", "overdue", "no_deadline", "done"]
    FILTER_LABELS = ["All", "Today", "Overdue", "No deadline", "Done"]

    PAGE_TASK_CARD = 0
    PAGE_CALENDAR = 1
    PAGE_NEW = 2

    CAL_MONTH = 0
    CAL_WEEK = 1
    CAL_DAY = 2

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

        self.current_week_anchor = QDate.currentDate()
        self.day_plan_date = QDate.currentDate()

        self.setWindowTitle("My Tasks")
        self.resize(1200, 760)

        self._build_ui()
        self._apply_saved_theme()
        self.load_tasks()
        self._start_reminder_timer()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel("My Tasks")
        title.setObjectName("titleLabel")
        top.addWidget(title)
        top.addStretch()

        self.test_notification_button = QPushButton("Тест сповіщення")
        self.test_notification_button.clicked.connect(self.handle_test_notification)
        top.addWidget(self.test_notification_button)

        top.addWidget(QLabel("Theme:"))
        self.theme_selector = QComboBox()
        self.theme_selector.addItems(["Dark", "Light"])
        self.theme_selector.currentTextChanged.connect(self.on_theme_changed)
        top.addWidget(self.theme_selector)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_panel())
        self.right_stack = self._build_right_panel()
        splitter.addWidget(self.right_stack)
        splitter.setSizes([300, 900])

        root_layout.addLayout(top)
        root_layout.addWidget(splitter)
        root.setLayout(root_layout)
        self.setCentralWidget(root)

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

        filters = QHBoxLayout()
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(["all_statuses", *self.MANUAL_STATUS_OPTIONS, STATUS_OVERDUE])
        self.status_filter_combo.currentTextChanged.connect(lambda _x: self.load_tasks())

        self.tag_filter_combo = QComboBox()
        self.tag_filter_combo.addItem("all_tags")
        self.tag_filter_combo.currentTextChanged.connect(lambda _x: self.load_tasks())

        filters.addWidget(QLabel("Статус"))
        filters.addWidget(self.status_filter_combo)
        filters.addWidget(QLabel("Тег"))
        filters.addWidget(self.tag_filter_combo)

        self.tasks_list = QListWidget()
        self.tasks_list.currentItemChanged.connect(self.on_task_selected)

        actions = QHBoxLayout()
        self.new_task_button = QPushButton("+ Нова задача")
        self.new_task_button.clicked.connect(lambda: self.open_right_page(self.PAGE_NEW))
        self.calendar_button = QPushButton("Календар")
        self.calendar_button.clicked.connect(lambda: self.open_right_page(self.PAGE_CALENDAR))
        actions.addWidget(self.new_task_button)
        actions.addWidget(self.calendar_button)

        layout.addWidget(self.filter_tabs)
        layout.addLayout(filters)
        layout.addWidget(self.tasks_list)
        layout.addLayout(actions)
        panel.setLayout(layout)
        return panel

    def _build_right_panel(self) -> QStackedWidget:
        stack = QStackedWidget()
        stack.addWidget(self._build_task_card_page())
        stack.addWidget(self._build_calendar_page())
        stack.addWidget(self._build_new_task_page())
        stack.setCurrentIndex(self.PAGE_CALENDAR)
        return stack

    def _build_task_card_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()

        card = QFrame()
        card.setObjectName("taskCard")
        card_layout = QVBoxLayout()

        header = QLabel("Task card")
        header.setObjectName("cardTitle")
        card_layout.addWidget(header)

        form = QFormLayout()
        self.details_title_input = QLineEdit()
        self.details_description_input = QTextEdit()
        self.details_description_input.setFixedHeight(80)
        self.details_tag_input = QLineEdit()

        self.details_status_combo = QComboBox()
        self.details_status_combo.addItems(self.MANUAL_STATUS_OPTIONS)
        self.details_status_combo.currentTextChanged.connect(self.handle_status_changed)

        self.details_priority_combo = QComboBox()
        self.details_priority_combo.addItems(self.PRIORITY_OPTIONS)

        self.details_deadline_input = QDateEdit()
        self.details_deadline_input.setCalendarPopup(True)
        self.details_deadline_input.setDate(QDate.currentDate())
        self.details_deadline_input.setDisplayFormat("yyyy-MM-dd")
        self.details_deadline_input.dateChanged.connect(lambda _d: self._set_details_deadline_active(True))
        self.details_deadline_today = QPushButton("Сьогодні")
        self.details_deadline_today.clicked.connect(self.set_details_deadline_today)
        self.details_deadline_clear = QPushButton("Очистити")
        self.details_deadline_clear.clicked.connect(self.clear_details_deadline)
        drow = QHBoxLayout()
        drow.addWidget(self.details_deadline_input)
        drow.addWidget(self.details_deadline_today)
        drow.addWidget(self.details_deadline_clear)

        self.details_reminder_input = QDateTimeEdit()
        self.details_reminder_input.setCalendarPopup(True)
        self.details_reminder_input.setDateTime(QDateTime.currentDateTime())
        self.details_reminder_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.details_reminder_input.dateTimeChanged.connect(lambda _d: self._set_details_reminder_active(True))
        self.details_reminder_today = QPushButton("Сьогодні")
        self.details_reminder_today.clicked.connect(self.set_details_reminder_now)
        self.details_reminder_clear = QPushButton("Очистити")
        self.details_reminder_clear.clicked.connect(self.clear_details_reminder)
        rrow = QHBoxLayout()
        rrow.addWidget(self.details_reminder_input)
        rrow.addWidget(self.details_reminder_today)
        rrow.addWidget(self.details_reminder_clear)

        self.status_preview_label = QLabel("Статус: —")
        self.status_preview_label.setObjectName("mutedLabel")
        self.created_at_label = QLabel("Створено: —")
        self.created_at_label.setObjectName("mutedLabel")

        form.addRow("Назва", self.details_title_input)
        form.addRow("Опис", self.details_description_input)
        form.addRow("Тег", self.details_tag_input)
        form.addRow("Статус", self.details_status_combo)
        form.addRow("Пріоритет", self.details_priority_combo)
        form.addRow("Дедлайн", drow)
        form.addRow("Нагадування", rrow)

        buttons = QHBoxLayout()
        self.save_button = QPushButton("Зберегти")
        self.save_button.clicked.connect(self.handle_save_task)
        self.delete_button = QPushButton("Видалити")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self.handle_delete_task)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.delete_button)

        card_layout.addLayout(form)
        card_layout.addWidget(self.status_preview_label)
        card_layout.addWidget(self.created_at_label)
        card_layout.addLayout(buttons)
        card.setLayout(card_layout)

        layout.addWidget(card)
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
        self.new_deadline_today = QPushButton("Сьогодні")
        self.new_deadline_today.clicked.connect(self.set_new_deadline_today)
        self.new_deadline_clear = QPushButton("Очистити")
        self.new_deadline_clear.clicked.connect(self.clear_new_deadline)
        ndrow = QHBoxLayout()
        ndrow.addWidget(self.new_deadline_input)
        ndrow.addWidget(self.new_deadline_today)
        ndrow.addWidget(self.new_deadline_clear)

        self.new_reminder_input = QDateTimeEdit()
        self.new_reminder_input.setCalendarPopup(True)
        self.new_reminder_input.setDateTime(QDateTime.currentDateTime())
        self.new_reminder_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.new_reminder_input.dateTimeChanged.connect(lambda _d: self._set_new_reminder_active(True))
        self.new_reminder_today = QPushButton("Сьогодні")
        self.new_reminder_today.clicked.connect(self.set_new_reminder_now)
        self.new_reminder_clear = QPushButton("Очистити")
        self.new_reminder_clear.clicked.connect(self.clear_new_reminder)
        nrrow = QHBoxLayout()
        nrrow.addWidget(self.new_reminder_input)
        nrrow.addWidget(self.new_reminder_today)
        nrrow.addWidget(self.new_reminder_clear)

        self.new_deadline_state = QLabel("Не задано")
        self.new_deadline_state.setObjectName("mutedLabel")
        self.new_reminder_state = QLabel("Не задано")
        self.new_reminder_state.setObjectName("mutedLabel")

        form.addRow("Назва", self.new_title_input)
        form.addRow("Опис", self.new_description_input)
        form.addRow("Тег", self.new_tag_input)
        form.addRow("Пріоритет", self.new_priority_combo)
        form.addRow("Дедлайн", ndrow)
        form.addRow("Стан дедлайну", self.new_deadline_state)
        form.addRow("Нагадування", nrrow)
        form.addRow("Стан нагадування", self.new_reminder_state)

        self.create_task_button = QPushButton("Створити")
        self.create_task_button.clicked.connect(self.handle_add_task)

        gl = QVBoxLayout()
        gl.addLayout(form)
        gl.addWidget(self.create_task_button)
        group.setLayout(gl)

        layout.addWidget(group)
        layout.addStretch()
        page.setLayout(layout)
        return page

    def _build_calendar_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()

        controls = QHBoxLayout()
        self.btn_today = QPushButton("Сьогодні")
        self.btn_today.clicked.connect(self.calendar_go_today)
        self.btn_week = QPushButton("Тиждень")
        self.btn_week.setCheckable(True)
        self.btn_week.clicked.connect(lambda: self.set_calendar_mode(self.CAL_WEEK))
        self.btn_month = QPushButton("Місяць")
        self.btn_month.setCheckable(True)
        self.btn_month.clicked.connect(lambda: self.set_calendar_mode(self.CAL_MONTH))
        self.btn_back = QPushButton("Назад")
        self.btn_back.clicked.connect(self.back_from_day_plan)
        self.btn_back.setVisible(False)
        controls.addWidget(self.btn_today)
        controls.addWidget(self.btn_week)
        controls.addWidget(self.btn_month)
        controls.addWidget(self.btn_back)
        controls.addStretch()

        self.calendar_mode_stack = QStackedWidget()

        # Month mode
        self.month_calendar = QCalendarWidget()
        self.month_calendar.setGridVisible(True)
        self.month_calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.month_calendar.setSelectedDate(QDate.currentDate())
        self.month_calendar.activated.connect(self.open_day_plan)

        # Week mode
        self.week_table = QTableWidget(1, 7)
        self.week_table.verticalHeader().setVisible(False)
        self.week_table.horizontalHeader().setStretchLastSection(True)
        self.week_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.week_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.week_table.cellDoubleClicked.connect(self.open_day_plan_from_week)

        # Day plan mode
        self.day_plan_list = QListWidget()

        self.calendar_mode_stack.addWidget(self.month_calendar)
        self.calendar_mode_stack.addWidget(self.week_table)
        self.calendar_mode_stack.addWidget(self.day_plan_list)

        layout.addLayout(controls)
        layout.addWidget(self.calendar_mode_stack)
        page.setLayout(layout)

        self.set_calendar_mode(self.CAL_MONTH)
        return page

    def _start_reminder_timer(self) -> None:
        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(30_000)
        self.reminder_timer.timeout.connect(self.check_due_reminders)
        self.reminder_timer.start()
        self.check_due_reminders()

    def check_due_reminders(self) -> None:
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M")
        for task in get_due_reminders(now_iso):
            message = "Час виконати задачу."
            if task["description"]:
                message = f"Час виконати задачу: {task['description'][:80]}"
            sent = send_desktop_notification(task["title"], message)
            if sent:
                mark_reminder_shown(task["id"])

    def handle_test_notification(self) -> None:
        send_desktop_notification("Test notification", "Це тестове сповіщення з застосунку")

    def open_right_page(self, index: int) -> None:
        self.right_stack.setCurrentIndex(index)
        if index == self.PAGE_CALENDAR:
            self.refresh_calendar_visuals()

    def on_filter_tab_changed(self, index: int) -> None:
        if 0 <= index < len(self.FILTER_KEYS):
            self.active_filter = self.FILTER_KEYS[index]
            self.load_tasks()

    def _refresh_tag_filter_options(self, tasks: list[dict]) -> None:
        current = self.tag_filter_combo.currentText()
        tags = sorted({task["tag"] for task in tasks if task.get("tag")})
        self.tag_filter_combo.blockSignals(True)
        self.tag_filter_combo.clear()
        self.tag_filter_combo.addItem("all_tags")
        self.tag_filter_combo.addItems(tags)
        self.tag_filter_combo.setCurrentText(current if current in ["all_tags", *tags] else "all_tags")
        self.tag_filter_combo.blockSignals(False)

    def _effective_status(self, task: dict) -> str:
        deadline = task.get("deadline")
        status = task.get("status") or STATUS_NEW
        if status in {STATUS_DONE, STATUS_CANCELLED}:
            return status
        if deadline and deadline < QDate.currentDate().toString("yyyy-MM-dd"):
            return STATUS_OVERDUE
        return status

    def handle_add_task(self) -> None:
        title = self.new_title_input.text().strip()
        if not title:
            return

        task_id = add_task(
            title=title,
            description=self.new_description_input.toPlainText().strip() or None,
            tag=self.new_tag_input.text().strip() or None,
            deadline=self.new_deadline_input.date().toString("yyyy-MM-dd") if self.new_deadline_active else None,
            reminder_at=self.new_reminder_input.dateTime().toString("yyyy-MM-dd HH:mm") if self.new_reminder_active else None,
            priority=self.new_priority_combo.currentText(),
        )

        self.new_title_input.clear()
        self.new_description_input.clear()
        self.new_tag_input.clear()
        self.new_priority_combo.setCurrentText("normal")
        self.clear_new_deadline()
        self.clear_new_reminder()

        self.load_tasks(select_task_id=task_id)
        self.open_right_page(self.PAGE_TASK_CARD)

    def load_tasks(self, select_task_id: int | None = None) -> None:
        all_tasks = get_tasks()
        self._refresh_tag_filter_options(all_tasks)
        tasks = self._apply_filter(all_tasks)

        self.tasks_list.clear()
        for task in tasks:
            effective_status = self._effective_status(task)
            text = task["title"]
            if task.get("tag"):
                text = f"[{task['tag']}] {text}"
            text = f"{text}  ·  {effective_status}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, task["id"])
            self._style_task_item(item, task, effective_status)
            self.tasks_list.addItem(item)

        if self.tasks_list.count() == 0:
            self.show_empty_card()
            self.refresh_calendar_visuals()
            return

        if select_task_id is not None:
            for i in range(self.tasks_list.count()):
                item = self.tasks_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == select_task_id:
                    self.tasks_list.setCurrentRow(i)
                    self.refresh_calendar_visuals()
                    return

        self.tasks_list.setCurrentRow(0)
        self.refresh_calendar_visuals()

    def on_task_selected(self, current: QListWidgetItem | None) -> None:
        if current is None:
            self.show_empty_card()
            return

        task_id = current.data(Qt.ItemDataRole.UserRole)
        task = get_task_by_id(task_id)
        if task is None:
            self.show_empty_card()
            return

        self.current_task_id = task["id"]
        self._loading_details = True
        self.set_card_enabled(True)

        self.details_title_input.setText(task["title"] or "")
        self.details_description_input.setPlainText(task["description"] or "")
        self.details_tag_input.setText(task["tag"] or "")

        effective_status = self._effective_status(task)
        manual_status = task.get("status") if task.get("status") in self.MANUAL_STATUS_OPTIONS else STATUS_NEW
        self.details_status_combo.setCurrentText(manual_status)
        self.details_priority_combo.setCurrentText(task.get("priority") or "normal")

        deadline = task.get("deadline")
        if deadline:
            d = QDate.fromString(deadline, "yyyy-MM-dd")
            self.details_deadline_input.setDate(d if d.isValid() else QDate.currentDate())
            self._set_details_deadline_active(True)
        else:
            self.clear_details_deadline()

        reminder = task.get("reminder_at")
        if reminder:
            dt = QDateTime.fromString(reminder, "yyyy-MM-dd HH:mm")
            self.details_reminder_input.setDateTime(dt if dt.isValid() else QDateTime.currentDateTime())
            self._set_details_reminder_active(True)
        else:
            self.clear_details_reminder()

        self.status_preview_label.setText(f"Статус: {effective_status}")
        if effective_status == STATUS_OVERDUE:
            self.status_preview_label.setStyleSheet("color: #ff7b7b;")
        else:
            self.status_preview_label.setStyleSheet("")
        self.created_at_label.setText(f"Створено: {self._format_datetime(task.get('created_at'))}")

        self._loading_details = False
        self.open_right_page(self.PAGE_TASK_CARD)

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
            deadline=self.details_deadline_input.date().toString("yyyy-MM-dd") if self.details_deadline_active else None,
            reminder_at=self.details_reminder_input.dateTime().toString("yyyy-MM-dd HH:mm") if self.details_reminder_active else None,
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

    # date helpers
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

    def set_details_reminder_now(self) -> None:
        self.details_reminder_input.setDateTime(QDateTime.currentDateTime())
        self._set_details_reminder_active(True)

    def clear_details_reminder(self) -> None:
        self.details_reminder_input.setDateTime(QDateTime.currentDateTime())
        self._set_details_reminder_active(False)

    def _set_details_reminder_active(self, active: bool) -> None:
        self.details_reminder_active = active

    # calendar modes
    def set_calendar_mode(self, mode: int) -> None:
        self.calendar_mode_stack.setCurrentIndex(mode)
        self.btn_week.setChecked(mode == self.CAL_WEEK)
        self.btn_month.setChecked(mode == self.CAL_MONTH)
        self.btn_back.setVisible(mode == self.CAL_DAY)
        self.refresh_calendar_visuals()

    def calendar_go_today(self) -> None:
        today = QDate.currentDate()
        self.month_calendar.setSelectedDate(today)
        self.current_week_anchor = today
        if self.calendar_mode_stack.currentIndex() == self.CAL_DAY:
            self.day_plan_date = today
            self.refresh_day_plan()
        else:
            self.refresh_calendar_visuals()

    def open_day_plan(self, date: QDate) -> None:
        self.day_plan_date = date
        self.set_calendar_mode(self.CAL_DAY)

    def open_day_plan_from_week(self, _row: int, col: int) -> None:
        start = self._start_of_week(self.current_week_anchor)
        self.day_plan_date = start.addDays(col)
        self.set_calendar_mode(self.CAL_DAY)

    def back_from_day_plan(self) -> None:
        self.set_calendar_mode(self.CAL_MONTH)

    def _start_of_week(self, date: QDate) -> QDate:
        return date.addDays(-(date.dayOfWeek() - 1))

    def refresh_calendar_visuals(self) -> None:
        mode = self.calendar_mode_stack.currentIndex()
        if mode == self.CAL_MONTH:
            self._refresh_month_view()
        elif mode == self.CAL_WEEK:
            self._refresh_week_view()
        elif mode == self.CAL_DAY:
            self.refresh_day_plan()

    def _refresh_month_view(self) -> None:
        # reset formats
        default_format = QTextCharFormat()
        for i in range(1, 32):
            self.month_calendar.setDateTextFormat(
                QDate(self.month_calendar.selectedDate().year(), self.month_calendar.selectedDate().month(), min(i, 28)).addDays(i - 1),
                default_format,
            )

        task_map: dict[str, list[dict]] = {}
        for task in get_tasks():
            d = task.get("deadline")
            if d:
                task_map.setdefault(d, []).append(task)

        for day_str, tasks in task_map.items():
            day = QDate.fromString(day_str, "yyyy-MM-dd")
            if not day.isValid():
                continue
            fmt = QTextCharFormat()
            overdue = any(self._effective_status(t) == STATUS_OVERDUE for t in tasks)
            done_or_cancelled = all(self._effective_status(t) in {STATUS_DONE, STATUS_CANCELLED} for t in tasks)
            if overdue:
                fmt.setBackground(QColor("#5a1f1f"))
            elif done_or_cancelled:
                fmt.setBackground(QColor("#2e3f2e"))
            else:
                fmt.setBackground(QColor("#2d6cdf"))
            self.month_calendar.setDateTextFormat(day, fmt)

    def _refresh_week_view(self) -> None:
        tasks = get_tasks()
        start = self._start_of_week(self.current_week_anchor)
        self.week_table.setRowCount(1)
        self.week_table.setColumnCount(7)

        for col in range(7):
            day = start.addDays(col)
            day_str = day.toString("yyyy-MM-dd")
            self.week_table.setHorizontalHeaderItem(col, QTableWidgetItem(day.toString("dd MMM")))

            day_tasks = [t for t in tasks if t.get("deadline") == day_str]
            lines = []
            for task in day_tasks[:3]:
                status = self._effective_status(task)
                lines.append(f"• {task['title']} ({status})")
            if len(day_tasks) > 3:
                lines.append(f"+{len(day_tasks)-3} ще")
            cell = QTableWidgetItem("\n".join(lines))
            if any(self._effective_status(t) == STATUS_OVERDUE for t in day_tasks):
                cell.setBackground(QColor("#5a1f1f"))
            elif day_tasks and all(self._effective_status(t) in {STATUS_DONE, STATUS_CANCELLED} for t in day_tasks):
                cell.setBackground(QColor("#2e3f2e"))
            self.week_table.setItem(0, col, cell)

    def refresh_day_plan(self) -> None:
        self.day_plan_list.clear()
        d = self.day_plan_date.toString("yyyy-MM-dd")
        tasks = [t for t in get_tasks() if t.get("deadline") == d]
        for task in tasks:
            status = self._effective_status(task)
            item = QListWidgetItem(f"{task['title']} · {status}")
            self._style_task_item(item, task, status)
            self.day_plan_list.addItem(item)

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
        self.setStyleSheet(self._light_stylesheet() if theme_name == "Light" else self._dark_stylesheet())

    def set_card_enabled(self, enabled: bool) -> None:
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

    def show_empty_card(self) -> None:
        self.current_task_id = None
        self.details_title_input.clear()
        self.details_description_input.clear()
        self.details_tag_input.clear()
        self.details_status_combo.setCurrentText(STATUS_NEW)
        self.details_priority_combo.setCurrentText("normal")
        self.clear_details_deadline()
        self.clear_details_reminder()
        self.status_preview_label.setText("Статус: —")
        self.created_at_label.setText("Створено: —")
        self.set_card_enabled(False)

    def _apply_filter(self, tasks: list[dict]) -> list[dict]:
        today = QDate.currentDate().toString("yyyy-MM-dd")
        status_filter = self.status_filter_combo.currentText()
        tag_filter = self.tag_filter_combo.currentText()

        filtered = tasks
        if self.active_filter == "done":
            filtered = [t for t in filtered if self._effective_status(t) == STATUS_DONE]
        elif self.active_filter == "today":
            filtered = [t for t in filtered if t.get("deadline") == today]
        elif self.active_filter == "no_deadline":
            filtered = [t for t in filtered if not t.get("deadline")]
        elif self.active_filter == "overdue":
            filtered = [t for t in filtered if self._effective_status(t) == STATUS_OVERDUE]

        if status_filter != "all_statuses":
            filtered = [t for t in filtered if self._effective_status(t) == status_filter]
        if tag_filter != "all_tags":
            filtered = [t for t in filtered if t.get("tag") == tag_filter]

        return filtered

    def _style_task_item(self, item: QListWidgetItem, task: dict, effective_status: str) -> None:
        priority = task.get("priority", "normal")
        if effective_status == STATUS_OVERDUE:
            item.setForeground(QColor("#ff7b7b"))
            return
        if effective_status in {STATUS_DONE, STATUS_CANCELLED}:
            item.setForeground(QColor("#8aa08a"))
            return
        if priority == "high":
            item.setForeground(QColor("#ffb3b3"))
        elif priority == "low":
            item.setForeground(QColor("#9aa4af"))

    def _format_datetime(self, value: str | None) -> str:
        if not value:
            return "—"
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value

    def _dark_stylesheet(self) -> str:
        return """
        QMainWindow { background-color: #121417; }
        QLabel, QGroupBox { color: #EAF0F5; }
        QLabel#titleLabel { font-size: 24px; font-weight: 700; }
        QLabel#mutedLabel { color: #A8B4C0; }
        QLabel#cardTitle { font-size: 18px; font-weight: 600; }
        QFrame#taskCard {
            background: #171b20;
            border: 1px solid #2b323a;
            border-radius: 12px;
            padding: 8px;
        }
        QGroupBox {
            border: 1px solid #2B323A;
            border-radius: 10px;
            margin-top: 8px;
            padding: 10px;
        }
        QLineEdit, QTextEdit, QDateEdit, QDateTimeEdit, QComboBox, QListWidget, QTabBar::tab, QCalendarWidget, QTableWidget {
            background-color: #1B2026;
            border: 1px solid #323B45;
            border-radius: 8px;
            color: #EAF0F5;
            padding: 6px;
        }
        QTabBar::tab:selected { background: #2D6CDF; color: #FFFFFF; }
        QPushButton { background-color: #2D6CDF; color: white; border: none; border-radius: 8px; padding: 7px 10px; }
        QPushButton:hover { background-color: #3B79E8; }
        QPushButton#dangerButton { background-color: #B33A3A; }
        """

    def _light_stylesheet(self) -> str:
        return """
        QMainWindow { background-color: #F4F6F8; }
        QLabel, QGroupBox { color: #1A2026; }
        QLabel#titleLabel { font-size: 24px; font-weight: 700; }
        QLabel#mutedLabel { color: #5F6D7A; }
        QLabel#cardTitle { font-size: 18px; font-weight: 600; }
        QFrame#taskCard {
            background: #ffffff;
            border: 1px solid #d5dde5;
            border-radius: 12px;
            padding: 8px;
        }
        QGroupBox {
            border: 1px solid #D5DDE5;
            border-radius: 10px;
            margin-top: 8px;
            padding: 10px;
        }
        QLineEdit, QTextEdit, QDateEdit, QDateTimeEdit, QComboBox, QListWidget, QTabBar::tab, QCalendarWidget, QTableWidget {
            background-color: white;
            border: 1px solid #CFD8E2;
            border-radius: 8px;
            color: #1A2026;
            padding: 6px;
        }
        QTabBar::tab:selected { background: #2D6CDF; color: #FFFFFF; }
        QPushButton { background-color: #2D6CDF; color: white; border: none; border-radius: 8px; padding: 7px 10px; }
        QPushButton:hover { background-color: #3B79E8; }
        QPushButton#dangerButton { background-color: #B33A3A; }
        """
