from datetime import datetime

from PySide6.QtCore import QDate, QDateTime, QSettings, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
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

    PAGE_CALENDAR = 0
    PAGE_NEW = 1
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

        self.current_month_anchor = QDate.currentDate()
        self.current_week_anchor = QDate.currentDate()
        self.day_plan_date = QDate.currentDate()

        self.month_day_task_map: dict[str, list[dict]] = {}
        self.week_day_task_map: dict[str, list[dict]] = {}

        self.setWindowTitle("My Tasks")
        self.resize(1240, 780)

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
        splitter.setSizes([280, 960])

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
        for label in ["All", "Today", "Overdue", "No deadline", "Done"]:
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
        btn_new = QPushButton("+ Нова задача")
        btn_new.clicked.connect(lambda: self.right_stack.setCurrentIndex(self.PAGE_NEW))
        btn_calendar = QPushButton("Календар")
        btn_calendar.clicked.connect(lambda: self.right_stack.setCurrentIndex(self.PAGE_CALENDAR))
        actions.addWidget(btn_new)
        actions.addWidget(btn_calendar)

        layout.addWidget(self.filter_tabs)
        layout.addLayout(filters)
        layout.addWidget(self.tasks_list)
        layout.addLayout(actions)
        panel.setLayout(layout)
        return panel

    def _build_right_panel(self) -> QStackedWidget:
        stack = QStackedWidget()
        stack.addWidget(self._build_calendar_page())
        stack.addWidget(self._build_new_task_page())
        return stack

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
        self.calendar_title = QLabel("")
        self.calendar_title.setObjectName("cardTitle")

        controls.addWidget(self.btn_today)
        controls.addWidget(self.btn_week)
        controls.addWidget(self.btn_month)
        controls.addWidget(self.btn_back)
        controls.addStretch()
        controls.addWidget(self.calendar_title)

        self.calendar_stack = QStackedWidget()

        # Month view with chips
        self.month_table = QTableWidget(6, 7)
        self.month_table.verticalHeader().setVisible(False)
        self.month_table.horizontalHeader().setVisible(True)
        self.month_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.month_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.month_table.cellClicked.connect(self.on_month_cell_clicked)
        self.month_table.cellDoubleClicked.connect(self.on_month_cell_double_clicked)

        # Week view with chips
        self.week_table = QTableWidget(1, 7)
        self.week_table.verticalHeader().setVisible(False)
        self.week_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.week_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.week_table.cellClicked.connect(self.on_week_cell_clicked)
        self.week_table.cellDoubleClicked.connect(self.on_week_cell_double_clicked)

        # Day plan full screen
        self.day_plan_list = QListWidget()
        self.day_plan_list.itemClicked.connect(self.on_day_plan_item_clicked)

        self.calendar_stack.addWidget(self.month_table)
        self.calendar_stack.addWidget(self.week_table)
        self.calendar_stack.addWidget(self.day_plan_list)

        # Popover card (compact)
        self.popover = self._build_task_popover()
        self.popover.setVisible(False)

        layout.addLayout(controls)
        layout.addWidget(self.calendar_stack)
        layout.addWidget(self.popover)

        page.setLayout(layout)

        self.set_calendar_mode(self.CAL_MONTH)
        return page

    def _build_task_popover(self) -> QFrame:
        pop = QFrame()
        pop.setObjectName("taskPopover")
        p = QVBoxLayout()

        self.pop_title = QLabel("—")
        self.pop_title.setObjectName("cardTitle")
        self.pop_desc = QLabel("—")
        self.pop_tag = QLabel("—")
        self.pop_status = QLabel("—")
        self.pop_priority = QLabel("—")
        self.pop_deadline = QLabel("—")
        self.pop_reminder = QLabel("—")
        self.pop_created = QLabel("—")

        fields = [
            ("Опис", self.pop_desc),
            ("Тег", self.pop_tag),
            ("Статус", self.pop_status),
            ("Пріоритет", self.pop_priority),
            ("Дедлайн", self.pop_deadline),
            ("Нагадування", self.pop_reminder),
            ("Створено", self.pop_created),
        ]

        p.addWidget(self.pop_title)
        for name, label in fields:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{name}:"))
            row.addWidget(label)
            p.addLayout(row)

        controls = QHBoxLayout()
        self.pop_edit_button = QPushButton("Редагувати")
        self.pop_edit_button.clicked.connect(self.open_edit_for_current_task)
        self.pop_close_button = QPushButton("Закрити")
        self.pop_close_button.clicked.connect(lambda: self.popover.setVisible(False))
        controls.addWidget(self.pop_edit_button)
        controls.addWidget(self.pop_close_button)

        p.addLayout(controls)
        pop.setLayout(p)
        return pop

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
        self.new_deadline_input.dateChanged.connect(lambda _d: self._set_new_deadline_active(True))
        self.new_deadline_today = QPushButton("Сьогодні")
        self.new_deadline_today.clicked.connect(self.set_new_deadline_today)
        self.new_deadline_clear = QPushButton("Очистити")
        self.new_deadline_clear.clicked.connect(self.clear_new_deadline)
        drow = QHBoxLayout()
        drow.addWidget(self.new_deadline_input)
        drow.addWidget(self.new_deadline_today)
        drow.addWidget(self.new_deadline_clear)

        self.new_reminder_input = QDateTimeEdit()
        self.new_reminder_input.setCalendarPopup(True)
        self.new_reminder_input.setDateTime(QDateTime.currentDateTime())
        self.new_reminder_input.dateTimeChanged.connect(lambda _dt: self._set_new_reminder_active(True))
        self.new_reminder_today = QPushButton("Сьогодні")
        self.new_reminder_today.clicked.connect(self.set_new_reminder_now)
        self.new_reminder_clear = QPushButton("Очистити")
        self.new_reminder_clear.clicked.connect(self.clear_new_reminder)
        rrow = QHBoxLayout()
        rrow.addWidget(self.new_reminder_input)
        rrow.addWidget(self.new_reminder_today)
        rrow.addWidget(self.new_reminder_clear)

        self.new_deadline_state = QLabel("Не задано")
        self.new_reminder_state = QLabel("Не задано")
        self.new_deadline_state.setObjectName("mutedLabel")
        self.new_reminder_state.setObjectName("mutedLabel")

        form.addRow("Назва", self.new_title_input)
        form.addRow("Опис", self.new_description_input)
        form.addRow("Тег", self.new_tag_input)
        form.addRow("Пріоритет", self.new_priority_combo)
        form.addRow("Дедлайн", drow)
        form.addRow("Стан дедлайну", self.new_deadline_state)
        form.addRow("Нагадування", rrow)
        form.addRow("Стан нагадування", self.new_reminder_state)

        btn_create = QPushButton("Створити")
        btn_create.clicked.connect(self.handle_add_task)

        gl = QVBoxLayout()
        gl.addLayout(form)
        gl.addWidget(btn_create)
        group.setLayout(gl)

        layout.addWidget(group)
        layout.addStretch()
        page.setLayout(layout)
        return page

    # Logic
    def _start_reminder_timer(self) -> None:
        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(30_000)
        self.reminder_timer.timeout.connect(self.check_due_reminders)
        self.reminder_timer.start()
        self.check_due_reminders()

    def check_due_reminders(self) -> None:
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M")
        for task in get_due_reminders(now_iso):
            msg = "Час виконати задачу."
            if task["description"]:
                msg = f"Час виконати задачу: {task['description'][:80]}"
            if send_desktop_notification(task["title"], msg):
                mark_reminder_shown(task["id"])

    def handle_test_notification(self) -> None:
        send_desktop_notification("Test notification", "Це тестове сповіщення з застосунку")

    def on_filter_tab_changed(self, index: int) -> None:
        mapping = ["all", "today", "overdue", "no_deadline", "done"]
        if 0 <= index < len(mapping):
            self.active_filter = mapping[index]
            self.load_tasks()

    def _refresh_tag_filter_options(self, tasks: list[dict]) -> None:
        current = self.tag_filter_combo.currentText()
        tags = sorted({t["tag"] for t in tasks if t.get("tag")})
        self.tag_filter_combo.blockSignals(True)
        self.tag_filter_combo.clear()
        self.tag_filter_combo.addItem("all_tags")
        self.tag_filter_combo.addItems(tags)
        self.tag_filter_combo.setCurrentText(current if current in ["all_tags", *tags] else "all_tags")
        self.tag_filter_combo.blockSignals(False)

    def _effective_status(self, task: dict) -> str:
        status = task.get("status") or STATUS_NEW
        if status in {STATUS_DONE, STATUS_CANCELLED}:
            return status
        deadline = task.get("deadline")
        if deadline and deadline < QDate.currentDate().toString("yyyy-MM-dd"):
            return STATUS_OVERDUE
        return status

    def _apply_filter(self, tasks: list[dict]) -> list[dict]:
        today = QDate.currentDate().toString("yyyy-MM-dd")
        status_filter = self.status_filter_combo.currentText()
        tag_filter = self.tag_filter_combo.currentText()

        out = tasks
        if self.active_filter == "done":
            out = [t for t in out if self._effective_status(t) == STATUS_DONE]
        elif self.active_filter == "today":
            out = [t for t in out if t.get("deadline") == today]
        elif self.active_filter == "no_deadline":
            out = [t for t in out if not t.get("deadline")]
        elif self.active_filter == "overdue":
            out = [t for t in out if self._effective_status(t) == STATUS_OVERDUE]

        if status_filter != "all_statuses":
            out = [t for t in out if self._effective_status(t) == status_filter]
        if tag_filter != "all_tags":
            out = [t for t in out if t.get("tag") == tag_filter]
        return out

    def load_tasks(self, select_task_id: int | None = None) -> None:
        all_tasks = get_tasks()
        self._refresh_tag_filter_options(all_tasks)
        tasks = self._apply_filter(all_tasks)

        self.tasks_list.clear()
        for task in tasks:
            status = self._effective_status(task)
            text = task["title"]
            if task.get("tag"):
                text = f"[{task['tag']}] {text}"
            item = QListWidgetItem(f"{text} · {status}")
            item.setData(Qt.ItemDataRole.UserRole, task["id"])
            self._style_task_item(item, task, status)
            self.tasks_list.addItem(item)

        if self.tasks_list.count() > 0:
            if select_task_id is not None:
                for i in range(self.tasks_list.count()):
                    if self.tasks_list.item(i).data(Qt.ItemDataRole.UserRole) == select_task_id:
                        self.tasks_list.setCurrentRow(i)
                        break
            else:
                self.tasks_list.setCurrentRow(0)

        self.refresh_calendar_visuals()

    def on_task_selected(self, current: QListWidgetItem | None) -> None:
        if current is None:
            return
        task_id = current.data(Qt.ItemDataRole.UserRole)
        self.show_task_popover(task_id)

    def show_task_popover(self, task_id: int) -> None:
        task = get_task_by_id(task_id)
        if task is None:
            return

        self.current_task_id = task_id
        self.pop_title.setText(task["title"] or "—")
        self.pop_desc.setText(task.get("description") or "—")
        self.pop_tag.setText(task.get("tag") or "—")
        self.pop_status.setText(self._effective_status(task))
        self.pop_priority.setText(task.get("priority") or "—")
        self.pop_deadline.setText(task.get("deadline") or "—")
        self.pop_reminder.setText(task.get("reminder_at") or "—")
        self.pop_created.setText(self._format_datetime(task.get("created_at")))
        self.popover.setVisible(True)
        self.right_stack.setCurrentIndex(self.PAGE_CALENDAR)

    def open_edit_for_current_task(self) -> None:
        if self.current_task_id is None:
            return
        task = get_task_by_id(self.current_task_id)
        if task is None:
            return

        self.right_stack.setCurrentIndex(self.PAGE_NEW)
        # use new task page as quick editor seed
        self.new_title_input.setText(task.get("title") or "")
        self.new_description_input.setPlainText(task.get("description") or "")
        self.new_tag_input.setText(task.get("tag") or "")
        self.new_priority_combo.setCurrentText(task.get("priority") or "normal")

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
        self.show_task_popover(task_id)

    def handle_save_task(self) -> None:
        if self.current_task_id is None:
            return
        task = get_task_by_id(self.current_task_id)
        if task is None:
            return

        update_task(
            task_id=self.current_task_id,
            title=task["title"],
            description=task.get("description"),
            tag=task.get("tag"),
            status=task.get("status") or STATUS_NEW,
            priority=task.get("priority") or "normal",
            deadline=task.get("deadline"),
            reminder_at=task.get("reminder_at"),
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
        self.popover.setVisible(False)
        self.load_tasks()

    # Calendar rendering
    def set_calendar_mode(self, mode: int) -> None:
        self.calendar_stack.setCurrentIndex(mode)
        self.btn_week.setChecked(mode == self.CAL_WEEK)
        self.btn_month.setChecked(mode == self.CAL_MONTH)
        self.btn_back.setVisible(mode == self.CAL_DAY)
        self.refresh_calendar_visuals()

    def calendar_go_today(self) -> None:
        today = QDate.currentDate()
        self.current_month_anchor = today
        self.current_week_anchor = today
        self.day_plan_date = today
        self.refresh_calendar_visuals()

    def on_month_cell_clicked(self, row: int, col: int) -> None:
        key = f"{row}:{col}"
        day_tasks = self.month_day_task_map.get(key, [])
        if day_tasks:
            self.show_task_popover(day_tasks[0]["id"])

    def on_month_cell_double_clicked(self, row: int, col: int) -> None:
        key = f"{row}:{col}"
        day_tasks = self.month_day_task_map.get(key, [])
        if day_tasks:
            day = day_tasks[0].get("deadline")
            if day:
                self.day_plan_date = QDate.fromString(day, "yyyy-MM-dd")
        self.set_calendar_mode(self.CAL_DAY)

    def on_week_cell_clicked(self, _row: int, col: int) -> None:
        key = str(col)
        day_tasks = self.week_day_task_map.get(key, [])
        if day_tasks:
            self.show_task_popover(day_tasks[0]["id"])

    def on_week_cell_double_clicked(self, _row: int, col: int) -> None:
        start = self._start_of_week(self.current_week_anchor)
        self.day_plan_date = start.addDays(col)
        self.set_calendar_mode(self.CAL_DAY)

    def back_from_day_plan(self) -> None:
        self.set_calendar_mode(self.CAL_MONTH)

    def _start_of_week(self, date: QDate) -> QDate:
        return date.addDays(-(date.dayOfWeek() - 1))

    def refresh_calendar_visuals(self) -> None:
        mode = self.calendar_stack.currentIndex()
        if mode == self.CAL_MONTH:
            self.refresh_month_view()
        elif mode == self.CAL_WEEK:
            self.refresh_week_view()
        else:
            self.refresh_day_plan()

    def refresh_month_view(self) -> None:
        self.calendar_title.setText(self.current_month_anchor.toString("MMMM yyyy"))
        self.month_table.setColumnCount(7)
        self.month_table.setRowCount(6)
        self.month_day_task_map.clear()

        headers = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
        for i, h in enumerate(headers):
            self.month_table.setHorizontalHeaderItem(i, QTableWidgetItem(h))

        first_day = QDate(self.current_month_anchor.year(), self.current_month_anchor.month(), 1)
        start = first_day.addDays(-(first_day.dayOfWeek() - 1))
        all_tasks = get_tasks()

        for r in range(6):
            for c in range(7):
                day = start.addDays(r * 7 + c)
                day_str = day.toString("yyyy-MM-dd")
                tasks = [t for t in all_tasks if t.get("deadline") == day_str]
                self.month_day_task_map[f"{r}:{c}"] = tasks

                lines = [day.toString("d")]
                for t in tasks[:3]:
                    lines.append(f"• {t['title'][:18]}")
                if len(tasks) > 3:
                    lines.append(f"+{len(tasks)-3} ще")

                item = QTableWidgetItem("\n".join(lines))
                if day == QDate.currentDate():
                    item.setBackground(QColor("#314a72"))
                if any(self._effective_status(t) == STATUS_OVERDUE for t in tasks):
                    item.setForeground(QColor("#ff7b7b"))
                elif tasks and all(self._effective_status(t) in {STATUS_DONE, STATUS_CANCELLED} for t in tasks):
                    item.setForeground(QColor("#8aa08a"))

                self.month_table.setItem(r, c, item)

    def refresh_week_view(self) -> None:
        start = self._start_of_week(self.current_week_anchor)
        self.calendar_title.setText(f"Тиждень: {start.toString('dd MMM')} - {start.addDays(6).toString('dd MMM')}")

        self.week_table.setColumnCount(7)
        self.week_table.setRowCount(1)
        self.week_day_task_map.clear()

        all_tasks = get_tasks()
        for c in range(7):
            day = start.addDays(c)
            day_str = day.toString("yyyy-MM-dd")
            self.week_table.setHorizontalHeaderItem(c, QTableWidgetItem(day.toString("dd MMM")))
            tasks = [t for t in all_tasks if t.get("deadline") == day_str]
            self.week_day_task_map[str(c)] = tasks

            lines = []
            for t in tasks[:4]:
                time_part = t.get("reminder_at", "")
                if time_part:
                    time_part = time_part[-5:]
                chip = f"• {t['title'][:18]}"
                if time_part:
                    chip += f" ({time_part})"
                lines.append(chip)
            if len(tasks) > 4:
                lines.append(f"+{len(tasks)-4} ще")

            cell = QTableWidgetItem("\n".join(lines))
            if any(self._effective_status(t) == STATUS_OVERDUE for t in tasks):
                cell.setForeground(QColor("#ff7b7b"))
            elif tasks and all(self._effective_status(t) in {STATUS_DONE, STATUS_CANCELLED} for t in tasks):
                cell.setForeground(QColor("#8aa08a"))
            self.week_table.setItem(0, c, cell)

    def refresh_day_plan(self) -> None:
        self.calendar_title.setText(f"План дня: {self.day_plan_date.toString('dd MMM yyyy')}")
        self.day_plan_list.clear()
        day_str = self.day_plan_date.toString("yyyy-MM-dd")
        tasks = [t for t in get_tasks() if t.get("deadline") == day_str]
        for task in tasks:
            status = self._effective_status(task)
            item = QListWidgetItem(f"{task['title']} · {status}")
            self._style_task_item(item, task, status)
            item.setData(Qt.ItemDataRole.UserRole, task["id"])
            self.day_plan_list.addItem(item)

    def on_day_plan_item_clicked(self, item: QListWidgetItem) -> None:
        task_id = item.data(Qt.ItemDataRole.UserRole)
        if task_id:
            self.show_task_popover(task_id)

    # Date controls for new task
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

    # detail helpers
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

    def _style_task_item(self, item: QListWidgetItem, task: dict, effective_status: str) -> None:
        if effective_status == STATUS_OVERDUE:
            item.setForeground(QColor("#ff7b7b"))
            return
        if effective_status in {STATUS_DONE, STATUS_CANCELLED}:
            item.setForeground(QColor("#8aa08a"))
            return
        priority = task.get("priority", "normal")
        if priority == "high":
            item.setForeground(QColor("#ffb3b3"))
        elif priority == "low":
            item.setForeground(QColor("#a0a7b0"))

    def _format_datetime(self, value: str | None) -> str:
        if not value:
            return "—"
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value

    def _dark_stylesheet(self) -> str:
        return """
        QMainWindow { background-color: #171a1f; }
        QLabel, QGroupBox { color: #E8EDF2; }
        QLabel#titleLabel { font-size: 24px; font-weight: 700; }
        QLabel#cardTitle { font-size: 18px; font-weight: 600; }
        QLabel#mutedLabel { color: #98A7B5; }
        QFrame#taskPopover {
            background: #20252b;
            border: 1px solid #2e353d;
            border-radius: 14px;
            padding: 10px;
        }
        QGroupBox {
            border: 1px solid #2e353d;
            border-radius: 12px;
            padding: 10px;
        }
        QLineEdit, QTextEdit, QDateEdit, QDateTimeEdit, QComboBox, QListWidget, QTabBar::tab, QTableWidget {
            background: #20252b;
            border: 1px solid #333b44;
            border-radius: 10px;
            color: #E8EDF2;
            padding: 6px;
        }
        QTabBar::tab:selected { background: #3f6bb5; color: white; }
        QPushButton {
            background: #3f6bb5;
            color: white;
            border: none;
            border-radius: 10px;
            padding: 7px 10px;
        }
        QPushButton:hover { background: #4d79c2; }
        QPushButton#dangerButton { background: #b74a4a; }
        QListWidget::item { padding: 8px 6px; }
        QListWidget::item:selected { background: #2e425f; }
        """

    def _light_stylesheet(self) -> str:
        return """
        QMainWindow { background-color: #f3f5f7; }
        QLabel, QGroupBox { color: #1e242b; }
        QLabel#titleLabel { font-size: 24px; font-weight: 700; }
        QLabel#cardTitle { font-size: 18px; font-weight: 600; }
        QLabel#mutedLabel { color: #6a7581; }
        QFrame#taskPopover {
            background: #ffffff;
            border: 1px solid #d5dde5;
            border-radius: 14px;
            padding: 10px;
        }
        QGroupBox {
            border: 1px solid #d5dde5;
            border-radius: 12px;
            padding: 10px;
        }
        QLineEdit, QTextEdit, QDateEdit, QDateTimeEdit, QComboBox, QListWidget, QTabBar::tab, QTableWidget {
            background: #ffffff;
            border: 1px solid #d0d9e2;
            border-radius: 10px;
            color: #1e242b;
            padding: 6px;
        }
        QTabBar::tab:selected { background: #3f6bb5; color: white; }
        QPushButton {
            background: #3f6bb5;
            color: white;
            border: none;
            border-radius: 10px;
            padding: 7px 10px;
        }
        QPushButton:hover { background: #4d79c2; }
        QPushButton#dangerButton { background: #b74a4a; }
        QListWidget::item { padding: 8px 6px; }
        QListWidget::item:selected { background: #d8e6f8; }
        """
