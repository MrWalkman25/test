import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "tasks.db"


def init_db() -> None:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'inbox',
            priority TEXT NOT NULL DEFAULT 'normal',
            is_done INTEGER NOT NULL DEFAULT 0,
            deadline TEXT,
            reminder_at TEXT,
            reminder_shown INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )

    _apply_simple_migrations(cursor)

    connection.commit()
    connection.close()


def _apply_simple_migrations(cursor: sqlite3.Cursor) -> None:
    cursor.execute("PRAGMA table_info(tasks)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if "description" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN description TEXT")

    if "status" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN status TEXT NOT NULL DEFAULT 'inbox'")

    if "priority" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'")

    if "deadline" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN deadline TEXT")

    if "reminder_at" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN reminder_at TEXT")

    if "reminder_shown" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN reminder_shown INTEGER NOT NULL DEFAULT 0")

    if "created_at" not in existing_columns:
        cursor.execute(
            "ALTER TABLE tasks ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"
        )
        cursor.execute(
            "UPDATE tasks SET created_at = ? WHERE created_at = ''",
            (datetime.now(timezone.utc).isoformat(),),
        )


def add_task(
    title: str,
    description: str | None,
    deadline: str | None,
    reminder_at: str | None,
    priority: str = "normal",
) -> int:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO tasks (
            title, description, status, priority,
            deadline, reminder_at, reminder_shown, created_at
        )
        VALUES (?, ?, 'inbox', ?, ?, ?, 0, ?)
        """,
        (
            title,
            description,
            priority,
            deadline,
            reminder_at,
            datetime.now(timezone.utc).isoformat(),
        ),
    )

    task_id = cursor.lastrowid
    connection.commit()
    connection.close()
    return int(task_id)


def get_tasks() -> list[dict]:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id, title, description, status, priority,
            deadline, reminder_at, reminder_shown, created_at
        FROM tasks
        ORDER BY id DESC
        """
    )
    rows = cursor.fetchall()

    connection.close()
    return [_row_to_task(row) for row in rows]


def update_task(
    task_id: int,
    title: str,
    description: str | None,
    status: str,
    priority: str,
    deadline: str | None,
    reminder_at: str | None,
) -> None:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE tasks
        SET
            title = ?,
            description = ?,
            status = ?,
            priority = ?,
            deadline = ?,
            reminder_at = ?,
            reminder_shown = CASE
                WHEN COALESCE(reminder_at, '') <> COALESCE(?, '') THEN 0
                ELSE reminder_shown
            END
        WHERE id = ?
        """,
        (title, description, status, priority, deadline, reminder_at, reminder_at, task_id),
    )

    connection.commit()
    connection.close()


def delete_task(task_id: int) -> None:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    connection.commit()
    connection.close()


def get_task_by_id(task_id: int) -> dict | None:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id, title, description, status, priority,
            deadline, reminder_at, reminder_shown, created_at
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    )
    row = cursor.fetchone()

    connection.close()
    if row is None:
        return None

    return _row_to_task(row)


def get_due_reminders(now_iso: str) -> list[dict]:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id, title, description, status, priority,
            deadline, reminder_at, reminder_shown, created_at
        FROM tasks
        WHERE reminder_at IS NOT NULL
          AND reminder_at != ''
          AND reminder_shown = 0
          AND reminder_at <= ?
        ORDER BY reminder_at ASC
        """,
        (now_iso,),
    )
    rows = cursor.fetchall()

    connection.close()
    return [_row_to_task(row) for row in rows]


def mark_reminder_shown(task_id: int) -> None:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        "UPDATE tasks SET reminder_shown = 1 WHERE id = ?",
        (task_id,),
    )

    connection.commit()
    connection.close()


def _row_to_task(row: tuple) -> dict:
    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "status": row[3],
        "priority": row[4],
        "deadline": row[5],
        "reminder_at": row[6],
        "reminder_shown": row[7],
        "created_at": row[8],
    }
