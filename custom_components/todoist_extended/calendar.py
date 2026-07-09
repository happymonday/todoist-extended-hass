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

        parts = [f"Priority: {task.priority_label}"]
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
            summary=task.content,
            start=start,
            end=end,
            description=description,
            uid=f"{self._kind}_{task.id}",
        )

    def _all_events(self) -> list[CalendarEvent]:
        events = []
        for task in self.coordinator.data or []:
            event = self._event_for(task)
            if event is not None:
                events.append(event)
        return events

    @property
    def event(self) -> Optional[CalendarEvent]:
        """Return the next upcoming event (drives the entity state)."""
        cutoff = dt_util.now() - timedelta(days=1)
        upcoming = [
            (_as_datetime(ev.start), ev)
            for ev in self._all_events()
            if _as_datetime(ev.start) >= cutoff
        ]
        if not upcoming:
            return None
        upcoming.sort(key=lambda item: item[0])
        return upcoming[0][1]

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return events within the requested range."""
        events = [
            ev
            for ev in self._all_events()
            if start_date <= _as_datetime(ev.start) < end_date
        ]
        events.sort(key=lambda ev: _as_datetime(ev.start))
        return events


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
