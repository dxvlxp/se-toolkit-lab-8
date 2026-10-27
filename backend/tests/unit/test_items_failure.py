"""Regression checks for the planted database-failure-to-404 translation."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest

from lms_backend.database import get_session
from lms_backend.main import app
from lms_backend.routers import items


@pytest.mark.asyncio
async def test_list_items_does_not_translate_database_error_to_404() -> None:
    failure = ConnectionError("PostgreSQL connection refused")
    with patch.object(items, "read_items", new=AsyncMock(side_effect=failure)):
        with pytest.raises(ConnectionError, match="PostgreSQL"):
            await items.get_items(AsyncMock())


@pytest.mark.asyncio
async def test_empty_item_collection_is_successful() -> None:
    with patch.object(items, "read_items", new=AsyncMock(return_value=[])):
        assert await items.get_items(AsyncMock()) == []


def test_api_exposes_underlying_failure_as_500() -> None:
    async def fake_session():
        yield AsyncMock()

    app.dependency_overrides[get_session] = fake_session
    try:
        with patch.object(
            items,
            "read_items",
            new=AsyncMock(side_effect=ConnectionError("PostgreSQL connection refused")),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get(
                    "/items/", headers={"Authorization": "Bearer test"}
                )
        assert response.status_code == 500
        assert response.json()["type"] == "ConnectionError"
        assert "PostgreSQL connection refused" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_session, None)
