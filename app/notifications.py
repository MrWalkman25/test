import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio
import subprocess


def send_desktop_notification(title: str, message: str, task_id: int | None = None) -> bool:
    """Send desktop notification. Uses Gio.Notification if task_id provided for actions, fallback to notify-send."""
    
    if task_id is not None:
        try:
            # We use the application's default Gio.Application if possible
            # or just create a notification object.
            # In GTK context, it's better to use the application object, 
            # but we can also just send it via DBus.
            notification = Gio.Notification.new(title)
            notification.set_body(message)
            notification.set_priority(Gio.NotificationPriority.URGENT)
            
            # Interactive buttons
            # Actions are registered on the Application object in window.py
            notification.add_button("Закрити", f"app.task-done({task_id})")
            notification.add_button("+1 год", f"app.task-delay-1h({task_id})")
            notification.add_button("Завтра", f"app.task-delay-day({task_id})")
            
            # Click action (just open)
            notification.set_default_action(f"app.task-open({task_id})")
            
            app = Gio.Application.get_default()
            if app:
                app.send_notification(f"task-{task_id}", notification)
                return True
        except Exception as e:
            print(f"GNotification error: {e}")

    # Fallback/Default for simple cases
    try:
        subprocess.Popen(
            ["notify-send", title, message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except FileNotFoundError:
        return False


def notify_reminder(task_id: int, task_title: str):
    """Specific reminder notification with quick actions."""
    send_desktop_notification("Не проїби таск!", task_title, task_id=task_id)


def notify_overdue(task_id: int, task_title: str):
    """Specific overdue notification with quick actions."""
    send_desktop_notification("Ти проїбав таск!", f"{task_title} (дедлайн минув)", task_id=task_id)


def notify_test():
    """Debug test notification."""
    send_desktop_notification("Хуяк! Розслабся, перевірка", "Тут скоро будуть твої пройобані дедлайни")
