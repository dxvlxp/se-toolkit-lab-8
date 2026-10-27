"""Stdio MCP server for read-only observability queries."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_obs.observability import DEFAULT_SERVICE, ObservabilityClient


server = FastMCP("obs")


@server.tool()
async def logs_search(
    keyword: str = "",
    minutes: int = 10,
    service: str = DEFAULT_SERVICE,
    severity: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Search recent logs by literal keyword, service and severity. Returns records with trace_id for correlation; minutes 1..1440, limit 1..200."""
    return await ObservabilityClient.from_env().logs_search(
        keyword, minutes, service, severity, limit
    )


@server.tool()
async def logs_error_count(
    minutes: int = 10, service: str = DEFAULT_SERVICE
) -> dict[str, Any]:
    """Count ERROR events per service in the time window using a server-side aggregate, not a sampled log list. Empty service means all services."""
    return await ObservabilityClient.from_env().logs_error_count(minutes, service)


@server.tool()
async def traces_list(
    service: str = DEFAULT_SERVICE, minutes: int = 10, limit: int = 10
) -> dict[str, Any]:
    """List recent Jaeger traces for a service in the last minutes (1..1440), limit 1..50. Prefer traces_get when a log provides a trace ID."""
    return await ObservabilityClient.from_env().traces_list(service, minutes, limit)


@server.tool()
async def traces_get(trace_id: str) -> dict[str, Any]:
    """Fetch one full trace by its 16- or 32-character hex ID, including spans, process/service names, operation names and errors."""
    return await ObservabilityClient.from_env().traces_get(trace_id)


def main() -> None:
    server.run(transport="stdio")
