from gi.repository import Gtk, Gdk, GLib, GObject
from app.models import Task, STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_CANCELLED, STATUS_OVERDUE


class TaskListView(Gtk.Box):
    __gsignals__ = {
        "task-selected": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "task-activated": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "task-context-menu": (GObject.SignalFlags.RUN_FIRST, None, (int, float, float)),
        "new-task-clicked": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add_css_class("section")
        self.set_size_request(340, -1)

        self.all_tasks: list[Task] = []
        self.filtered_tasks: list[Task] = []
        self.selected_task_id: int | None = None
        
        self.pending_single_click_source: int | None = None
        self.pending_single_click_row: Gtk.ListBoxRow | None = None
        self._suppress_selection_signal = False # Flag for programmatic selection

        self._build_ui()

    def _build_ui(self):
        title = Gtk.Label(label="Задачі")
        title.set_xalign(0)
        title.add_css_class("panel-title")
        self.append(title)

        # Filters
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
        self.status_filter.connect("notify::selected", self._on_filter_changed)

        self.tag_model = Gtk.StringList.new(["усі теги"])
        self.tag_filter = Gtk.DropDown(model=self.tag_model)
        self.tag_filter.connect("notify::selected", self._on_filter_changed)

        filters_row.append(Gtk.Label(label="Статус"))
        filters_row.append(self.status_filter)
        filters_row.append(Gtk.Label(label="Тег"))
        filters_row.append(self.tag_filter)
        self.append(filters_row)

        # New Task Button
        self.new_task_button = Gtk.Button(label="+ Нова задача")
        self.new_task_button.add_css_class("suggested-action") # Give it some color
        self.new_task_button.connect("clicked", lambda _: self.emit("new-task-clicked"))
        self.append(self.new_task_button)


        # ListBox
        self.tasks_listbox = Gtk.ListBox()
        self.tasks_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.tasks_listbox.connect("row-selected", self._on_row_selected)
        self.tasks_listbox.set_header_func(self._list_header_func, None)
        
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_child(self.tasks_listbox)
        self.append(scroller)

    def set_tasks(self, tasks: list[Task]):
        self.all_tasks = tasks
        self._refresh_tag_filter_options()
        self.apply_filters()

    def _refresh_tag_filter_options(self):
        current_tag = self._get_selected_tag()
        tags = sorted({t.tag for t in self.all_tasks if t.tag})

        new_model = Gtk.StringList.new(["усі теги", *tags])
        self.tag_filter.set_model(new_model)
        self.tag_model = new_model

        selected_index = 0
        if current_tag and current_tag in tags:
            selected_index = tags.index(current_tag) + 1
        self.tag_filter.set_selected(selected_index)

    def _get_selected_status(self) -> str:
        idx = self.status_filter.get_selected()
        return self.status_model.get_string(idx) or "усі"

    def _get_selected_tag(self) -> str | None:
        idx = self.tag_filter.get_selected()
        item = self.tag_model.get_string(idx)
        return item if item and item != "усі теги" else None

    def _on_filter_changed(self, *_args):
        self.apply_filters()

    def apply_filters(self):
        status_filter = self._get_selected_status()
        tag_filter = self._get_selected_tag()

        tasks = self.all_tasks

        if status_filter != "усі":
            tasks = [t for t in tasks if t.effective_status == status_filter]

        if tag_filter is not None:
            tasks = [t for t in tasks if t.tag == tag_filter]

        # Priority Sort: Overdue first, then others
        self.filtered_tasks = sorted(tasks, key=lambda t: (0 if t.effective_status == STATUS_OVERDUE else 1, t.deadline or "9999"))
        self._render_list()

    def _render_list(self):
        # Clear list
        while (child := self.tasks_listbox.get_first_child()):
            self.tasks_listbox.remove(child)

        for task in self.filtered_tasks:
            row = Gtk.ListBoxRow()
            row.task_id = task.id
            row.add_css_class("task-row") 
            
            eff_status = task.effective_status
            if eff_status == STATUS_OVERDUE:
                row.add_css_class("task-row-overdue")

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12) # Horizontal to side-by-side with icon
            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            text_box.set_hexpand(True)


            title = Gtk.Label(label=task.title or "(без назви)")
            title.set_xalign(0)
            title.add_css_class("task-title")

            eff_status = task.effective_status
            meta_parts = [eff_status]
            if task.tag: meta_parts.append(f"#{task.tag}")
            if task.deadline: meta_parts.append(task.deadline)

            meta = Gtk.Label(label=" · ".join(meta_parts))
            meta.set_xalign(0)
            meta.add_css_class("task-meta")

            if eff_status == STATUS_OVERDUE:
                title.add_css_class("overdue-text")
                meta.add_css_class("overdue-text")
                
                # Warning Icon
                icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
                icon.add_css_class("overdue-text")
                box.append(icon)

            elif eff_status in {STATUS_DONE, STATUS_CANCELLED}:
                title.add_css_class("muted-text")
                meta.add_css_class("muted-text")
            
            text_box.append(title)
            text_box.append(meta)
            box.append(text_box)
            row.set_child(box)

            # Events
            click = Gtk.GestureClick.new()
            click.set_button(0) # Handle all buttons
            click.connect("released", self._on_row_clicked, row)
            row.add_controller(click)

            self.tasks_listbox.append(row)

        if not self.filtered_tasks:
            empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            empty_box.set_valign(Gtk.Align.CENTER); empty_box.set_vexpand(True); empty_box.set_margin_top(40)
            empty_label = Gtk.Label(label="Чіназес. Можна ще трохи пожити.")
            empty_label.add_css_class("muted-text"); empty_label.set_wrap(True); empty_label.set_justify(Gtk.Justification.CENTER)
            empty_box.append(empty_label)
            self.tasks_listbox.append(empty_box)

        self._suppress_selection_signal = True
        if self.selected_task_id:
            self.select_task(self.selected_task_id)
        self._suppress_selection_signal = False


    def select_task(self, task_id: int):
        self.selected_task_id = task_id
        for row in self._get_rows():
            if getattr(row, "task_id", None) == task_id:
                self.tasks_listbox.select_row(row)
                return

    def find_row_by_task_id(self, task_id: int) -> Gtk.ListBoxRow | None:
        for row in self._get_rows():
            if getattr(row, "task_id", None) == task_id:
                return row
        return None

    def _get_rows(self):
        rows = []
        child = self.tasks_listbox.get_first_child()
        while child:
            if isinstance(child, Gtk.ListBoxRow):
                rows.append(child)
            child = child.get_next_sibling()
        return rows

    def _on_row_selected(self, _, row):
        if row and not self._suppress_selection_signal:
            task_id = getattr(row, "task_id", None)
            if task_id:
                self.selected_task_id = task_id
                self.emit("task-selected", task_id)

    def _on_row_clicked(self, gesture, n_press, x, y, row):
        task_id = getattr(row, "task_id", None)
        if not task_id: return

        if gesture.get_current_button() == 3: # Right click
            self.emit("task-context-menu", task_id, x, y)
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            return

        if n_press == 2:
            self._cancel_pending_click()
            self.emit("task-activated", task_id)
        elif n_press == 1:
            self._cancel_pending_click()
            self.pending_single_click_row = row
            self.pending_single_click_source = GLib.timeout_add(300, self._run_pending_click)

    def _run_pending_click(self):
        row = self.pending_single_click_row
        self.pending_single_click_source = None
        self.pending_single_click_row = None
        if row:
            task_id = getattr(row, "task_id", None)
            if task_id:
                self.emit("task-selected", task_id)
        return False

    def _cancel_pending_click(self):
        if self.pending_single_click_source:
            GLib.source_remove(self.pending_single_click_source)
            self.pending_single_click_source = None
            self.pending_single_click_row = None


    def _list_header_func(self, row, before, user_data):
        if before is None:
            # First row
            task = next((t for t in self.all_tasks if t.id == row.task_id), None)
            if task and task.effective_status == STATUS_OVERDUE:
                row.set_header(self._create_header_label("ПРОСТРОЧЕНІ"))
            return

        task_curr = next((t for t in self.all_tasks if t.id == row.task_id), None)
        task_prev = next((t for t in self.all_tasks if t.id == before.task_id), None)
        
        if not task_curr or not task_prev:
            return

        # Header between Overdue and normal
        if task_curr.effective_status != STATUS_OVERDUE and task_prev.effective_status == STATUS_OVERDUE:
            row.set_header(self._create_header_label("ІНШІ ТАСКИ"))
        elif task_curr.effective_status == STATUS_OVERDUE and task_prev.effective_status != STATUS_OVERDUE:
             row.set_header(self._create_header_label("ПРОСТРОЧЕНІ"))
        else:
            row.set_header(None)

    def _create_header_label(self, text: str) -> Gtk.Label:
        lbl = Gtk.Label(label=text)
        lbl.set_xalign(0)
        lbl.add_css_class("panel-title")
        lbl.set_margin_top(12)
        lbl.set_margin_bottom(6)
        lbl.set_margin_start(10)
        lbl.set_opacity(0.7)
        return lbl
