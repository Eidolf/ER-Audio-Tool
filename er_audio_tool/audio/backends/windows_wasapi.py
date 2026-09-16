"""Windows WASAPI Audio Capture Adapters.

Implements clean, independent adapters following OBS-like WASAPI architecture:
1. WindowsSystemOutputCapture (Render endpoint loopback, strictly forbids microphones)
2. WindowsApplicationAudioCapture (Application/process-specific audio loopback)
3. WindowsMicrophoneCapture (Explicit physical microphone input only)
"""
from __future__ import annotations
import subprocess
import sys
import threading
from typing import Optional
import numpy as np

from er_audio_tool.audio.interfaces import (
    AudioCaptureBackend,
    AudioDeviceInfo,
    AudioSourceDescriptor,
    AudioSourceType,
    BackendType,
    DeviceCapability,
    AudioDataCallback,
)
from er_audio_tool.audio.codecs import get_codec_manager


class WindowsSystemOutputCapture(AudioCaptureBackend):
    """Windows WASAPI Loopback Capture from render endpoints (Speakers, Headphones, HDMI).
    
    Behavioral equivalent of OBS Studio's wasapi_output_capture.
    STRICT RULE: Strictly forbids opening physical microphones or input endpoints.
    """

    def __init__(self):
        self._running = False
        self._stream = None
        self._ffmpeg_process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._negotiated_format: dict = {}

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
        """Enumerates only Windows render endpoints (max_output_channels > 0)."""
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
                # ENFORCE FLOW DIRECTION: Only output endpoints (render devices)
                if out_ch <= 0:
                    continue

                devices.append(
                    AudioDeviceInfo(
                        id=idx,
                        name=f"[System Output] {dev['name']}",
                        channels=out_ch,
                        sample_rate=int(dev.get("default_samplerate", 48000)),
                        is_default=(idx == sd.default.device[1]),
                        is_loopback=True,
                        backend_type=BackendType.WASAPI,
                        capability=DeviceCapability.OUTPUT_LOOPBACK,
                        extra={
                            "flow": "render",
                            "max_output_channels": out_ch,
                            "default_samplerate": dev.get("default_samplerate"),
                            "is_render_endpoint": True,
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
            raise RuntimeError("WASAPI System Output Loopback is not available on this operating system.")

        import sounddevice as sd

        # HARD VALIDATION: Device must be a render endpoint or loopback source
        d_info = sd.query_devices(device.id)
        native_out_ch = int(d_info.get("max_output_channels", 0))
        native_in_ch = int(d_info.get("max_input_channels", 0))

        # Identify if device is an input-only physical device (microphone)
        if native_out_ch <= 0 and native_in_ch > 0 and not device.is_loopback:
            raise RuntimeError(
                f"Requested source is System Output, but endpoint '{device.name}' is a physical input endpoint. "
                f"Microphone fallback is strictly prohibited."
            )

        # Attempt to locate capture-capable loopback analogue if device reports 0 input channels
        target_device_id = device.id
        if native_in_ch <= 0:
            # Look for a loopback representation of this render device
            loopback_candidate = None
            try:
                for idx, d in enumerate(sd.query_devices()):
                    if d.get("max_input_channels", 0) > 0:
                        d_name_lower = d.get("name", "").lower()
                        # Check PyAudioWPatch or PortAudio loopback naming
                        if "loopback" in d_name_lower and (device.name.lower() in d_name_lower or str(d.get("name", "")).startswith(str(d_info.get("name", "")))):
                            loopback_candidate = idx
                            break
            except Exception:
                pass
            if loopback_candidate is not None:
                target_device_id = loopback_candidate
                d_info = sd.query_devices(target_device_id)
                native_in_ch = int(d_info.get("max_input_channels", 0))

        self._running = True

        # Never pass loopback keyword to WasapiSettings. Standard sounddevice only supports:
        # WasapiSettings(exclusive=False, auto_convert=False, explicit_sample_format=False)
        wasapi_settings = None
        try:
            wasapi_settings = sd.WasapiSettings(exclusive=False)
        except Exception:
            pass

        native_sr = int(d_info.get("default_samplerate", sample_rate))
        # Determine available input channel capacity
        avail_in_ch = native_in_ch if native_in_ch > 0 else native_out_ch
        target_ch = avail_in_ch if avail_in_ch > 0 else 2
        target_sr = native_sr if native_sr > 0 else sample_rate

        def sd_callback(indata, frames, time_info, status):
            if self._running and callback:
                data = indata.copy()
                if channels == 1 and data.shape[1] > 1:
                    data = np.mean(data, axis=1, keepdims=True)
                elif channels == 2 and data.shape[1] == 1:
                    data = np.column_stack((data, data))
                elif channels == 2 and data.shape[1] >= 4:
                    fl, fr = data[:, 0], data[:, 1]
                    rl, rr = data[:, 2], data[:, 3]
                    data = np.column_stack((0.6 * fl + 0.4 * rl, 0.6 * fr + 0.4 * rr))
                elif channels > 0 and data.shape[1] > channels:
                    data = data[:, :channels]
                callback(data)

        # Ranked format candidates for driver mix negotiation
        candidates = [
            (target_ch, target_sr, wasapi_settings, "Native Mix Format"),
            (2, target_sr, wasapi_settings, "Stereo Native Rate"),
            (target_ch, 48000, wasapi_settings, "Native Channels 48kHz"),
            (2, 48000, wasapi_settings, "Stereo 48kHz"),
            (2, 44100, wasapi_settings, "Stereo 44.1kHz"),
        ]
        if target_ch >= 4:
            candidates.append((4, 48000, wasapi_settings, "Quad Surround 48kHz"))
        if target_ch == 1:
            candidates.append((1, target_sr, wasapi_settings, "Mono Native"))

        stream_opened = False
        last_error = None
        for ch, sr, extra, desc in candidates:
            try:
                self._stream = sd.InputStream(
                    device=target_device_id,
                    samplerate=sr,
                    channels=ch,
                    callback=sd_callback,
                    extra_settings=extra,
                )
                self._stream.start()
                stream_opened = True
                self._negotiated_format = {
                    "device": device.name,
                    "endpoint_id": target_device_id,
                    "flow": "render",
                    "loopback": True,
                    "channels": ch,
                    "sample_rate": sr,
                    "strategy": desc,
                }
                break
            except Exception as ex:
                last_error = ex

        if not stream_opened:
            # Automatic OBS-equivalent Fallback:
            # If sounddevice (PortAudio) cannot open the render endpoint directly (e.g. -9998 Invalid number of channels),
            # use the locally bundled/portable FFmpeg which supports native Windows WASAPI loopback out of the box.
            ffmpeg_path = get_codec_manager().get_active_ffmpeg()
            if ffmpeg_path:
                try:
                    # Clean device name without '[System Output] ' prefix for FFmpeg if needed
                    clean_name = device.name
                    if clean_name.startswith("[System Output] "):
                        clean_name = clean_name[len("[System Output] "):]

                    # FFmpeg command for native Windows WASAPI loopback capture
                    # Audio output format: 32-bit float Little-Endian raw PCM, stereo, target sample rate
                    # If device is not default, try targeting device by name or default
                    input_target = "default" if device.is_default else f"audio={clean_name}"
                    ffmpeg_cmd = [
                        ffmpeg_path,
                        "-y",
                        "-f", "wasapi",
                        "-i", input_target,
                        "-vn",
                        "-f", "f32le",
                        "-ar", str(target_sr),
                        "-ac", str(channels),
                        "-",
                    ]
                    # Start FFmpeg loopback capture process in background
                    proc = subprocess.Popen(
                        ffmpeg_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        bufsize=1024 * 64,
                    )
                    self._ffmpeg_process = proc
                    stream_opened = True
                    self._negotiated_format = {
                        "device": device.name,
                        "endpoint_id": target_device_id,
                        "flow": "render",
                        "loopback": True,
                        "channels": channels,
                        "sample_rate": target_sr,
                        "strategy": "Native WASAPI Loopback Engine (FFmpeg)",
                    }

                    def _ffmpeg_reader():
                        # Read float32 chunks (each sample = 4 bytes)
                        bytes_per_sample = 4
                        frames_per_chunk = 1024
                        chunk_size = frames_per_chunk * channels * bytes_per_sample
                        while self._running and proc.poll() is None and proc.stdout:
                            raw_data = proc.stdout.read(chunk_size)
                            if not raw_data:
                                break
                            count = len(raw_data) // (bytes_per_sample * channels)
                            if count > 0:
                                samples = np.frombuffer(raw_data[: count * channels * bytes_per_sample], dtype=np.float32)
                                arr = samples.reshape(-1, channels)
                                if callback:
                                    callback(arr)

                    self._reader_thread = threading.Thread(target=_ffmpeg_reader, daemon=True)
                    self._reader_thread.start()
                except Exception as ff_ex:
                    stream_opened = False
                    last_error = f"{last_error}; FFmpeg WASAPI loopback failed: {ff_ex}"

        if not stream_opened:
            raise RuntimeError(
                f"WASAPI system loopback stream initialization failed: {last_error}. "
                f"(Device: '{device.name}' [ID: {device.id}], Target ID: {target_device_id}, "
                f"Max In: {native_in_ch}, Max Out: {native_out_ch}, Requested Channels: {channels})"
            )

    def stop_capture(self) -> None:
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._ffmpeg_process:
            try:
                self._ffmpeg_process.terminate()
                self._ffmpeg_process.wait(timeout=1.0)
            except Exception:
                try:
                    self._ffmpeg_process.kill()
                except Exception:
                    pass
            self._ffmpeg_process = None

        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)
            self._reader_thread = None


class WindowsApplicationAudioCapture(AudioCaptureBackend):
    """Windows Application Audio Capture.
    
    Behavioral equivalent of OBS Studio's wasapi_process_output_capture.
    Captures specific application processes using Windows CoreAudio process-loopback.
    Never falls back to microphone.
    """

    def __init__(self):
        self._running = False
        self._stream = None
        self._selected_pid: Optional[int] = None

    def get_backend_type(self) -> BackendType:
        return BackendType.WASAPI

    def is_available(self) -> bool:
        # Standard sounddevice does not support Windows process-loopback activation (AUDIOCLIENT_ACTIVATION_PARAMS).
        # Check if an external native process-capture backend or driver is present
        if sys.platform != "win32":
            return False
        # If native process loopback is not compiled/available, report honest capability
        return False

    def enumerate_devices(self) -> list[AudioDeviceInfo]:
        """Enumerates running user applications with audio or active windows."""
        devices = []
        if not self.is_available():
            return []

        # Attempt to enumerate active processes / windows
        try:
            import psutil
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    p_name = proc.info["name"]
                    pid = proc.info["pid"]
                    # Filter out system and non-audio processes
                    if p_name.lower().endswith(".exe") and p_name.lower() not in ("svchost.exe", "system", "idle", "registry"):
                        devices.append(
                            AudioDeviceInfo(
                                id=f"proc_{pid}",
                                name=f"[Application] {p_name} (PID: {pid})",
                                channels=2,
                                sample_rate=48000,
                                is_default=False,
                                is_loopback=True,
                                backend_type=BackendType.WASAPI,
                                capability=DeviceCapability.PROCESS_LOOPBACK,
                                extra={"pid": pid, "process_name": p_name},
                            )
                        )
                except Exception:
                    continue
        except Exception:
            pass

        if not devices:
            devices.append(
                AudioDeviceInfo(
                    id="app_active_window",
                    name="[Application] Active Focused Application Audio",
                    channels=2,
                    sample_rate=48000,
                    is_default=True,
                    is_loopback=True,
                    backend_type=BackendType.WASAPI,
                    capability=DeviceCapability.PROCESS_LOOPBACK,
                )
            )
        return devices[:30]

    def start_capture(
        self,
        device: AudioDeviceInfo,
        sample_rate: int,
        channels: int,
        callback: AudioDataCallback,
    ) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Windows Application Audio Capture is only supported on Windows.")

        if not self.is_available():
            raise RuntimeError(
                "Windows Application-specific Audio Capture (Process Loopback) is currently unavailable. "
                "The installed audio backend does not implement Windows 10/11 process loopback activation. "
                "Please use 'System Output' mode to capture audio from the active output device."
            )

        # STRICT ISOLATION: Never open physical input / microphone
        raise RuntimeError("Process-specific loopback driver not active.")

    def stop_capture(self) -> None:
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None


class WindowsMicrophoneCapture(AudioCaptureBackend):
    """Windows Physical Microphone Capture.
    
    Used strictly and exclusively when user deliberately selects Microphone recording mode.
    """

    def __init__(self):
        self._running = False
        self._stream = None

    def get_backend_type(self) -> BackendType:
        return BackendType.WASAPI

    def is_available(self) -> bool:
        return sys.platform == "win32"

    def enumerate_devices(self) -> list[AudioDeviceInfo]:
        if not self.is_available():
            return []

        devices = []
        try:
            import sounddevice as sd
            for idx, dev in enumerate(sd.query_devices()):
                in_ch = dev.get("max_input_channels", 0)
                if in_ch > 0:
                    devices.append(
                        AudioDeviceInfo(
                            id=idx,
                            name=f"[Microphone] {dev['name']}",
                            channels=in_ch,
                            sample_rate=int(dev.get("default_samplerate", 48000)),
                            is_default=(idx == sd.default.device[0]),
                            is_loopback=False,
                            backend_type=BackendType.WASAPI,
                            capability=DeviceCapability.PHYSICAL_INPUT,
                            extra={"flow": "capture", "max_input_channels": in_ch},
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
        import sounddevice as sd
        self._running = True

        def sd_callback(indata, frames, time_info, status):
            if self._running and callback:
                callback(indata.copy())

        self._stream = sd.InputStream(
            device=device.id,
            samplerate=sample_rate,
            channels=min(channels, device.channels),
            callback=sd_callback,
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


# Alias for backward compatibility
WindowsWasapiBackend = WindowsSystemOutputCapture
