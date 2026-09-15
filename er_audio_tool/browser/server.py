"""Secure local loopback server for companion browser extension."""
from __future__ import annotations
import asyncio
import secrets
import json
import logging
from typing import Callable, Optional
import numpy as np

logger = logging.getLogger("er_audio_tool.browser")


class BrowserServer:
    """Loopback-only server (127.0.0.1) communicating securely with Chrome/Edge extension."""

    def __init__(self, host: str = "127.0.0.1", port: int = 58291, token_entropy_bytes: int = 24):
        self.host = host
        self.port = port
        self.token_entropy_bytes = token_entropy_bytes
        self.auth_token = secrets.token_hex(token_entropy_bytes)
        self.is_running = False
        self._server = None
        self.on_audio_data: Optional[Callable[[np.ndarray], None]] = None
        self.on_status_change: Optional[Callable[[str], None]] = None

    def get_pairing_token(self) -> str:
        return self.auth_token

    def regenerate_token(self) -> str:
        self.auth_token = secrets.token_hex(self.token_entropy_bytes)
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

        try:
            # First message must be authentication handshake
            line = await reader.readline()
            if not line:
                return

            msg = json.loads(line.decode("utf-8"))
            if msg.get("action") != "auth" or msg.get("token") != self.auth_token:
                logger.warning("Invalid or missing auth token from extension")
                writer.write(json.dumps({"status": "unauthorized"}).encode("utf-8") + b"\n")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

            writer.write(json.dumps({"status": "authenticated", "version": "1.0.0"}).encode("utf-8") + b"\n")
            await writer.drain()
            if self.on_status_change:
                self.on_status_change("Extension connected")

            # Stream audio messages
            while self.is_running:
                header = await reader.readline()
                if not header:
                    break
                event = json.loads(header.decode("utf-8"))
                ev_type = event.get("type")

                if ev_type == "audio_chunk":
                    # Raw PCM bytes follow or base64
                    payload_len = event.get("length", 0)
                    raw_data = await reader.readexactly(payload_len)
                    # Convert float32 array
                    audio_arr = np.frombuffer(raw_data, dtype=np.float32).reshape(-1, 2)
                    if self.on_audio_data:
                        self.on_audio_data(audio_arr)
                elif ev_type == "tab_closed":
                    if self.on_status_change:
                        self.on_status_change("Tab closed by user")
                    break
        except Exception as ex:
            logger.error(f"Browser server communication error: {ex}")
        finally:
            writer.close()
            await writer.wait_closed()
            if self.on_status_change:
                self.on_status_change("Extension disconnected")

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
