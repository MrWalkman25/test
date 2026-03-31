from gi.repository import Gtk, Gdk, GLib, GObject
from datetime import date, datetime
from app.models import Task, STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_CANCELLED


class TaskFormView(Gtk.Box):
    __gsignals__ = {
        "saved": (GObject.SignalFlags.RUN_FIRST, None, (object,)), # Emits the form data as dict
        "cancelled": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, mode="new"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.mode = mode # "new" or "edit"
        self.task_id: int | None = None
        self._active_popover: Gtk.Popover | None = None
        self._build_ui()


    def _build_ui(self):
        self.title_lbl = Gtk.Label(label="Ще одна справа, про яку ти забудеш")

        self.title_lbl.set_xalign(0); self.title_lbl.add_css_class("panel-title")
        self.append(self.title_lbl)

        self.error_lbl = Gtk.Label(); self.error_lbl.set_xalign(0); self.error_lbl.add_css_class("overdue-text")
        self.error_lbl.set_text("Заповни хоча б назву, не лінуйся")
        self.append(self.error_lbl)


        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        self.append(grid)


        self.entry_title = Gtk.Entry(placeholder_text="Назви це якось розумно")
        self.tv_description = Gtk.TextView(vexpand=True); self.tv_description.set_size_request(-1, 120)
        self.entry_tag = Gtk.Entry(placeholder_text="Якийсь тег, якщо треба")


        self.status_model = Gtk.StringList.new([STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_CANCELLED])
        self.drop_status = Gtk.DropDown(model=self.status_model)

        self.priority_map = {"low": "Низький", "normal": "Звичайний", "high": "Високий"}
        self.priority_inv_map = {v: k for k, v in self.priority_map.items()}
        self.priority_model = Gtk.StringList.new(["Низький", "Звичайний", "Високий"])
        self.drop_priority = Gtk.DropDown(model=self.priority_model); self.drop_priority.set_selected(1)

        self.entry_deadline = Gtk.Entry(placeholder_text="YYYY-MM-DDTHH:MM (буде боляче)")
        self.entry_reminder = Gtk.Entry(placeholder_text="YYYY-MM-DDTHH:MM (коли смикнути)")

        for entry in [self.entry_deadline, self.entry_reminder]:
            entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "calendar-symbolic")
            entry.set_icon_activatable(Gtk.EntryIconPosition.SECONDARY, True)
            entry.set_icon_sensitive(Gtk.EntryIconPosition.SECONDARY, True)
            
            # Click gesture for the entry itself (no focus controller to avoid loops)
            click = Gtk.GestureClick.new()
            click.connect("released", self._on_entry_clicked, entry)
            entry.add_controller(click)
            
            # Icon release signal
            entry.connect("icon-release", self._on_entry_icon_released)




        deadline_row = self._build_date_row(self.entry_deadline, True)
        reminder_row = self._build_date_row(self.entry_reminder, True)


        rows = [("Назва", self.entry_title), ("Опис", self.tv_description), ("Тег", self.entry_tag),
                ("Статус", self.drop_status), ("Пріоритет", self.drop_priority),
                ("Дедлайн", deadline_row), ("Нагадування", reminder_row)]

        for i, (l_text, w) in enumerate(rows):
            lbl = Gtk.Label(label=l_text); lbl.set_xalign(0)
            grid.attach(lbl, 0, i, 1, 1); grid.attach(w, 1, i, 1, 1)

        self.btn_submit = Gtk.Button(label="Зберегти")
        self.btn_submit.connect("clicked", self._on_submit)
        
        self.btn_test_notify = Gtk.Button(label="Тест сповіщення")
        self.btn_test_notify.add_css_class("suggested-action")
        self.btn_test_notify.add_css_class("pill") # If we had pill class, but we don't. Let's stick to consistent buttons.
        self.btn_test_notify.connect("clicked", self._on_test_notify_clicked)


        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btns.append(self.btn_submit)
        btns.append(self.btn_test_notify)
        self.append(btns)


    def _build_date_row(self, entry, with_time):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.append(entry)
        
        btn_pick = Gtk.Button(label="Обрати")
        btn_pick.connect("clicked", lambda b: self._show_picker(b, entry, with_time))
        row.append(btn_pick)
        
        btn_today = Gtk.Button(label="Сьогодні")
        btn_today.connect("clicked", lambda _: entry.set_text(datetime.now().strftime("%Y-%m-%dT%H:%M" if with_time else "%Y-%m-%d")))
        row.append(btn_today)
        
        btn_clear = Gtk.Button(label="Очистити")
        btn_clear.connect("clicked", lambda _: entry.set_text(""))
        row.append(btn_clear)
        return row

    def _on_entry_clicked(self, gesture, n_press, x, y, entry):
        if n_press == 1:
            self._show_picker(entry, entry, True)

    def _on_entry_icon_released(self, entry, icon_pos):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            self._show_picker(entry, entry, True)



    def _on_test_notify_clicked(self, _):
        from app.notifications import notify_test
        notify_test()


    def clear(self):
        self.task_id = None
        self.entry_title.set_text("")
        self.tv_description.get_buffer().set_text("")
        self.entry_tag.set_text("")
        self.drop_status.set_selected(0)
        self.drop_priority.set_selected(1)
        self.entry_deadline.set_text("")
        self.entry_reminder.set_text("")
        self.error_lbl.set_text("")
        self.title_lbl.set_text("Ще одна справа, про яку ти забудеш")
        self.btn_submit.set_label("Додати цей тягар")


    def set_task(self, task: Task):
        self.task_id = task.id
        self.entry_title.set_text(task.title or "")
        self.tv_description.get_buffer().set_text(task.description or "")
        self.entry_tag.set_text(task.tag or "")
        self._set_drop(self.drop_status, self.status_model, task.status or STATUS_NEW)
        self._set_priority_drop(task.priority or "normal")
        self.entry_deadline.set_text(task.deadline or "")
        self.entry_reminder.set_text(task.reminder_at or "")
        self.error_lbl.set_text("")
        self.title_lbl.set_text(f"Спроба виправити помилки в задачі {task.id}")
        self.btn_submit.set_label("Зберегти, як є")


    def _set_priority_drop(self, val):
        ukr_val = self.priority_map.get(val, "Звичайний")
        for i in range(self.priority_model.get_n_items()):
            if self.priority_model.get_string(i) == ukr_val:
                self.drop_priority.set_selected(i); return
        self.drop_priority.set_selected(1)

    def _set_drop(self, drop, model, val):
        for i in range(model.get_n_items()):
            if model.get_string(i) == val:
                drop.set_selected(i); return
        drop.set_selected(0)

    def _on_submit(self, _):
        title = self.entry_title.get_text().strip()
        if not title:
            self.error_lbl.set_text("Назва задачі є обов'язковою."); return
        
        buf = self.tv_description.get_buffer()
        desc = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True).strip()
        
        data = {
            "id": self.task_id,
            "title": title,
            "description": desc or None,
            "tag": self.entry_tag.get_text().strip() or None,
            "status": self.status_model.get_string(self.drop_status.get_selected()),
            "priority": self.priority_inv_map.get(self.priority_model.get_string(self.drop_priority.get_selected()), "normal"),
            "deadline": self.entry_deadline.get_text().strip() or None,
            "reminder_at": self.entry_reminder.get_text().strip() or None,
        }
        self.emit("saved", data)

    def _show_picker(self, parent, entry, with_time):
        if self._active_popover:
            self._active_popover.popdown()
            self._active_popover = None

        popover = Gtk.Popover(); popover.set_parent(parent)
        popover.set_position(Gtk.PositionType.TOP)
        popover.set_has_arrow(True)
        self._active_popover = popover


        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6); box.add_css_class("popover-card")
        cal = Gtk.Calendar(); box.append(cal)
        # Hours selection: 00-23
        hours_list = [f"{i:02d}" for i in range(24)]
        hours_model = Gtk.StringList.new(hours_list)
        drop_h = Gtk.DropDown(model=hours_model)
        
        # Minutes selection: 00, 15, 30, 45
        minutes_list = ["00", "15", "30", "45"]
        minutes_model = Gtk.StringList.new(minutes_list)
        drop_m = Gtk.DropDown(model=minutes_model)
        
        # Try to parse current value to pre-select items
        curr = entry.get_text().strip()
        h_val, m_val = datetime.now().hour, 0
        try:
            if "T" in curr:
                dt = datetime.fromisoformat(curr)
                cal.select_day(GLib.DateTime.new_local(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0))
                h_val, m_val = dt.hour, dt.minute
            elif curr:
                dt = datetime.strptime(curr, "%Y-%m-%d")
                cal.select_day(GLib.DateTime.new_local(dt.year, dt.month, dt.day, 0, 0, 0))
                h_val, m_val = 0, 0
        except:
            pass
            
        # Select closest values in dropdowns
        drop_h.set_selected(h_val)
        # Find closest minute in list [0, 15, 30, 45]
        closest_m_idx = 0
        if m_val >= 45: closest_m_idx = 3
        elif m_val >= 30: closest_m_idx = 2
        elif m_val >= 15: closest_m_idx = 1
        drop_m.set_selected(closest_m_idx)

        if with_time:
            tr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            tr.set_halign(Gtk.Align.CENTER)
            tr.append(Gtk.Label(label="Час: "))
            tr.append(drop_h)
            tr.append(Gtk.Label(label=":"))
            tr.append(drop_m)
            box.append(tr)
        
        btn = Gtk.Button(label="Готово")
        btn.add_css_class("suggested-action")
        
        def on_apply(_):
            dt_glib = cal.get_date()
            ds = f"{dt_glib.get_year():04d}-{dt_glib.get_month()+1:02d}-{dt_glib.get_day_of_month():02d}"
            selected_h = hours_model.get_string(drop_h.get_selected())
            selected_m = minutes_model.get_string(drop_m.get_selected())
            entry.set_text(f"{ds}T{selected_h}:{selected_m}" if with_time else ds)
            popover.popdown()
            self._active_popover = None
            
        btn.connect("clicked", on_apply)
        box.append(btn)
        popover.set_child(box)
        popover.popup()



