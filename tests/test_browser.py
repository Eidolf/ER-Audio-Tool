"""Tests for loopback browser server authentication and protocol."""
import asyncio
import json
import pytest
from er_audio_tool.browser.server import BrowserServer


def test_browser_server_auth():
    asyncio.run(_run_browser_auth_test())


async def _run_browser_auth_test():
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

        # 3. HTTP connection test endpoint
        reader3, writer3 = await asyncio.open_connection("127.0.0.1", 59123)
        body = json.dumps({"token": server.auth_token})
        req = (
            f"POST /api/test_connection HTTP/1.1\r\n"
            f"Host: 127.0.0.1:59123\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n\r\n{body}"
        ).encode("utf-8")
        writer3.write(req)
        await writer3.drain()

        http_resp = await reader3.read(4096)
        http_resp_str = http_resp.decode("utf-8", errors="replace")
        assert "200 OK" in http_resp_str
        assert "desktop_version" in http_resp_str
        assert '"authenticated": true' in http_resp_str.lower()
        writer3.close()
        await writer3.wait_closed()

        # 4. HTTP CORS OPTIONS preflight test
        reader4, writer4 = await asyncio.open_connection("127.0.0.1", 59123)
        opt_req = (
            "OPTIONS /api/test_connection HTTP/1.1\r\n"
            "Host: 127.0.0.1:59123\r\n"
            "Origin: chrome-extension://test\r\n\r\n"
        ).encode("utf-8")
        writer4.write(opt_req)
        await writer4.drain()

        opt_resp = await reader4.read(2048)
        opt_resp_str = opt_resp.decode("utf-8", errors="replace")
        assert "200 OK" in opt_resp_str
        assert "Access-Control-Allow-Origin: *" in opt_resp_str
        writer4.close()
        await writer4.wait_closed()

    finally:
        await server.stop()
