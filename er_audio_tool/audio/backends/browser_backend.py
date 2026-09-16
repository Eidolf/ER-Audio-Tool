"""Dedicated audio capture backend for browser tab companion stream.

Receives audio frames exclusively from the authenticated loopback companion
extension server. Never invokes PortAudio or queries physical microphones.
"""
from __future__ import annotations
import threading
import time
from typing import Optional
import numpy as np

from er_audio_tool.audio.interfaces import (
    AudioCaptureBackend,
    AudioDeviceInfo,
    BackendType,
    DeviceCapability,
    AudioDataCallback,
)
from er_audio_tool.browser.server import BrowserServer, BrowserTabInfo


class BrowserTabCaptureBackend(AudioCaptureBackend):
    """Captures audio frames streamed directly from paired Chrome/Edge extension."""

    def __init__(self, browser_server: BrowserServer):
        self.server = browser_server
        self._running = False
        self._callback: Optional[AudioDataCallback] = None

    def get_backend_type(self) -> BackendType:
        return BackendType.BROWSER_TAB

    def is_available(self) -> bool:
        return True

    def enumerate_devices(self) -> list[AudioDeviceInfo]:
        """Returns the currently selected or available browser tabs as capture endpoints."""
        devices = []
        if self.server.selected_tab:
            tab = self.server.selected_tab
            devices.append(
                AudioDeviceInfo(
                    id=f"tab_{tab.tab_id}",
                    name=f"[Browser Tab] {tab.title[:45]}",
                    channels=2,
                    sample_rate=48000,
                    is_default=True,
                    is_loopback=True,
                    backend_type=BackendType.BROWSER_TAB,
                    capability=DeviceCapability.BROWSER_STREAM,
                    extra={
                        "tab_id": tab.tab_id,
                        "title": tab.title,
                        "audible": tab.audible,
                    },
                )
            )
        elif self.server.available_tabs:
            for tab in self.server.available_tabs:
                devices.append(
                    AudioDeviceInfo(
                        id=f"tab_{tab.tab_id}",
                        name=f"[Browser Tab] {tab.title[:45]}",
                        channels=2,
                        sample_rate=48000,
                        is_default=tab.active,
                        is_loopback=True,
                        backend_type=BackendType.BROWSER_TAB,
                        capability=DeviceCapability.BROWSER_STREAM,
                        extra={
                            "tab_id": tab.tab_id,
                            "title": tab.title,
                            "audible": tab.audible,
                        },
                    )
                )
        else:
            devices.append(
                AudioDeviceInfo(
                    id="browser_tab_pending",
                    name="[Browser Tab] Waiting for extension tab selection...",
                    channels=2,
                    sample_rate=48000,
                    is_default=True,
                    is_loopback=True,
                    backend_type=BackendType.BROWSER_TAB,
                    capability=DeviceCapability.BROWSER_STREAM,
                )
            )
        return devices

    def start_capture(
        self,
        device: AudioDeviceInfo,
        sample_rate: int,
        channels: int,
        callback: AudioDataCallback,
    ) -> None:
        if not self.server.is_authenticated:
            raise RuntimeError(
                "Browser extension is not paired and authenticated. "
                "Open Record > Browser Tab, copy the session token into the extension popup, and select a tab."
            )

        self._running = True
        self._callback = callback

        def on_browser_audio(chunk: np.ndarray):
            if self._running and self._callback:
                self._callback(chunk)

        self.server.on_audio_data = on_browser_audio

    def stop_capture(self) -> None:
        self._running = False
        self._callback = None
        self.server.on_audio_data = None
