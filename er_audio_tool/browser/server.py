"""Secure local loopback server for companion browser extension with unified registry binding."""
from __future__ import annotations
import asyncio
import json
import logging
import secrets
import threading
from dataclasses import dataclass
from typing import Callable, Optional
import numpy as np
from er_audio_tool.version import get_version
from er_audio_tool.browser.registry import (
    BrowserConnectionRegistry,
    ConnectionState,
    ConnectionSnapshot,
)


logger = logging.getLogger("er_audio_tool.browser")


@dataclass
class BrowserTabInfo:
    tab_id: int
    title: str
    audible: bool = False
    muted: bool = False
    window_id: int = 0
    active: bool = False


class BrowserServer:
    """Loopback-only server (127.0.0.1) communicating securely with Chrome/Edge extension."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 58291,
        token_entropy_bytes: int = 24,
        registry: Optional[BrowserConnectionRegistry] = None,
    ):
        self.host = host
        self.port = port
        self.token_entropy_bytes = token_entropy_bytes
        self.auth_token = secrets.token_hex(token_entropy_bytes)
        self.is_running = False
        self._server = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        
        # Authoritative shared registry
        self.registry = registry or BrowserConnectionRegistry.get_instance()

        # Callbacks for backward compatibility
        self.on_audio_data: Optional[Callable[[np.ndarray], None]] = None
        self.on_status_change: Optional[Callable[[str], None]] = None
        self.on_tab_selected: Optional[Callable[[BrowserTabInfo], None]] = None

        # Bind registry frame consumer
        self.registry.set_audio_frame_consumer(self._handle_registry_audio_frame)

    def _handle_registry_audio_frame(self, audio: np.ndarray, capture_session_id: str):
        if self.on_audio_data:
            self.on_audio_data(audio)

    # State properties proxying directly to authoritative registry
    @property
    def is_connected(self) -> bool:
        snap = self.registry.get_snapshot()
        return snap.state not in (ConnectionState.SERVER_STOPPED, ConnectionState.DISCONNECTED, ConnectionState.ERROR)

    @is_connected.setter
    def is_connected(self, val: bool):
        pass

    @property
    def is_authenticated(self) -> bool:
        snap = self.registry.get_snapshot()
        return snap.authenticated_session_id is not None and snap.state in (
            ConnectionState.AUTHENTICATED,
            ConnectionState.CAPABILITIES_CONFIRMED,
            ConnectionState.READY_FOR_TAB_SELECTION,
            ConnectionState.TAB_SELECTED,
            ConnectionState.CAPTURE_STARTING,
            ConnectionState.AUDIO_STREAM_ACTIVE,
            ConnectionState.SILENT_AUDIO_STREAM_ACTIVE,
            ConnectionState.PAUSED,
        )

    @is_authenticated.setter
    def is_authenticated(self, val: bool):
        pass

    @property
    def extension_version(self) -> Optional[str]:
        return self.registry.get_snapshot().extension_version

    @extension_version.setter
    def extension_version(self, val: Optional[str]):
        pass

    @property
    def selected_tab(self) -> Optional[BrowserTabInfo]:
        st = self.registry.get_snapshot().selected_tab
        if st is None:
            return None
        return BrowserTabInfo(
            tab_id=st.tab_id,
            title=st.title,
            audible=st.audible,
            muted=st.muted,
            window_id=st.window_id,
            active=st.active,
        )

    @selected_tab.setter
    def selected_tab(self, val: Optional[BrowserTabInfo]):
        if val is None:
            self.registry.clear_selected_tab()
        else:
            self.registry.select_tab(
                tab_id=val.tab_id,
                title=val.title,
                audible=val.audible,
                muted=val.muted,
                window_id=val.window_id,
                active=val.active,
            )

    @property
    def received_frames_count(self) -> int:
        return self.registry.get_snapshot().received_frames_count

    @received_frames_count.setter
    def received_frames_count(self, val: int):
        pass

    @property
    def last_audio_timestamp(self) -> float:
        return self.registry._last_audio_monotonic

    def get_pairing_token(self) -> str:
        return self.auth_token

    def regenerate_token(self) -> str:
        self.auth_token = secrets.token_hex(self.token_entropy_bytes)
        self.registry.handle_disconnect("Token regenerated")
        return self.auth_token

    def validate_token(self, token: str) -> bool:
        return bool(token and secrets.compare_digest(self.auth_token, token))

    async def _send_http_response(
        self,
        writer: asyncio.StreamWriter,
        status_code: int,
        data: dict | str,
        content_type: str = "application/json",
    ):
        body = json.dumps(data).encode("utf-8") if isinstance(data, dict) else data.encode("utf-8")
        status_text = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found", 405: "Method Not Allowed"}.get(status_code, "OK")
        resp = (
            f"HTTP/1.1 {status_code} {status_text}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            f"Access-Control-Allow-Headers: Content-Type, Authorization, X-Session-Token\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("latin1") + body
        writer.write(resp)
        await writer.drain()

    async def _handle_http_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        first_line: str,
    ):
        parts = first_line.split()
        if len(parts) < 2:
            await self._send_http_response(writer, 400, {"error": "Invalid HTTP request"})
            return

        method, path = parts[0].upper(), parts[1].split("?")[0]
        headers = {}
        while True:
            hline = await reader.readline()
            if not hline or hline in (b"\r\n", b"\n"):
                break
            decoded = hline.decode("latin1").strip()
            if ":" in decoded:
                k, v = decoded.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        # Handle CORS preflight
        if method == "OPTIONS":
            await self._send_http_response(writer, 200, {"status": "ok"})
            return

        # Read body if present
        body_bytes = b""
        content_length = int(headers.get("content-length", 0))
        if content_length > 0:
            body_bytes = await reader.readexactly(content_length)

        payload = {}
        if body_bytes:
            try:
                payload = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                pass

        token = payload.get("token") or headers.get("x-session-token", "")

        # Route endpoints
        if path == "/api/test_connection":
            token_valid = self.validate_token(token)
            if token_valid:
                # Commit to authoritative registry
                ext_id = payload.get("extension_id", "chrome-extension-companion")
                ext_ver = payload.get("version", "1.0.0")
                browser_fam = payload.get("browser", "Chromium")
                self.registry.authenticate_client(
                    extension_instance_id=ext_id,
                    extension_version=ext_ver,
                    browser_family=browser_fam,
                )
                if self.on_status_change:
                    self.on_status_change("Extension Verified & Connected")

            snap = self.registry.get_snapshot()
            resp_data = {
                "ok": True,
                "desktop_version": get_version(),
                "app_name": "er-audio-tool",
                "authenticated": token_valid,
                "token_provided": bool(token),
                "connection_id": snap.connection_id,
                "connection_generation": snap.connection_generation,
                "server_time": asyncio.get_event_loop().time(),
                "selected_tab": {
                    "tab_id": snap.selected_tab.tab_id,
                    "title": snap.selected_tab.title,
                } if snap.selected_tab else None,
                "audio_stream_active": snap.state in (ConnectionState.AUDIO_STREAM_ACTIVE, ConnectionState.SILENT_AUDIO_STREAM_ACTIVE),
            }
            status_code = 200 if token_valid else 401
            await self._send_http_response(writer, status_code, resp_data)
            return

        if path in ("/api/auth", "/"):
            if not self.validate_token(token):
                await self._send_http_response(writer, 401, {"status": "unauthorized", "error": "Invalid token"})
                return
            ext_id = payload.get("extension_id", "companion-ext")
            ext_ver = payload.get("version", "1.0.0")
            sess_id = self.registry.authenticate_client(
                extension_instance_id=ext_id,
                extension_version=ext_ver,
            )
            if self.on_status_change:
                self.on_status_change("Authenticated & Ready")
            await self._send_http_response(writer, 200, {
                "status": "authenticated",
                "session_id": sess_id,
                "version": get_version(),
                "protocol": "1.0",
            })
            return

        if path == "/api/tab_selected":
            if not self.validate_token(token):
                await self._send_http_response(writer, 401, {"status": "unauthorized"})
                return
            tab_data = payload.get("tabInfo") or payload.get("tab") or payload
            tab_info = BrowserTabInfo(
                tab_id=tab_data.get("id", tab_data.get("tab_id", 0)),
                title=tab_data.get("title", "Selected Tab"),
                audible=tab_data.get("audible", False),
                muted=tab_data.get("muted", False),
                window_id=tab_data.get("windowId", tab_data.get("window_id", 0)),
                active=tab_data.get("active", True),
            )
            self.registry.select_tab(
                tab_id=tab_info.tab_id,
                title=tab_info.title,
                audible=tab_info.audible,
                muted=tab_info.muted,
                window_id=tab_info.window_id,
                active=tab_info.active,
            )
            if self.on_tab_selected:
                self.on_tab_selected(tab_info)
            if self.on_status_change:
                self.on_status_change(f"Tab Selected: {tab_info.title[:30]}")
            await self._send_http_response(writer, 200, {"status": "ok", "tab_id": tab_info.tab_id})
            return

        if path == "/api/heartbeat":
            if not self.validate_token(token):
                await self._send_http_response(writer, 401, {"status": "unauthorized"})
                return
            self.registry.record_heartbeat()
            snap = self.registry.get_snapshot()
            await self._send_http_response(writer, 200, {
                "status": "ok",
                "connection_generation": snap.connection_generation,
                "state": snap.state.value,
            })
            return

        if path == "/api/status":
            snap = self.registry.get_snapshot()
            await self._send_http_response(writer, 200, {
                "connected": self.is_connected,
                "authenticated": self.is_authenticated,
                "state": snap.state.value,
                "selected_tab": snap.selected_tab.title if snap.selected_tab else None,
                "received_frames": snap.received_frames_count,
            })
            return

        if path == "/api/audio_chunk":
            if not self.validate_token(token):
                await self._send_http_response(writer, 401, {"status": "unauthorized"})
                return

            cap_session = payload.get("capture_session_id") or headers.get("x-capture-session-id")
            content_type = headers.get("content-type", "")

            # Parse audio chunk payload (base64 PCM float32, base64 int16, or raw binary)
            audio_arr = None
            if "data" in payload:
                import base64
                b64_data = payload["data"]
                raw_bytes = base64.b64decode(b64_data)
                sample_format = payload.get("sample_format", "float32").lower()
                ch_count = int(payload.get("channels", 2))

                if sample_format == "float32":
                    audio_arr = np.frombuffer(raw_bytes, dtype=np.float32)
                elif sample_format == "int16":
                    audio_arr = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                elif sample_format == "int32":
                    audio_arr = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
                else:
                    audio_arr = np.frombuffer(raw_bytes, dtype=np.float32)

                if audio_arr is not None and len(audio_arr) > 0:
                    if ch_count > 0 and len(audio_arr) % ch_count == 0:
                        audio_arr = audio_arr.reshape(-1, ch_count)
                    else:
                        audio_arr = audio_arr.reshape(-1, 1)

            elif body_bytes and not payload:
                # Raw binary float32 stereo stream
                raw_bytes = body_bytes
                audio_arr = np.frombuffer(raw_bytes, dtype=np.float32)
                if len(audio_arr) % 2 == 0:
                    audio_arr = audio_arr.reshape(-1, 2)
                else:
                    audio_arr = audio_arr.reshape(-1, 1)

            if audio_arr is not None and len(audio_arr) > 0:
                pushed = self.registry.push_audio_frame(audio_arr, capture_session_id=cap_session)
                await self._send_http_response(writer, 200, {
                    "status": "ok",
                    "accepted": pushed,
                    "frames": len(audio_arr),
                })
            else:
                await self._send_http_response(writer, 400, {"error": "No valid audio frames in payload"})
            return

        await self._send_http_response(writer, 404, {"error": "Not Found"})

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_addr = writer.get_extra_info("peername")
        logger.info(f"Connection attempt from {client_addr}")

        # Enforce loopback check
        if client_addr[0] not in ("127.0.0.1", "::1"):
            logger.warning(f"Rejected non-loopback connection from {client_addr}")
            writer.close()
            await writer.wait_closed()
            return

        self.registry.handle_client_connected(str(client_addr))
        if self.on_status_change:
            self.on_status_change("Connected (Awaiting Auth)")

        try:
            # Read first line to inspect if HTTP request or raw TCP JSON stream
            first_line_bytes = await reader.readline()
            if not first_line_bytes:
                return

            first_line_str = first_line_bytes.decode("utf-8", errors="replace")

            # Detect HTTP methods
            if any(first_line_str.startswith(m + " ") for m in ("GET", "POST", "OPTIONS", "PUT", "DELETE", "HEAD")):
                await self._handle_http_request(reader, writer, first_line_str)
                return

            # Otherwise handle raw TCP JSON stream
            msg = json.loads(first_line_str)
            if msg.get("action") != "auth" or not self.validate_token(msg.get("token", "")):
                logger.warning("Invalid or missing auth token from extension")
                writer.write(json.dumps({"status": "unauthorized"}).encode("utf-8") + b"\n")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                self.registry.handle_disconnect("Unauthorized token")
                return

            ext_ver = msg.get("version", "1.0.0")
            sess_id = self.registry.authenticate_client(
                extension_instance_id=msg.get("extension_id", "ext-tcp"),
                extension_version=ext_ver,
            )
            writer.write(json.dumps({
                "status": "authenticated",
                "session_id": sess_id,
                "version": "1.0.0",
                "protocol": "1.0",
            }).encode("utf-8") + b"\n")
            await writer.drain()

            if self.on_status_change:
                self.on_status_change("Authenticated & Ready")

            # Stream messages
            while self.is_running:
                header = await reader.readline()
                if not header:
                    break
                event = json.loads(header.decode("utf-8"))
                ev_type = event.get("type")

                if ev_type == "tab_selected":
                    tab_info = BrowserTabInfo(
                        tab_id=event.get("tab_id", 0),
                        title=event.get("title", "Selected Tab"),
                        audible=event.get("audible", False),
                        muted=event.get("muted", False),
                        window_id=event.get("window_id", 0),
                        active=event.get("active", True),
                    )
                    self.registry.select_tab(
                        tab_id=tab_info.tab_id,
                        title=tab_info.title,
                        audible=tab_info.audible,
                        muted=tab_info.muted,
                        window_id=tab_info.window_id,
                        active=tab_info.active,
                    )
                    if self.on_tab_selected:
                        self.on_tab_selected(tab_info)
                    if self.on_status_change:
                        self.on_status_change(f"Tab Selected: {tab_info.title[:30]}")

                elif ev_type == "audio_chunk":
                    payload_len = event.get("length", 0)
                    cap_session = event.get("capture_session_id")
                    raw_data = await reader.readexactly(payload_len)
                    audio_arr = np.frombuffer(raw_data, dtype=np.float32).reshape(-1, 2)
                    self.registry.push_audio_frame(audio_arr, capture_session_id=cap_session)

                elif ev_type == "tab_closed":
                    self.registry.clear_selected_tab()
                    if self.on_status_change:
                        self.on_status_change("Selected tab was closed")
                    break

                elif ev_type == "ping":
                    self.registry.record_heartbeat()
                    writer.write(json.dumps({"type": "pong"}).encode("utf-8") + b"\n")
                    await writer.drain()

        except Exception as ex:
            logger.error(f"Browser server error: {ex}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            # Note: Do not wipe out authenticated registry session on socket close,
            # as extension lifecycle (HTTP/polling) retains valid session state.
            if self.on_status_change:
                self.on_status_change("Ready")

    def start_background(self):
        """Starts the asyncio loop and server in a dedicated background daemon thread."""
        if self.is_running:
            return

        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self.start())
            self._loop.run_forever()

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()

    async def start(self):
        self.is_running = True
        self.registry.set_server_listening(True)
        self._server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logger.info(f"Browser integration server listening on {self.host}:{self.port}")

    async def stop(self):
        self.is_running = False
        self.registry.set_server_listening(False)
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._loop and self._loop.is_running():
            self._loop.stop()
