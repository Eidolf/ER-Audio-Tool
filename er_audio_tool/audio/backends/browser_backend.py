"""Dedicated audio capture backend for browser tab companion stream.

Receives audio frames exclusively from the authenticated loopback companion
extension server. Never invokes PortAudio or queries physical microphones.
Enforces atomic recording-session reservation and immutable source descriptors.
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
from er_audio_tool.browser.registry import (
    BrowserConnectionRegistry,
    BrowserTabSourceDescriptor,
    ReservationError,
)


class BrowserTabCaptureBackend(AudioCaptureBackend):
    """Captures audio frames streamed directly from paired Chrome/Edge extension."""

    def __init__(self, browser_server: BrowserServer):
        self.server = browser_server
        self.registry = getattr(browser_server, "registry", BrowserConnectionRegistry.get_instance())
        self._running = False
        self._callback: Optional[AudioDataCallback] = None
        self._active_descriptor: Optional[BrowserTabSourceDescriptor] = None

    def get_backend_type(self) -> BackendType:
        return BackendType.BROWSER_TAB

    def is_available(self) -> bool:
        return True

    def enumerate_devices(self) -> list[AudioDeviceInfo]:
        """Returns the currently selected browser tab as an isolated capture endpoint."""
        devices = []
        snap = self.registry.get_snapshot()
        if snap.selected_tab:
            tab = snap.selected_tab
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
                        "generation": tab.connection_generation,
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
        # Atomic reservation through the authoritative connection registry
        try:
            descriptor = self.registry.reserve_for_recording()
            self._active_descriptor = descriptor
        except ReservationError as re:
            raise RuntimeError(f"{re.message} (Recommendation: {re.recommendation})")
        except Exception as ex:
            raise RuntimeError(f"Browser tab capture reservation failed: {ex}")

        self._running = True
        self._callback = callback

        def on_browser_audio(chunk: np.ndarray, capture_session_id: str):
            if self._running and self._callback:
                if not self._active_descriptor or self._active_descriptor.capture_session_id == capture_session_id:
                    self._callback(chunk)

        self.registry.set_audio_frame_consumer(on_browser_audio)

    def stop_capture(self) -> None:
        self._running = False
        self._callback = None
        self.registry.finish_capture_session()
        self._active_descriptor = None
