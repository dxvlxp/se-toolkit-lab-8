---
name: lms
description: Query live course data through LMS MCP tools and clarify missing lab choices
always: true
---

# LMS strategy

- Use `lms_health` for current backend availability and item count. An unhealthy
  result is a failure, not proof of an empty course.
- Use `lms_labs` to discover current labs. Never present remembered or example
  lab names as live data. Use `lms_learners` for enrolled learners.
- `lms_pass_rates`, `lms_timeline`, `lms_groups`, `lms_top_learners`, and
  `lms_completion_rate` require a lab. If it is missing, first call `lms_labs`.
  For several labs, ask the user to choose. Provide the shared structured-ui
  layer with the lab title as label and a stable `lab-NN` value extracted from
  the title. If a title does not identify its number, ask rather than inventing it.
- For a webchat lab choice, use the shared structured-ui skill and the current
  runtime chat ID. Do not put API keys in labels, values, text, or UI payloads.
- After the user chooses, call the requested tool with that lab. Never choose
  a tool using client-side keyword routing: reason from its description.
- For a comparison across labs, discover the labs, fetch each relevant lab's
  task averages or completion rate, then compare. Say which metric you used.
  `lms_pass_rates` returns mean task scores and attempts, not a count of passes.
- Format percentages with one decimal place and counts as integers. Preserve
  the difference between zero observations and a genuine zero score.
- `lms_sync_pipeline` changes data. Use it only for an explicit sync/refresh
  request, never just because a query returned an empty list.
- For a capabilities question, describe the tools actually available in this
  session, their limits, observability if present, and chat-bound cron if present.
  Without an MCP connection explain that live data is unavailable.
- Give a concise answer in the user's language. Keep actual failure details
  when a request fails; do not replace errors with a fabricated healthy answer.
