"""Linux PipeWire and PulseAudio capture backends."""
from __future__ import annotations
import shutil
import subprocess
import threading
import sys
from typing import Optional
import numpy as np

from er_audio_tool.audio.interfaces import (
    AudioCaptureBackend,
    AudioDeviceInfo,
    BackendType,
    AudioDataCallback,
)


class LinuxPipeWireBackend(AudioCaptureBackend):
    """Captures system output on modern Linux desktop via PipeWire."""

    def __init__(self):
        self._running = False
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None

    def get_backend_type(self) -> BackendType:
        return BackendType.PIPEWIRE

    def is_available(self) -> bool:
        if sys.platform != "linux":
            return False
        return shutil.which("pw-record") is not None or shutil.which("pipewire") is not None

    def enumerate_devices(self) -> list[AudioDeviceInfo]:
        if not self.is_available():
            return []
        # Return primary PipeWire system sink loopback
        return [
            AudioDeviceInfo(
                id="pipewire-default-sink-monitor",
                name="PipeWire System Output (Default Sink)",
                channels=2,
                sample_rate=48000,
                is_default=True,
                is_loopback=True,
                backend_type=BackendType.PIPEWIRE,
            )
        ]

    def start_capture(
        self,
        device: AudioDeviceInfo,
        sample_rate: int,
        channels: int,
        callback: AudioDataCallback,
    ) -> None:
        self._running = True
        pw_rec = shutil.which("pw-record")
        if not pw_rec:
            raise RuntimeError("pw-record binary is not installed in the system PATH.")

        # Dynamically find the default sink monitor name for true loopback capture.
        # pw-record with --target set to a monitor sink captures system output audio.
        monitor_target = self._find_default_sink_monitor()

        cmd = [
            pw_rec,
            "--format", "f32",
            "--rate", str(sample_rate),
            "--channels", str(channels),
        ]
        if monitor_target:
            cmd.extend(["--target", monitor_target])
        # If no monitor found, omit --target and let PipeWire pick its default
        # capture node (may still be a mic – but avoids the wrong --target 0).
        cmd.append("-")  # stdout

        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=4096 * 4 * channels
        )

        def read_loop():
            bytes_per_sample = 4  # float32
            block_samples = 1024
            chunk_size = block_samples * channels * bytes_per_sample

            while self._running and self._proc and self._proc.stdout:
                raw_bytes = self._proc.stdout.read(chunk_size)
                if not raw_bytes:
                    break
                data = np.frombuffer(raw_bytes, dtype=np.float32)
                if channels > 1:
                    data = data.reshape(-1, channels)
                else:
                    data = data.reshape(-1, 1)
                callback(data)

        self._thread = threading.Thread(target=read_loop, daemon=True)
        self._thread.start()

    def _find_default_sink_monitor(self) -> str | None:
        """Returns the PipeWire monitor target name for the default audio output sink.

        Tries pw-cli first, falls back to pactl list short sinks.
        Returns None if no monitor target can be detected.
        """
        # Strategy 1: Use pactl to find .monitor sources (works on PipeWire + PulseAudio layer)
        pactl = shutil.which("pactl")
        if pactl:
            try:
                out = subprocess.check_output(
                    [pactl, "get-default-sink"], text=True, timeout=3
                ).strip()
                if out:
                    return f"{out}.monitor"
            except Exception:
                pass
            # Fallback: list all sinks and pick first monitor
            try:
                out = subprocess.check_output(
                    [pactl, "list", "short", "sources"], text=True, timeout=3
                )
                for line in out.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and ".monitor" in parts[1]:
                        return parts[1]
            except Exception:
                pass

        # Strategy 2: pw-cli list objects
        pw_cli = shutil.which("pw-cli")
        if pw_cli:
            try:
                out = subprocess.check_output(
                    [pw_cli, "list-objects", "Node"],
                    text=True, timeout=5, stderr=subprocess.DEVNULL
                )
                for line in out.splitlines():
                    if "Monitor" in line and "name" in line.lower():
                        # Extract name value from e.g. name = "alsa_output.pci.monitor"
                        idx = line.find('"')
                        if idx != -1:
                            end = line.find('"', idx + 1)
                            if end != -1:
                                return line[idx + 1:end]
            except Exception:
                pass

        return None

    def stop_capture(self) -> None:
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1.0)
            except Exception:
                self._proc.kill()
            self._proc = None


class LinuxPulseAudioBackend(AudioCaptureBackend):
    """Fallback Linux capture backend utilizing PulseAudio monitor sources."""

    def __init__(self):
        self._running = False
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None

    def get_backend_type(self) -> BackendType:
        return BackendType.PULSEAUDIO

    def is_available(self) -> bool:
        if sys.platform != "linux":
            return False
        return shutil.which("parec") is not None or shutil.which("pulseaudio") is not None

    def enumerate_devices(self) -> list[AudioDeviceInfo]:
        if not self.is_available():
            return []
        devices = []
        pactl = shutil.which("pactl")
        if pactl:
            try:
                out = subprocess.check_output([pactl, "list", "short", "sources"], text=True)
                for line in out.strip().splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and ".monitor" in parts[1]:
                        devices.append(
                            AudioDeviceInfo(
                                id=parts[1],
                                name=f"PulseAudio Monitor: {parts[1]}",
                                channels=2,
                                sample_rate=48000,
                                is_default=len(devices) == 0,
                                is_loopback=True,
                                backend_type=BackendType.PULSEAUDIO,
                            )
                        )
            except Exception:
                pass

        if not devices:
            devices.append(
                AudioDeviceInfo(
                    id="default-pulse-monitor",
                    name="PulseAudio Default Output Monitor",
                    channels=2,
                    sample_rate=48000,
                    is_default=True,
                    is_loopback=True,
                    backend_type=BackendType.PULSEAUDIO,
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
        parec = shutil.which("parec")
        if not parec:
            raise RuntimeError("parec command is not available.")

        self._running = True
        cmd = [
            parec,
            "--format=float32le",
            f"--rate={sample_rate}",
            f"--channels={channels}",
        ]
        if device.id and device.id != "default-pulse-monitor":
            cmd.extend(["-d", str(device.id)])

        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=4096 * 4 * channels
        )

        def read_loop():
            chunk_size = 1024 * channels * 4
            while self._running and self._proc and self._proc.stdout:
                raw_bytes = self._proc.stdout.read(chunk_size)
                if not raw_bytes:
                    break
                data = np.frombuffer(raw_bytes, dtype=np.float32)
                if channels > 1:
                    data = data.reshape(-1, channels)
                else:
                    data = data.reshape(-1, 1)
                callback(data)

        self._thread = threading.Thread(target=read_loop, daemon=True)
        self._thread.start()

    def stop_capture(self) -> None:
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1.0)
            except Exception:
                self._proc.kill()
            self._proc = None
