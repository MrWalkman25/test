import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from datetime import datetime

from gi.repository import Adw, Gdk, Gtk

from app.database import (
    STATUS_CANCELLED,
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    STATUS_NEW,
    STATUS_OVERDUE,
    get_tasks,
)


class TaskManagerGtkWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Local Task Manager (GTK Migration)")
        self.set_default_size(1200, 760)

        self.all_tasks: list[dict] = []
        self.filtered_tasks: list[dict] = []
        self.selected_task_id: int | None = None

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

        # Left panel
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        left.set_size_request(320, -1)
        left.add_css_class("section")

        left_title = Gtk.Label(label="Tasks")
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

        # Right area
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right.add_css_class("section")

        right_title = Gtk.Label(label="Workspace")
        right_title.set_xalign(0)
        right_title.add_css_class("panel-title")

        self.mode_stack = Gtk.Stack()
        self.mode_stack.set_hexpand(True)
        self.mode_stack.set_vexpand(True)

        self.calendar_placeholder = Gtk.Label(label="Calendar view (наступний етап міграції)")

        self.details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.details_title = Gtk.Label(label="Details")
        self.details_title.set_xalign(0)
        self.details_title.add_css_class("panel-title")
        self.details_content = Gtk.Label(label="Оберіть задачу у списку зліва")
        self.details_content.set_xalign(0)
        self.details_content.set_wrap(True)
        self.details_box.append(self.details_title)
        self.details_box.append(self.details_content)

        self.new_task_placeholder = Gtk.Label(label="New task view (placeholder на цьому етапі)")

        self.mode_stack.add_titled(self.calendar_placeholder, "calendar", "Calendar")
        self.mode_stack.add_titled(self.details_box, "details", "Details")
        self.mode_stack.add_titled(self.new_task_placeholder, "new", "New Task")

        stack_switcher = Gtk.StackSwitcher(stack=self.mode_stack)

        right.append(right_title)
        right.append(stack_switcher)
        right.append(self.mode_stack)

        content.append(left)
        content.append(right)

        root.append(content)
        self.set_content(root)

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

            self.tasks_listbox.append(row)

            if self.selected_task_id is not None and task["id"] == self.selected_task_id:
                selected_row_index = i

        if selected_row_index is not None:
            row = self.tasks_listbox.get_row_at_index(selected_row_index)
            if row:
                self.tasks_listbox.select_row(row)

    def _on_row_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            self.selected_task_id = None
            self.details_content.set_text("Оберіть задачу у списку зліва")
            return

        task_id = getattr(row, "task_id", None)
        self.selected_task_id = task_id

        selected_task = next((t for t in self.filtered_tasks if t["id"] == task_id), None)
        if selected_task is None:
            self.details_content.set_text("Задачу не знайдено")
            return

        self.mode_stack.set_visible_child_name("details")

        details_text = (
            f"Назва: {selected_task.get('title') or '—'}\n"
            f"Статус: {self._effective_status(selected_task)}\n"
            f"Тег: {selected_task.get('tag') or '—'}\n"
            f"Пріоритет: {selected_task.get('priority') or '—'}\n"
            f"Дедлайн: {selected_task.get('deadline') or '—'}"
        )
        self.details_content.set_text(details_text)

    def _on_new_task_clicked(self, _button: Gtk.Button) -> None:
        self.mode_stack.set_visible_child_name("new")
