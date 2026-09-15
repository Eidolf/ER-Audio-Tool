"""Windows WASAPI Loopback Capture Backend."""
from __future__ import annotations
import sys
import threading
from typing import Optional
import numpy as np

from er_audio_tool.audio.interfaces import (
    AudioCaptureBackend,
    AudioDeviceInfo,
    BackendType,
    AudioDataCallback,
)


class WindowsWasapiBackend(AudioCaptureBackend):
    """Windows WASAPI loopback capture from render endpoints without Stereo Mix."""

    def __init__(self):
        self._running = False
        self._stream = None

    def get_backend_type(self) -> BackendType:
        return BackendType.WASAPI

    def is_available(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import sounddevice as sd
            for api in sd.query_hostapis():
                if "wasapi" in api["name"].lower():
                    return True
        except Exception:
            pass
        return False

    def enumerate_devices(self) -> list[AudioDeviceInfo]:
        if not self.is_available():
            return []

        devices = []
        try:
            import sounddevice as sd
            wasapi_api_idx = None
            for idx, api in enumerate(sd.query_hostapis()):
                if "wasapi" in api["name"].lower():
                    wasapi_api_idx = idx
                    break

            if wasapi_api_idx is None:
                return []

            dev_list = sd.query_devices()
            for idx, dev in enumerate(dev_list):
                # We want WASAPI render endpoints (max_output_channels > 0) for loopback
                if dev["hostapi"] == wasapi_api_idx and dev["max_output_channels"] > 0:
                    devices.append(
                        AudioDeviceInfo(
                            id=idx,
                            name=f"[Output Loopback] {dev['name']}",
                            channels=dev["max_output_channels"],
                            sample_rate=int(dev["default_samplerate"]),
                            is_default=(idx == sd.default.device[1]),
                            is_loopback=True,
                            backend_type=BackendType.WASAPI,
                            extra={"is_render_endpoint": True},
                        )
                    )
        except Exception:
            pass
        return devices

    def start_capture(
        self,
        device: AudioDeviceInfo,
        sample_rate: int,
        channels: int,
        callback: AudioDataCallback,
    ) -> None:
        if not self.is_available():
            raise RuntimeError("WASAPI backend is not available on this operating system.")

        import sounddevice as sd

        self._running = True

        def sd_callback(indata, frames, time_info, status):
            if self._running and callback:
                callback(indata.copy())

        # In sounddevice, loopback on WASAPI is enabled using extra_settings
        try:
            # sounddevice.WasapiSettings(loopback=True)
            wasapi_settings = sd.WasapiSettings(loopback=True)
        except Exception:
            wasapi_settings = None

        self._stream = sd.InputStream(
            device=device.id,
            samplerate=sample_rate,
            channels=channels,
            callback=sd_callback,
            extra_settings=wasapi_settings,
        )
        self._stream.start()

    def stop_capture(self) -> None:
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
