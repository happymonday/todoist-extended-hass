"""Async client for the Todoist API v1."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import API_BASE, API_TIMEOUT, PAGE_LIMIT

_LOGGER = logging.getLogger(__name__)


class TodoistApiError(Exception):
    """Generic Todoist API error."""


class TodoistAuthError(TodoistApiError):
    """Raised when the token is rejected (401/403)."""


class TodoistApiClient:
    """Thin async client for the Todoist API v1.

    Only implements what the integration needs: listing all active tasks and
    projects (with cursor pagination), plus the task write operations used by
    the todo entity.
    """

    def __init__(self, token: str, session: aiohttp.ClientSession) -> None:
        """Initialise the client."""
        self._token = token
        self._session = session

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Perform a request and return decoded JSON (or None for empty bodies)."""
        url = f"{API_BASE}/{path.lstrip('/')}"
        try:
            async with asyncio.timeout(API_TIMEOUT):
                async with self._session.request(
                    method, url, headers=self._headers, **kwargs
                ) as resp:
                    if resp.status in (401, 403):
                        raise TodoistAuthError(
                            f"Todoist rejected the token ({resp.status})"
                        )
                    resp.raise_for_status()
                    if resp.status == 204 or resp.content_length == 0:
                        return None
                    return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise TodoistApiError(f"Todoist API request failed: {err}") from err

    async def _get_all(self, path: str) -> list[dict[str, Any]]:
        """Follow cursor pagination and return every result across all pages."""
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": PAGE_LIMIT}
            if cursor:
                params["cursor"] = cursor
            data = await self._request("GET", path, params=params)
            if not isinstance(data, dict):
                break
            results.extend(data.get("results") or [])
            cursor = data.get("next_cursor")
            if not cursor:
                break
        return results

    async def async_get_tasks(self) -> list[dict[str, Any]]:
        """Return all active tasks across every project."""
        return await self._get_all("tasks")

    async def async_get_projects(self) -> list[dict[str, Any]]:
        """Return all projects."""
        return await self._get_all("projects")

    async def async_close_task(self, task_id: str) -> None:
        """Complete a task."""
        await self._request("POST", f"tasks/{task_id}/close")

    async def async_reopen_task(self, task_id: str) -> None:
        """Reopen a completed task."""
        await self._request("POST", f"tasks/{task_id}/reopen")

    async def async_delete_task(self, task_id: str) -> None:
        """Delete a task."""
        await self._request("DELETE", f"tasks/{task_id}")

    async def async_create_task(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Create a task."""
        return await self._request("POST", "tasks", json=payload)

    async def async_update_task(
        self, task_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Update a task's fields."""
        return await self._request("POST", f"tasks/{task_id}", json=payload)
