"""DataUpdateCoordinator for the Todoist Extended integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TodoistApiClient, TodoistApiError, TodoistAuthError
from .const import DOMAIN
from .model import TodoistTask

_LOGGER = logging.getLogger(__name__)


class TodoistCoordinator(DataUpdateCoordinator[list[TodoistTask]]):
    """Fetch all active Todoist tasks (every project) on an interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: TodoistApiClient,
        scan_interval: int,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self._project_names: dict[str, str] = {}

    async def _async_update_data(self) -> list[TodoistTask]:
        """Fetch projects (for names) and all active tasks."""
        try:
            projects = await self.client.async_get_projects()
            self._project_names = {
                str(p["id"]): p.get("name")
                for p in projects
                if p.get("id") is not None
            }
            raw_tasks = await self.client.async_get_tasks()
        except TodoistAuthError as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except TodoistApiError as err:
            raise UpdateFailed(str(err)) from err

        return [TodoistTask.from_json(task, self._project_names) for task in raw_tasks]
