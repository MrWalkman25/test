import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, Gtk, Gio
from app.database import (
    get_tasks,
    get_task_by_id,
    add_task,
    update_task,
    delete_task,
    update_last_interaction,
    update_reminder_tracking,
)
from app.models import (
    Task,
    STATUS_NEW,
    STATUS_IN_PROGRESS,
    STATUS_DONE,
    STATUS_CANCELLED,
    STATUS_OVERDUE,
    MAX_REMINDERS,
    REMINDER_REPEAT_MINS,
)
from app.gtk.style import setup_css
from app.gtk.components.task_list import TaskListView
from app.gtk.components.calendar_view import CalendarView
from app.gtk.components.task_form import TaskFormView
from app.gtk.components.task_details import TaskDetailsView
from app.gtk.components.today_view import TodayView
from app.gtk.components.popovers import TaskInfoPopover, TaskContextPopover
from datetime import datetime, timedelta, date


class TaskManagerGtkWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Мій Йобаний Таск-Менеджер")
        self.set_default_size(1200, 760)

        # Background reminder and overdue status checker (every 60s)
        self._notification_timer_id = GLib.timeout_add_seconds(60, self._check_background_notifications)
        self.connect("destroy", self._on_destroy)

        # Actions for notifications
        self._setup_notification_actions()



        self.all_tasks: list[Task] = []
        self.active_context_popover: Gtk.Popover | None = None
        self.active_task_popover: Gtk.Popover | None = None
        self.active_day_popover: Gtk.Popover | None = None

        setup_css()
        self._build_ui()
        self._load_tasks()

    def _setup_notification_actions(self):
        # Action: task-done
        action_done = Gio.SimpleAction.new("task-done", GLib.VariantType.new("i"))
        action_done.connect("activate", self._on_action_task_done)
        self.add_action(action_done)

        # Action: task-delay-1h
        action_delay_1h = Gio.SimpleAction.new("task-delay-1h", GLib.VariantType.new("i"))
        action_delay_1h.connect("activate", self._on_action_task_delay_1h)
        self.add_action(action_delay_1h)

        # Action: task-delay-day
        action_delay_day = Gio.SimpleAction.new("task-delay-day", GLib.VariantType.new("i"))
        action_delay_day.connect("activate", self._on_action_task_delay_day)
        self.add_action(action_delay_day)

        # Action: task-open
        action_open = Gio.SimpleAction.new("task-open", GLib.VariantType.new("i"))
        action_open.connect("activate", self._on_action_task_open)
        self.add_action(action_open)

    def _build_ui(self) -> None:
        header = Adw.HeaderBar()
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_box.append(Gtk.Label(label="Таски, які ти все одно проїбеш"))
        
        # Focus Toggle Button
        self.focus_toggle = Gtk.ToggleButton()
        self.focus_toggle.set_icon_name("preferences-system-notifications-symbolic")
        self.focus_toggle.set_tooltip_text("Увімкнути Фокус")
        self.focus_toggle.connect("toggled", self._on_focus_toggle)
        header.pack_end(self.focus_toggle)

        # Hide to Tray Button (Disabled for stability)
        self.btn_hide = Gtk.Button()
        self.btn_hide.set_icon_name("window-minimize-symbolic")
        self.btn_hide.set_tooltip_text("Сховати в трей (Вимкнено)")
        self.btn_hide.connect("clicked", self._on_hide_to_tray)
        self.btn_hide.set_visible(False) # Hiding it
        header.pack_end(self.btn_hide)
        
        header.set_title_widget(title_box)


        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.append(header)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        # Side Task List
        self.task_list = TaskListView()
        self.task_list.connect("task-selected", self._on_task_selected)
        self.task_list.connect("task-activated", self._on_task_activated)
        self.task_list.connect("task-context-menu", self._on_task_context_menu)
        self.task_list.connect("task-action", self._on_task_action)
        self.task_list.connect("new-task-clicked", self._on_new_task_clicked)

        # Right Stack
        self.mode_stack = Gtk.Stack()
        self.mode_stack.set_hexpand(True)
        self.mode_stack.set_vexpand(True)

        # Calendar Component
        self.calendar = CalendarView()
        self.calendar.connect("task-clicked", self._on_calendar_task_clicked)
        self.calendar.connect("task-right-clicked", self._on_calendar_task_right_clicked)
        self.calendar.connect("task-activated", self._on_task_activated)
        self.calendar.connect("task-action", self._on_task_action)
        self.calendar.connect("day-right-clicked", self._on_day_right_clicked)
        self.calendar.connect("task-dropped", self._on_task_dropped)

        # Keyboard Controller
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

        # Form Component (Reused for New/Edit)
        self.task_form = TaskFormView()
        self.task_form.connect("saved", self._on_task_form_saved)

        # Details Component
        self.task_details = TaskDetailsView()
        self.task_details.connect("edit-clicked", self._on_edit_mode_requested)

        # Today View Component (Priority Screen)
        self.today_view = TodayView()
        self.today_view.connect("task-selected", self._on_task_selected)
        self.today_view.connect("task-activated", self._on_task_activated)
        self.today_view.connect("task-context-menu", self._on_task_context_menu)
        self.today_view.connect("task-action", self._on_task_action)

        self.mode_stack.add_titled(self.today_view, "today", "Сьогодні")
        self.mode_stack.add_titled(self.calendar, "calendar", "Календар")
        self.mode_stack.add_titled(self.task_details, "task", "Деталі")
        self.mode_stack.add_titled(self.task_form, "form", "Форма")

        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right_box.add_css_class("section")
        
        stack_switcher = Gtk.StackSwitcher(stack=self.mode_stack)
        right_box.append(stack_switcher)
        right_box.append(self.mode_stack)

        content.append(self.task_list)
        content.append(right_box)
        root.append(content)
        self.set_content(root)

    def _load_tasks(self) -> None:
        self._dismiss_all_popovers()
        raw_tasks = get_tasks()
        self.all_tasks = [Task.from_dict(t) for t in raw_tasks]
        self.task_list.set_tasks(self.all_tasks)
        self.calendar.set_tasks(self.all_tasks)
        self.today_view.set_tasks(self.all_tasks)

    # --- Signals Handlers ---

    def _on_task_selected(self, _comp, task_id, widget):
        # Triggered on single click in the task list or today view
        task = self._get_task(task_id)
        if task:
            self._show_task_popover(widget, task)
            update_last_interaction(task_id)

    def _on_task_activated(self, _comp, task_id):
        self._open_full_task_view(task_id)

    def _on_new_task_clicked(self, _list):
        self._dismiss_all_popovers()
        self.task_form.clear()
        self.mode_stack.set_visible_child_name("form")

    def _on_edit_mode_requested(self, _comp, task_id):
        self._open_edit_mode(task_id)

    def _on_task_form_saved(self, _form, data):
        if data.get("id"):
            update_task(
                task_id=data["id"],
                title=data["title"],
                description=data["description"],
                tag=data["tag"],
                status=data["status"],
                priority=data["priority"],
                deadline=data["deadline"],
                reminder_at=data["reminder_at"]
            )
        else:
            add_task(
                title=data["title"],
                description=data["description"],
                tag=data["tag"],
                deadline=data["deadline"],
                reminder_at=data["reminder_at"],
                priority=data["priority"]
            )
            update_last_interaction(data["id"])
        self._load_tasks()
        self.mode_stack.set_visible_child_name("calendar")

    # --- Popover Management ---

    def _on_task_context_menu(self, _comp, task_id, widget, x, y):
        self._show_context_popover(widget, task_id, x, y)

    def _on_calendar_task_clicked(self, _comp, task_id, widget):
        task = self._get_task(task_id)
        if task: self._show_task_popover(widget, task)

    def _on_calendar_task_right_clicked(self, _comp, task_id, widget, x, y):
        self._show_context_popover(widget, task_id, x, y)

    def _on_day_right_clicked(self, _comp, iso_date, widget, x, y):
        self._show_day_popover(widget, iso_date, x, y)

    # --- Helpers ---

    def _get_task(self, task_id: int) -> Task | None:
        return next((t for t in self.all_tasks if t.id == task_id), None)

    def _open_full_task_view(self, task_id: int):
        task = self._get_task(task_id)
        if task:
            self.task_details.set_task(task)
            self._dismiss_all_popovers()
            self.mode_stack.set_visible_child_name("task")
            update_last_interaction(task_id)
            
            # Highlight in list
            row = self.task_list.find_row_by_task_id(task_id)
            if row:
                self.task_list.tasks_listbox.select_row(row)
                # GtkListBox mapping focuses by row

    def _open_edit_mode(self, task_id: int):
        task = self._get_task(task_id)
        if task:
            self.task_form.set_task(task)
            self._dismiss_all_popovers()
            self.mode_stack.set_visible_child_name("form")
            update_last_interaction(task_id)

    def _dismiss_all_popovers(self):
        for p in [self.active_context_popover, self.active_task_popover, self.active_day_popover]:
            if p:
                p.popdown()
                p.unparent()
        self.active_context_popover = self.active_task_popover = self.active_day_popover = None

    def _show_task_popover(self, anchor, task: Task):
        if self.mode_stack.get_visible_child_name() == "task":
            if self.task_details.current_task_id == task.id:
                return
        
        self._dismiss_all_popovers()
        pop = TaskInfoPopover(task, anchor)
        pop.connect("edit-clicked", self._on_edit_mode_requested)
        pop.connect("open-clicked", lambda _, t_id: self._open_full_task_view(t_id))
        pop.connect("status-toggled", lambda _, t_id, s: self._quick_update_status(t_id, s))
        pop.popup()
        self.active_task_popover = pop

    def _show_context_popover(self, anchor, task_id: int, x: float, y: float):
        self._dismiss_all_popovers()
        pop = TaskContextPopover(task_id, anchor, x, y)
        pop.connect("action", self._on_context_action)
        pop.popup()
        self.active_context_popover = pop

    def _on_context_action(self, _pop, task_id, action):
        if action == "open":
            self._open_full_task_view(task_id)
        elif action == "edit":
            self._open_edit_mode(task_id)
        elif action == "delete":
            self._delete_task_confirm(task_id)
        elif action == "duplicate":
            from app.database import duplicate_task
            new_id = duplicate_task(task_id)
            if new_id: self._load_tasks()
        else:
            # Handle all other quick actions
            self._handle_quick_action(task_id, action)

    def _on_task_action(self, _comp, task_id, action):
        self._handle_quick_action(task_id, action)

    def _handle_quick_action(self, task_id: int, action: str):
        if action == "edit":
            self._open_edit_mode(task_id)
            return
        elif action == "delete":
            self._delete_task_confirm(task_id)
            return

        task = get_task_by_id(task_id)
        if not task: return

        if action == "done":
            new_status = STATUS_DONE if task.get("status") != STATUS_DONE else STATUS_NEW
            self._quick_update_status(task_id, new_status)
        elif action == "tomorrow":
            self._postpone_task(task_id)
        elif action == "plus_1h":
            # Reuse logic from notification action
            param = GLib.Variant("i", task_id)
            self._on_action_task_delay_1h(None, param)
        elif action == "clear_date":
            update_task(
                task_id=task_id,
                title=task["title"],
                description=task["description"],
                tag=task["tag"],
                status=task["status"],
                priority=task["priority"],
                deadline=None,
                reminder_at=None
            )
            self._load_tasks()

    def _on_key_pressed(self, _controller, keyval, _keycode, _state):
        task_id = self.task_list.selected_task_id
        if not task_id: return False

        key_name = Gdk.keyval_name(keyval)
        
        if key_name == "Return":
            self._open_full_task_view(task_id)
            return True
        elif key_name in {"d", "D", "space"}:
            self._handle_quick_action(task_id, "done")
            return True
        elif key_name in {"t", "T"}:
            self._handle_quick_action(task_id, "tomorrow")
            return True
        elif key_name in {"h", "H"}:
            self._handle_quick_action(task_id, "plus_1h")
            return True
        elif key_name in {"Delete", "BackSpace"}:
            self._handle_quick_action(task_id, "delete")
            return True
        elif key_name == "Escape":
            self.mode_stack.set_visible_child_name("calendar")
            self._dismiss_all_popovers()
            return True
        elif key_name in {"f", "F"} and (_state & Gdk.ModifierType.CONTROL_MASK):
            self.focus_toggle.set_active(not self.focus_toggle.get_active())
            return True

        return False

    def _postpone_task(self, task_id):
        task = get_task_by_id(task_id)
        if task and task.get("deadline"):
            try:
                d = datetime.strptime(task["deadline"][:10], "%Y-%m-%d").date()
                new_date = (d + timedelta(days=1)).isoformat()
                update_task(
                    task_id=task_id,
                    title=task.get("title") or "—",
                    description=task.get("description"),
                    tag=task.get("tag"),
                    status=task.get("status") or STATUS_NEW,
                    priority=task.get("priority") or "normal",
                    deadline=new_date,
                    reminder_at=task.get("reminder_at")
                )
                self._load_tasks()
            except ValueError: pass

    def _on_task_dropped(self, _comp, task_id, new_date):
        task = get_task_by_id(task_id)
        if not task: return
        
        old_deadline = task.get("deadline")
        if old_deadline and len(old_deadline) > 10:
            # Preservation of time
            time_part = old_deadline[10:]
            final_deadline = new_date + time_part
        else:
            final_deadline = new_date
            
        update_task(
            task_id=task_id,
            title=task.get("title") or "—",
            description=task.get("description"),
            tag=task.get("tag"),
            status=task.get("status") or STATUS_NEW,
            priority=task.get("priority") or "normal",
            deadline=final_deadline,
            reminder_at=task.get("reminder_at")
        )
        self._load_tasks()

    def _show_day_popover(self, anchor, iso_date: str, x: float, y: float):
        self._dismiss_all_popovers()
        pop = Gtk.Popover(); pop.set_parent(anchor); pop.set_autohide(True)
        rect = Gdk.Rectangle(); rect.x=int(x); rect.y=int(y); rect.width=1; rect.height=1
        pop.set_pointing_to(rect)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4); box.add_css_class("popover-card")
        
        btn_add = Gtk.Button(label="Додати задачу"); btn_add.connect("clicked", lambda _: (pop.popdown(), self._open_new_task_for_date(iso_date)))
        btn_view = Gtk.Button(label="Відкрити день"); btn_view.connect("clicked", lambda _: (pop.popdown(), self._open_day_plan(iso_date)))
        
        box.append(btn_add); box.append(btn_view); pop.set_child(box); pop.popup(); self.active_day_popover = pop

    def _open_new_task_for_date(self, iso_date):
        self.task_form.clear()
        self.task_form.entry_deadline.set_text(iso_date)
        self.mode_stack.set_visible_child_name("form")

    def _open_day_plan(self, iso_date):
        self.calendar.day_plan_date = date.fromisoformat(iso_date)
        self.calendar.render()
        self.mode_stack.set_visible_child_name("calendar")

    def _quick_update_status(self, task_id, status):
        task = get_task_by_id(task_id)
        if task:
            update_task(
                task_id=task_id,
                title=task.get("title") or "—",
                description=task.get("description"),
                tag=task.get("tag"),
                status=status,
                priority=task.get("priority") or "normal",
                deadline=task.get("deadline"),
                reminder_at=task.get("reminder_at")
            )
            update_last_interaction(task_id)
            self._load_tasks()

    # --- Notification Action Handlers ---

    def _on_action_task_done(self, _action, param):
        task_id = param.get_int32()
        self._quick_update_status(task_id, STATUS_DONE)
        self.present()

    def _on_action_task_delay_1h(self, _action, param):
        task_id = param.get_int32()
        task = get_task_by_id(task_id)
        if task:
            try:
                # Add 1 hour to deadline
                dl = task.get("deadline")
                if dl:
                    if len(dl) > 10:
                        dt = datetime.strptime(dl, "%Y-%m-%d %H:%M")
                    else:
                        dt = datetime.strptime(dl, "%Y-%m-%d").replace(hour=datetime.now().hour, minute=0)
                    new_dl = (dt + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
                    
                    update_task(
                        task_id=task_id,
                        title=task["title"],
                        description=task["description"],
                        tag=task["tag"],
                        status=task["status"],
                        priority=task["priority"],
                        deadline=new_dl,
                        reminder_at=task["reminder_at"]
                    )
                    self._load_tasks()
            except Exception: pass
        self.present()

    def _on_action_task_delay_day(self, _action, param):
        task_id = param.get_int32()
        self._postpone_task(task_id)
        self.present()

    def _on_action_task_open(self, _action, param):
        task_id = param.get_int32()
        self._open_full_task_view(task_id)
        self.present()
        
    def _check_background_notifications(self):
        """Periodically check for reminders and overdue tasks with escalation logic."""
        now = datetime.now()
        now_iso = now.strftime("%Y-%m-%dT%H:%M")
        from app.notifications import notify_reminder, notify_overdue
        
        updated = False
        
        for task in self.all_tasks:
            if task.status in {STATUS_DONE, STATUS_CANCELLED}:
                continue
                
            # 1. Determine if task is overdue using smart logic
            is_overdue = task.effective_status == STATUS_OVERDUE
            
            # 2. Check for initial reminder_at
            should_notify = False
            notif_type = "reminder"
            
            if task.reminder_at and task.reminder_at <= now_iso and not task.reminder_shown:
                should_notify = True
                notif_type = "reminder"
            elif is_overdue:
                # If overdue, we check if we should notify for the first time or escalate
                if not task.reminder_shown: # First time overdue notification
                    should_notify = True
                    notif_type = "overdue_init"
                elif task.reminder_count < MAX_REMINDERS:
                    # Escalation check
                    if task.last_reminder_at:
                        last_notif_time = datetime.fromisoformat(task.last_reminder_at)
                        mins_since = (now - last_notif_time).total_seconds() / 60
                        
                        if mins_since >= REMINDER_REPEAT_MINS:
                            # Check for interaction
                            user_interacted = False
                            if task.last_interaction_at:
                                interaction_time = datetime.fromisoformat(task.last_interaction_at)
                                if interaction_time > last_notif_time:
                                    user_interacted = True
                            
                            if not user_interacted:
                                should_notify = True
                                notif_type = "escalated"

            if should_notify:
                if notif_type == "reminder":
                    notify_reminder(task.id, task.title)
                    from app.database import mark_reminder_shown
                    mark_reminder_shown(task.id)
                else:
                    notify_overdue(task.id, task.title)
                    # For overdue, also mark reminder_shown so we don't trigger simple reminder
                    from app.database import mark_reminder_shown
                    mark_reminder_shown(task.id)
                
                # Update tracking
                new_count = task.reminder_count + 1
                update_reminder_tracking(task.id, new_count, now.isoformat())
                updated = True

        if updated:
            self._load_tasks()

        return True # Keep timeout running



    def _on_destroy(self, _window):
        if self._notification_timer_id:
            GLib.Source.remove(self._notification_timer_id)
            self._notification_timer_id = 0

    def _on_focus_toggle(self, btn):
        active = btn.get_active()
        app = self.get_application()
        if hasattr(app, "set_focus_mode"):
            app.set_focus_mode(active)
            if active:
                btn.set_icon_name("notifications-disabled-symbolic")
                btn.set_tooltip_text("Вимкнути Фокус")
            else:
                btn.set_icon_name("preferences-system-notifications-symbolic")
                btn.set_tooltip_text("Увімкнути Фокус")

    def _on_hide_to_tray(self, _btn):
        print("Window: Tray disabled. Cannot hide.")
        # self.hide()

    def _delete_task_confirm(self, task_id):

        delete_task(task_id)
        self._load_tasks()
        self.mode_stack.set_visible_child_name("calendar")
