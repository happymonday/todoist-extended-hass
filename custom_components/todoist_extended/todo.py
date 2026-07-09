"""Todo platform: a single list of all active tasks with write-back."""
from __future__ import annotations

import logging
from datetime import date, datetime

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import TodoistCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the todo list entity."""
    coordinator: TodoistCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TodoistTodoList(coordinator, entry)])


def _apply_due(payload: dict, due: date | datetime | None) -> None:
    """Add the appropriate v1 due field to a create/update payload."""
    if due is None:
        return
    if isinstance(due, datetime):
        payload["due_datetime"] = dt_util.as_local(due).isoformat()
    elif isinstance(due, date):
        payload["due_date"] = due.isoformat()


class TodoistTodoList(CoordinatorEntity[TodoistCoordinator], TodoListEntity):
    """All active Todoist tasks as a HA to-do list."""

    _attr_has_entity_name = True
    _attr_name = "Tasks"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
    )

    def __init__(
        self, coordinator: TodoistCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_todo"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Todoist",
            manufacturer="Todoist",
            model="Tasks",
        )

    @property
    def todo_items(self) -> list[TodoItem] | None:
        if self.coordinator.data is None:
            return None
        items: list[TodoItem] = []
        for task in self.coordinator.data:
            if task.parent_id:
                # Skip sub-tasks, matching the core Todoist integration.
                continue
            items.append(
                TodoItem(
                    summary=task.content,
                    uid=task.id,
                    status=TodoItemStatus.NEEDS_ACTION,
                    due=task.due,
                    description=task.description or None,
                )
            )
        return items

    async def async_create_todo_item(self, item: TodoItem) -> None:
        payload: dict = {"content": item.summary}
        if item.description:
            payload["description"] = item.description
        _apply_due(payload, item.due)
        await self.coordinator.client.async_create_task(payload)
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if item.status == TodoItemStatus.COMPLETED:
            await self.coordinator.client.async_close_task(item.uid)
            await self.coordinator.async_request_refresh()
            return

        payload: dict = {
            "content": item.summary,
            "description": item.description or "",
        }
        _apply_due(payload, item.due)
        await self.coordinator.client.async_update_task(item.uid, payload)
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            await self.coordinator.client.async_delete_task(uid)
        await self.coordinator.async_request_refresh()
