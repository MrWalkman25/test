# Local Task Manager

Локальний desktop task manager на **Python + PySide6 + SQLite**.

## Швидкий старт (через скрипти)
1. Перейдіть у папку проєкту:
   ```bash
   cd /workspace/test
   ```
2. Зробіть перше налаштування:
   ```bash
   ./setup.sh
   ```
3. Запустіть застосунок:
   ```bash
   ./run.sh
   ```

## Що роблять скрипти
- `setup.sh`:
  - створює `.venv`
  - активує `.venv`
  - встановлює залежності з `requirements.txt`

- `run.sh`:
  - перевіряє, чи існує `.venv`
  - якщо `.venv` немає, показує повідомлення запустити `./setup.sh`
  - якщо `.venv` є, активує середовище і запускає `python3 main.py`

Після першого запуску в корені проєкту з'явиться файл `tasks.db`.
