"""Mock audio capture backend for testing and CI without audio hardware."""
from __future__ import annotations
import math
import threading
import time
import numpy as np
from er_audio_tool.audio.interfaces import (
    AudioCaptureBackend,
    AudioDeviceInfo,
    BackendType,
    AudioDataCallback,
)


class MockAudioBackend(AudioCaptureBackend):
    """Simulates an audio capture device generating synthetic tones or test signals."""

    def __init__(self, generate_tone_hz: float = 440.0):
        self.tone_hz = generate_tone_hz
        self._running = False
        self._thread: threading.Thread | None = None

    def get_backend_type(self) -> BackendType:
        return BackendType.MOCK

    def is_available(self) -> bool:
        return True

    def enumerate_devices(self) -> list[AudioDeviceInfo]:
        return [
            AudioDeviceInfo(
                id=0,
                name="Mock System Loopback Endpoint",
                channels=2,
                sample_rate=48000,
                is_default=True,
                is_loopback=True,
                backend_type=BackendType.MOCK,
            ),
            AudioDeviceInfo(
                id=1,
                name="Mock Application Capture (Process #1234)",
                channels=2,
                sample_rate=48000,
                is_default=False,
                is_loopback=True,
                backend_type=BackendType.MOCK,
            ),
        ]

    def start_capture(
        self,
        device: AudioDeviceInfo,
        sample_rate: int,
        channels: int,
        callback: AudioDataCallback,
    ) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._generate_loop,
            args=(sample_rate, channels, callback),
            daemon=True,
        )
        self._thread.start()

    def _generate_loop(self, sample_rate: int, channels: int, callback: AudioDataCallback):
        block_size = 1024
        t = 0.0
        dt = 1.0 / sample_rate
        interval = block_size / sample_rate

        while self._running:
            start_time = time.time()
            # Generate sine tone with slight harmonic
            samples_t = np.arange(block_size) * dt + t
            t += block_size * dt
            sine = 0.5 * np.sin(2 * np.pi * self.tone_hz * samples_t)
            if channels == 2:
                frame = np.column_stack((sine, sine)).astype(np.float32)
            else:
                frame = sine.reshape(-1, 1).astype(np.float32)

            callback(frame)

            elapsed = time.time() - start_time
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop_capture(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
