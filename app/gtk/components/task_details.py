from gi.repository import Gtk, Gdk, GLib, GObject
from app.models import Task


class TaskDetailsView(Gtk.Box):
    __gsignals__ = {
        "edit-clicked": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._build_ui()

    def _build_ui(self):
        title_lbl = Gtk.Label(label="Повний перегляд задачі")
        title_lbl.set_xalign(0); title_lbl.add_css_class("panel-title")
        self.append(title_lbl)

        self.lbl_title = Gtk.Label(); self.lbl_title.set_xalign(0); self.lbl_title.add_css_class("popover-title")
        self.append(self.lbl_title)

        self.lbl_desc = Gtk.Label(); self.lbl_desc.set_xalign(0); self.lbl_desc.set_wrap(True)
        self.append(self.lbl_desc)
        
        self.append(Gtk.Separator())

        self.lbl_tag = Gtk.Label(); self.lbl_status = Gtk.Label(); self.lbl_priority = Gtk.Label()
        self.lbl_deadline = Gtk.Label(); self.lbl_reminder = Gtk.Label(); self.lbl_created = Gtk.Label()

        for lbl in [self.lbl_tag, self.lbl_status, self.lbl_priority, self.lbl_deadline, self.lbl_reminder, self.lbl_created]:
            lbl.set_xalign(0); self.append(lbl)

        self.btn_edit = Gtk.Button(label="Редагувати")
        self.btn_edit.connect("clicked", self._on_edit)
        self.append(self.btn_edit)

        self.current_task_id = None

    def set_task(self, task: Task):
        self.current_task_id = task.id
        self.lbl_title.set_text(task.title or "—")
        self.lbl_desc.set_text(f"Опис: {task.description or '—'}")
        self.lbl_tag.set_text(f"Тег: {task.tag or '—'}")
        self.lbl_status.set_text(f"Статус: {task.effective_status}")
        priority_map = {"low": "Низький", "normal": "Звичайний", "high": "Високий"}
        self.lbl_priority.set_text(f"Пріоритет: {priority_map.get(task.priority, '—')}")
        self.lbl_deadline.set_text(f"Дедлайн: {task.deadline or '—'}")
        self.lbl_reminder.set_text(f"Нагадування: {task.reminder_at or '—'}")
        self.lbl_created.set_text(f"Створено: {task.created_at or '—'}")

    def _on_edit(self, _):
        if self.current_task_id:
            self.emit("edit-clicked", self.current_task_id)
