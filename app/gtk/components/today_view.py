from gi.repository import Gtk, Gdk, GLib, GObject
from datetime import date, datetime
from app.models import Task, STATUS_DONE, STATUS_CANCELLED, STATUS_OVERDUE, STATUS_NEW


class TodayView(Gtk.Box):
    __gsignals__ = {
        "task-selected": (GObject.SignalFlags.RUN_FIRST, None, (int, Gtk.Widget)),
        "task-activated": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "task-context-menu": (GObject.SignalFlags.RUN_FIRST, None, (int, Gtk.Widget, float, float)),
        "task-action": (GObject.SignalFlags.RUN_FIRST, None, (int, str)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("section")
        
        self.all_tasks: list[Task] = []
        self.selected_task_id: int | None = None

        self._build_ui()

    def _build_ui(self):
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        self.content.set_margin_top(16)
        self.content.set_margin_bottom(16)
        self.content.set_margin_start(16)
        self.content.set_margin_end(16)
        
        scroller.set_child(self.content)
        self.append(scroller)

    def set_tasks(self, tasks: list[Task]):
        self.all_tasks = tasks
        self.render()

    def render(self):
        while (child := self.content.get_first_child()):
            self.content.remove(child)

        today_str = date.today().isoformat()
        
        overdue = [t for t in self.all_tasks if t.effective_status == STATUS_OVERDUE]
        today_timed = []
        today_untimed = []
        no_date = []

        for t in self.all_tasks:
            if t.effective_status == STATUS_OVERDUE: continue
            if t.status in {STATUS_DONE, STATUS_CANCELLED}: continue
            
            if t.deadline and t.deadline[:10] == today_str:
                if "T" in t.deadline:
                    today_timed.append(t)
                else:
                    today_untimed.append(t)
            elif not t.deadline:
                no_date.append(t)

        # Sort timed today
        today_timed.sort(key=lambda t: t.deadline)

        if overdue:
            self._add_section("ПРОСТРОЧЕНІ", overdue, "overdue-section")
        
        if today_timed:
            self._add_section("СЬОГОДНІ З ЧАСОМ", today_timed)
            
        if today_untimed:
            self._add_section("СЬОГОДНІ БЕЗ ЧАСУ", today_untimed)

        if no_date:
            self._add_section("БЕЗ ДАТИ", no_date, is_collapsible=True)

        if not (overdue or today_timed or today_untimed):
            empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            empty.set_valign(Gtk.Align.CENTER); empty.set_vexpand(True)
            lbl = Gtk.Label(label="На сьогодні планів немає. Чіназес!")
            lbl.add_css_class("muted-text")
            empty.append(lbl)
            self.content.append(empty)

    def _add_section(self, title: str, tasks: list[Task], css_class: str = None, is_collapsible: bool = False):
        sec_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        if css_class: sec_box.add_css_class(css_class)
        
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl = Gtk.Label(label=title)
        lbl.add_css_class("panel-title")
        lbl.set_xalign(0)
        header_box.append(lbl)
        
        if is_collapsible:
            # For now just a simple label, can be expanded to real Gtk.Expander if needed
            lbl.set_text(f"▼ {title}")
            
        sec_box.append(header_box)
        
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE) # Selection handled manually or per-row
        listbox.add_css_class("transparent-list")
        
        for t in tasks:
            row = self._build_task_row(t)
            listbox.append(row)
            
        sec_box.append(listbox)
        self.content.append(sec_box)

    def _build_task_row(self, task: Task) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.task_id = task.id
        row.add_css_class("task-row")
        
        eff_status = task.effective_status
        if eff_status == STATUS_OVERDUE:
            row.add_css_class("task-row-overdue")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        text_box.set_hexpand(True)

        title = Gtk.Label(label=task.title or "(без назви)")
        title.set_xalign(0); title.add_css_class("task-title")

        meta_parts = []
        if task.tag: meta_parts.append(f"#{task.tag}")
        if task.deadline:
            if "T" in task.deadline:
                meta_parts.append(task.deadline[11:16]) # Only time
            else:
                meta_parts.append(task.deadline)

        meta = Gtk.Label(label=" · ".join(meta_parts))
        meta.set_xalign(0); meta.add_css_class("task-meta")

        if eff_status == STATUS_OVERDUE:
            title.add_css_class("overdue-text")
            meta.add_css_class("overdue-text")
            icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            icon.add_css_class("overdue-text")
            box.append(icon)

        text_box.append(title); text_box.append(meta)
        box.append(text_box)
        
        # Action Bar (Reused logic)
        actions = self._build_quick_actions(task.id)
        box.append(actions)

        row.set_child(box)

        # Interactivity
        click = Gtk.GestureClick.new()
        click.set_button(0)
        click.connect("released", self._on_row_clicked, task.id)
        row.add_controller(click)
        
        return row

    def _build_quick_actions(self, task_id: int) -> Gtk.Box:
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        actions.add_css_class("quick-action-bar")
        btns = [
            ("object-select-symbolic", "done", "Готово", "quick-action-btn-done"),
            ("go-next-symbolic", "tomorrow", "На завтра", ""),
            ("appointment-new-symbolic", "plus_1h", "+1 год", ""),
            ("edit-clear-all-symbolic", "clear_date", "Без дати", ""),
            ("edit-symbolic", "edit", "Редагувати", ""),
            ("user-trash-symbolic", "delete", "Видалити", "quick-action-btn-delete"),
        ]
        for icon, action, tooltip, extra_class in btns:
            btn = Gtk.Button(); btn.set_has_frame(False); btn.add_css_class("quick-action-btn")
            if extra_class: btn.add_css_class(extra_class)
            btn.set_icon_name(icon); btn.set_tooltip_text(tooltip)
            btn.connect("clicked", lambda _, a=action: self.emit("task-action", task_id, a))
            actions.append(btn)
        return actions

    def _on_row_clicked(self, gesture, n_press, x, y, task_id):
        if gesture.get_current_button() == 3:
            self.emit("task-context-menu", task_id, gesture.get_widget(), x, y)
        elif n_press == 2:
            self.emit("task-activated", task_id)
        else:
            self.selected_task_id = task_id
            self.emit("task-selected", task_id, gesture.get_widget())
