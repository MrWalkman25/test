import gi
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib
import logging
import os

logger = logging.getLogger(__name__)

# Absolute paths for icons
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS_DIR = os.path.join(BASE_DIR, "app", "assets")
ICON_NORMAL = "tray_normal.svg"
ICON_FOCUS = "tray_focus.svg"

# --- DBus XML Interfaces ---

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiia(ii))ss)" access="read"/>
    <method name="ContextMenu">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="Activate">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="Scroll">
      <arg type="i" name="delta" direction="in"/>
      <arg type="s" name="orientation" direction="in"/>
    </method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus">
      <arg type="s" name="status" direction="out"/>
    </signal>
  </interface>
</node>
"""

DBUS_MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" name="parentId" direction="in"/>
      <arg type="i" name="recursionDepth" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="u" name="revision" direction="out"/>
      <arg type="(ia{sv}av)" name="layout" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="a(ia{sv})" name="properties" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="name" direction="in"/>
      <arg type="v" name="value" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="eventId" direction="in"/>
      <arg type="v" name="data" direction="in"/>
      <arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" name="id" direction="in"/>
      <arg type="b" name="needUpdate" direction="out"/>
    </method>
    <signal name="LayoutUpdated">
      <arg type="u" name="revision"/>
      <arg type="i" name="parentId"/>
    </signal>
  </interface>
</node>
"""

class TrayManager:
    DBUS_PATH = "/org/ayatana/NotificationItem/taskmanager"
    MENU_PATH = "/org/ayatana/NotificationItem/taskmanager/Menu"
    
    def __init__(self, app) -> None:
        self.app = app
        self.bus = None
        self.reg_id = None
        self.menu_reg_id = None
        
        # State: "normal" | "focus_active"
        self.current_mode = "normal"
        self.tooltip_text = "Task Manager"
        self.icon_name = "org.gnome.Todo-symbolic"
        
        GLib.idle_add(self._start_dbus)

    def _start_dbus(self):
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            
            # --- Register SNI ---
            sni_node = Gio.DBusNodeInfo.new_for_xml(SNI_XML)
            self.reg_id = self.bus.register_object(
                self.DBUS_PATH,
                sni_node.interfaces[0],
                self._handle_sni_method_call,
                self._handle_sni_get_property,
                None
            )
            
            # --- Register Menu ---
            menu_node = Gio.DBusNodeInfo.new_for_xml(DBUS_MENU_XML)
            self.menu_reg_id = self.bus.register_object(
                self.MENU_PATH,
                menu_node.interfaces[0],
                self._handle_menu_method_call,
                self._handle_menu_get_property,
                None
            )
            
            # --- Notify Watcher ---
            self._register_with_watcher()
            print("Tray: Registered DBus SNI at " + self.DBUS_PATH)
            
        except Exception as e:
            print(f"Tray: DBus initialization failed: {e}")

    def _register_with_watcher(self):
        try:
            msg = Gio.DBusMessage.new_method_call(
                "org.kde.StatusNotifierWatcher",
                "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher",
                "RegisterStatusNotifierItem"
            )
            msg.set_body(GLib.Variant("(s)", [self.DBUS_PATH]))
            # Fix: Gio.DBusConnection.send_message in Python often expects 2 args
            self.bus.send_message(msg, Gio.DBusSendMessageFlags.NONE)
            print(f"Tray: SNI registration sent for {self.DBUS_PATH}")
        except Exception as e:
            print(f"Tray: Could not register with StatusNotifierWatcher: {e}")

    # --- SNI Property/Method Handlers ---

    def _handle_sni_get_property(self, connection, sender, path, interface, name, error, user_data):
        props = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", "taskmanager"),
            "Title": GLib.Variant("s", "Task Manager"),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            "IconThemePath": GLib.Variant("s", ASSETS_DIR),
            "Menu": GLib.Variant("o", self.MENU_PATH),
            "ItemIsMenu": GLib.Variant("b", True),
            "IconName": GLib.Variant("s", self.icon_name),
            "ToolTip": GLib.Variant("(sa(iiia(ii))ss)", (
                self.icon_name, [], self.tooltip_text, ""
            ))
        }
        return props.get(name)

    def _handle_sni_method_call(self, connection, sender, path, interface, name, params, invocation, user_data):
        if name == "Activate":
            GLib.idle_add(lambda: (self.app.activate(), print("Tray: App restored via tray click")))
        elif name in ("SecondaryActivate", "ContextMenu"):
            # Signal the host to show the menu
            pass
        invocation.return_value(None)

    # --- DBusMenu Property/Method Handlers ---

    def _handle_menu_get_property(self, connection, sender, path, interface, name, error, user_data):
        props = {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", [])
        }
        return props.get(name)

    def _handle_menu_method_call(self, connection, sender, path, interface, name, params, invocation, user_data):
        if name == "GetLayout":
            # [id, properties, children]
            layout = (0, {
                "children-display": GLib.Variant("s", "submenu")
            }, [
                GLib.Variant("(ia{sv}av)", (1, {"label": GLib.Variant("s", "Відкрити застосунок")}, [])),
                GLib.Variant("(ia{sv}av)", (2, {"label": GLib.Variant("s", "Вийти з фокусу")}, [])),
                GLib.Variant("(ia{sv}av)", (0, {"type": GLib.Variant("s", "separator")}, [])),
                GLib.Variant("(ia{sv}av)", (3, {"label": GLib.Variant("s", "Вийти з програми")}, []))
            ])
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (1, layout)))
            
        elif name == "Event":
            id_arg, event_id, data, timestamp = params
            if event_id == "clicked":
                if id_arg == 1: GLib.idle_add(lambda: self.app.activate())
                elif id_arg == 2: GLib.idle_add(lambda: self.app.set_focus_mode(False))
                elif id_arg == 3: GLib.idle_add(lambda: self.app.quit())
            invocation.return_value(None)
        else:
            invocation.return_value(None)

    # --- Public API ---

    def set_tray_mode(self, mode: str):
        self.current_mode = mode
        if mode == "focus_active":
            self.icon_name = ICON_FOCUS.split(".")[0] # Just the name if IconThemePath used
            self.tooltip_text = "Фокус увімкнено"
        else:
            self.icon_name = ICON_NORMAL.split(".")[0]
            self.tooltip_text = "Task Manager"
            
        if self.bus:
            # Emit signals to notify host of changes
            self.bus.emit_signal(None, self.DBUS_PATH, "org.kde.StatusNotifierItem", "NewIcon", None)
            self.bus.emit_signal(None, self.DBUS_PATH, "org.kde.StatusNotifierItem", "NewToolTip", None)
            print(f"Tray: Icon changed to {self.icon_name} (Focus: {mode})")
            
        logger.info(f"Tray mode set to: {mode}")

    def log_status(self):
        return f"Tray: DBus SNI active at {self.DBUS_PATH}"
