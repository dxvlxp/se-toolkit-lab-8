"""Bounded, read-only queries against VictoriaLogs and Jaeger-compatible traces."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, cast
from urllib.parse import urlsplit

import httpx


DEFAULT_SERVICE = "Learning Management Service"


class ObservabilityError(Exception):
    """An observability request failed; empty results must not mask this."""


def endpoint(value: str, name: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ObservabilityError(
            f"Set {name} to an HTTP(S) base URL without embedded credentials"
        )
    return value.rstrip("/")


def bounded(value: int, minimum: int, maximum: int, name: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def log_query(
    minutes: int, service: str = "", keyword: str = "", severity: str = ""
) -> str:
    bounded(minutes, 1, 1440, "minutes")
    query = f"_time:{minutes}m"
    if service:
        query += f" service.name:={json.dumps(service)}"
    if keyword:
        query += " " + json.dumps(keyword)
    if severity:
        if severity.upper() not in {
            "TRACE",
            "DEBUG",
            "INFO",
            "WARN",
            "WARNING",
            "ERROR",
            "FATAL",
        }:
            raise ValueError("Unknown severity")
        query += f" severity:={json.dumps(severity.upper())}"
    return query


class ObservabilityClient:
    def __init__(
        self,
        logs_url: str,
        traces_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.logs_url = endpoint(logs_url, "NANOBOT_VICTORIALOGS_URL")
        self.traces_url = endpoint(traces_url, "NANOBOT_VICTORIATRACES_URL")
        self.transport = transport

    @classmethod
    def from_env(cls) -> ObservabilityClient:
        return cls(
            os.getenv("NANOBOT_VICTORIALOGS_URL", ""),
            os.getenv("NANOBOT_VICTORIATRACES_URL", ""),
        )

    async def _request(
        self, base: str, path: str, params: dict[str, str | int], method: str = "GET"
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15, connect=5), transport=self.transport
            ) as client:
                if method == "POST":
                    response = await client.post(base + path, data=params)
                else:
                    response = await client.get(base + path, params=params)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            raise ObservabilityError(
                f"HTTP {exc.response.status_code} {exc.response.reason_phrase} from observability service"
            ) from exc
        except httpx.RequestError as exc:
            raise ObservabilityError(
                f"{type(exc).__name__}: observability service unavailable"
            ) from exc

    async def _logs(self, query: str, limit: int) -> list[dict[str, Any]]:
        response = await self._request(
            self.logs_url,
            "/select/logsql/query",
            {"query": query, "limit": limit},
            "POST",
        )
        try:
            rows: list[dict[str, Any]] = []
            for line in response.text.splitlines():
                if line.strip():
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError("Expected a log object")
                    rows.append(cast(dict[str, Any], row))
            return rows
        except (ValueError, TypeError) as exc:
            raise ObservabilityError("Invalid NDJSON returned by VictoriaLogs") from exc

    async def logs_search(
        self,
        keyword: str = "",
        minutes: int = 10,
        service: str = DEFAULT_SERVICE,
        severity: str = "",
        limit: int = 50,
    ) -> dict[str, Any]:
        bounded(limit, 1, 200, "limit")
        query = log_query(minutes, service, keyword, severity)
        # Sort before limiting so investigations use the newest relevant events.
        rows = await self._logs(query + " | sort by (_time desc)", limit)
        return {
            "query": query,
            "minutes": minutes,
            "records": rows,
            "limit": limit,
            "possibly_truncated": len(rows) >= limit,
        }

    async def logs_error_count(
        self, minutes: int = 10, service: str = DEFAULT_SERVICE
    ) -> dict[str, Any]:
        query = (
            log_query(minutes, service, severity="ERROR")
            + " | stats by (service.name) count() errors"
        )
        # Aggregate on the server, never count a truncated log sample.
        rows = await self._logs(query, 1000)
        counts: list[dict[str, Any]] = []
        try:
            for row in rows:
                counts.append(
                    {
                        "service": str(row.get("service.name", "unknown")),
                        "errors": int(row["errors"]),
                    }
                )
        except (KeyError, ValueError, TypeError) as exc:
            raise ObservabilityError(
                "Invalid error-count response from VictoriaLogs"
            ) from exc
        return {
            "query": query,
            "minutes": minutes,
            "services": counts,
            "total_errors": sum(row["errors"] for row in counts),
            "possibly_truncated": len(rows) >= 1000,
        }

    async def _traces(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        response = await self._request(self.traces_url, path, params)
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Expected Jaeger response object")
            payload = cast(dict[str, Any], payload)
            if payload.get("errors"):
                raise ObservabilityError("VictoriaTraces returned a Jaeger API error")
            if not isinstance(payload.get("data"), list):
                raise ValueError("Expected a Jaeger data list")
            return payload
        except (ValueError, TypeError) as exc:
            raise ObservabilityError(
                "Invalid Jaeger JSON returned by VictoriaTraces"
            ) from exc

    async def traces_list(
        self, service: str = DEFAULT_SERVICE, minutes: int = 10, limit: int = 10
    ) -> dict[str, Any]:
        bounded(minutes, 1, 1440, "minutes")
        bounded(limit, 1, 50, "limit")
        end = time.time_ns() // 1000
        return await self._traces(
            "/select/jaeger/api/traces",
            {
                "service": service,
                "start": end - minutes * 60 * 1_000_000,
                "end": end,
                "limit": limit,
            },
        )

    async def traces_get(self, trace_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"(?:[0-9a-fA-F]{16}|[0-9a-fA-F]{32})", trace_id):
            raise ValueError("trace_id must contain 16 or 32 hexadecimal characters")
        return await self._traces(f"/select/jaeger/api/traces/{trace_id}", {})
