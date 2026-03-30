# Local Task Manager

Локальний desktop task manager (поточна версія на PySide6 + SQLite) + паралельний GTK skeleton для міграції.

## Основний запуск поточної Qt-версії
```bash
./start.sh
```

## Запуск GTK skeleton (перший етап міграції)
```bash
./start_gtk.sh
```

### Системні пакети для GTK4 + libadwaita (Ubuntu / Zorin OS)
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

## Що вже є в GTK skeleton
- `Adw.Application` + `Adw.ApplicationWindow`
- HeaderBar
- двоколонковий layout:
  - вузька ліва панель (місце під фільтри + список задач + кнопка нової задачі)
  - велика права область (Stack: calendar/details/new placeholders)
- читання задач із поточної SQLite БД та показ у лівому списку

## Legacy-скрипти
- `setup.sh` і `run.sh` залишені для сумісності.

## Нагадування (Linux)
- Для системних сповіщень використовується команда `notify-send`.
- На більшості Linux-дистрибутивів вона доступна через пакет `libnotify-bin`.

Після першого запуску в корені проєкту з'явиться файл `tasks.db`.
