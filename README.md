# Todoist Extended (Home Assistant)

A custom Home Assistant integration that surfaces the Todoist task metadata the
**built-in** Todoist integration drops — specifically **deadlines** and
**per-task priority** — for every active task across **all** projects.

Built on the **Todoist API v1** (`https://api.todoist.com/api/v1`, the unified
successor to Sync v9 + REST v2).

## Why this exists

The core Home Assistant `todoist` integration only reads a task's `due` field.
It never reads `deadline`, and priority is exposed for only a single "active"
calendar event at a time. If you want to build automations/blueprints that key
off **deadlines** or **each task's priority (P1–P4)**, that data isn't available.

This integration fetches every active task and exposes all three date/priority
dimensions in template-friendly and trigger-friendly forms.

## What you get

One config entry (one API token) creates a `Todoist` device with:

| Entity | Purpose |
| --- | --- |
| `sensor.todoist_tasks` | **Aggregate.** State = task count. Attribute `tasks` is a list of every task with `due`, `deadline`, `priority` (P1–P4), `priority_rank` (1 = highest), `labels`, `project`, `overdue`, `due_today`, `url`. Best for "scan all tasks" templates. |
| `sensor.<task name>` | **Per task** (optional, on by default). One sensor per task; same fields as attributes. Added/removed automatically as tasks appear/complete. Best for direct triggers. |
| `todo.todoist_tasks` | A to-do list of all active tasks. Create / update / complete / delete write back to Todoist. |
| `calendar.todoist_due_dates` | Calendar events from each task's **due** date. |
| `calendar.todoist_deadlines` | Calendar events from each task's **deadline**. |

### Priority mapping

Todoist's API uses `priority` `1–4` where **`4` is the highest** (shown as
**P1** in the app). This integration normalises that so you never have to
remember the inversion:

| Todoist UI | `priority` attr | `priority_rank` | raw `priority_api` |
| --- | --- | --- | --- |
| P1 (highest) | `"P1"` | `1` | `4` |
| P2 | `"P2"` | `2` | `3` |
| P3 | `"P3"` | `3` | `2` |
| P4 (none) | `"P4"` | `4` | `1` |

## Installation

1. Copy `custom_components/todoist_extended/` into your HA `config/custom_components/`
   directory (or add this repo to HACS as a custom repository).
2. Restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Todoist Extended.**
4. Paste your API token (Todoist → Settings → Integrations → Developer).

## Recorder note

`sensor.todoist_tasks` carries the full task list in its attributes. To keep
your recorder database small, exclude it:

```yaml
recorder:
  exclude:
    entities:
      - sensor.todoist_tasks
```

## Example blueprint use

Notify when any **P1** task's **deadline** is today:

```yaml
trigger:
  - platform: time
    at: "08:00:00"
condition: []
action:
  - variables:
      due_p1: >
        {{ state_attr('sensor.todoist_tasks', 'tasks')
           | selectattr('priority', 'eq', 'P1')
           | selectattr('deadline', 'eq', now().date().isoformat())
           | list }}
  - condition: template
    value_template: "{{ due_p1 | count > 0 }}"
  - service: notify.mobile_app
    data:
      message: "{{ due_p1 | count }} P1 task(s) due by deadline today"
```

## Status

`0.1.0` — read/sync of tasks, due dates, deadlines, and priority; todo write-back.
Todoist gives only the next occurrence of a recurring task's due date, so
recurrence rules are not projected.
