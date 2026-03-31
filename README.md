# Local Task Manager (GTK)

Локальний desktop task manager на **GTK4 + libadwaita** з SQLite.

## Системні пакети (Ubuntu / Zorin / Debian-based)
```bash
sudo apt update
sudo apt install -y \
  python3-gi \
  python3-gi-cairo \
  gir1.2-gtk-4.0 \
  gir1.2-adw-1 \
  libadwaita-1-0 \
  libgtk-4-1 \
  libnotify-bin
```

## Запуск (основний сценарій)
```bash
./start.sh
```

## Альтернативні скрипти
- `./setup.sh` — створити `.venv` і встановити pip-залежності.
- `./run.sh` — запуск з уже створеного `.venv`.
- `./start_gtk.sh` — legacy alias на `./start.sh`.

## Що більше не використовується
- Qt / PySide6 UI видалено з основного шляху запуску.
- `main.py` тепер запускає GTK-версію як основну.

## Дані
- SQLite база: `tasks.db` у корені проєкту (створюється автоматично).
