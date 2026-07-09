"""Calendar platform: separate calendars for due dates and deadlines."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import TodoistCoordinator
from .model import TodoistTask


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Todoist",
        manufacturer="Todoist",
        model="Tasks",
    )


def _as_datetime(value: date | datetime) -> datetime:
    """Coerce a date or datetime to an aware local datetime for comparisons."""
    if isinstance(value, datetime):
        return dt_util.as_local(value)
    return dt_util.start_of_local_day(value)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the due-date and deadline calendars."""
    coordinator: TodoistCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            TodoistDueCalendar(coordinator, entry),
            TodoistDeadlineCalendar(coordinator, entry),
        ]
    )


class _TodoistCalendarBase(CoordinatorEntity[TodoistCoordinator], CalendarEntity):
    """Shared logic for turning tasks into calendar events."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TodoistCoordinator,
        entry: ConfigEntry,
        kind: str,
        label: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._kind = kind
        self._attr_name = label
        self._attr_unique_id = f"{entry.entry_id}_calendar_{kind}"
        self._attr_device_info = _device_info(entry)

    def _task_date(self, task: TodoistTask) -> Optional[date | datetime]:
        """Return the date this calendar represents for the task."""
        raise NotImplementedError

    def _event_for(self, task: TodoistTask) -> Optional[CalendarEvent]:
        value = self._task_date(task)
        if value is None:
            return None

        # Shared cross-integration event contract (see the personal `tasks`
        # integration's calendar.py): priority is carried both as a "P{n} · "
        # summary prefix (for display + summary keyword matching) and as a
        # "Priority: P{n}" description line, so calendar blueprints behave
        # identically no matter which integration synced the event.
        label = task.priority_label
        summary = f"{label} · {task.content}" if label else task.content

        parts = []
        if label:
            parts.append(f"Priority: {label}")
        if task.project_name:
            parts.append(f"Project: {task.project_name}")
        if task.labels:
            parts.append("Labels: " + ", ".join(task.labels))
        if task.description:
            parts.append(task.description)
        description = "\n".join(parts)

        if isinstance(value, datetime):
            start: date | datetime = dt_util.as_local(value)
            end: date | datetime = start + timedelta(hours=1)
        else:
            start = value
            end = value + timedelta(days=1)

        return CalendarEvent(
            summary=summary,
            start=start,
            end=end,
            description=description,
            uid=f"{self._kind}_{task.id}",
        )

    def _event_pairs(self) -> list[tuple[CalendarEvent, TodoistTask]]:
        """All (event, task) pairs on this calendar, sorted by start."""
        pairs: list[tuple[CalendarEvent, TodoistTask]] = []
        for task in self.coordinator.data or []:
            event = self._event_for(task)
            if event is not None:
                pairs.append((event, task))
        pairs.sort(key=lambda p: _as_datetime(p[0].start))
        return pairs

    def _upcoming(self) -> list[tuple[CalendarEvent, TodoistTask]]:
        """(event, task) pairs whose event hasn't ended yet, soonest first."""
        now = dt_util.now()
        return [p for p in self._event_pairs() if _as_datetime(p[0].end) > now]

    @property
    def event(self) -> Optional[CalendarEvent]:
        """Return the current or next upcoming event (drives entity state)."""
        upcoming = self._upcoming()
        return upcoming[0][0] if upcoming else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return events within the requested range."""
        return [
            ev
            for ev, _task in self._event_pairs()
            if start_date <= _as_datetime(ev.start) < end_date
        ]

    @property
    def extra_state_attributes(self) -> dict:
        """Todoist-style attributes reflecting the current/next event.

        Matches the `tasks` integration's calendar attributes so both expose
        the same shape: config_entry_id, all_tasks, priority, overdue,
        due_today.
        """
        now = dt_util.now()
        today = now.date()
        upcoming = self._upcoming()
        attrs: dict = {
            "config_entry_id": self._entry.entry_id,
            "all_tasks": [ev.summary for ev, _ in upcoming],
            "priority": None,
            "overdue": False,
            "due_today": False,
        }
        if upcoming:
            event, task = upcoming[0]
            start = _as_datetime(event.start)
            attrs["priority"] = task.priority_rank
            attrs["overdue"] = start < now
            attrs["due_today"] = start.date() == today
        return attrs


class TodoistDueCalendar(_TodoistCalendarBase):
    """Calendar of task due dates."""

    def __init__(self, coordinator: TodoistCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "due", "Due Dates")

    def _task_date(self, task: TodoistTask) -> Optional[date | datetime]:
        return task.due


class TodoistDeadlineCalendar(_TodoistCalendarBase):
    """Calendar of task deadlines."""

    def __init__(self, coordinator: TodoistCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "deadline", "Deadlines")

    def _task_date(self, task: TodoistTask) -> Optional[date | datetime]:
        return task.deadline
