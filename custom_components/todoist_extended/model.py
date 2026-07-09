"""Data model for the Todoist Extended integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

from homeassistant.util import dt as dt_util

from .const import API_PRIORITY_TO_LABEL, API_PRIORITY_TO_RANK


def _parse_due_value(due_raw: dict | None) -> tuple[Optional[date | datetime], Optional[str], bool]:
    """Parse a Todoist v1 ``due`` object.

    In API v1 the ``date`` field is a string that holds EITHER a plain date
    (``YYYY-MM-DD``, all-day) OR a full datetime (contains ``T``). There is no
    separate ``datetime`` key like there was in REST v2.

    Returns ``(value, due_string, is_recurring)`` where ``value`` is a
    timezone-aware ``datetime`` for timed tasks, a ``date`` for all-day tasks,
    or ``None``.
    """
    if not due_raw:
        return None, None, False

    is_recurring = bool(due_raw.get("is_recurring"))
    due_string = due_raw.get("string")
    date_str = due_raw.get("date")
    if not date_str:
        return None, due_string, is_recurring

    if "T" in date_str:
        parsed = dt_util.parse_datetime(date_str)
        if parsed is not None:
            if parsed.tzinfo is None:
                # Floating due time — interpret as the user's local wall time.
                parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
            return dt_util.as_local(parsed), due_string, is_recurring

    try:
        return date.fromisoformat(date_str[:10]), due_string, is_recurring
    except ValueError:
        return None, due_string, is_recurring


def _parse_deadline_value(deadline_raw: dict | None) -> Optional[date]:
    """Parse a Todoist v1 ``deadline`` object (date only)."""
    if not deadline_raw:
        return None
    date_str = deadline_raw.get("date")
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str[:10])
    except ValueError:
        return None


@dataclass
class TodoistTask:
    """A normalised Todoist task."""

    id: str
    content: str
    description: str
    project_id: Optional[str]
    project_name: Optional[str]
    priority_api: int
    labels: list[str]
    due: Optional[date | datetime]
    due_string: Optional[str]
    is_recurring: bool
    deadline: Optional[date]
    url: Optional[str]
    parent_id: Optional[str]

    @property
    def priority_label(self) -> str:
        """User-facing priority label (P1 = highest)."""
        return API_PRIORITY_TO_LABEL.get(self.priority_api, "P4")

    @property
    def priority_rank(self) -> int:
        """Sortable rank where 1 = highest (P1)."""
        return API_PRIORITY_TO_RANK.get(self.priority_api, 4)

    @classmethod
    def from_json(cls, data: dict[str, Any], project_names: dict[str, str]) -> "TodoistTask":
        """Build a task from a raw API v1 task dict."""
        due, due_string, is_recurring = _parse_due_value(data.get("due"))
        project_id = data.get("project_id")
        project_id = str(project_id) if project_id is not None else None
        return cls(
            id=str(data["id"]),
            content=data.get("content") or "",
            description=data.get("description") or "",
            project_id=project_id,
            project_name=project_names.get(project_id) if project_id else None,
            priority_api=int(data.get("priority", 1) or 1),
            labels=list(data.get("labels") or []),
            due=due,
            due_string=due_string,
            is_recurring=is_recurring,
            deadline=_parse_deadline_value(data.get("deadline")),
            url=data.get("url"),
            parent_id=(str(data["parent_id"]) if data.get("parent_id") else None),
        )

    def due_date_only(self) -> Optional[date]:
        """Return the due value collapsed to a local date, if any."""
        if isinstance(self.due, datetime):
            return dt_util.as_local(self.due).date()
        if isinstance(self.due, date):
            return self.due
        return None

    def is_overdue(self, today: date) -> bool:
        """True if the due date is before today."""
        d = self.due_date_only()
        return d is not None and d < today

    def is_due_today(self, today: date) -> bool:
        """True if the due date is today."""
        return self.due_date_only() == today

    def to_dict(self, today: date) -> dict[str, Any]:
        """Serialise for use as a state attribute / in templates."""
        due_only = self.due_date_only()
        return {
            "id": self.id,
            "content": self.content,
            "description": self.description or None,
            "project": self.project_name,
            "project_id": self.project_id,
            "priority": self.priority_label,
            "priority_rank": self.priority_rank,
            "priority_api": self.priority_api,
            "labels": self.labels,
            "due": self.due.isoformat() if self.due else None,
            "due_date": due_only.isoformat() if due_only else None,
            "has_time": isinstance(self.due, datetime),
            "due_string": self.due_string,
            "is_recurring": self.is_recurring,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "overdue": self.is_overdue(today),
            "due_today": self.is_due_today(today),
            "url": self.url,
        }
