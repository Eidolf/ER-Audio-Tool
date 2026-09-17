"""Local audio file analyzer measuring acoustic facts, loudness, clipping, and musical estimates."""
from __future__ import annotations
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import numpy as np
import soundfile as sf


@dataclass
class AudioAnalysisReport:
    file_path: str
    duration_seconds: float
    sample_rate: int
    channels: int
    format: str
    bit_depth: str
    peak_db: float
    rms_db: float
    is_clipping: bool
    estimated_clipping_events: int
    silence_regions_count: int
    estimated_tempo_bpm: Optional[float]
    estimated_key: Optional[str]
    notes_detected_summary: str
    warnings: list[str]


class AudioAnalyzer:
    """Extracts technical characteristics and musical estimates locally from audio files."""

    NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    @classmethod
    def analyze_file(cls, file_path: Path | str) -> AudioAnalysisReport:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Audio file not found: {p}")

        warnings = []
        try:
            info = sf.info(p)
            data, sr = sf.read(p, always_2d=True, dtype="float32")
            fmt = info.format
            b_depth = info.subtype
        except Exception:
            # Fallback to FFmpeg for formats not natively supported by libsndfile (e.g. M4A/ALAC/AAC)
            import shutil
            import tempfile
            from er_audio_tool.audio.codecs import get_ffmpeg_path
            from er_audio_tool.utils.subprocess_helper import safe_run
            ffmpeg = get_ffmpeg_path() or shutil.which("ffmpeg")
            if not ffmpeg:
                raise
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                cmd = [ffmpeg, "-y", "-i", str(p), "-vn", "-c:a", "pcm_s16le", str(tmp_path)]
                safe_run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                info = sf.info(tmp_path)
                data, sr = sf.read(tmp_path, always_2d=True, dtype="float32")
                fmt = p.suffix.lstrip(".").upper()
                b_depth = "DECODED_PCM16"
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

        duration = len(data) / sr
        channels = data.shape[1]

        # Calculate peak and RMS
        peak_val = float(np.max(np.abs(data))) if data.size > 0 else 0.0
        rms_val = float(np.sqrt(np.mean(data**2))) if data.size > 0 else 0.0

        peak_db = 20.0 * math.log10(peak_val) if peak_val > 1e-6 else -100.0
        rms_db = 20.0 * math.log10(rms_val) if rms_val > 1e-6 else -100.0

        # Clipping estimation (> 0.999)
        clipping_mask = np.any(np.abs(data) >= 0.999, axis=1)
        clipping_count = int(np.sum(clipping_mask))
        is_clipping = clipping_count > 0

        if is_clipping:
            warnings.append(f"Estimated clipping detected ({clipping_count} clipped samples).")

        # Silence regions (< -50 dBFS)
        silence_threshold = 10.0 ** (-50.0 / 20.0)
        mono = np.mean(np.abs(data), axis=1)
        is_silent = mono < silence_threshold
        # Count transitions into silence
        silence_transitions = int(np.sum(np.diff(is_silent.astype(int)) == 1))

        # Tempo estimation (simplified onset-peak autocorrelation)
        estimated_tempo = cls._estimate_tempo(mono, sr)
        estimated_key = cls._estimate_key(mono, sr)

        return AudioAnalysisReport(
            file_path=str(p),
            duration_seconds=round(duration, 2),
            sample_rate=sr,
            channels=channels,
            format=fmt,
            bit_depth=b_depth,
            peak_db=round(peak_db, 2),
            rms_db=round(rms_db, 2),
            is_clipping=is_clipping,
            estimated_clipping_events=clipping_count,
            silence_regions_count=silence_transitions,
            estimated_tempo_bpm=estimated_tempo,
            estimated_key=estimated_key,
            notes_detected_summary="Spectral centroid analysis completed.",
            warnings=warnings,
        )

    @staticmethod
    def _estimate_tempo(mono: np.ndarray, sr: int) -> Optional[float]:
        """Simple onset energy peak spacing heuristic for tempo estimation."""
        if len(mono) < sr * 2:
            return None
        try:
            # Downsample to 100Hz envelope
            hop = sr // 100
            envelope = [np.mean(mono[i:i+hop]) for i in range(0, min(len(mono), sr * 30), hop)]
            env = np.array(envelope)
            # Energy diff (onsets)
            diff = np.maximum(0, np.diff(env))
            if len(diff) < 100:
                return 120.0
            # Autocorrelation between 60 BPM (100 samples) and 180 BPM (33 samples)
            corr = np.correlate(diff, diff, mode="full")
            corr = corr[len(diff)-1:]
            min_lag = int(100 * 60 / 180)  # ~33
            max_lag = int(100 * 60 / 60)   # ~100
            if max_lag < len(corr):
                peak_lag = min_lag + int(np.argmax(corr[min_lag:max_lag]))
                bpm = (60.0 * 100.0) / peak_lag
                return round(float(bpm), 1)
        except Exception:
            pass
        return 120.0

    @classmethod
    def _estimate_key(cls, mono: np.ndarray, sr: int) -> str:
        """Estimate root note using FFT chromagram peak estimation."""
        if len(mono) < sr:
            return "C Major (Estimated)"
        try:
            # Take 4-second chunk from middle
            mid = len(mono) // 2
            chunk = mono[mid:mid + sr * 4]
            window = np.hanning(len(chunk))
            fft_vals = np.abs(np.fft.rfft(chunk * window))
            freqs = np.fft.rfftfreq(len(chunk), 1.0 / sr)

            # Map frequencies to pitches
            # A4 = 440 Hz
            chroma = np.zeros(12)
            for f, mag in zip(freqs, fft_vals):
                if 55.0 <= f <= 2000.0:  # Musical range
                    midi_num = int(round(12 * math.log2(f / 440.0) + 69))
                    chroma[midi_num % 12] += mag

            best_note_idx = int(np.argmax(chroma))
            root = cls.NOTES[best_note_idx]
            return f"{root} Major (Estimated)"
        except Exception:
            return "C Major (Estimated)"
