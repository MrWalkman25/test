import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

def get_prop(connection, sender, path, interface, name):
    print("get_prop called with", name)
    return None

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
SNI_XML = "<node><interface name='org.test'><property name='Prop' type='s' access='read'/></interface></node>"
node = Gio.DBusNodeInfo.new_for_xml(SNI_XML)

bus.register_object("/test1234", node.interfaces[0], None, get_prop, None)

def call_it():
    res = bus.call_sync("org.freedesktop.DBus", "/test1234", "org.freedesktop.DBus.Properties", "Get",
                  GLib.Variant("(ss)", ("org.test", "Prop")), None, Gio.DBusCallFlags.NONE, -1, None)
    print("Called Get, res:", res)

GLib.idle_add(call_it)
GLib.MainLoop().run()
