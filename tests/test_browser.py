"""Tests for loopback browser server authentication and protocol."""
import asyncio
import json
import pytest
from er_audio_tool.browser.server import BrowserServer


@pytest.mark.asyncio
async def test_browser_server_auth():
    server = BrowserServer(host="127.0.0.1", port=59123)
    await server.start()

    try:
        # 1. Connect without token -> should be rejected
        reader, writer = await asyncio.open_connection("127.0.0.1", 59123)
        writer.write(json.dumps({"action": "auth", "token": "invalid-token"}).encode() + b"\n")
        await writer.drain()

        resp = await reader.readline()
        res_data = json.loads(resp.decode())
        assert res_data.get("status") == "unauthorized"
        writer.close()
        await writer.wait_closed()

        # 2. Connect with valid token
        reader2, writer2 = await asyncio.open_connection("127.0.0.1", 59123)
        writer2.write(json.dumps({"action": "auth", "token": server.auth_token}).encode() + b"\n")
        await writer2.drain()

        resp2 = await reader2.readline()
        res_data2 = json.loads(resp2.decode())
        assert res_data2.get("status") == "authenticated"

        writer2.close()
        await writer2.wait_closed()
    finally:
        await server.stop()
