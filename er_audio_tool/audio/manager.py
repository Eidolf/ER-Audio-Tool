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


class DeviceManager:
    """Detects audio backends and enumerates capture endpoints across platforms."""

    def __init__(self, preferred_backend: str = "auto"):
        self.preferred_backend = preferred_backend
        self._backends: dict[BackendType, AudioCaptureBackend] = {
            BackendType.MOCK: MockAudioBackend(),
            BackendType.WASAPI: WindowsWasapiBackend(),
            BackendType.PIPEWIRE: LinuxPipeWireBackend(),
            BackendType.PULSEAUDIO: LinuxPulseAudioBackend(),
        }

    def get_active_backend(self) -> AudioCaptureBackend:
        """Selects the most capable available backend."""
        if self.preferred_backend == "mock":
            return self._backends[BackendType.MOCK]

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

        # Return mock backend if no native hardware/daemon capture is available
        return self._backends[BackendType.MOCK]

    def enumerate_all_devices(self) -> list[AudioDeviceInfo]:
        backend = self.get_active_backend()
        devs = backend.enumerate_devices()
        if not devs:
            # Fallback to mock
            return self._backends[BackendType.MOCK].enumerate_devices()
        return devs
