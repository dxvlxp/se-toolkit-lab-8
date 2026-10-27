"""Check real local channel transport and MCP discovery without a live LLM."""

import asyncio
from contextlib import suppress
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot_webchat import WebChatChannel, WebChatConfig
import pytest
import websockets


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module", "expected"),
    [
        ("mcp_lms", {"lms_health", "lms_labs", "lms_pass_rates"}),
        ("mcp_obs", {"logs_search", "logs_error_count", "traces_list", "traces_get"}),
        ("mcp_webchat", {"ui_message"}),
    ],
)
async def test_stdio_mcp_discovery(module: str, expected: set[str]) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", module],
        env={
            "NANOBOT_LMS_BACKEND_URL": "http://127.0.0.1:1",
            "NANOBOT_LMS_API_KEY": "test",
            "NANOBOT_UI_RELAY_URL": "http://127.0.0.1:1",
            "NANOBOT_UI_RELAY_TOKEN": "test",
        },
    )
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            result = await session.list_tools()
            assert expected <= {tool.name for tool in result.tools}


@pytest.mark.asyncio
async def test_websocket_key_rejection_and_authorized_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NANOBOT_ACCESS_KEY", "test-access")
    monkeypatch.setenv("NANOBOT_UI_RELAY_PORT", "0")
    bus = MessageBus()
    channel = WebChatChannel(WebChatConfig(host="127.0.0.1", port=0), bus)
    task = asyncio.create_task(channel.start())
    try:
        for _ in range(100):
            if channel._server is not None:
                break
            if task.done():
                await task
            await asyncio.sleep(0.01)
        assert channel._server is not None
        port = channel._server.sockets[0].getsockname()[1]
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/chat?access_key=wrong"
        ) as socket:
            with pytest.raises(websockets.ConnectionClosed):
                await socket.recv()
            assert socket.close_code == 4001
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/chat?access_key=test-access"
        ) as socket:
            await socket.send(json.dumps({"content": "hello"}))
            inbound = await asyncio.wait_for(bus.consume_inbound(), timeout=5)
            assert inbound.content == "hello"
            assert inbound.channel == "webchat"
            await channel.send(
                OutboundMessage(
                    channel="webchat",
                    chat_id=inbound.chat_id,
                    content="Local transport works",
                )
            )
            result = json.loads(await asyncio.wait_for(socket.recv(), timeout=5))
            assert result["type"] == "text"
            assert result["content"] == "Local transport works"
    finally:
        await channel.stop()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
