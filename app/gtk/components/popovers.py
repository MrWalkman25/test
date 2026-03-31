from gi.repository import Gtk, Gdk, GLib, GObject, Adw
from app.models import Task, STATUS_DONE, STATUS_NEW


class TaskInfoPopover(Gtk.Popover):
    __gsignals__ = {
        "edit-clicked": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "open-clicked": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "status-toggled": (GObject.SignalFlags.RUN_FIRST, None, (int, str)), # task_id, new_status
    }

    def __init__(self, task: Task, anchor):
        super().__init__(autohide=True)
        self.set_parent(anchor)
        self.set_position(Gtk.PositionType.TOP) # Default to TOP, flip to BOTTOM if needed
        self.set_has_arrow(True)
        self.task = task
        self._build_ui()



    def _build_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.add_css_class("popover-card")

        # Header with Title and Toggle Done
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        title_lbl = Gtk.Label(label=self.task.title or "—")
        title_lbl.add_css_class("popover-title")
        title_lbl.set_xalign(0)
        title_lbl.set_hexpand(True)
        header.append(title_lbl)

        self.done_btn = Gtk.Button()
        self.done_btn.set_has_frame(False)
        is_done = self.task.status == STATUS_DONE
        self.done_btn.set_icon_name("object-select-symbolic" if is_done else "checkbox-checked-symbolic")
        self.done_btn.set_tooltip_text("Відмітити як виконане" if not is_done else "Відмітити як нове")
        self.done_btn.connect("clicked", self._on_toggle_done)
        header.append(self.done_btn)
        
        box.append(header)

        if self.task.description:
            desc_lbl = Gtk.Label(label=self.task.description)
            desc_lbl.set_xalign(0); desc_lbl.set_wrap(True)
            desc_lbl.add_css_class("task-meta")
            box.append(desc_lbl)

        box.append(Gtk.Separator())

        # Details using Adw.ActionRow style (simulated with box/labels if Adw not perfectly available in popover context, but we use Adw)
        details_list = Gtk.ListBox()
        details_list.set_selection_mode(Gtk.SelectionMode.NONE)
        details_list.add_css_class("boxed-list")
        
        if self.task.tag:
            row = Adw.ActionRow(title="Тег", subtitle=f"#{self.task.tag}")
            row.add_prefix(Gtk.Image.new_from_icon_name("tag-symbolic"))
            details_list.append(row)

        deadline_val = self.task.deadline or "Немає"
        row_dl = Adw.ActionRow(title="Дедлайн", subtitle=deadline_val)
        row_dl.add_prefix(Gtk.Image.new_from_icon_name("calendar-symbolic"))
        if self.task.effective_status == "Протерміноване":
            row_dl.add_css_class("overdue-text")
        details_list.append(row_dl)

        row_status = Adw.ActionRow(title="Статус", subtitle=self.task.effective_status)
        row_status.add_prefix(Gtk.Image.new_from_icon_name("view-more-symbolic"))
        details_list.append(row_status)

        box.append(details_list)

        # Bottom Buttons
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btns.set_homogeneous(True)
        
        btn_open = Gtk.Button(label="Відкрити")
        btn_open.add_css_class("suggested-action")
        btn_open.connect("clicked", lambda _: (self.popdown(), self.emit("open-clicked", self.task.id)))
        
        btn_edit = Gtk.Button(label="Редагувати")
        btn_edit.connect("clicked", lambda _: (self.popdown(), self.emit("edit-clicked", self.task.id)))

        btns.append(btn_open); btns.append(btn_edit)
        box.append(btns)

        self.set_child(box)

    def _on_toggle_done(self, _):
        new_status = STATUS_DONE if self.task.status != STATUS_DONE else STATUS_NEW
        self.popdown()
        self.emit("status-toggled", self.task.id, new_status)


class TaskContextPopover(Gtk.Popover):
    __gsignals__ = {
        "action": (GObject.SignalFlags.RUN_FIRST, None, (int, str)), # task_id, action_name
    }

    def __init__(self, task_id: int, anchor, x, y):
        super().__init__(autohide=True)
        self.set_parent(anchor)
        self.set_position(Gtk.PositionType.TOP) # Flip to BOTTOM if needed
        self.set_has_arrow(True)
        self.task_id = task_id
        rect = Gdk.Rectangle(); rect.x=int(x); rect.y=int(y); rect.width=1; rect.height=1
        self.set_pointing_to(rect)
        self._build_ui()



    def _build_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.add_css_class("popover-card")

        actions = [
            ("Відкрити", "open", "document-open-symbolic"),
            ("Редагувати", "edit", "document-edit-symbolic"),
            ("Дублювати", "duplicate", "content-copy-symbolic"),
            ("На завтра", "postpone", "go-next-symbolic"),
            ("Видалити", "delete", "user-trash-symbolic"),
        ]

        for label, action, icon in actions:
            btn = Gtk.Button()
            btn.set_has_frame(False)
            btn_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            btn_content.append(Gtk.Image.new_from_icon_name(icon))
            btn_content.append(Gtk.Label(label=label))
            btn.set_child(btn_content)
            
            if action == "delete": btn.add_css_class("error")

            btn.connect("clicked", lambda _, a=action: (self.popdown(), self.emit("action", self.task_id, a)))
            box.append(btn)

        self.set_child(box)
