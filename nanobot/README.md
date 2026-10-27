# LMS agent deployment

This project uses the course-pinned Nanobot commit
`e7d371ec1e6531b28898ec2c869ef338e8dd46ec` through its GitHub archive.
The archive's internal package version is `0.1.4.post5`, but its source in
`uv.lock` is the explicit commit URL, not the PyPI release of that version.
Do not replace it with an unpinned `uv add nanobot-ai` installation.

The webchat/Flutter code is the pinned `nanobot-websocket-channel` submodule.
The LMS MCP server is supplied by the lab; `mcp/mcp-obs` adds four read-only
observability tools. Nanobot supplies its agent loop, memory and cron tools.

## Prepare on the VM

Follow [lab setup](../lab/setup/setup-simple.md) for Docker, Qwen login, backend
credentials and ETL data. Do not reuse running Lab 7 services on the same ports.

```sh
git clone --recurse-submodules --branch implementation/lab-8 https://github.com/dxvlxp/se-toolkit-lab-8.git
cd se-toolkit-lab-8
git submodule update --init --recursive
cp .env.docker.example .env.docker.secret
```

Edit `.env.docker.secret` locally. Set the LMS/autochecker credentials,
`QWEN_CODE_API_KEY`, a separate `NANOBOT_ACCESS_KEY`, and the correct `HOST_UID`
and `HOST_GID` from `id -u` / `id -g`. Leave these files out of Git.

| Shell configuration | Agent/container configuration |
| --- | --- |
| `LLM_API_KEY` | `providers.custom.apiKey` |
| `LLM_API_BASE_URL` | `providers.custom.apiBase`; Compose uses `qwen-code-api:8080/v1` |
| `LLM_API_MODEL` | `agents.defaults.model` |
| `LMS_API_KEY` / `NANOBOT_LMS_API_KEY` | LMS MCP Bearer key; never sent by the browser |
| `NANOBOT_LMS_BACKEND_URL` | `http://localhost:42002` in the shell, `http://backend:8000` in Compose |
| `NANOBOT_ACCESS_KEY` | WebSocket deployment authentication |
| `NANOBOT_VICTORIALOGS_URL` | Host CLI: `http://localhost:42010`; container: `http://victorialogs:9428` |
| `NANOBOT_VICTORIATRACES_URL` | Host CLI: `http://localhost:42011`; container: `http://victoriatraces:10428` |

The entrypoint explicitly injects environment values into a private
`config.resolved.json` file (mode 0600). It preserves unrelated settings from
your local `config.json`, or uses `config.example.json` if that file is absent.
JSON `${VAR}` placeholders are not used. The UI relay stays on container
loopback and shares the access key unless a separate relay token is supplied.

## CLI checkpoints

Run these commands on the VM, from the repository's `nanobot/` directory:

```sh
uv sync --locked
uv run nanobot onboard --config config.json --workspace ./workspace
```

Choose the custom OpenAI-compatible provider, model `coder-model`, and the
VM-local Qwen API during onboarding. Keep the resulting config private.
Then use fresh sessions to collect the Task 1 evidence:

```sh
uv run --env-file ../.env.docker.secret python entrypoint.py --stage bare --run agent --session cli:task1a-loop -m "What is the agentic loop?"
uv run --env-file ../.env.docker.secret python entrypoint.py --stage bare --run agent --session cli:task1a-labs -m "What labs are available in our LMS?"
uv run --env-file ../.env.docker.secret python entrypoint.py --stage lms --run agent --session cli:task1b-labs -m "What labs are available?"
uv run --env-file ../.env.docker.secret python entrypoint.py --stage lms --run agent --session cli:task1b-health -m "Is the LMS backend healthy?"
uv run --env-file ../.env.docker.secret python entrypoint.py --stage lms --run agent --session cli:task1c -m "Show me the scores"
```

`bare` removes MCP connections and disables webchat. `lms` enables only LMS
tools; `full` enables LMS, observability and structured UI. The LMS skill is
already present, so to compare without/with that skill, temporarily move its
directory out of `workspace/skills`, record Task 1B, and restore it for 1C.
Do not overwrite or duplicate the shared structured-ui skill.

