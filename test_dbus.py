import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio
def cb(*args, **kwargs):
    print("ARGS:", args)
    print("KWARGS:", kwargs)
    return gi.repository.GLib.Variant('s', 'foo')

reg = Gio.bus_get_sync(Gio.BusType.SESSION, None).register_object(
    "/test",
    Gio.DBusNodeInfo.new_for_xml("""
    <node>
      <interface name="org.test">
        <property name="Prop" type="s" access="read"/>
      </interface>
    </node>
    """).interfaces[0],
    None,
    cb,
    None
)
import time
Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None,
                               "org.freedesktop.DBus", "/test", "org.test", None).get_cached_property("Prop")
