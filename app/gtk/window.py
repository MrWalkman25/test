import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

import calendar as pycalendar
from datetime import date, datetime, timedelta

from gi.repository import Adw, Gdk, GLib, Gtk

from app.database import (
    STATUS_CANCELLED,
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    STATUS_NEW,
    STATUS_OVERDUE,
    add_task,
    delete_task,
    get_task_by_id,
    get_tasks,
    update_task,
)


class TaskManagerGtkWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Local Task Manager (GTK Migration)")
        self.set_default_size(1200, 760)

        self.all_tasks: list[dict] = []
        self.filtered_tasks: list[dict] = []
        self.selected_task_id: int | None = None
        self.pending_single_click_source: int | None = None
        self.pending_single_click_row: Gtk.ListBoxRow | None = None
        self.active_context_popover: Gtk.Popover | None = None
        self.active_task_popover: Gtk.Popover | None = None

        self._setup_css()
        self._build_ui()
        self._load_tasks()

    def _setup_css(self) -> None:
        css = """
        .section {
            border-radius: 14px;
            padding: 12px;
            background: alpha(@window_fg_color, 0.04);
        }
        .panel-title {
            font-size: 15px;
            font-weight: 700;
        }
        .task-title {
            font-weight: 600;
        }
        .task-meta {
            opacity: 0.75;
            font-size: 12px;
        }
        .popover-card {
            padding: 12px;
            min-width: 300px;
        }
        .popover-title {
            font-weight: 700;
            font-size: 15px;
        }
        .popover-row {
            font-size: 12px;
            opacity: 0.9;
        }
        .overdue-text {
            color: #d14b4b;
        }
        .muted-text {
            color: #7a8793;
        }
        .calendar-chip {
            border-radius: 8px;
            padding: 3px 6px;
            font-size: 11px;
        }
        .chip-overdue {
            background: alpha(#d14b4b, 0.18);
            color: #d14b4b;
        }
        .chip-muted {
            background: alpha(#7a8793, 0.16);
            color: #7a8793;
        }
        .chip-active {
            background: alpha(#4e8ad9, 0.16);
            color: #4e8ad9;
        }
        .chip-new {
            background: alpha(#67a26d, 0.16);
            color: #4f8c55;
        }
        .calendar-day-box {
            border-radius: 10px;
            padding: 8px;
            background: alpha(@window_fg_color, 0.03);
        }
        .calendar-day-title {
            font-weight: 600;
            opacity: 0.85;
        }
        .mode-button-active {
            background: alpha(#4e8ad9, 0.2);
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build_ui(self) -> None:
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label="GTK4 + libadwaita migration"))

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.append(header)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        left.set_size_request(340, -1)
        left.add_css_class("section")

        left_title = Gtk.Label(label="Задачі")
        left_title.set_xalign(0)
        left_title.add_css_class("panel-title")

        filters_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.status_model = Gtk.StringList.new([
            "усі",
            STATUS_NEW,
            STATUS_IN_PROGRESS,
            STATUS_DONE,
            STATUS_CANCELLED,
            STATUS_OVERDUE,
        ])
        self.status_filter = Gtk.DropDown(model=self.status_model)
        self.status_filter.set_selected(0)
        self.status_filter.connect("notify::selected", self._on_filter_changed)

        self.tag_model = Gtk.StringList.new(["усі теги"])
        self.tag_filter = Gtk.DropDown(model=self.tag_model)
        self.tag_filter.set_selected(0)
        self.tag_filter.connect("notify::selected", self._on_filter_changed)

        filters_row.append(Gtk.Label(label="Статус"))
        filters_row.append(self.status_filter)
        filters_row.append(Gtk.Label(label="Тег"))
        filters_row.append(self.tag_filter)

        self.new_task_button = Gtk.Button(label="+ Нова задача")
        self.new_task_button.set_halign(Gtk.Align.FILL)
        self.new_task_button.connect("clicked", self._on_new_task_clicked)

        self.tasks_listbox = Gtk.ListBox()
        self.tasks_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.tasks_listbox.connect("row-selected", self._on_row_selected)

        left.append(left_title)
        left.append(filters_row)
        left.append(self.new_task_button)
        left.append(self.tasks_listbox)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right.add_css_class("section")

        right_title = Gtk.Label(label="Workspace")
        right_title.set_xalign(0)
        right_title.add_css_class("panel-title")

        self.mode_stack = Gtk.Stack()
        self.mode_stack.set_hexpand(True)
        self.mode_stack.set_vexpand(True)

        self.calendar_mode: str = "month"
        self.calendar_focus_date = date.today()
        self.day_plan_date: date | None = None
        self.calendar_page = self._build_calendar_page()

        self.new_task_page = self._build_new_task_page()

        self.edit_page = self._build_edit_page()
        self.task_view_page = self._build_task_view_page()

        self.mode_stack.add_titled(self.calendar_page, "calendar", "Calendar")
        self.mode_stack.add_titled(self.task_view_page, "task", "Task View")
        self.mode_stack.add_titled(self.edit_page, "edit", "Edit Task")
        self.mode_stack.add_titled(self.new_task_page, "new", "New Task")

        stack_switcher = Gtk.StackSwitcher(stack=self.mode_stack)

        right.append(right_title)
        right.append(stack_switcher)
        right.append(self.mode_stack)

        content.append(left)
        content.append(right)

        root.append(content)
        self.set_content(root)

    def _build_task_popover(self, task: dict, anchor_widget: Gtk.Widget) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.set_autohide(True)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("popover-card")

        pop_title = Gtk.Label(label=task.get("title") or "—")
        pop_title.set_xalign(0)
        pop_title.add_css_class("popover-title")

        pop_description = Gtk.Label(label=f"Опис: {self._fmt(task.get('description'))}")
        pop_description.set_xalign(0)
        pop_description.set_wrap(True)

        pop_tag = Gtk.Label(label=f"Тег: {self._fmt(task.get('tag'))}")
        pop_status = Gtk.Label(label=f"Статус: {self._effective_status(task)}")
        pop_priority = Gtk.Label(label=f"Пріоритет: {self._fmt(task.get('priority'))}")
        pop_deadline = Gtk.Label(label=f"Дедлайн: {self._fmt(task.get('deadline'))}")
        pop_reminder = Gtk.Label(label=f"Нагадування: {self._fmt(task.get('reminder_at'))}")
        pop_created = Gtk.Label(label=f"Створено: {self._fmt(task.get('created_at'))}")

        for field in [
            pop_tag,
            pop_status,
            pop_priority,
            pop_deadline,
            pop_reminder,
            pop_created,
        ]:
            field.set_xalign(0)
            field.add_css_class("popover-row")

        open_button = Gtk.Button(label="Відкрити")
        open_button.connect("clicked", self._on_popover_open_clicked, task["id"], popover)

        edit_button = Gtk.Button(label="Редагувати")
        edit_button.connect("clicked", self._on_popover_edit_clicked, task["id"], popover)

        card.append(pop_title)
        card.append(pop_description)
        card.append(Gtk.Separator())
        card.append(pop_tag)
        card.append(pop_status)
        card.append(pop_priority)
        card.append(pop_deadline)
        card.append(pop_reminder)
        card.append(pop_created)
        card.append(open_button)
        card.append(edit_button)

        popover.set_child(card)
        popover.set_parent(anchor_widget)
        popover.connect("closed", self._on_task_popover_closed, popover)
        return popover

    def _build_context_popover(self, task_id: int) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.set_autohide(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.add_css_class("popover-card")

        actions: list[tuple[str, str]] = [
            ("Відкрити", "open"),
            ("Редагувати", "edit"),
            ("Видалити", "delete"),
            ('Позначити як "В процесі"', "set_in_progress"),
            ('Позначити як "Завершене"', "set_done"),
            ('Позначити як "Відмінене"', "set_cancelled"),
        ]

        for label, action in actions:
            button = Gtk.Button(label=label)
            button.set_halign(Gtk.Align.FILL)
            button.connect("clicked", self._on_context_action_clicked, action, task_id, popover)
            box.append(button)

        popover.set_child(box)
        return popover

    def _build_calendar_page(self) -> Gtk.Box:
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        container.set_hexpand(True)
        container.set_vexpand(True)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        controls.set_halign(Gtk.Align.FILL)

        self.calendar_month_button = Gtk.Button(label="Місяць")
        self.calendar_week_button = Gtk.Button(label="Тиждень")
        self.calendar_today_mode_button = Gtk.Button(label="Сьогодні")

        self.calendar_month_button.connect("clicked", self._on_calendar_mode_clicked, "month")
        self.calendar_week_button.connect("clicked", self._on_calendar_mode_clicked, "week")
        self.calendar_today_mode_button.connect("clicked", self._on_calendar_mode_clicked, "today")

        self.calendar_prev_button = Gtk.Button(label="←")
        self.calendar_next_button = Gtk.Button(label="→")
        self.calendar_prev_button.connect("clicked", self._on_calendar_shift_clicked, -1)
        self.calendar_next_button.connect("clicked", self._on_calendar_shift_clicked, 1)

        self.calendar_jump_today_button = Gtk.Button(label="Сьогодні")
        self.calendar_jump_today_button.connect("clicked", self._on_calendar_jump_today_clicked)

        self.calendar_back_button = Gtk.Button(label="Назад")
        self.calendar_back_button.connect("clicked", self._on_calendar_back_clicked)
        self.calendar_back_button.set_visible(False)

        self.calendar_title = Gtk.Label()
        self.calendar_title.set_xalign(0)
        self.calendar_title.add_css_class("panel-title")
        self.calendar_title.set_hexpand(True)

        controls.append(self.calendar_month_button)
        controls.append(self.calendar_week_button)
        controls.append(self.calendar_today_mode_button)
        controls.append(self.calendar_prev_button)
        controls.append(self.calendar_next_button)
        controls.append(self.calendar_jump_today_button)
        controls.append(self.calendar_back_button)

        self.calendar_scroller = Gtk.ScrolledWindow()
        self.calendar_scroller.set_hexpand(True)
        self.calendar_scroller.set_vexpand(True)
        self.calendar_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.calendar_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.calendar_content.set_margin_top(4)
        self.calendar_content.set_margin_bottom(4)
        self.calendar_content.set_margin_start(4)
        self.calendar_content.set_margin_end(4)
        self.calendar_scroller.set_child(self.calendar_content)

        container.append(controls)
        container.append(self.calendar_title)
        container.append(self.calendar_scroller)
        return container

    def _build_new_task_page(self) -> Gtk.Box:
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        container.set_size_request(520, -1)

        title = Gtk.Label(label="Створення нової задачі")
        title.set_xalign(0)
        title.add_css_class("panel-title")

        self.new_form_error = Gtk.Label()
        self.new_form_error.set_xalign(0)
        self.new_form_error.add_css_class("overdue-text")

        grid = Gtk.Grid(column_spacing=8, row_spacing=8)

        self.new_title = Gtk.Entry()
        self.new_title.set_placeholder_text("Обов'язково")

        self.new_description = Gtk.TextView()
        self.new_description.set_vexpand(True)
        self.new_description.set_size_request(-1, 120)

        self.new_tag = Gtk.Entry()

        self.new_status_model = Gtk.StringList.new([
            STATUS_NEW,
            STATUS_IN_PROGRESS,
            STATUS_DONE,
            STATUS_CANCELLED,
        ])
        self.new_status = Gtk.DropDown(model=self.new_status_model)
        self.new_status.set_selected(0)

        self.new_priority_model = Gtk.StringList.new(["low", "normal", "high"])
        self.new_priority = Gtk.DropDown(model=self.new_priority_model)
        self.new_priority.set_selected(1)

        self.new_deadline_entry = Gtk.Entry()
        self.new_deadline_entry.set_placeholder_text("YYYY-MM-DD")
        deadline_row = self._build_date_input_row(
            self.new_deadline_entry,
            self._on_new_deadline_pick,
            with_now_button=False,
        )

        self.new_reminder_entry = Gtk.Entry()
        self.new_reminder_entry.set_placeholder_text("YYYY-MM-DDTHH:MM")
        reminder_row = self._build_date_input_row(
            self.new_reminder_entry,
            self._on_new_reminder_pick,
            with_now_button=True,
        )

        rows: list[tuple[str, Gtk.Widget]] = [
            ("Назва", self.new_title),
            ("Опис", self.new_description),
            ("Тег", self.new_tag),
            ("Статус", self.new_status),
            ("Пріоритет", self.new_priority),
            ("Дедлайн", deadline_row),
            ("Нагадування", reminder_row),
        ]

        for i, (label_text, widget) in enumerate(rows):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            grid.attach(label, 0, i, 1, 1)
            grid.attach(widget, 1, i, 1, 1)

        self.create_task_button = Gtk.Button(label="Створити задачу")
        self.create_task_button.connect("clicked", self._on_create_task_clicked)

        container.append(title)
        container.append(self.new_form_error)
        container.append(grid)
        container.append(self.create_task_button)
        return container

    def _build_date_input_row(
        self,
        entry: Gtk.Entry,
        pick_callback,
        with_now_button: bool,
    ) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.append(entry)

        pick_button = Gtk.Button(label="Обрати")
        pick_button.connect("clicked", pick_callback)
        row.append(pick_button)

        today_button = Gtk.Button(label="Сьогодні")
        today_button.connect("clicked", self._on_today_clicked, entry, with_now_button)
        row.append(today_button)

        clear_button = Gtk.Button(label="Очистити")
        clear_button.connect("clicked", self._on_clear_date_clicked, entry)
        row.append(clear_button)
        return row

    def _build_task_view_page(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        title = Gtk.Label(label="Повний перегляд задачі")
        title.set_xalign(0)
        title.add_css_class("panel-title")

        self.task_view_title = Gtk.Label()
        self.task_view_title.set_xalign(0)
        self.task_view_title.add_css_class("popover-title")
        self.task_view_description = Gtk.Label()
        self.task_view_description.set_xalign(0)
        self.task_view_description.set_wrap(True)
        self.task_view_tag = Gtk.Label()
        self.task_view_status = Gtk.Label()
        self.task_view_priority = Gtk.Label()
        self.task_view_deadline = Gtk.Label()
        self.task_view_reminder = Gtk.Label()
        self.task_view_created = Gtk.Label()

        for field in [
            self.task_view_tag,
            self.task_view_status,
            self.task_view_priority,
            self.task_view_deadline,
            self.task_view_reminder,
            self.task_view_created,
        ]:
            field.set_xalign(0)

        open_edit = Gtk.Button(label="Редагувати")
        open_edit.connect("clicked", self._on_task_view_edit_clicked)

        box.append(title)
        box.append(self.task_view_title)
        box.append(self.task_view_description)
        box.append(Gtk.Separator())
        box.append(self.task_view_tag)
        box.append(self.task_view_status)
        box.append(self.task_view_priority)
        box.append(self.task_view_deadline)
        box.append(self.task_view_reminder)
        box.append(self.task_view_created)
        box.append(open_edit)
        return box

    def _build_edit_page(self) -> Gtk.Box:
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        container.set_hexpand(True)
        container.set_vexpand(True)

        title = Gtk.Label(label="Редагування задачі")
        title.set_xalign(0)
        title.add_css_class("panel-title")

        self.edit_task_info = Gtk.Label(label="Оберіть задачу")
        self.edit_task_info.set_xalign(0)

        form_scroller = Gtk.ScrolledWindow()
        form_scroller.set_hexpand(True)
        form_scroller.set_vexpand(True)
        form_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        form_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        form_box.set_margin_top(4)
        form_box.set_margin_bottom(4)
        form_box.set_margin_start(4)
        form_box.set_margin_end(4)

        self.edit_title = Gtk.Entry()
        self.edit_title.set_hexpand(True)
        self.edit_description = Gtk.TextView()
        self.edit_description.set_vexpand(True)
        self.edit_description.set_size_request(-1, 180)
        self.edit_tag = Gtk.Entry()
        self.edit_tag.set_hexpand(True)

        self.edit_status_model = Gtk.StringList.new([
            STATUS_NEW,
            STATUS_IN_PROGRESS,
            STATUS_DONE,
            STATUS_CANCELLED,
        ])
        self.edit_status = Gtk.DropDown(model=self.edit_status_model)
        self.edit_status.set_hexpand(True)

        self.edit_priority_model = Gtk.StringList.new(["low", "normal", "high"])
        self.edit_priority = Gtk.DropDown(model=self.edit_priority_model)
        self.edit_priority.set_selected(1)
        self.edit_priority.set_hexpand(True)

        self.edit_deadline = Gtk.Entry()
        self.edit_deadline.set_placeholder_text("YYYY-MM-DD")
        self.edit_deadline.set_hexpand(True)
        self.edit_reminder = Gtk.Entry()
        self.edit_reminder.set_placeholder_text("YYYY-MM-DDTHH:MM")
        self.edit_reminder.set_hexpand(True)

        rows: list[tuple[str, Gtk.Widget]] = [
            ("Назва", self.edit_title),
            ("Опис", self.edit_description),
            ("Тег", self.edit_tag),
            ("Статус", self.edit_status),
            ("Пріоритет", self.edit_priority),
            ("Дедлайн", self.edit_deadline),
            ("Нагадування", self.edit_reminder),
        ]

        for label_text, widget in rows:
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            form_box.append(label)
            form_box.append(widget)

        form_scroller.set_child(form_box)

        self.edit_save_button = Gtk.Button(label="Зберегти зміни")
        self.edit_save_button.connect("clicked", self._on_save_edit_clicked)

        container.append(title)
        container.append(self.edit_task_info)
        container.append(form_scroller)
        container.append(self.edit_save_button)
        return container

    def _load_tasks(self) -> None:
        self.all_tasks = get_tasks()
        self._refresh_tag_filter_options()
        self._apply_filters_and_render()
        self._render_calendar()

    def _render_calendar(self) -> None:
        self._update_calendar_mode_buttons()

        for child in list(self.calendar_content):
            self.calendar_content.remove(child)

        if self.day_plan_date is not None:
            self.calendar_title.set_text(f"План на день: {self.day_plan_date.isoformat()}")
            self.calendar_back_button.set_visible(True)
            self._render_day_plan(self.day_plan_date)
            return

        self.calendar_back_button.set_visible(False)
        if self.calendar_mode == "month":
            self._render_month_view()
        elif self.calendar_mode == "week":
            self._render_week_view()
        else:
            self._render_today_view()

    def _update_calendar_mode_buttons(self) -> None:
        buttons = [
            (self.calendar_month_button, "month"),
            (self.calendar_week_button, "week"),
            (self.calendar_today_mode_button, "today"),
        ]
        for button, mode in buttons:
            if mode == self.calendar_mode and self.day_plan_date is None:
                button.add_css_class("mode-button-active")
            else:
                button.remove_css_class("mode-button-active")

    def _on_calendar_mode_clicked(self, _button: Gtk.Button, mode: str) -> None:
        self.day_plan_date = None
        self.calendar_mode = mode
        if mode == "today":
            self.calendar_focus_date = date.today()
        self._render_calendar()

    def _on_calendar_shift_clicked(self, _button: Gtk.Button, delta: int) -> None:
        if self.day_plan_date is not None:
            self.day_plan_date = self.day_plan_date + timedelta(days=delta)
            self._render_calendar()
            return

        if self.calendar_mode == "month":
            year = self.calendar_focus_date.year
            month = self.calendar_focus_date.month + delta
            if month < 1:
                year -= 1
                month = 12
            elif month > 12:
                year += 1
                month = 1
            self.calendar_focus_date = self.calendar_focus_date.replace(year=year, month=month, day=1)
        else:
            self.calendar_focus_date = self.calendar_focus_date + timedelta(days=7 * delta)
        self._render_calendar()

    def _on_calendar_jump_today_clicked(self, _button: Gtk.Button) -> None:
        self.calendar_focus_date = date.today()
        self.day_plan_date = None
        self._render_calendar()

    def _on_calendar_back_clicked(self, _button: Gtk.Button) -> None:
        self.day_plan_date = None
        self._render_calendar()

    def _render_month_view(self) -> None:
        self.calendar_title.set_text(self.calendar_focus_date.strftime("%B %Y"))
        grid = Gtk.Grid(column_spacing=6, row_spacing=6)
        grid.set_column_homogeneous(True)

        week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
        for i, wd in enumerate(week_days):
            header = Gtk.Label(label=wd)
            header.add_css_class("calendar-day-title")
            grid.attach(header, i, 0, 1, 1)

        month_matrix = pycalendar.Calendar(firstweekday=0).monthdatescalendar(
            self.calendar_focus_date.year,
            self.calendar_focus_date.month,
        )
        for row_i, week in enumerate(month_matrix, start=1):
            for col_i, day_date in enumerate(week):
                day_widget = self._build_day_cell(day_date, compact=True)
                if day_date.month != self.calendar_focus_date.month:
                    day_widget.set_sensitive(False)
                grid.attach(day_widget, col_i, row_i, 1, 1)

        self.calendar_content.append(grid)

    def _render_week_view(self) -> None:
        week_start = self.calendar_focus_date - timedelta(days=self.calendar_focus_date.weekday())
        week_end = week_start + timedelta(days=6)
        self.calendar_title.set_text(
            f"Тиждень: {week_start.isoformat()} — {week_end.isoformat()}"
        )
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            day_widget = self._build_day_cell(day_date, compact=False)
            day_widget.set_hexpand(True)
            row.append(day_widget)
        self.calendar_content.append(row)

    def _render_today_view(self) -> None:
        today = date.today()
        self.calendar_title.set_text(f"Сьогодні: {today.isoformat()}")
        self.calendar_content.append(self._build_day_cell(today, compact=False))

    def _render_day_plan(self, day_date: date) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        tasks = self._tasks_for_date(day_date)
        if not tasks:
            box.append(Gtk.Label(label="На цей день задач із дедлайном немає"))
        else:
            for task in tasks:
                box.append(self._build_task_chip(task, day_date, emphasize=True))
        self.calendar_content.append(box)

    def _build_day_cell(self, day_date: date, compact: bool) -> Gtk.Box:
        day_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        day_box.add_css_class("calendar-day-box")
        title = Gtk.Label(label=day_date.strftime("%d.%m (%a)"))
        title.set_xalign(0)
        title.add_css_class("calendar-day-title")
        day_box.append(title)

        tasks = self._tasks_for_date(day_date)
        limit = 3 if compact else 8
        for task in tasks[:limit]:
            day_box.append(self._build_task_chip(task, day_date, emphasize=not compact))

        if len(tasks) > limit:
            more = Gtk.Label(label=f"+{len(tasks) - limit} ще")
            more.set_xalign(0)
            more.add_css_class("muted-text")
            day_box.append(more)

        day_double_click = Gtk.GestureClick.new()
        day_double_click.set_button(1)
        day_double_click.connect("released", self._on_day_cell_clicked, day_date)
        day_box.add_controller(day_double_click)
        return day_box

    def _build_task_chip(self, task: dict, day_date: date, emphasize: bool) -> Gtk.Button:
        label_parts = [task.get("title") or "(без назви)"]
        reminder = task.get("reminder_at")
        if reminder and len(reminder) >= 16:
            label_parts.append(reminder[11:16])
        chip = Gtk.Button(label=" • ".join(label_parts))
        chip.set_halign(Gtk.Align.FILL)
        chip.add_css_class("calendar-chip")
        if emphasize:
            chip.set_hexpand(True)
        self._apply_task_chip_style(chip, task)

        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect("released", self._on_calendar_task_clicked, task["id"], chip)
        chip.add_controller(click)
        return chip

    def _on_day_cell_clicked(
        self,
        _gesture: Gtk.GestureClick,
        n_press: int,
        _x: float,
        _y: float,
        day_date: date,
    ) -> None:
        if n_press == 2:
            self.day_plan_date = day_date
            self._render_calendar()

    def _on_calendar_task_clicked(
        self,
        _gesture: Gtk.GestureClick,
        n_press: int,
        _x: float,
        _y: float,
        task_id: int,
        widget: Gtk.Widget,
    ) -> None:
        task = self._task_by_id(task_id)
        if task is None:
            return

        self.selected_task_id = task_id
        row = self._find_row_by_task_id(task_id)
        if row:
            self.tasks_listbox.select_row(row)

        if n_press == 2:
            self._open_full_task_view(task_id)
            return

        if n_press == 1:
            self._show_task_popover(widget, task)

    def _tasks_for_date(self, day_date: date) -> list[dict]:
        return [t for t in self.all_tasks if self._deadline_date(t) == day_date]

    def _deadline_date(self, task: dict) -> date | None:
        deadline = task.get("deadline")
        if not deadline:
            return None
        deadline_str = str(deadline)[:10]
        try:
            return datetime.strptime(deadline_str, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _apply_task_chip_style(self, chip: Gtk.Button, task: dict) -> None:
        status = self._effective_status(task)
        if status == STATUS_OVERDUE:
            chip.add_css_class("chip-overdue")
        elif status in {STATUS_DONE, STATUS_CANCELLED}:
            chip.add_css_class("chip-muted")
        elif status == STATUS_IN_PROGRESS:
            chip.add_css_class("chip-active")
        else:
            chip.add_css_class("chip-new")

    def _refresh_tag_filter_options(self) -> None:
        current_tag = self._get_selected_tag()
        tags = sorted({task["tag"] for task in self.all_tasks if task.get("tag")})

        new_model = Gtk.StringList.new(["усі теги", *tags])
        self.tag_filter.set_model(new_model)
        self.tag_model = new_model

        selected_index = 0
        if current_tag and current_tag in tags:
            selected_index = tags.index(current_tag) + 1
        self.tag_filter.set_selected(selected_index)

    def _on_filter_changed(self, *_args) -> None:
        self._apply_filters_and_render()

    def _get_selected_status(self) -> str:
        idx = self.status_filter.get_selected()
        item = self.status_model.get_string(idx)
        return item or "усі"

    def _get_selected_tag(self) -> str | None:
        idx = self.tag_filter.get_selected()
        item = self.tag_model.get_string(idx)
        if not item or item == "усі теги":
            return None
        return item

    def _effective_status(self, task: dict) -> str:
        status = task.get("status") or STATUS_NEW
        if status in {STATUS_DONE, STATUS_CANCELLED}:
            return status

        deadline = task.get("deadline")
        if deadline and deadline < datetime.now().strftime("%Y-%m-%d"):
            return STATUS_OVERDUE
        return status

    def _apply_filters_and_render(self) -> None:
        status_filter = self._get_selected_status()
        tag_filter = self._get_selected_tag()

        tasks = self.all_tasks

        if status_filter != "усі":
            tasks = [t for t in tasks if self._effective_status(t) == status_filter]

        if tag_filter is not None:
            tasks = [t for t in tasks if t.get("tag") == tag_filter]

        self.filtered_tasks = tasks
        self._render_task_list()

        if self.selected_task_id is not None and not any(
            task["id"] == self.selected_task_id for task in self.filtered_tasks
        ):
            self.selected_task_id = None
            self._dismiss_task_popover()

    def _render_task_list(self) -> None:
        for child in list(self.tasks_listbox):
            self.tasks_listbox.remove(child)

        selected_row_index = None

        for i, task in enumerate(self.filtered_tasks):
            row = Gtk.ListBoxRow()
            row.set_selectable(True)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.set_margin_top(6)
            box.set_margin_bottom(6)
            box.set_margin_start(6)
            box.set_margin_end(6)

            title = Gtk.Label(label=task.get("title") or "(без назви)")
            title.set_xalign(0)
            title.add_css_class("task-title")

            effective_status = self._effective_status(task)
            meta_parts = [effective_status]
            if task.get("tag"):
                meta_parts.append(f"#{task['tag']}")
            if task.get("deadline"):
                meta_parts.append(task["deadline"])

            meta = Gtk.Label(label=" · ".join(meta_parts))
            meta.set_xalign(0)
            meta.add_css_class("task-meta")

            if effective_status == STATUS_OVERDUE:
                title.add_css_class("overdue-text")
                meta.add_css_class("overdue-text")
            elif effective_status in {STATUS_DONE, STATUS_CANCELLED}:
                title.add_css_class("muted-text")
                meta.add_css_class("muted-text")

            box.append(title)
            box.append(meta)
            row.set_child(box)
            row.task_id = task["id"]  # type: ignore[attr-defined]

            right_click = Gtk.GestureClick.new()
            right_click.set_button(3)
            right_click.connect("pressed", self._on_row_right_click, row)
            row.add_controller(right_click)

            left_click = Gtk.GestureClick.new()
            left_click.set_button(1)
            left_click.connect("released", self._on_row_left_click, row)
            row.add_controller(left_click)

            self.tasks_listbox.append(row)

            if self.selected_task_id is not None and task["id"] == self.selected_task_id:
                selected_row_index = i

        if selected_row_index is not None:
            row = self.tasks_listbox.get_row_at_index(selected_row_index)
            if row:
                self.tasks_listbox.select_row(row)

    def _task_by_id(self, task_id: int | None) -> dict | None:
        if task_id is None:
            return None
        return next((t for t in self.all_tasks if t["id"] == task_id), None)

    def _on_row_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            self.selected_task_id = None
            self._dismiss_task_popover()
            return

        task_id = getattr(row, "task_id", None)
        self.selected_task_id = task_id

    def _on_row_left_click(
        self,
        _gesture: Gtk.GestureClick,
        n_press: int,
        _x: float,
        _y: float,
        row: Gtk.ListBoxRow,
    ) -> None:
        self.tasks_listbox.select_row(row)
        task_id = getattr(row, "task_id", None)
        self.selected_task_id = task_id
        self._dismiss_context_popover()

        if n_press == 2:
            self._cancel_pending_single_click()
            self._open_full_task_view(task_id)
            return

        if n_press == 1:
            self._cancel_pending_single_click()
            self.pending_single_click_row = row
            self.pending_single_click_source = GLib.timeout_add(
                200, self._run_single_click_action
            )

    def _cancel_pending_single_click(self) -> None:
        if self.pending_single_click_source is not None:
            GLib.source_remove(self.pending_single_click_source)
            self.pending_single_click_source = None
            self.pending_single_click_row = None

    def _run_single_click_action(self) -> bool:
        row = self.pending_single_click_row
        self.pending_single_click_source = None
        self.pending_single_click_row = None

        if row is None:
            return False

        task_id = getattr(row, "task_id", None)
        task = self._task_by_id(task_id)
        if task is None:
            self._dismiss_task_popover()
            return False

        self._show_task_popover(row, task)
        return False

    def _show_task_popover(self, anchor_widget: Gtk.Widget, task: dict) -> None:
        self._dismiss_context_popover()
        self._dismiss_task_popover()
        popover = self._build_task_popover(task, anchor_widget)
        popover.popup()
        self.active_task_popover = popover

    def _on_popover_edit_clicked(
        self,
        _button: Gtk.Button,
        task_id: int,
        popover: Gtk.Popover,
    ) -> None:
        popover.popdown()
        if self.active_task_popover is popover:
            self.active_task_popover = None
        self._open_edit_mode(task_id)

    def _on_popover_open_clicked(
        self,
        _button: Gtk.Button,
        task_id: int,
        popover: Gtk.Popover,
    ) -> None:
        popover.popdown()
        if self.active_task_popover is popover:
            self.active_task_popover = None
        self._open_full_task_view(task_id)

    def _on_row_right_click(
        self,
        gesture: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
        row: Gtk.ListBoxRow,
    ) -> None:
        self._cancel_pending_single_click()
        self.tasks_listbox.select_row(row)
        task_id = getattr(row, "task_id", None)
        self._dismiss_task_popover()
        self._dismiss_context_popover()

        if task_id is None:
            return

        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1

        popover = self._build_context_popover(task_id)
        popover.set_parent(row)
        popover.set_pointing_to(rect)
        popover.connect("closed", self._on_context_popover_closed, popover)
        popover.popup()
        self.active_context_popover = popover
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def _on_context_action_clicked(
        self,
        _button: Gtk.Button,
        action: str,
        task_id: int,
        popover: Gtk.Popover,
    ) -> None:
        popover.popdown()
        if self.active_context_popover is popover:
            self.active_context_popover = None

        if action == "open":
            self._open_full_task_view(task_id)
            return

        if action == "edit":
            self._open_edit_mode(task_id)
            return

        if action == "delete":
            delete_task(task_id)
            self._after_task_mutation(task_id, deleted=True)
            return

        status_map = {
            "set_in_progress": STATUS_IN_PROGRESS,
            "set_done": STATUS_DONE,
            "set_cancelled": STATUS_CANCELLED,
        }
        new_status = status_map.get(action)
        if new_status is None:
            return

        task = get_task_by_id(task_id)
        if task is None:
            self._after_task_mutation(task_id, deleted=True)
            return

        update_task(
            task_id=task_id,
            title=task.get("title") or "(без назви)",
            description=task.get("description"),
            tag=task.get("tag"),
            status=new_status,
            priority=task.get("priority") or "normal",
            deadline=task.get("deadline"),
            reminder_at=task.get("reminder_at"),
        )
        self._after_task_mutation(task_id, deleted=False)

    def _on_context_popover_closed(self, _popover: Gtk.Popover, popover: Gtk.Popover) -> None:
        if self.active_context_popover is popover:
            self.active_context_popover = None

    def _dismiss_context_popover(self) -> None:
        if self.active_context_popover is not None:
            self.active_context_popover.popdown()
            self.active_context_popover = None

    def _on_task_popover_closed(self, _popover: Gtk.Popover, popover: Gtk.Popover) -> None:
        if self.active_task_popover is popover:
            self.active_task_popover = None

    def _dismiss_task_popover(self) -> None:
        if self.active_task_popover is not None:
            self.active_task_popover.popdown()
            self.active_task_popover = None

    def _after_task_mutation(self, task_id: int, deleted: bool) -> None:
        if deleted and self.selected_task_id == task_id:
            self.selected_task_id = None
            self._dismiss_task_popover()
            self.mode_stack.set_visible_child_name("calendar")

        self._load_tasks()

        if not deleted:
            self.selected_task_id = task_id
            row = self._find_row_by_task_id(task_id)
            if row:
                self.tasks_listbox.select_row(row)

    def _find_row_by_task_id(self, task_id: int) -> Gtk.ListBoxRow | None:
        for row in self.tasks_listbox:
            if getattr(row, "task_id", None) == task_id:
                return row
        return None

    def _open_full_task_view(self, task_id: int | None) -> None:
        task = self._task_by_id(task_id)
        if task is None:
            return

        self.selected_task_id = task["id"]
        self._fill_task_view(task)
        self._dismiss_task_popover()
        self.mode_stack.set_visible_child_name("task")

    def _fill_task_view(self, task: dict) -> None:
        self.task_view_title.set_text(task.get("title") or "—")
        self.task_view_description.set_text(f"Опис: {self._fmt(task.get('description'))}")
        self.task_view_tag.set_text(f"Тег: {self._fmt(task.get('tag'))}")
        self.task_view_status.set_text(f"Статус: {self._effective_status(task)}")
        self.task_view_priority.set_text(f"Пріоритет: {self._fmt(task.get('priority'))}")
        self.task_view_deadline.set_text(f"Дедлайн: {self._fmt(task.get('deadline'))}")
        self.task_view_reminder.set_text(f"Нагадування: {self._fmt(task.get('reminder_at'))}")
        self.task_view_created.set_text(f"Створено: {self._fmt(task.get('created_at'))}")

    def _on_task_view_edit_clicked(self, _button: Gtk.Button) -> None:
        if self.selected_task_id is None:
            return
        self._open_edit_mode(self.selected_task_id)

    def _open_edit_mode(self, task_id: int) -> None:
        task = get_task_by_id(task_id)
        if task is None:
            return

        self.selected_task_id = task_id
        self.edit_task_info.set_text(f"ID: {task_id}")
        self.edit_title.set_text(task.get("title") or "")

        description_buffer = self.edit_description.get_buffer()
        description_buffer.set_text(task.get("description") or "")

        self.edit_tag.set_text(task.get("tag") or "")
        self._set_dropdown_by_text(self.edit_status, self.edit_status_model, task.get("status") or STATUS_NEW)
        self._set_dropdown_by_text(
            self.edit_priority,
            self.edit_priority_model,
            task.get("priority") or "normal",
        )
        self.edit_deadline.set_text(task.get("deadline") or "")
        self.edit_reminder.set_text(task.get("reminder_at") or "")

        self.mode_stack.set_visible_child_name("edit")

    def _set_dropdown_by_text(self, dropdown: Gtk.DropDown, model: Gtk.StringList, value: str) -> None:
        for i in range(model.get_n_items()):
            if model.get_string(i) == value:
                dropdown.set_selected(i)
                return
        dropdown.set_selected(0)

    def _on_save_edit_clicked(self, _button: Gtk.Button) -> None:
        task_id = self.selected_task_id
        if task_id is None:
            return

        description_buffer = self.edit_description.get_buffer()
        start = description_buffer.get_start_iter()
        end = description_buffer.get_end_iter()
        description = description_buffer.get_text(start, end, True).strip()

        title = self.edit_title.get_text().strip() or "(без назви)"
        tag = self.edit_tag.get_text().strip() or None

        status_idx = self.edit_status.get_selected()
        status = self.edit_status_model.get_string(status_idx) or STATUS_NEW

        priority_idx = self.edit_priority.get_selected()
        priority = self.edit_priority_model.get_string(priority_idx) or "normal"

        deadline = self.edit_deadline.get_text().strip() or None
        reminder = self.edit_reminder.get_text().strip() or None

        update_task(
            task_id=task_id,
            title=title,
            description=description or None,
            tag=tag,
            status=status,
            priority=priority,
            deadline=deadline,
            reminder_at=reminder,
        )

        self._load_tasks()
        self.mode_stack.set_visible_child_name("calendar")

        row = self._find_row_by_task_id(task_id)
        if row:
            self.tasks_listbox.select_row(row)
        self._open_full_task_view(task_id)

    def _on_create_task_clicked(self, _button: Gtk.Button) -> None:
        title = self.new_title.get_text().strip()
        if not title:
            self.new_form_error.set_text("Назва задачі є обов'язковою.")
            return

        description_buffer = self.new_description.get_buffer()
        start = description_buffer.get_start_iter()
        end = description_buffer.get_end_iter()
        description = description_buffer.get_text(start, end, True).strip() or None

        tag = self.new_tag.get_text().strip() or None
        status_idx = self.new_status.get_selected()
        status = self.new_status_model.get_string(status_idx) or STATUS_NEW
        priority_idx = self.new_priority.get_selected()
        priority = self.new_priority_model.get_string(priority_idx) or "normal"
        deadline = self.new_deadline_entry.get_text().strip() or None
        reminder = self.new_reminder_entry.get_text().strip() or None

        task_id = add_task(
            title=title,
            description=description,
            tag=tag,
            deadline=deadline,
            reminder_at=reminder,
            priority=priority,
        )

        if status != STATUS_NEW:
            created_task = get_task_by_id(task_id)
            if created_task is not None:
                update_task(
                    task_id=task_id,
                    title=created_task.get("title") or title,
                    description=created_task.get("description"),
                    tag=created_task.get("tag"),
                    status=status,
                    priority=created_task.get("priority") or priority,
                    deadline=created_task.get("deadline"),
                    reminder_at=created_task.get("reminder_at"),
                )

        self.new_form_error.set_text("")
        self._clear_new_task_form()
        self._load_tasks()
        self.selected_task_id = task_id

        row = self._find_row_by_task_id(task_id)
        if row:
            self.tasks_listbox.select_row(row)
        self._open_full_task_view(task_id)

    def _on_new_task_clicked(self, _button: Gtk.Button) -> None:
        self._clear_new_task_form()
        self.new_form_error.set_text("")
        self.mode_stack.set_visible_child_name("new")

    def _clear_new_task_form(self) -> None:
        self.new_title.set_text("")
        self.new_tag.set_text("")
        self.new_deadline_entry.set_text("")
        self.new_reminder_entry.set_text("")
        self.new_status.set_selected(0)
        self.new_priority.set_selected(1)
        description_buffer = self.new_description.get_buffer()
        description_buffer.set_text("")

    def _on_new_deadline_pick(self, button: Gtk.Button) -> None:
        self._show_calendar_picker(button, self.new_deadline_entry, include_time=False)

    def _on_new_reminder_pick(self, button: Gtk.Button) -> None:
        self._show_calendar_picker(button, self.new_reminder_entry, include_time=True)

    def _show_calendar_picker(self, parent: Gtk.Button, entry: Gtk.Entry, include_time: bool) -> None:
        popover = Gtk.Popover()
        popover.set_parent(parent)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.add_css_class("popover-card")

        calendar = Gtk.Calendar()
        box.append(calendar)

        hour = Gtk.SpinButton.new_with_range(0, 23, 1)
        minute = Gtk.SpinButton.new_with_range(0, 59, 1)
        now = datetime.now()
        hour.set_value(now.hour)
        minute.set_value(now.minute)

        if include_time:
            time_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            time_row.append(Gtk.Label(label="Година"))
            time_row.append(hour)
            time_row.append(Gtk.Label(label="Хвилина"))
            time_row.append(minute)
            box.append(time_row)

        apply_button = Gtk.Button(label="Готово")
        apply_button.connect(
            "clicked",
            self._on_picker_apply_clicked,
            calendar,
            entry,
            include_time,
            hour,
            minute,
            popover,
        )
        box.append(apply_button)

        popover.set_child(box)
        popover.popup()

    def _on_picker_apply_clicked(
        self,
        _button: Gtk.Button,
        calendar: Gtk.Calendar,
        entry: Gtk.Entry,
        include_time: bool,
        hour: Gtk.SpinButton,
        minute: Gtk.SpinButton,
        popover: Gtk.Popover,
    ) -> None:
        selected = calendar.get_date()
        date_str = f"{selected.get_year():04d}-{selected.get_month() + 1:02d}-{selected.get_day_of_month():02d}"

        if include_time:
            entry.set_text(f"{date_str}T{int(hour.get_value()):02d}:{int(minute.get_value()):02d}")
        else:
            entry.set_text(date_str)

        popover.popdown()

    def _on_today_clicked(self, _button: Gtk.Button, entry: Gtk.Entry, with_time: bool) -> None:
        now = datetime.now()
        if with_time:
            entry.set_text(now.strftime("%Y-%m-%dT%H:%M"))
        else:
            entry.set_text(now.strftime("%Y-%m-%d"))

    def _on_clear_date_clicked(self, _button: Gtk.Button, entry: Gtk.Entry) -> None:
        entry.set_text("")

    def _fmt(self, value: str | None) -> str:
        return value if value else "—"
