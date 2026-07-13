"""Constants for the Todoist Extended integration."""
from __future__ import annotations

DOMAIN = "todoist_extended"

CONF_TOKEN = "token"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_CREATE_PER_TASK_SENSORS = "create_per_task_sensors"
CONF_CREATE_PRIORITY_LISTS = "create_priority_lists"

DEFAULT_NAME = "Todoist Extended"
DEFAULT_SCAN_INTERVAL = 60  # seconds
DEFAULT_CREATE_PER_TASK_SENSORS = True
DEFAULT_CREATE_PRIORITY_LISTS = False
MIN_SCAN_INTERVAL = 15  # seconds

# Todoist API v1 — unifies the old Sync v9 and REST v2 APIs.
API_BASE = "https://api.todoist.com/api/v1"
API_TIMEOUT = 30  # seconds
PAGE_LIMIT = 200  # max page size for cursor pagination

# Todoist priority: the API uses 1-4 where 4 is the HIGHEST (shown as "P1" in the
# UI). We normalise to the user-facing label and to a rank where 1 is highest so
# blueprints can read/sort intuitively.
API_PRIORITY_TO_LABEL = {4: "P1", 3: "P2", 2: "P3", 1: "P4"}
API_PRIORITY_TO_RANK = {4: 1, 3: 2, 2: 3, 1: 4}
