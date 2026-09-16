"""Audio Device and Backend Manager."""
from __future__ import annotations
import sys
from typing import Optional
from er_audio_tool.audio.interfaces import (
    AudioCaptureBackend,
    AudioDeviceInfo,
    BackendType,
)
from er_audio_tool.audio.backends.mock_backend import MockAudioBackend
from er_audio_tool.audio.backends.windows_wasapi import WindowsWasapiBackend
from er_audio_tool.audio.backends.linux_backends import (
    LinuxPipeWireBackend,
    LinuxPulseAudioBackend,
)


from er_audio_tool.audio.backends.browser_backend import BrowserTabCaptureBackend
from er_audio_tool.browser.server import BrowserServer


class DeviceManager:
    """Detects audio backends and enumerates capture endpoints across platforms with strict source isolation."""

    def __init__(self, preferred_backend: str = "auto", browser_server: BrowserServer | None = None):
        self.preferred_backend = preferred_backend
        self.browser_server = browser_server
        self._backends: dict[BackendType, AudioCaptureBackend] = {
            BackendType.MOCK: MockAudioBackend(),
            BackendType.WASAPI: WindowsWasapiBackend(),
            BackendType.PIPEWIRE: LinuxPipeWireBackend(),
            BackendType.PULSEAUDIO: LinuxPulseAudioBackend(),
        }
        if self.browser_server:
            self._backends[BackendType.BROWSER_TAB] = BrowserTabCaptureBackend(self.browser_server)

    def set_browser_server(self, server: BrowserServer):
        self.browser_server = server
        self._backends[BackendType.BROWSER_TAB] = BrowserTabCaptureBackend(server)

    def get_backend_for_source_type(self, source_mode: str) -> AudioCaptureBackend:
        """Returns the isolated backend for the specified recording source mode."""
        if self.preferred_backend == "mock":
            return self._backends[BackendType.MOCK]

        if source_mode == "rec_browser":
            if BackendType.BROWSER_TAB in self._backends:
                return self._backends[BackendType.BROWSER_TAB]
            if self.browser_server:
                b = BrowserTabCaptureBackend(self.browser_server)
                self._backends[BackendType.BROWSER_TAB] = b
                return b
            raise RuntimeError("Browser integration server is not active.")

        # System output loopback & Application audio
        if sys.platform == "win32":
            wasapi = self._backends[BackendType.WASAPI]
            if wasapi.is_available():
                return wasapi

        if sys.platform.startswith("linux"):
            pw = self._backends[BackendType.PIPEWIRE]
            if pw.is_available():
                return pw
            pulse = self._backends[BackendType.PULSEAUDIO]
            if pulse.is_available():
                return pulse

        # Only use Mock if native hardware backends are unavailable
        return self._backends[BackendType.MOCK]

    def get_active_backend(self) -> AudioCaptureBackend:
        """Selects the most capable available backend."""
        return self.get_backend_for_source_type("rec_system")

    def enumerate_all_devices(self, source_mode: str = "rec_system") -> list[AudioDeviceInfo]:
        backend = self.get_backend_for_source_type(source_mode)
        devs = backend.enumerate_devices()

        # If we are using mock backend, return mock devices
        if backend.get_backend_type() == BackendType.MOCK:
            return devs

        # Never silently inject mock devices on real hardware systems!
        # If rec_app is selected on Windows and no separate app loopback exists, return loopback output endpoints
        # so the user can still capture the active audio stream.
        if not devs and source_mode == "rec_app" and sys.platform == "win32":
            wasapi = self._backends[BackendType.WASAPI]
            return wasapi.enumerate_devices()

        return devs

