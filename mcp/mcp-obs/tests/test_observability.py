"""HTTP contract tests for observability tools without live telemetry services."""

import json
from collections.abc import Callable
from urllib.parse import parse_qs

import httpx
import pytest

from mcp_obs.observability import ObservabilityClient, ObservabilityError, log_query
from mcp_obs.server import server


def client(handler: Callable[[httpx.Request], httpx.Response]) -> ObservabilityClient:
    return ObservabilityClient(
        "http://logs.test:9428",
        "http://traces.test:10428",
        httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_search_sends_scoped_escaped_post_and_reads_ndjson() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            text='{"event":"db_query","trace_id":"0123456789abcdef"}\n{"event":"request_completed"}\n',
        )

    result = await client(respond).logs_search(
        '" | stats count()', minutes=2, severity="error", limit=12
    )
    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/select/logsql/query"
    query = parse_qs(request.content.decode())["query"][0]
    assert '_time:2m service.name:="Learning Management Service"' in query
    assert json.dumps('" | stats count()') in query
    assert query.endswith("| sort by (_time desc)")
    assert result["records"][0]["trace_id"] == "0123456789abcdef"


@pytest.mark.asyncio
async def test_error_count_is_server_side_aggregation() -> None:
    queries: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        queries.append(parse_qs(request.content.decode())["query"][0])
        return httpx.Response(
            200,
            text='{"service.name":"backend","errors":"9876"}\n{"service.name":"proxy","errors":"2"}\n',
        )

    result = await client(respond).logs_error_count(10, "")
    assert "| stats by (service.name) count() errors" in queries[0]
    assert result["total_errors"] == 9878


@pytest.mark.asyncio
async def test_empty_log_response_is_zero_errors() -> None:
    result = await client(lambda _: httpx.Response(200, text="")).logs_error_count()
    assert result["total_errors"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 500, 503])
async def test_failed_telemetry_is_not_treated_as_healthy(status: int) -> None:
    with pytest.raises(ObservabilityError, match=f"HTTP {status}"):
        await client(lambda _: httpx.Response(status)).logs_error_count()


@pytest.mark.asyncio
async def test_timeout_is_reported() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(ObservabilityError, match="ReadTimeout"):
        await client(fail).logs_search()


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["not json", "[]", '{"errors":"not a number"}'])
async def test_invalid_count_payload_is_reported(body: str) -> None:
    with pytest.raises(ObservabilityError):
        await client(lambda _: httpx.Response(200, text=body)).logs_error_count()


@pytest.mark.parametrize("minutes", [0, -1, 1441, True])
def test_invalid_window_is_rejected(minutes: int) -> None:
    with pytest.raises(ValueError):
        log_query(minutes)


@pytest.mark.asyncio
async def test_trace_list_uses_jaeger_path_and_microsecond_window() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200, json={"data": [{"traceID": "0123456789abcdef"}], "errors": None}
        )

    result = await client(respond).traces_list(minutes=2, limit=3)
    request = requests[0]
    assert request.url.path == "/select/jaeger/api/traces"
    assert (
        int(request.url.params["end"]) - int(request.url.params["start"]) == 120_000_000
    )
    assert request.url.params["limit"] == "3"
    assert result["data"][0]["traceID"] == "0123456789abcdef"


@pytest.mark.asyncio
async def test_trace_get_preserves_full_trace() -> None:
    payload = {
        "data": [
            {"traceID": "0123456789abcdef", "spans": [{"operationName": "SELECT item"}]}
        ]
    }

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/select/jaeger/api/traces/0123456789abcdef"
        return httpx.Response(200, json=payload)

    assert await client(respond).traces_get("0123456789abcdef") == payload


@pytest.mark.asyncio
@pytest.mark.parametrize("trace_id", ["../private", "xyz", "", "0" * 33])
async def test_invalid_trace_id_is_rejected(trace_id: str) -> None:
    with pytest.raises(ValueError):
        await client(lambda _: httpx.Response(200)).traces_get(trace_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"data": [], "errors": ["bad query"]}, []])
async def test_invalid_trace_payload_is_reported(payload: object) -> None:
    with pytest.raises(ObservabilityError):
        await client(lambda _: httpx.Response(200, json=payload)).traces_list()


@pytest.mark.asyncio
async def test_server_registers_four_typed_tools() -> None:
    tools = await server.list_tools()
    assert {tool.name for tool in tools} == {
        "logs_search",
        "logs_error_count",
        "traces_list",
        "traces_get",
    }
    trace_tool = next(tool for tool in tools if tool.name == "traces_get")
    assert "trace_id" in trace_tool.inputSchema["required"]
