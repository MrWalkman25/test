import logging

logger = logging.getLogger(__name__)

class TrayManager:
    DBUS_PATH = "/org/ayatana/NotificationItem/taskmanager"
    MENU_PATH = "/org/ayatana/NotificationItem/taskmanager/Menu"
    
    def __init__(self, app) -> None:
        self.app = app
        self.bus = None
        self.reg_id = None
        self.menu_reg_id = None
        
        # State
        self.current_mode = "normal"
        self.tooltip_text = "Task Manager"
        self.icon_name = "org.gnome.Todo-symbolic"
        
        logger.info("Tray integration is currently disabled for stability. (Safe Rollback)")

    def set_tray_mode(self, mode: str):
        self.current_mode = mode
        logger.info(f"Tray mode set to: {mode} (Tray disabled)")

    def log_status(self):
        return "Tray: DBus SNI disabled."
