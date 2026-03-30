# Local Task Manager (v0.1 skeleton)

Мінімальний каркас desktop-застосунку на **Python + PySide6 + SQLite**.

## Що вже є
- Головне вікно з:
  - заголовком
  - полем для назви задачі
  - кнопкою "Додати"
  - порожнім списком задач
- Ініціалізація SQLite при запуску
- Автоматичне створення таблиці `tasks`

## Запуск
1. Перейдіть у папку проєкту:
   ```bash
   cd /workspace/test
   ```
2. (Рекомендовано) створіть віртуальне середовище:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Встановіть залежності:
   ```bash
   pip install -r requirements.txt
   ```
4. Запустіть програму:
   ```bash
   python3 main.py
   ```

Після першого запуску в корені проєкту з'явиться файл `tasks.db`.
