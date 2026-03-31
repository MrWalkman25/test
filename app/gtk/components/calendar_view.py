from gi.repository import Gtk, Gdk, GLib, GObject
from datetime import date, datetime, timedelta
import calendar as pycalendar
from app.models import Task, STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_CANCELLED, STATUS_OVERDUE


class CalendarView(Gtk.Box):
    __gsignals__ = {
        "task-clicked": (GObject.SignalFlags.RUN_FIRST, None, (int, Gtk.Widget)),
        "task-right-clicked": (GObject.SignalFlags.RUN_FIRST, None, (int, Gtk.Widget, float, float)),
        "task-activated": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "day-right-clicked": (GObject.SignalFlags.RUN_FIRST, None, (str, Gtk.Widget, float, float)), # str iso date
        "day-activated": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "task-dropped": (GObject.SignalFlags.RUN_FIRST, None, (int, str)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.add_css_class("section")

        self.all_tasks: list[Task] = []
        self.calendar_mode: str = "month"
        self.calendar_focus_date = date.today()

        
        self.pending_calendar_click_source: int | None = None
        self.pending_calendar_task_id: int | None = None
        self.pending_calendar_widget: Gtk.Widget | None = None

        self._build_ui()

    def _build_ui(self):
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        controls.set_halign(Gtk.Align.FILL)

        self.btn_month = Gtk.Button(label="Місяць")
        self.btn_week = Gtk.Button(label="Тиждень")
        self.btn_day_mode = Gtk.Button(label="Сьогодні")
        self.btn_month.connect("clicked", lambda _: self.set_mode("month"))
        self.btn_week.connect("clicked", lambda _: self.set_mode("week"))
        self.btn_day_mode.connect("clicked", lambda _: self.set_mode("day"))


        self.btn_prev = Gtk.Button(label="←")
        self.btn_next = Gtk.Button(label="→")
        self.btn_prev.connect("clicked", lambda _: self._shift_focus(-1))
        self.btn_next.connect("clicked", lambda _: self._shift_focus(1))

        self.btn_jump_today = Gtk.Button(label="Сьогодні (Перейти)")
        self.btn_jump_today.connect("clicked", lambda _: self.jump_today())

        self.btn_back = Gtk.Button(label="Назад")
        self.btn_back.connect("clicked", lambda _: self.set_mode("month"))
        self.btn_back.set_visible(False)


        self.title_label = Gtk.Label()
        self.title_label.set_xalign(0)
        self.title_label.add_css_class("panel-title")
        self.title_label.set_hexpand(True)

        controls.append(self.btn_month)
        controls.append(self.btn_week)
        controls.append(self.btn_day_mode)

        
        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        controls.append(spacer)

        controls.append(self.btn_prev)
        controls.append(self.btn_next)
        controls.append(self.btn_jump_today)
        controls.append(self.btn_back)


        self.append(controls)
        self.append(self.title_label)

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_hexpand(True)
        self.scroller.set_vexpand(True)
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.content_box.set_margin_top(4)
        self.content_box.set_margin_bottom(4)
        self.content_box.set_margin_start(4)
        self.content_box.set_margin_end(4)
        self.scroller.set_child(self.content_box)
        self.append(self.scroller)

    def set_tasks(self, tasks: list[Task]):
        self.all_tasks = tasks
        self.render()

    def set_mode(self, mode: str):
        self.calendar_mode = mode
        if mode == "day": self.calendar_focus_date = date.today()
        self.render()


    def jump_today(self):
        self.calendar_focus_date = date.today()
        self.render()

    def clear_day_plan(self):
        self.render()


    def _shift_focus(self, delta: int):
        if self.calendar_mode == "day":
            self.calendar_focus_date += timedelta(days=delta)
        elif self.calendar_mode == "month":
            year = self.calendar_focus_date.year
            month = self.calendar_focus_date.month + delta
            if month < 1: year -= 1; month = 12
            elif month > 12: year += 1; month = 1
            self.calendar_focus_date = self.calendar_focus_date.replace(year=year, month=month, day=1)
        else: # week
            self.calendar_focus_date += timedelta(days=7 * delta)
        self.render()


    def render(self):
        # Update mode buttons
        for btn, mode in [(self.btn_month, "month"), (self.btn_week, "week"), (self.btn_day_mode, "day")]:
            if mode == self.calendar_mode:
                btn.add_css_class("mode-button-active")
            else:
                btn.remove_css_class("mode-button-active")

        # Clear content
        while (child := self.content_box.get_first_child()):
            self.content_box.remove(child)

        self.btn_back.set_visible(self.calendar_mode == "day")
        
        if self.calendar_mode == "month": self._render_month_view()
        elif self.calendar_mode == "week": self._render_week_view()
        else: self._render_day_view()


    def _render_month_view(self):
        self.title_label.set_text(self.calendar_focus_date.strftime("%B %Y"))
        grid = Gtk.Grid(column_spacing=12, row_spacing=12, column_homogeneous=True, row_homogeneous=True)
        grid.set_hexpand(True); grid.set_vexpand(True)


        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
        for i, d in enumerate(days):
            lbl = Gtk.Label(label=d); lbl.add_css_class("calendar-day-title")
            grid.attach(lbl, i, 0, 1, 1)

        matrix = pycalendar.Calendar(0).monthdatescalendar(self.calendar_focus_date.year, self.calendar_focus_date.month)
        while len(matrix) < 6:
            last = matrix[-1][-1]
            matrix.append([last + timedelta(days=i) for i in range(1, 8)])

        for row_i, week in enumerate(matrix, start=1):
            for col_i, day_date in enumerate(week):
                cell = self._build_day_cell(day_date, compact=True)
                if day_date.month != self.calendar_focus_date.month: cell.set_sensitive(False)
                grid.attach(cell, col_i, row_i, 1, 1)
        self.content_box.append(grid)

    def _render_week_view(self):
        start = self.calendar_focus_date - timedelta(days=self.calendar_focus_date.weekday())
        end = start + timedelta(days=6)
        self.title_label.set_text(f"Тиждень: {start.isoformat()} — {end.isoformat()}")
        grid = Gtk.Grid(column_spacing=6, row_spacing=6, column_homogeneous=True)
        grid.set_hexpand(True); grid.set_vexpand(True)
        for i in range(7):
            day_date = start + timedelta(days=i)
            grid.attach(self._build_day_cell(day_date, compact=False), i, 0, 1, 1)
        self.content_box.append(grid)

    def _render_day_view(self):
        day_date = self.calendar_focus_date
        self.title_label.set_text(f"День: {day_date.isoformat()}")
        
        # We reuse _render_day_plan's expanded list feel for Day View
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        tasks = self._tasks_for_date(day_date)
        
        if not tasks:
            label = Gtk.Label(label="Чіназес. Можна ще трохи пожити.")
            label.add_css_class("muted-text")
            label.set_margin_top(40)
            box.append(label)
        else:
            for t in tasks:
                box.append(self._build_task_chip(t, day_date, emphasize=True))
        
        self.content_box.append(box)


    def _build_day_cell(self, day_date: date, compact: bool) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.add_css_class("calendar-day-box")
        box.set_hexpand(True); box.set_vexpand(True)
        box.set_size_request(-1, 128 if compact else 220)

        tasks = self._tasks_for_date(day_date)

        lbl = Gtk.Label(label=day_date.strftime("%d.%m (%a)"))
        lbl.set_xalign(0); lbl.add_css_class("calendar-day-title")
        
        if day_date == date.today():
            box.add_css_class("chip-active") # Highlight today
        
        box.append(lbl)

        # Overdue Indicator for the day
        has_overdue = any(t.effective_status == STATUS_OVERDUE for t in tasks)
        if has_overdue:
            box.add_css_class("calendar-day-box-overdue")
            # Small warning icon in title
            indicator = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            indicator.add_css_class("day-overdue-indicator")
            indicator.set_halign(Gtk.Align.END)
            # Find a way to stick it to the top right
            header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            header_box.append(lbl)
            lbl.set_hexpand(True)
            header_box.append(indicator)
            
            # Replace single label with header box
            box.remove(lbl)
            box.prepend(header_box)


        chips = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        chips.set_vexpand(True); chips.set_valign(Gtk.Align.START)
        
        limit = 3 if compact else 8
        for t in tasks[:limit]:
            chips.append(self._build_task_chip(t, day_date, emphasize=not compact))
        
        if len(tasks) > limit:
            more = Gtk.Label(label=f"+{len(tasks) - limit} ще")
            more.set_xalign(0); more.add_css_class("muted-text")
            chips.append(more)
        
        box.append(chips)

        # Gestures
        click = Gtk.GestureClick.new()
        click.set_button(0)
        click.connect("released", self._on_day_clicked, day_date)
        box.add_controller(click)

        motion = Gtk.EventControllerMotion()
        motion.connect("leave", lambda *_: box.remove_css_class("calendar-day-box-hover"))
        box.add_controller(motion)

        # Drop Target
        drop_target = Gtk.DropTarget.new(GObject.TYPE_INT, Gdk.DragAction.MOVE)
        drop_target.connect("enter", self._on_drag_enter)
        drop_target.connect("leave", self._on_drag_leave)
        drop_target.connect("drop", self._on_drop, day_date.isoformat())
        box.add_controller(drop_target)

        return box

    def _build_task_chip(self, task: Task, day_date: date, emphasize: bool) -> Gtk.Button:
        parts = []
        
        # Show time in primary day view (emphasized)
        if emphasize and task.deadline and "T" in task.deadline:
            parts.append(task.deadline[11:16])
        
        parts.append(task.title or "(без назви)")
        
        # In small chips (not emphasized), show reminder if no deadline time
        if not emphasize and not (task.deadline and "T" in task.deadline):
            if task.reminder_at and len(task.reminder_at) >= 16:
                parts.append(task.reminder_at[11:16])
        
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl = Gtk.Label(label=" • ".join(parts))
        lbl.set_xalign(0); lbl.set_ellipsize(3) # PANGO_ELLIPSIZE_END
        box.append(lbl)

        box.set_halign(Gtk.Align.FILL)
        box.add_css_class("calendar-chip")
        if emphasize: box.set_hexpand(True)
        
        eff_status = task.effective_status
        if eff_status == STATUS_OVERDUE: box.add_css_class("chip-overdue")
        elif eff_status in {STATUS_DONE, STATUS_CANCELLED}: box.add_css_class("chip-muted")
        elif eff_status == STATUS_IN_PROGRESS: box.add_css_class("chip-active")
        else: box.add_css_class("chip-new")

        click = Gtk.GestureClick.new()
        click.set_button(0) # Handle all buttons
        click.connect("released", self._on_task_clicked, task.id, box)
        box.add_controller(click)

        # Drag Source
        drag_source = Gtk.DragSource.new()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("prepare", self._on_drag_prepare, task.id)
        drag_source.connect("drag-begin", self._on_drag_begin, task.id)
        box.add_controller(drag_source)

        return box

    def _tasks_for_date(self, d: date) -> list[Task]:
        res = []
        target_date_str = d.isoformat()
        for t in self.all_tasks:
            if not t.deadline: continue
            if t.deadline[:10] == target_date_str:
                res.append(t)
        
        # Sort logic: 
        # Group 0: Timed tasks (e.g. 2024-01-01T10:00) -> sort by full string
        # Group 1: Date-only tasks (e.g. 2024-01-01) -> stay at bottom
        def sort_key(task):
            eff_status = task.effective_status
            is_overdue = eff_status == STATUS_OVERDUE
            is_timed = "T" in task.deadline
            return (0 if is_overdue else 1, 0 if is_timed else 1, task.deadline)

        return sorted(res, key=sort_key)


    def _on_day_clicked(self, gesture, n_press, x, y, day_date):
        if gesture.get_current_button() == 3:
            self.emit("day-right-clicked", day_date.isoformat(), gesture.get_widget(), x, y)
        elif n_press == 2:
            self.calendar_focus_date = day_date
            self.set_mode("day")
            self.emit("day-activated", day_date.isoformat())

    def _on_task_clicked(self, gesture, n_press, x, y, task_id, widget):
        if gesture.get_current_button() == 3:
            self._cancel_pending_click()
            self.emit("task-right-clicked", task_id, widget, x, y)
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            return

        if n_press == 2:
            self._cancel_pending_click()
            self.emit("task-activated", task_id)
        elif n_press == 1:
            self._cancel_pending_click()
            self.pending_calendar_task_id = task_id
            self.pending_calendar_widget = widget
            self.pending_calendar_click_source = GLib.timeout_add(300, self._run_pending_click)

    def _run_pending_click(self):
        t_id, w = self.pending_calendar_task_id, self.pending_calendar_widget
        self.pending_calendar_click_source = self.pending_calendar_task_id = self.pending_calendar_widget = None
        if t_id and w: self.emit("task-clicked", t_id, w)
        return False

    def _cancel_pending_click(self):
        if self.pending_calendar_click_source:
            GLib.source_remove(self.pending_calendar_click_source)
            self.pending_calendar_click_source = self.pending_calendar_task_id = self.pending_calendar_widget = None

    # --- Drag & Drop Handlers ---

    def _on_drag_prepare(self, _source, _x, _y, task_id):
        return Gdk.ContentProvider.new_for_value(task_id)

    def _on_drag_begin(self, _source, drag, task_id):
        task = next((t for t in self.all_tasks if t.id == task_id), None)
        if not task: return
        
        chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        chip.add_css_class("calendar-chip")
        
        eff_status = task.effective_status
        if eff_status == STATUS_OVERDUE: chip.add_css_class("chip-overdue")
        elif eff_status in {STATUS_DONE, STATUS_CANCELLED}: chip.add_css_class("chip-muted")
        elif eff_status == STATUS_IN_PROGRESS: chip.add_css_class("chip-active")
        else: chip.add_css_class("chip-new")
        
        lbl = Gtk.Label(label=task.title or "(без назви)")
        chip.append(lbl)
        
        icon = Gtk.DragIcon.get_for_drag(drag)
        icon.set_child(chip)

    def _on_drag_enter(self, target, _x, _y):
        target.get_widget().add_css_class("calendar-day-drop-target")
        return Gdk.DragAction.MOVE

    def _on_drag_leave(self, target):
        target.get_widget().remove_css_class("calendar-day-drop-target")

    def _on_drop(self, target, task_id, _x, _y, iso_date):
        target.get_widget().remove_css_class("calendar-day-drop-target")
        self.emit("task-dropped", task_id, iso_date)
        return True
