import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from datetime import datetime

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

        self.calendar_placeholder = Gtk.Label(
            label="Calendar view (наступний етап міграції).\nШвидкі деталі задачі доступні через popover у списку зліва."
        )
        self.calendar_placeholder.set_wrap(True)

        self.new_task_page = self._build_new_task_page()

        self.edit_page = self._build_edit_page()
        self.task_view_page = self._build_task_view_page()

        self.mode_stack.add_titled(self.calendar_placeholder, "calendar", "Calendar")
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

    def _build_task_popover(self, task: dict, row: Gtk.ListBoxRow) -> Gtk.Popover:
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
        popover.set_parent(row)
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

        title = Gtk.Label(label="Редагування задачі")
        title.set_xalign(0)
        title.add_css_class("panel-title")

        self.edit_task_info = Gtk.Label(label="Оберіть задачу")
        self.edit_task_info.set_xalign(0)

        grid = Gtk.Grid(column_spacing=8, row_spacing=8)

        self.edit_title = Gtk.Entry()
        self.edit_description = Gtk.TextView()
        self.edit_description.set_vexpand(True)
        self.edit_description.set_size_request(-1, 120)
        self.edit_tag = Gtk.Entry()

        self.edit_status_model = Gtk.StringList.new([
            STATUS_NEW,
            STATUS_IN_PROGRESS,
            STATUS_DONE,
            STATUS_CANCELLED,
        ])
        self.edit_status = Gtk.DropDown(model=self.edit_status_model)

        self.edit_priority_model = Gtk.StringList.new(["low", "normal", "high"])
        self.edit_priority = Gtk.DropDown(model=self.edit_priority_model)
        self.edit_priority.set_selected(1)

        self.edit_deadline = Gtk.Entry()
        self.edit_deadline.set_placeholder_text("YYYY-MM-DD")
        self.edit_reminder = Gtk.Entry()
        self.edit_reminder.set_placeholder_text("YYYY-MM-DDTHH:MM")

        rows: list[tuple[str, Gtk.Widget]] = [
            ("Назва", self.edit_title),
            ("Опис", self.edit_description),
            ("Тег", self.edit_tag),
            ("Статус", self.edit_status),
            ("Пріоритет", self.edit_priority),
            ("Дедлайн", self.edit_deadline),
            ("Нагадування", self.edit_reminder),
        ]

        for i, (label_text, widget) in enumerate(rows):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            grid.attach(label, 0, i, 1, 1)
            grid.attach(widget, 1, i, 1, 1)

        self.edit_save_button = Gtk.Button(label="Зберегти зміни")
        self.edit_save_button.connect("clicked", self._on_save_edit_clicked)

        container.append(title)
        container.append(self.edit_task_info)
        container.append(grid)
        container.append(self.edit_save_button)
        return container

    def _load_tasks(self) -> None:
        self.all_tasks = get_tasks()
        self._refresh_tag_filter_options()
        self._apply_filters_and_render()

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

    def _show_task_popover(self, row: Gtk.ListBoxRow, task: dict) -> None:
        self._dismiss_context_popover()
        self._dismiss_task_popover()
        popover = self._build_task_popover(task, row)
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
            task = self._task_by_id(task_id)
            if row and task:
                self.tasks_listbox.select_row(row)
                self._show_task_popover(row, task)

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
        task = self._task_by_id(task_id)
        if row and task:
            self.tasks_listbox.select_row(row)
            self._show_task_popover(row, task)

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
        task = self._task_by_id(task_id)
        if row and task:
            self.tasks_listbox.select_row(row)
            self._show_task_popover(row, task)
            self.mode_stack.set_visible_child_name("calendar")

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
