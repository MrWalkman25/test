import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "tasks.db"

from app.models import (
    STATUS_NEW,
    STATUS_IN_PROGRESS,
    STATUS_DONE,
    STATUS_CANCELLED,
    STATUS_OVERDUE,
)



def init_db() -> None:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            tag TEXT,
            status TEXT NOT NULL DEFAULT 'Нове',
            priority TEXT NOT NULL DEFAULT 'normal',
            is_done INTEGER NOT NULL DEFAULT 0,
            deadline TEXT,
            reminder_at TEXT,
            reminder_shown INTEGER NOT NULL DEFAULT 0,
            overdue_notified INTEGER NOT NULL DEFAULT 0,
            last_interaction_at TEXT,
            reminder_count INTEGER NOT NULL DEFAULT 0,
            last_reminder_at TEXT,
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

    if "tag" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN tag TEXT")

    if "status" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN status TEXT NOT NULL DEFAULT 'Нове'")

    if "priority" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'")

    if "deadline" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN deadline TEXT")

    if "reminder_at" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN reminder_at TEXT")

    if "reminder_shown" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN reminder_shown INTEGER NOT NULL DEFAULT 0")

    if "overdue_notified" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN overdue_notified INTEGER NOT NULL DEFAULT 0")

    if "last_interaction_at" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN last_interaction_at TEXT")

    if "reminder_count" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN reminder_count INTEGER NOT NULL DEFAULT 0")

    if "last_reminder_at" not in existing_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN last_reminder_at TEXT")


    if "created_at" not in existing_columns:
        cursor.execute(
            "ALTER TABLE tasks ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"
        )
        cursor.execute(
            "UPDATE tasks SET created_at = ? WHERE created_at = ''",
            (datetime.now(timezone.utc).isoformat(),),
        )

    cursor.execute("UPDATE tasks SET status = 'Нове' WHERE status = 'inbox'")
    cursor.execute("UPDATE tasks SET status = 'В процесі' WHERE status = 'in_progress'")
    cursor.execute("UPDATE tasks SET status = 'Завершене' WHERE status = 'done'")


def add_task(
    title: str,
    description: str | None,
    tag: str | None,
    deadline: str | None,
    reminder_at: str | None,
    priority: str = "normal",
) -> int:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO tasks (
            title, description, tag, status, priority,
            deadline, reminder_at, reminder_shown, overdue_notified, 
            last_interaction_at, reminder_count, last_reminder_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?, 0, NULL, ?)

        """,
        (
            title,
            description,
            tag,
            STATUS_NEW,
            priority,
            deadline,
            reminder_at,
            datetime.now(timezone.utc).isoformat(), # last_interaction_at
            datetime.now(timezone.utc).isoformat(), # created_at
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
            id, title, description, tag, status, priority,
            deadline, reminder_at, reminder_shown, overdue_notified, 
            last_interaction_at, reminder_count, last_reminder_at, created_at
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
    tag: str | None,
    status: str,
    priority: str,
    deadline: str | None,
    reminder_at: str | None,
) -> None:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    safe_status = _safe_manual_status(status)

    cursor.execute(
        """
        UPDATE tasks
        SET
            title = ?,
            description = ?,
            tag = ?,
            status = ?,
            priority = ?,
            deadline = ?,
            reminder_at = ?,
            reminder_shown = CASE
                WHEN COALESCE(reminder_at, '') <> COALESCE(?, '') THEN 0
                ELSE reminder_shown
            END,
            overdue_notified = CASE
                WHEN COALESCE(deadline, '') <> COALESCE(?, '') THEN 0
                ELSE overdue_notified
            END,
            reminder_count = CASE
                WHEN COALESCE(reminder_at, '') <> COALESCE(?, '') THEN 0
                ELSE reminder_count
            END
        WHERE id = ?

        """,
        (
            title,
            description,
            tag,
            safe_status,
            priority,
            deadline,
            reminder_at,
            reminder_at,
            deadline,
            reminder_at,
            task_id,
        ),

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
            id, title, description, tag, status, priority,
            deadline, reminder_at, reminder_shown, overdue_notified,
            last_interaction_at, reminder_count, last_reminder_at, created_at
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
            id, title, description, tag, status, priority,
            deadline, reminder_at, reminder_shown, overdue_notified,
            last_interaction_at, reminder_count, last_reminder_at, created_at
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
    cursor.execute("UPDATE tasks SET reminder_shown = 1 WHERE id = ?", (task_id,))
    connection.commit()
    connection.close()


def get_overdue_tasks_to_notify(now_iso: str) -> list[dict]:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            id, title, description, tag, status, priority,
            deadline, reminder_at, reminder_shown, overdue_notified,
            last_interaction_at, reminder_count, last_reminder_at, created_at
        FROM tasks
        WHERE deadline IS NOT NULL
          AND deadline != ''
          AND overdue_notified = 0
          AND status NOT IN ('Завершене', 'Відмінене')
          AND deadline <= ?
        ORDER BY deadline ASC
        """,
        (now_iso,),
    )
    rows = cursor.fetchall()
    connection.close()
    return [_row_to_task(row) for row in rows]


def mark_overdue_notified(task_id: int) -> None:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    cursor.execute("UPDATE tasks SET overdue_notified = 1 WHERE id = ?", (task_id,))
    connection.commit()
    connection.close()



def _safe_manual_status(status: str) -> str:
    if status == STATUS_OVERDUE:
        return STATUS_NEW
    if status in {STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_CANCELLED}:
        return status
    return STATUS_NEW


def update_last_interaction(task_id: int) -> None:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE tasks SET last_interaction_at = ? WHERE id = ?",
        (datetime.now().isoformat(), task_id),
    )
    connection.commit()
    connection.close()


def update_reminder_tracking(task_id: int, count: int, last_time: str) -> None:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE tasks SET reminder_count = ?, last_reminder_at = ? WHERE id = ?",
        (count, last_time, task_id),
    )
    connection.commit()
    connection.close()


def _row_to_task(row: tuple) -> dict:
    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "tag": row[3],
        "status": row[4],
        "priority": row[5],
        "deadline": row[6],
        "reminder_at": row[7],
        "reminder_shown": row[8],
        "overdue_notified": row[9],
        "last_interaction_at": row[10],
        "reminder_count": row[11],
        "last_reminder_at": row[12],
        "created_at": row[13],
    }



def duplicate_task(task_id: int) -> int:
    task = get_task_by_id(task_id)
    if not task:
        return 0

    return add_task(
        title=f"{task['title']} (Копія)",
        description=task['description'],
        tag=task['tag'],
        deadline=task['deadline'],
        reminder_at=task['reminder_at'],
        priority=task['priority']
    )
