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
        wasapi_settings = None
        try:
            wasapi_settings = sd.WasapiSettings(loopback=True)
        except TypeError:
            try:
                wasapi_settings = sd.WasapiSettings()
                setattr(wasapi_settings, "loopback", True)
            except Exception:
                pass
        except Exception:
            pass

        # Query native device parameters to match hardware channels exactly
        target_sr = sample_rate
        target_ch = channels
        try:
            d_info = sd.query_devices(device.id)
            native_sr = int(d_info.get("default_samplerate", sample_rate))
            # On WASAPI loopback, the input stream records from the output endpoint:
            out_ch = int(d_info.get("max_output_channels", 0))
            in_ch = int(d_info.get("max_input_channels", 0))
            device_ch = out_ch if out_ch > 0 else (in_ch if in_ch > 0 else channels)
            target_ch = device_ch if device_ch > 0 else channels
            target_sr = native_sr if native_sr > 0 else sample_rate
        except Exception:
            pass

        # Attempt stream opening with fallback strategy for channels/rates
        stream_opened = False
        candidates = [
            (target_ch, target_sr),
            (device.channels if device.channels > 0 else 2, target_sr),
            (2, target_sr),
            (1, target_sr),
            (target_ch, sample_rate),
            (2, sample_rate),
        ]
        # De-duplicate while preserving order
        seen = set()
        unique_candidates = []
        for c, s in candidates:
            if (c, s) not in seen:
                seen.add((c, s))
                unique_candidates.append((c, s))

        last_error = None
        for ch, sr in unique_candidates:
            try:
                self._stream = sd.InputStream(
                    device=device.id,
                    samplerate=sr,
                    channels=ch,
                    callback=sd_callback,
                    extra_settings=wasapi_settings,
                )
                self._stream.start()
                stream_opened = True
                break
            except Exception as ex:
                last_error = ex

        if not stream_opened:
            raise last_error or RuntimeError("Failed to open WASAPI input stream.")

    def stop_capture(self) -> None:
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
