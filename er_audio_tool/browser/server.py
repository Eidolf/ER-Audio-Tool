"""Secure local loopback server for companion browser extension."""
from __future__ import annotations
import asyncio
import json
import logging
import secrets
import threading
from dataclasses import dataclass
from typing import Callable, Optional
import numpy as np


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

    def __init__(self, host: str = "127.0.0.1", port: int = 58291, token_entropy_bytes: int = 24):
        self.host = host
        self.port = port
        self.token_entropy_bytes = token_entropy_bytes
        self.auth_token = secrets.token_hex(token_entropy_bytes)
        self.is_running = False
        self._server = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        
        # State tracking
        self.is_connected = False
        self.is_authenticated = False
        self.extension_version: str | None = None
        self.selected_tab: BrowserTabInfo | None = None
        self.available_tabs: list[BrowserTabInfo] = []
        self.received_frames_count = 0
        self.last_audio_timestamp = 0.0

        self.on_audio_data: Optional[Callable[[np.ndarray], None]] = None
        self.on_status_change: Optional[Callable[[str], None]] = None
        self.on_tab_selected: Optional[Callable[[BrowserTabInfo], None]] = None

    def get_pairing_token(self) -> str:
        return self.auth_token

    def regenerate_token(self) -> str:
        self.auth_token = secrets.token_hex(self.token_entropy_bytes)
        self.is_authenticated = False
        return self.auth_token

    def validate_token(self, token: str) -> bool:
        return bool(token and secrets.compare_digest(self.auth_token, token))

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_addr = writer.get_extra_info("peername")
        logger.info(f"Connection attempt from {client_addr}")

        # Enforce loopback check
        if client_addr[0] not in ("127.0.0.1", "::1"):
            logger.warning(f"Rejected non-loopback connection from {client_addr}")
            writer.close()
            await writer.wait_closed()
            return

        self.is_connected = True
        if self.on_status_change:
            self.on_status_change("Connected (Awaiting Auth)")

        try:
            # First message must be authentication handshake
            line = await reader.readline()
            if not line:
                return

            msg = json.loads(line.decode("utf-8"))
            if msg.get("action") != "auth" or not self.validate_token(msg.get("token", "")):
                logger.warning("Invalid or missing auth token from extension")
                writer.write(json.dumps({"status": "unauthorized"}).encode("utf-8") + b"\n")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                self.is_connected = False
                self.is_authenticated = False
                return

            self.is_authenticated = True
            self.extension_version = msg.get("version", "1.0.0")
            writer.write(json.dumps({
                "status": "authenticated",
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
                    self.selected_tab = tab_info
                    if self.on_tab_selected:
                        self.on_tab_selected(tab_info)
                    if self.on_status_change:
                        self.on_status_change(f"Tab Selected: {tab_info.title[:30]}")

                elif ev_type == "tabs_list":
                    tabs_data = event.get("tabs", [])
                    self.available_tabs = [
                        BrowserTabInfo(
                            tab_id=t.get("id", 0),
                            title=t.get("title", "Tab"),
                            audible=t.get("audible", False),
                            muted=t.get("muted", False),
                            window_id=t.get("windowId", 0),
                            active=t.get("active", False),
                        )
                        for t in tabs_data
                    ]

                elif ev_type == "audio_chunk":
                    payload_len = event.get("length", 0)
                    raw_data = await reader.readexactly(payload_len)
                    audio_arr = np.frombuffer(raw_data, dtype=np.float32).reshape(-1, 2)
                    self.received_frames_count += len(audio_arr)
                    self.last_audio_timestamp = asyncio.get_event_loop().time()
                    if self.on_audio_data:
                        self.on_audio_data(audio_arr)

                elif ev_type == "tab_closed":
                    self.selected_tab = None
                    if self.on_status_change:
                        self.on_status_change("Selected tab was closed")
                    break

                elif ev_type == "ping":
                    writer.write(json.dumps({"type": "pong"}).encode("utf-8") + b"\n")
                    await writer.drain()

        except Exception as ex:
            logger.error(f"Browser server error: {ex}")
        finally:
            self.is_connected = False
            self.is_authenticated = False
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            if self.on_status_change:
                self.on_status_change("Disconnected")

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
        self._server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logger.info(f"Browser integration server listening on {self.host}:{self.port}")

    async def stop(self):
        self.is_running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._loop and self._loop.is_running():
            self._loop.stop()

