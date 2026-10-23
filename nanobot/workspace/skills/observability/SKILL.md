---
name: observability
description: Investigate current LMS failures with correlated logs and traces and manage requested chat health checks
always: true
---

# Observability strategy

For "What went wrong?", "Check system health", and recent-error questions:

1. Use `logs_error_count` with the requested time window; default to ten minutes
   and service `Learning Management Service`. Use two minutes in a two-minute
   scheduled health check. Do not substitute old evidence from a wider window.
2. Use `logs_search` for that service/window and severity ERROR. Inspect the
   newest events: `db_query`, `request_completed`, and `unhandled_exception`.
3. Extract an available `trace_id` and use `traces_get` with that exact ID.
   If no log has an ID, use `traces_list` for the same service/window. State
   explicitly if no matching trace is available; never invent correlation.
4. Explain the affected service, failing operation, observed HTTP status, and
   likely cause using both log and span evidence. Mention their timestamps and
   trace ID, but do not dump full JSON or credentials. Distinguish observations
   from inferences. In this lab a database failure may have been incorrectly
   translated into `404 Items not found`; only claim that for matching evidence.
5. A failed logs/trace query means telemetry is unavailable, not zero errors.
   Zero recent errors alone does not prove that the backend is responding.
   For a health check also call `lms_health`. If no recent errors exist and the
   live health check succeeds, say the system looks healthy in that window.

## Requested proactive checks

Use Nanobot's built-in `cron` tool only when the user requests a recurring job.
Use the current runtime webchat channel and chat ID for delivery. For the lab's
two-minute check, create an every-120-seconds job whose message requests the
investigation above for the last two minutes and a short reply in this chat.
In this pinned version, `cron` automatically takes the current channel/chat
from runtime context and enables delivery; do not invent channel/deliver
arguments absent from its schema. Use `every_seconds: 120` with action `add`.
List jobs afterward and report the actual returned job ID. Do not create a
global job during startup and do not use HEARTBEAT.md in place of cron.

Warn that reconnecting/refreshing the web page creates a different chat ID;
the old job cannot reach the new socket. Remove the test job when asked, and
list jobs to verify removal. After recovery, create a new job in the current
chat only if asked. Change it to fifteen minutes or remove it at the end of
the exercise. Never claim a scheduled reply arrived before it actually did.
