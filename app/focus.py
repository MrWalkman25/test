import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio
import logging

logger = logging.getLogger(__name__)

class FocusManager:
    GSETTINGS_PATH = "org.gnome.desktop.notifications"
    GSETTINGS_KEY = "show-banners"

    def __init__(self, app) -> None:
        self.app = app
        self._settings = self._get_settings()
        self.previous_dnd_state = None
        self.is_focus_active = False

    def _get_settings(self):
        """Safe access to GSettings."""
        try:
            # Check if schema exists
            schemas = Gio.SettingsSchemaSource.get_default().list_schemas(True)[0]
            if self.GSETTINGS_PATH in schemas:
                return Gio.Settings.new(self.GSETTINGS_PATH)
        except Exception as e:
            logger.warning(f"Could not initialize GSettings for GNOME notifications: {e}")
        return None

    def enable_focus_dnd(self):
        """Save current notification state and enable Do Not Disturb."""
        if not self._settings:
            logger.warning("GSettings not available. Focus DND skipped.")
            return

        try:
            # 1. Store previous state
            self.previous_dnd_state = self._settings.get_boolean(self.GSETTINGS_KEY)
            
            # 2. Disable banners
            self._settings.set_boolean(self.GSETTINGS_KEY, False)
            self.is_focus_active = True
            
            logger.info(f"GNOME Focus DND enabled. Saved state: {self.previous_dnd_state}")
        except Exception as e:
            logger.error(f"Failed to enable GNOME DND: {e}")

    def restore_previous_dnd_state(self):
        """Restore notifications to their previous state."""
        if not self._settings or self.previous_dnd_state is None:
            logger.warning("No state to restore.")
            return

        try:
            self._settings.set_boolean(self.GSETTINGS_KEY, self.previous_dnd_state)
            self.is_focus_active = False
            
            logger.info(f"GNOME Focus DND restored to: {self.previous_dnd_state}")
            self.previous_dnd_state = None
        except Exception as e:
            logger.error(f"Failed to restore GNOME DND: {e}")

    def get_current_dnd_status(self):
        """Read current system DND status."""
        if not self._settings:
            return "Unavailable"
        return "Banners OFF" if not self._settings.get_boolean(self.GSETTINGS_KEY) else "Banners ON"
