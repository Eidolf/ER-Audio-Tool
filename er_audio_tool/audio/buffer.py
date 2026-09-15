"""Audio buffer, metering, peak detection, and clipping computation."""
from __future__ import annotations
import math
import threading
from collections import deque
import numpy as np


class AudioBuffer:
    """Thread-safe ring buffer and real-time audio statistics processor."""

    def __init__(self, max_seconds: float = 10.0, sample_rate: int = 48000, channels: int = 2):
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_samples = int(max_seconds * sample_rate)
        self._lock = threading.Lock()
        self._buffer = deque(maxlen=self.max_samples)
        self._latest_peak_db = -100.0
        self._latest_rms_db = -100.0
        self._clipping_detected = False

    def push(self, data: np.ndarray) -> None:
        """Pushes raw float32 audio samples [-1.0, 1.0]."""
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        peak = np.max(np.abs(data)) if data.size > 0 else 0.0
        rms = np.sqrt(np.mean(data**2)) if data.size > 0 else 0.0

        with self._lock:
            # Check clipping (>= 0.999 threshold)
            if peak >= 0.999:
                self._clipping_detected = True

            # Calculate dBFS (0 dBFS max)
            self._latest_peak_db = 20.0 * math.log10(peak) if peak > 1e-6 else -100.0
            self._latest_rms_db = 20.0 * math.log10(rms) if rms > 1e-6 else -100.0

            # Store recent samples in ring buffer
            # Flatten or downsample if needed for waveform display
            if data.shape[1] > 1:
                mono = np.mean(data, axis=1)
            else:
                mono = data.flatten()
            self._buffer.extend(mono.tolist())

    def get_levels(self) -> tuple[float, float, bool]:
        """Returns (peak_db, rms_db, is_clipping)."""
        with self._lock:
            clip = self._clipping_detected
            self._clipping_detected = False
            return self._latest_peak_db, self._latest_rms_db, clip

    def get_recent_waveform(self, num_points: int = 400) -> np.ndarray:
        """Returns a downsampled array of recent waveform values for UI visualization."""
        with self._lock:
            count = len(self._buffer)
            if count == 0:
                return np.zeros(num_points, dtype=np.float32)
            arr = np.array(self._buffer, dtype=np.float32)

        if count <= num_points:
            return arr
        # Resample / decimate down to num_points
        step = count / num_points
        indices = (np.arange(num_points) * step).astype(int)
        return arr[indices]

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._latest_peak_db = -100.0
            self._latest_rms_db = -100.0
            self._clipping_detected = False
