# Lab 8 report

## Evidence status

Repository implementation and automated checks are prepared. VM deployment,
live provider responses, screenshots, incident traces and scheduled chat
delivery have not been observed during repository preparation. The sections
below must be completed with real VM evidence; they are not completed lab
checkpoints. See [the deployment runbook](nanobot/README.md).

## Task 1A — Bare agent

Pending VM evidence: paste the actual answers to the agentic-loop question and
the LMS-labs question from fresh bare-agent sessions. Explain why the latter
cannot establish live LMS data without MCP.

## Task 1B — Agent with LMS tools

Pending VM evidence: paste real lab and health answers, with the corresponding
MCP tool calls. Capture this without the LMS-specific skill for the comparison.

## Task 1C — Skill prompt

Pending VM evidence: restore the LMS skill, use a fresh session, ask for scores
without a lab, and paste the actual clarification/list response.

## Task 2A — Deployed agent

Pending VM evidence: paste Compose status and startup logs confirming the
gateway, webchat channel, and MCP connections. Redact credentials.

## Task 2B — Web client

Pending VM evidence: add a screenshot of the Flutter chat showing a real
capability answer, a backend-backed answer and structured lab selection.
Record successful WebSocket access and wrong-key rejection.

## Task 3A — Structured logging

Pending VM evidence: paste a real successful request's structured log sequence
and a real database-error log. Add a VictoriaLogs query screenshot. Include
the service name, time window, event names and trace ID when present.

## Task 3B — Traces

Pending VM evidence: add healthy/error trace screenshots with span hierarchy,
service names, operations and durations. Match IDs to the log records.

## Task 3C — Observability MCP tools

Implemented tools: `logs_search`, `logs_error_count`, `traces_list`, and
`traces_get`. Error counts use a server-side LogsQL aggregate.

Pending VM evidence: paste answers to the scoped ten-minute LMS error question
under normal operation and immediately after triggering a database failure.
Restore PostgreSQL after the exercise.

## Task 4A — Multi-step investigation

Pending VM evidence: paste the actual investigation with a recent error log
and matching trace. For a genuine before/after experiment, use the original
route temporarily as described in the runbook. Distinguish observations from
inferences and identify the failing service/operation.

## Task 4B — Proactive health check

Pending VM evidence: in the same open chat, request a built-in cron job every
120 seconds. Paste the returned job ID, job listing and an actual proactive
failure report. Remove the test job and record its removal. Restart PostgreSQL.

## Task 4C — Bug fix and recovery

Source-level root cause: `backend/src/lms_backend/routers/items.py` caught every
exception from `read_items` and raised `404 Items not found`, hiding database
failures as a missing resource.

Fix: remove the broad catch so the existing database log and application
exception handler retain the real failure and return HTTP 500. An empty
collection still returns HTTP 200 with `[]`. Regression tests verify error
propagation, the HTTP error response and the empty-collection behavior.

Pending VM evidence: after deploying the fixed route, paste the newest
failure investigation, then restore PostgreSQL and paste a later healthy
scheduled report. Include timestamps/trace IDs so pre-fix records are not
mistaken for post-fix evidence. Remove or replace the short test job afterward.
