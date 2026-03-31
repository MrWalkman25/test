# Local Task Manager (GTK)

Фінальна версія застосунку працює на **GTK4 + libadwaita**.

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

## Запуск
```bash
./start.sh
```

## Поточний стан
- Основний та єдиний UI: GTK/libadwaita.
- Запуск тільки через системний `python3`.
- `.venv`, Qt/PySide6 і legacy-скрипти більше не використовуються.

## Дані
- SQLite база: `tasks.db` у корені проєкту (створюється автоматично).
