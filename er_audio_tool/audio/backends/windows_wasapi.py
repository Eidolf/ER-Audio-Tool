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
                if dev["hostapi"] != wasapi_api_idx:
                    continue
                out_ch = dev.get("max_output_channels", 0)
                in_ch = dev.get("max_input_channels", 0)

                # Classify capability
                if out_ch > 0:
                    cap = DeviceCapability.OUTPUT_LOOPBACK
                    name = f"[Output Loopback] {dev['name']}"
                    ch_count = out_ch
                elif in_ch > 0:
                    cap = DeviceCapability.PHYSICAL_INPUT
                    name = f"[Input Device] {dev['name']}"
                    ch_count = in_ch
                else:
                    cap = DeviceCapability.UNSUPPORTED
                    name = f"[Unsupported] {dev['name']}"
                    ch_count = 0

                devices.append(
                    AudioDeviceInfo(
                        id=idx,
                        name=name,
                        channels=ch_count,
                        sample_rate=int(dev.get("default_samplerate", 48000)),
                        is_default=(idx == sd.default.device[1] or idx == sd.default.device[0]),
                        is_loopback=(out_ch > 0),
                        backend_type=BackendType.WASAPI,
                        capability=cap,
                        extra={
                            "max_output_channels": out_ch,
                            "max_input_channels": in_ch,
                            "default_samplerate": dev.get("default_samplerate"),
                            "is_render_endpoint": (out_ch > 0),
                        },
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

        # Validate device existence in PortAudio
        all_devs = []
        try:
            all_devs = sd.query_devices()
        except Exception:
            pass

        if isinstance(device.id, int) and (device.id < 0 or device.id >= len(all_devs)):
            raise RuntimeError(
                f"Audio endpoint ID {device.id} ('{device.name}') is not recognized by Windows PortAudio.\n"
                f"Total active devices detected: {len(all_devs)}.\n"
                f"Recommendation: Refresh device list or check Windows sound configuration."
            )

        # Query native device parameters
        d_info = {}
        try:
            d_info = sd.query_devices(device.id)
        except Exception as ex:
            raise RuntimeError(f"Cannot query properties for audio endpoint {device.id} ('{device.name}'): {ex}")

        native_out_ch = int(d_info.get("max_output_channels", 0))
        native_in_ch = int(d_info.get("max_input_channels", 0))
        native_sr = int(d_info.get("default_samplerate", sample_rate))

        is_render = (native_out_ch > 0) or device.is_loopback

        wasapi_settings = None
        if is_render:
            try:
                wasapi_settings = sd.WasapiSettings(loopback=True)
            except Exception:
                try:
                    wasapi_settings = sd.WasapiSettings()
                    setattr(wasapi_settings, "loopback", True)
                except Exception:
                    pass

        # Target channels: for loopback, always respect the hardware mix format (never force mono on stereo hardware)
        if is_render:
            target_ch = native_out_ch if native_out_ch > 0 else 2
        else:
            target_ch = native_in_ch if native_in_ch > 0 else channels

        target_sr = native_sr if native_sr > 0 else sample_rate

        def sd_callback(indata, frames, time_info, status):
            if self._running and callback:
                data = indata.copy()
                # Post-capture channel downmixing / adaptation:
                # If caller specifically asked for mono (channels==1), downmix cleanly
                if channels == 1 and data.shape[1] > 1:
                    data = np.mean(data, axis=1, keepdims=True)
                elif channels == 2 and data.shape[1] == 1:
                    data = np.column_stack((data, data))
                elif channels == 2 and data.shape[1] > 2:
                    # Quad/Surround (4ch, 5.1ch, 7.1ch) downmix to stereo
                    # Left = Front-L + 0.707*Center + 0.707*Rear-L
                    # Right = Front-R + 0.707*Center + 0.707*Rear-R
                    fl = data[:, 0]
                    fr = data[:, 1]
                    if data.shape[1] >= 4:
                        rl = data[:, 2]
                        rr = data[:, 3]
                        left_mix = 0.6 * fl + 0.4 * rl
                        right_mix = 0.6 * fr + 0.4 * rr
                        data = np.column_stack((left_mix, right_mix))
                    else:
                        data = data[:, :2]
                elif channels > 0 and data.shape[1] > channels:
                    data = data[:, :channels]
                callback(data)

        # Ranked format candidates
        candidates = []
        if is_render:
            # Render endpoints MUST use loopback settings and must NEVER fall back to standard input stream (which captures microphone)
            if wasapi_settings is None:
                raise RuntimeError(
                    f"WASAPI loopback settings could not be initialized for render endpoint '{device.name}'. "
                    f"Microphone fallback is strictly prohibited for System Audio."
                )
            # 1. Native output mix layout & rate (GetMixFormat match)
            candidates.append((target_ch, target_sr, wasapi_settings, "Method 1: Native Driver Mix Format"))
            # 2. Stereo & native rate
            candidates.append((2, target_sr, wasapi_settings, "Method 2: Stereo Native Rate"))
            # 3. Native output mix & 48000 Hz (standard for Realtek & Intel HD Audio)
            candidates.append((target_ch, 48000, wasapi_settings, "Method 3: Native Channels 48kHz"))
            # 4. Stereo & 48000 Hz
            candidates.append((2, 48000, wasapi_settings, "Method 4: Stereo 48kHz Shared"))
            # 5. Stereo & 44100 Hz
            candidates.append((2, 44100, wasapi_settings, "Method 5: Stereo 44.1kHz Shared"))
            # 6. Fallback to 4-channel surround if multichannel Realtek endpoint
            if native_out_ch >= 4:
                candidates.append((4, 48000, wasapi_settings, "Method 6: Quad Surround 48kHz (Downmixed)"))
                candidates.append((4, 44100, wasapi_settings, "Method 7: Quad Surround 44.1kHz (Downmixed)"))
        else:
            candidates.append((target_ch, target_sr, None, "Native Input Format"))
            candidates.append((channels, target_sr, None, "Requested Channels"))
            candidates.append((2, target_sr, None, "Stereo Input"))
            candidates.append((1, target_sr, None, "Mono Input"))

        seen = set()
        unique_candidates = []
        for c, s, w, desc in candidates:
            k = (c, s, w is not None)
            if k not in seen:
                seen.add(k)
                unique_candidates.append((c, s, w, desc))

        stream_opened = False
        attempted_log = []
        last_error = None

        for ch, sr, extra, desc in unique_candidates:
            try:
                self._stream = sd.InputStream(
                    device=device.id,
                    samplerate=sr,
                    channels=ch,
                    callback=sd_callback,
                    extra_settings=extra,
                )
                self._stream.start()
                stream_opened = True
                attempted_log.append(f"[OK] {desc} ({ch}ch @ {sr}Hz)")
                self._negotiated_format = {
                    "device": device.name,
                    "channels": ch,
                    "sample_rate": sr,
                    "loopback": extra is not None,
                    "strategy": desc,
                }
                break
            except Exception as ex:
                last_error = ex
                err_msg = str(ex).strip().replace("\n", " ")
                attempted_log.append(f"[FAIL] {desc} ({ch}ch @ {sr}Hz): {err_msg}")

        if not stream_opened:
            attempts_report = "\n".join(f"  • {entry}" for entry in attempted_log)
            err_detail = (
                f"Audio Capture konnte nicht gestartet werden.\n\n"
                f"Geräteinformationen:\n"
                f"  • Endpunkt: '{device.name}' (ID: {device.id})\n"
                f"  • Treiber Max In: {native_in_ch}, Max Out: {native_out_ch}, Standardrate: {native_sr} Hz\n\n"
                f"Versuchte Methoden:\n{attempts_report}\n\n"
                f"Unterliegender Fehler: {last_error}\n\n"
                f"Empfohlene Abhilfemaßnahmen:\n"
                f"1. Sicherstellen, dass auf diesem Ausgabegerät eine Audiowiedergabe aktiv ist.\n"
                f"2. Windows-Soundeinstellungen prüfen (Wiedergabe > Eigenschaften > Erweitert: 24/16 Bit, 48000 Hz Standardformat).\n"
                f"3. Exklusiven Modus in Windows deaktivieren, damit Shared Loopback möglich ist."
            )
            raise RuntimeError(err_detail)

    def stop_capture(self) -> None:
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
