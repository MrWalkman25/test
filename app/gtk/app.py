import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw

from app.gtk.window import TaskManagerGtkWindow


class TaskManagerGtkApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="com.local.taskmanager")

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = TaskManagerGtkWindow(application=self)
        window.present()
