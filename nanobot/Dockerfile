ARG REGISTRY_PREFIX_DOCKER_HUB
FROM ${REGISTRY_PREFIX_DOCKER_HUB}astral/uv:0.12.23 AS uv
FROM ${REGISTRY_PREFIX_DOCKER_HUB}python:3.14.2-slim-bookworm AS builder
COPY --from=uv /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY --from=workspace pyproject.toml uv.lock ./
COPY --from=workspace backend/pyproject.toml backend/pyproject.toml
COPY --from=workspace qwen-code-api/pyproject.toml qwen-code-api/pyproject.toml
COPY --from=workspace mcp/mcp-lms/pyproject.toml mcp/mcp-lms/pyproject.toml
COPY --from=workspace mcp/mcp-obs/pyproject.toml mcp/mcp-obs/pyproject.toml
COPY --from=workspace nanobot-websocket-channel/nanobot-channel-protocol/pyproject.toml nanobot-websocket-channel/nanobot-channel-protocol/pyproject.toml
COPY --from=workspace nanobot-websocket-channel/nanobot-webchat/pyproject.toml nanobot-websocket-channel/nanobot-webchat/pyproject.toml
COPY --from=workspace nanobot-websocket-channel/mcp-webchat/pyproject.toml nanobot-websocket-channel/mcp-webchat/pyproject.toml
COPY pyproject.toml nanobot/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-workspace --package lab8-agent
COPY --from=workspace mcp/mcp-lms mcp/mcp-lms
COPY --from=workspace mcp/mcp-obs mcp/mcp-obs
COPY --from=workspace nanobot-websocket-channel/nanobot-channel-protocol nanobot-websocket-channel/nanobot-channel-protocol
COPY --from=workspace nanobot-websocket-channel/nanobot-webchat nanobot-websocket-channel/nanobot-webchat
COPY --from=workspace nanobot-websocket-channel/mcp-webchat nanobot-websocket-channel/mcp-webchat
COPY . nanobot
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --package lab8-agent

FROM ${REGISTRY_PREFIX_DOCKER_HUB}python:3.14.2-slim-bookworm
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid ${APP_GID} agent && useradd --uid ${APP_UID} --gid agent --create-home agent
ENV PATH="/app/.venv/bin:$PATH" HOME=/home/agent PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=builder --chown=agent:agent /app /app
WORKDIR /app/nanobot
USER agent
CMD ["python", "/app/nanobot/entrypoint.py"]
