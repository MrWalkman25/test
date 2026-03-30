import subprocess


def send_desktop_notification(title: str, message: str) -> bool:
    """Send Linux desktop notification through notify-send."""
    try:
        subprocess.run(
            ["notify-send", title, message],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except FileNotFoundError:
        return False
