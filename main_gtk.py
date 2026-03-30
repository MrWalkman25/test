from app.database import init_db
from app.gtk.app import TaskManagerGtkApp


def main() -> None:
    init_db()
    app = TaskManagerGtkApp()
    app.run([])


if __name__ == "__main__":
    main()
