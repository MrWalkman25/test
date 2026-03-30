import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk

from app.database import get_tasks


class TaskManagerGtkWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Local Task Manager (GTK Skeleton)")
        self.set_default_size(1200, 760)

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
        header.set_title_widget(Gtk.Label(label="GTK4 + libadwaita skeleton"))

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.append(header)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        # Left panel
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        left.set_size_request(300, -1)
        left.add_css_class("section")

        left_title = Gtk.Label(label="Tasks")
        left_title.set_xalign(0)
        left_title.add_css_class("panel-title")

        filters_placeholder = Gtk.Label(label="[Фільтри тут]")
        filters_placeholder.set_xalign(0)

        self.new_task_button = Gtk.Button(label="+ Нова задача")
        self.new_task_button.set_halign(Gtk.Align.FILL)

        self.tasks_listbox = Gtk.ListBox()
        self.tasks_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)

        left.append(left_title)
        left.append(filters_placeholder)
        left.append(self.new_task_button)
        left.append(self.tasks_listbox)

        # Right area (future stacked workspace)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right.add_css_class("section")

        right_title = Gtk.Label(label="Workspace")
        right_title.set_xalign(0)
        right_title.add_css_class("panel-title")

        self.mode_stack = Gtk.Stack()
        self.mode_stack.set_hexpand(True)
        self.mode_stack.set_vexpand(True)

        calendar_placeholder = Gtk.Label(label="Calendar view (placeholder)")
        details_placeholder = Gtk.Label(label="Task details / popover target (placeholder)")
        new_task_placeholder = Gtk.Label(label="New task view (placeholder)")

        self.mode_stack.add_titled(calendar_placeholder, "calendar", "Calendar")
        self.mode_stack.add_titled(details_placeholder, "details", "Details")
        self.mode_stack.add_titled(new_task_placeholder, "new", "New Task")

        stack_switcher = Gtk.StackSwitcher(stack=self.mode_stack)

        right.append(right_title)
        right.append(stack_switcher)
        right.append(self.mode_stack)

        content.append(left)
        content.append(right)

        root.append(content)
        self.set_content(root)

    def _load_tasks(self) -> None:
        tasks = get_tasks()

        for child in list(self.tasks_listbox):
            self.tasks_listbox.remove(child)

        for task in tasks:
            title = task.get("title") or "(без назви)"
            tag = task.get("tag")
            text = f"[{tag}] {title}" if tag else title

            row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            label = Gtk.Label(label=text)
            label.set_xalign(0)
            row_box.append(label)

            row = Gtk.ListBoxRow()
            row.set_child(row_box)
            self.tasks_listbox.append(row)
