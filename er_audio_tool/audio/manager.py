"""Audio Device and Backend Manager with strict source isolation."""
from __future__ import annotations
import sys
from typing import Optional
from er_audio_tool.audio.interfaces import (
    AudioCaptureBackend,
    AudioDeviceInfo,
    BackendType,
)
from er_audio_tool.audio.backends.mock_backend import MockAudioBackend
from er_audio_tool.audio.backends.windows_wasapi import (
    WindowsSystemOutputCapture,
    WindowsApplicationAudioCapture,
    WindowsMicrophoneCapture,
)
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
        self._win_system_capture = WindowsSystemOutputCapture()
        self._win_app_capture = WindowsApplicationAudioCapture()
        self._win_mic_capture = WindowsMicrophoneCapture()

        self._backends: dict[BackendType, AudioCaptureBackend] = {
            BackendType.MOCK: MockAudioBackend(),
            BackendType.WASAPI: self._win_system_capture,
            BackendType.PIPEWIRE: LinuxPipeWireBackend(),
            BackendType.PULSEAUDIO: LinuxPulseAudioBackend(),
        }
        if self.browser_server:
            self._backends[BackendType.BROWSER_TAB] = BrowserTabCaptureBackend(self.browser_server)

    def set_browser_server(self, server: BrowserServer):
        self.browser_server = server
        self._backends[BackendType.BROWSER_TAB] = BrowserTabCaptureBackend(server)

    def get_backend_for_source_type(self, source_mode: str) -> AudioCaptureBackend:
        """Returns the isolated backend for the specified recording source mode.
        
        Strict rules:
        - rec_browser: returns BrowserTabCaptureBackend (never mic)
        - rec_system: returns WindowsSystemOutputCapture (never mic)
        - rec_app: returns WindowsApplicationAudioCapture (never mic)
        - rec_mic: returns WindowsMicrophoneCapture
        """
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

        if sys.platform == "win32":
            if source_mode == "rec_system":
                if self._win_system_capture.is_available():
                    return self._win_system_capture
                raise RuntimeError("WASAPI System Output loopback backend is unavailable.")
            elif source_mode == "rec_app":
                if self._win_app_capture.is_available():
                    return self._win_app_capture
                raise RuntimeError(
                    "Windows Application-specific Audio Capture is currently unavailable. "
                    "The installed backend does not implement Windows process loopback."
                )
            elif source_mode == "rec_mic":
                if self._win_mic_capture.is_available():
                    return self._win_mic_capture
                raise RuntimeError("Microphone backend is unavailable.")
            else:
                return self._win_system_capture

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
        return devs
