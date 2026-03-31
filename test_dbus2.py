import gi
gi.require_version('Gio', '2.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gio, GLib

class TrayManager:
    def _handle_sni_get_property(self, connection, sender, path, interface, name):
        print("Called get_property with", name)
        return GLib.Variant('s', 'Active')

tray = TrayManager()
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Status" type="s" access="read"/>
  </interface>
</node>
"""
sni_node = Gio.DBusNodeInfo.new_for_xml(SNI_XML)

bus.register_object(
    "/test1234",
    sni_node.interfaces[0],
    None,
    tray._handle_sni_get_property,
    None
)

import threading, dbus
def call_it():
    bus = dbus.SessionBus()
    obj = bus.get_object("org.freedesktop.DBus", "/test1234")
    try:
        obj.Get("org.kde.StatusNotifierItem", "Status", dbus_interface="org.freedesktop.DBus.Properties")
    except Exception as e:
        print("DBus Error:", e)

threading.Thread(target=call_it).start()
import time; time.sleep(1)
