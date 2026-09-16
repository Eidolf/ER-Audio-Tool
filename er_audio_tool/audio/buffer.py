"""Audio buffer, metering, peak detection, and clipping computation."""
from __future__ import annotations
import math
import threading
from collections import deque
import numpy as np


class AudioBuffer:
    """Thread-safe ring buffer and real-time audio statistics processor with stereo L/R support."""

    def __init__(self, max_seconds: float = 10.0, sample_rate: int = 48000, channels: int = 2):
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_samples = int(max_seconds * sample_rate)
        self._lock = threading.Lock()
        self._buffer = deque(maxlen=self.max_samples)
        self._latest_peak_db = -100.0
        self._latest_rms_db = -100.0
        self._peak_l_db = -100.0
        self._peak_r_db = -100.0
        self._clipping_detected = False
        self._active_session_id: str | None = None
        self._frame_count = 0

    def set_active_session(self, session_id: str | None) -> None:
        with self._lock:
            self._active_session_id = session_id
            self._frame_count = 0
            self._latest_peak_db = -100.0
            self._latest_rms_db = -100.0
            self._peak_l_db = -100.0
            self._peak_r_db = -100.0
            self._clipping_detected = False
            self._buffer.clear()

    def push(self, data: np.ndarray, session_id: str | None = None) -> None:
        """Pushes raw float32 audio samples [-1.0, 1.0]."""
        with self._lock:
            if self._active_session_id and session_id and self._active_session_id != session_id:
                # Reject stale frames from prior session
                return

        # Handle integer PCM normalization if needed
        if np.issubdtype(data.dtype, np.integer):
            if data.dtype == np.int16:
                data = data.astype(np.float32) / 32768.0
            elif data.dtype == np.int32:
                data = data.astype(np.float32) / 2147483648.0

        if data.ndim == 1:
            data = data.reshape(-1, 1)

        frames = len(data)
        if frames == 0:
            return

        # Compute per-channel peak
        pk_l = float(np.max(np.abs(data[:, 0]))) if data.shape[1] > 0 else 0.0
        pk_r = float(np.max(np.abs(data[:, 1]))) if data.shape[1] > 1 else pk_l

        peak = max(pk_l, pk_r)
        rms = float(np.sqrt(np.mean(data**2)))

        pk_l_db = 20.0 * math.log10(pk_l) if pk_l > 1e-6 else -100.0
        pk_r_db = 20.0 * math.log10(pk_r) if pk_r > 1e-6 else -100.0
        overall_pk_db = 20.0 * math.log10(peak) if peak > 1e-6 else -100.0
        overall_rms_db = 20.0 * math.log10(rms) if rms > 1e-6 else -100.0

        with self._lock:
            self._frame_count += frames
            if peak >= 0.999:
                self._clipping_detected = True

            self._peak_l_db = pk_l_db
            self._peak_r_db = pk_r_db
            self._latest_peak_db = overall_pk_db
            self._latest_rms_db = overall_rms_db

            # Store recent samples in ring buffer
            if data.shape[1] > 1:
                mono = np.mean(data, axis=1)
            else:
                mono = data.flatten()
            self._buffer.extend(mono.tolist())

    def get_levels(self) -> tuple[float, float, bool]:
        """Returns (peak_db, rms_db, is_clipping) with decay."""
        with self._lock:
            clip = self._clipping_detected
            self._clipping_detected = False
            pk = self._latest_peak_db
            rms = self._latest_rms_db
            # Smoothly decay meter levels towards silence (-100 dB)
            self._latest_peak_db = max(-100.0, self._latest_peak_db - 3.0)
            self._latest_rms_db = max(-100.0, self._latest_rms_db - 3.0)
            return pk, rms, clip

    def get_stereo_levels(self) -> tuple[float, float, float, float, bool, int]:
        """Returns (peak_l_db, peak_r_db, peak_db, rms_db, is_clipping, frame_count) with decay."""
        with self._lock:
            clip = self._clipping_detected
            self._clipping_detected = False
            pk_l = self._peak_l_db
            pk_r = self._peak_r_db
            pk = self._latest_peak_db
            rms = self._latest_rms_db
            frames = self._frame_count
            # Smoothly decay meter levels by ~3 dB per 50ms polling cycle
            self._peak_l_db = max(-100.0, self._peak_l_db - 3.0)
            self._peak_r_db = max(-100.0, self._peak_r_db - 3.0)
            self._latest_peak_db = max(-100.0, self._latest_peak_db - 3.0)
            self._latest_rms_db = max(-100.0, self._latest_rms_db - 3.0)
            return (
                pk_l,
                pk_r,
                pk,
                rms,
                clip,
                frames,
            )

    def get_recent_waveform(self, num_points: int = 400) -> np.ndarray:
        """Returns a downsampled array of recent waveform values for UI visualization."""
        with self._lock:
            count = len(self._buffer)
            if count == 0:
                return np.zeros(num_points, dtype=np.float32)
            arr = np.array(self._buffer, dtype=np.float32)

        if count <= num_points:
            return arr
        step = count / num_points
        indices = (np.arange(num_points) * step).astype(int)
        return arr[indices]

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._latest_peak_db = -100.0
            self._latest_rms_db = -100.0
            self._peak_l_db = -100.0
            self._peak_r_db = -100.0
            self._clipping_detected = False
            self._frame_count = 0

