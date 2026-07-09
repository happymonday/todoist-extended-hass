"""Sensor platform: one aggregate tasks sensor + one sensor per task."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CREATE_PER_TASK_SENSORS,
    DEFAULT_CREATE_PER_TASK_SENSORS,
    DOMAIN,
)
from .coordinator import TodoistCoordinator
from .model import TodoistTask

_LOGGER = logging.getLogger(__name__)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Todoist",
        manufacturer="Todoist",
        model="Tasks",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the aggregate sensor and, optionally, per-task sensors."""
    coordinator: TodoistCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([TodoistAllTasksSensor(coordinator, entry)])

    if entry.options.get(
        CONF_CREATE_PER_TASK_SENSORS, DEFAULT_CREATE_PER_TASK_SENSORS
    ):
        _setup_per_task_sensors(hass, coordinator, entry, async_add_entities)


class TodoistAllTasksSensor(CoordinatorEntity[TodoistCoordinator], SensorEntity):
    """A single sensor holding every active task in a ``tasks`` attribute."""

    _attr_has_entity_name = True
    _attr_name = "Tasks"
    _attr_icon = "mdi:checkbox-multiple-marked-circle-outline"
    _attr_native_unit_of_measurement = "tasks"

    def __init__(
        self, coordinator: TodoistCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_all_tasks"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        today = dt_util.now().date()
        task_dicts = [t.to_dict(today) for t in (self.coordinator.data or [])]
        return {
            "tasks": task_dicts,
            "overdue_count": sum(1 for t in task_dicts if t["overdue"]),
            "due_today_count": sum(1 for t in task_dicts if t["due_today"]),
            "p1_count": sum(1 for t in task_dicts if t["priority"] == "P1"),
            "with_deadline_count": sum(1 for t in task_dicts if t["deadline"]),
        }


class TodoistTaskSensor(CoordinatorEntity[TodoistCoordinator], SensorEntity):
    """A sensor for a single task, exposing its dates/priority/labels."""

    _attr_icon = "mdi:checkbox-blank-circle-outline"

    def __init__(
        self,
        coordinator: TodoistCoordinator,
        entry: ConfigEntry,
        task_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._task_id = task_id
        self._attr_unique_id = f"{entry.entry_id}_task_{task_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def _task(self) -> TodoistTask | None:
        for task in self.coordinator.data or []:
            if task.id == self._task_id:
                return task
        return None

    @property
    def available(self) -> bool:
        return super().available and self._task is not None

    @property
    def name(self) -> str:
        task = self._task
        return task.content if task else f"Task {self._task_id}"

    @property
    def native_value(self) -> str | None:
        task = self._task
        if task is None:
            return None
        # Sensor state is capped at 255 chars.
        return task.content[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        task = self._task
        if task is None:
            return {}
        return task.to_dict(dt_util.now().date())


@callback
def _setup_per_task_sensors(
    hass: HomeAssistant,
    coordinator: TodoistCoordinator,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a sensor per task and keep the set in sync as tasks come and go."""
    known: set[str] = set()

    @callback
    def _sync() -> None:
        if coordinator.data is None:
            return
        current = {task.id for task in coordinator.data}
        new_ids = current - known
        removed_ids = known - current

        if new_ids:
            async_add_entities(
                TodoistTaskSensor(coordinator, entry, task_id)
                for task_id in new_ids
            )
        if removed_ids:
            registry = er.async_get(hass)
            for task_id in removed_ids:
                unique_id = f"{entry.entry_id}_task_{task_id}"
                entity_id = registry.async_get_entity_id(
                    "sensor", DOMAIN, unique_id
                )
                if entity_id:
                    _LOGGER.debug("Removing sensor for gone task %s", task_id)
                    registry.async_remove(entity_id)

        known.clear()
        known.update(current)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))
