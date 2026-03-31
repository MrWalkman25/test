import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio

from app.gtk.window import TaskManagerGtkWindow
from app.gtk.tray import TrayManager
from app.focus import FocusManager
import logging

logger = logging.getLogger(__name__)



class TaskManagerGtkApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="com.local.taskmanager")
        self.tray = TrayManager(self)
        self.focus = FocusManager(self)
        self._setup_actions()

    def _setup_actions(self):
        # Action: present (to bring window to front)
        action_present = Gio.SimpleAction.new("present", None)
        action_present.connect("activate", lambda *_: self.do_activate())
        self.add_action(action_present)

        # Action: focus-off (to turn off focus mode)
        action_focus_off = Gio.SimpleAction.new("focus-off", None)
        action_focus_off.connect("activate", lambda *_: self.set_focus_mode(False))
        self.add_action(action_focus_off)

        # Action: quit
        action_quit = Gio.SimpleAction.new("quit", None)
        action_quit.connect("activate", lambda *_: self.quit())
        self.add_action(action_quit)

    def set_focus_mode(self, active: bool):
        """Main API for toggling Focus Mode."""
        if active:
            self.focus.enable_focus_dnd()
            self.tray.set_tray_mode("focus_active")
            logger.info("Focus mode activated.")
        else:
            self.focus.restore_previous_dnd_state()
            self.tray.set_tray_mode("normal")
            logger.info("Focus mode deactivated.")

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = TaskManagerGtkWindow(application=self)
        window.present()
