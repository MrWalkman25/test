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
            is_done INTEGER NOT NULL DEFAULT 0,
            deadline TEXT,
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

    if "deadline" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN deadline TEXT")

    if "created_at" not in existing_columns:
        cursor.execute(
            "ALTER TABLE tasks ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"
        )
        cursor.execute(
            "UPDATE tasks SET created_at = ? WHERE created_at = ''",
            (datetime.now(timezone.utc).isoformat(),),
        )


def add_task(title: str, description: str | None, deadline: str | None) -> int:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        "INSERT INTO tasks (title, description, deadline, created_at) VALUES (?, ?, ?, ?)",
        (
            title,
            description,
            deadline,
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
        "SELECT id, title, description, deadline, created_at FROM tasks ORDER BY id DESC"
    )
    rows = cursor.fetchall()

    connection.close()
    return [
        {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "deadline": row[3],
            "created_at": row[4],
        }
        for row in rows
    ]


def update_task(task_id: int, title: str, description: str | None, deadline: str | None) -> None:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE tasks
        SET title = ?, description = ?, deadline = ?
        WHERE id = ?
        """,
        (title, description, deadline, task_id),
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
        "SELECT id, title, description, deadline, created_at FROM tasks WHERE id = ?",
        (task_id,),
    )
    row = cursor.fetchone()

    connection.close()
    if row is None:
        return None

    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "deadline": row[3],
        "created_at": row[4],
    }
