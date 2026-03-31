from dataclasses import dataclass
from datetime import datetime


STATUS_NEW = "Нове"
STATUS_IN_PROGRESS = "В процесі"
STATUS_DONE = "Завершене"
STATUS_CANCELLED = "Відмінене"
STATUS_OVERDUE = "Протерміноване"

DAY_OVERDUE_HOUR = 18  # Tasks without time are overdue after this hour
REMINDER_REPEAT_MINS = 10
MAX_REMINDERS = 3


@dataclass
class Task:
    id: int
    title: str
    description: str | None = None
    tag: str | None = None
    status: str = STATUS_NEW
    priority: str = "normal"
    deadline: str | None = None
    reminder_at: str | None = None
    reminder_shown: bool = False
    
    # New tracking fields
    last_interaction_at: str | None = None
    reminder_count: int = 0
    last_reminder_at: str | None = None
    
    created_at: str = ""

    @property
    def effective_status(self) -> str:
        if self.status in {STATUS_DONE, STATUS_CANCELLED}:
            return self.status

        if not self.deadline:
            return self.status

        now = datetime.now()
        try:
            if len(self.deadline) > 10:  # Has time
                dt = datetime.strptime(self.deadline, "%Y-%m-%d %H:%M")
            else:  # Date only
                dt = datetime.strptime(self.deadline, "%Y-%m-%d").replace(hour=DAY_OVERDUE_HOUR)
            
            if now > dt:
                return STATUS_OVERDUE
        except ValueError:
            pass

        return self.status

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data.get("id", 0),
            title=data.get("title", ""),
            description=data.get("description"),
            tag=data.get("tag"),
            status=data.get("status", STATUS_NEW),
            priority=data.get("priority", "normal"),
            deadline=data.get("deadline"),
            reminder_at=data.get("reminder_at"),
            reminder_shown=bool(data.get("reminder_shown", 0)),
            last_interaction_at=data.get("last_interaction_at"),
            reminder_count=data.get("reminder_count", 0),
            last_reminder_at=data.get("last_reminder_at"),
            created_at=data.get("created_at", ""),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "tag": self.tag,
            "status": self.status,
            "priority": self.priority,
            "deadline": self.deadline,
            "reminder_at": self.reminder_at,
            "reminder_shown": int(self.reminder_shown),
            "last_interaction_at": self.last_interaction_at,
            "reminder_count": self.reminder_count,
            "last_reminder_at": self.last_reminder_at,
            "created_at": self.created_at,
        }