For CLI observability, also export the two host telemetry URLs in the table
above. In Docker, Compose supplies the internal telemetry URLs automatically.

## Build and start

From the repository root, build first because Compose uses named build contexts:

```sh
docker compose --env-file .env.docker.secret config --quiet
docker compose --env-file .env.docker.secret build
docker compose --env-file .env.docker.secret up -d
docker compose --env-file .env.docker.secret ps
docker compose --env-file .env.docker.secret logs nanobot --tail 60
```

The agent runs as the configured non-root UID/GID. Its workspace bind mount
persists sessions, memory and cron jobs. The final image uses Python 3.14.2 and
the committed root uv lockfile. The Flutter build container copies files to a
named volume and may exit successfully rather than stay running.

Open `http://YOUR_VM_IP:42002/flutter/`, enter `NANOBOT_ACCESS_KEY`, and ask
"What can you do?", "How is the backend doing?", and "Show me the scores".
The last prompt should offer a structured lab choice when several labs exist.
The request path is browser → Caddy `/ws/chat` → webchat channel → Nanobot →
MCP → backend. The structured-reply path uses the internal UI relay.

## Logs, traces, and the failure exercise

Use the [Task 3 checkpoints](../lab/tasks/required/task-3.md) to capture real
happy-path logs, failure logs, and screenshots from both Victoria UIs.
The observability tools use the documented LogsQL HTTP query endpoint and
Jaeger-compatible `/select/jaeger/api/traces` paths. Log counts are computed
with server-side aggregation, not by counting a truncated sample. Tool results
identify their query window; telemetry failures are reported as failures.

The planted item-route bug is already fixed in this branch. To collect an
honest before/after comparison for Task 4, first ensure your working tree is
clean. Temporarily restore only the original item route on the VM:

```sh
git restore --source 8803ac1201428b3de80dc2d28f60ce2d24b4f026 -- backend/src/lms_backend/routers/items.py
docker compose --env-file .env.docker.secret build backend
docker compose --env-file .env.docker.secret up -d backend
```

Follow Task 4A/B: stop PostgreSQL, ask for labs, investigate immediately, and
create the requested two-minute cron job in the same open web chat. Collect
real responses, log/trace IDs and a proactive report. Remove the test job and
restart PostgreSQL afterward. Do not refresh the chat: jobs use that socket's
chat ID, and reconnecting creates a different one.

Restore the branch's fixed route and redeploy:

```sh
git restore backend/src/lms_backend/routers/items.py
docker compose --env-file .env.docker.secret build backend
docker compose --env-file .env.docker.secret up -d backend
```

Repeat the failure check, restart PostgreSQL, then collect a new healthy report
in the current chat. Use the built-in `cron` tool, not HEARTBEAT.md. No cron
job is installed automatically by startup. At the end, remove the short test
job or replace it with the requested fifteen-minute job. Fill in
[REPORT.md](../REPORT.md) with the actual evidence; no sample answers count.

## Automated checks and limits

```sh
uv sync --locked --all-packages --all-groups
uv run --no-sync --env-file backend/.env.tests.unit.example pytest backend/tests/unit mcp/mcp-obs/tests nanobot/tests -q
uv run --no-sync ruff check nanobot/entrypoint.py nanobot/tests mcp/mcp-obs backend/tests/unit/test_items_failure.py
uv run --no-sync pyright
uv run --no-sync ty check
```

Tests cover config injection, private config permissions, pinned framework
schema/plugin discovery, MCP stdio discovery, real local WebSocket access-key
validation and bus delivery, observability HTTP contracts and backend regression
cases. These tests do not replace VM deployment, live LLM answers, screenshots
or observed cron delivery. The GitHub test workflow also builds the agent image.

For a blank Flutter page, check its completed build and Caddy volume. For
missing structured replies, check webchat MCP registration and relay settings.
For a read-only/permission error, check host UID/GID and the nanobot bind mount.
For unavailable model replies, check Qwen authentication and the resolved API
base URL locally without publishing credentials.
