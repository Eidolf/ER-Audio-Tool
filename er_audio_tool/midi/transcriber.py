"""Local Audio-to-MIDI transcription engine using pitch detection and onset tracking."""
from __future__ import annotations
import math
from pathlib import Path
from typing import Optional
import numpy as np
import soundfile as sf
from er_audio_tool.midi.model import NoteEvent


class AudioToMidiTranscriber:
    """Offline audio-to-MIDI transcriber without external ML framework dependencies."""

    @classmethod
    def transcribe(
        cls,
        audio_path: Path | str,
        profile: str = "melody",
        confidence_threshold: float = 0.5,
        min_duration: float = 0.08,
    ) -> list[NoteEvent]:
        p = Path(audio_path)
        data, sr = sf.read(p, always_2d=True, dtype="float32")
        mono = np.mean(data, axis=1)

        notes: list[NoteEvent] = []

        # Analysis frame configuration
        hop_size = int(sr * 0.02)  # 20ms hops
        window_size = int(sr * 0.06)  # 60ms window

        if len(mono) < window_size:
            return notes

        current_note: Optional[tuple[int, float]] = None  # (pitch, start_time)

        for i in range(0, len(mono) - window_size, hop_size):
            chunk = mono[i:i + window_size]
            t = i / sr

            # RMS energy threshold for silence
            rms = np.sqrt(np.mean(chunk**2))
            if rms < 0.01:
                # Silence; close open note
                if current_note:
                    pitch, start_t = current_note
                    dur = t - start_t
                    if dur >= min_duration:
                        notes.append(NoteEvent(pitch=pitch, start_time=start_t, duration=dur))
                    current_note = None
                continue

            # Estimate pitch via autocorrelation
            pitch = cls._detect_pitch(chunk, sr)
            if pitch is not None and 21 <= pitch <= 108:  # Standard 88-key piano range
                if current_note is None:
                    current_note = (pitch, t)
                elif current_note[0] != pitch:
                    # Note transition
                    old_pitch, start_t = current_note
                    dur = t - start_t
                    if dur >= min_duration:
                        notes.append(NoteEvent(pitch=old_pitch, start_time=start_t, duration=dur))
                    current_note = (pitch, t)
            else:
                if current_note:
                    pitch, start_t = current_note
                    dur = t - start_t
                    if dur >= min_duration:
                        notes.append(NoteEvent(pitch=pitch, start_time=start_t, duration=dur))
                    current_note = None

        if current_note:
            pitch, start_t = current_note
            dur = (len(mono) / sr) - start_t
            if dur >= min_duration:
                notes.append(NoteEvent(pitch=pitch, start_time=start_t, duration=dur))

        return notes

    @staticmethod
    def _detect_pitch(chunk: np.ndarray, sr: int) -> Optional[int]:
        """Detects fundamental pitch using autocorrelation peak finding."""
        corr = np.correlate(chunk, chunk, mode="full")
        corr = corr[len(chunk) - 1:]

        # Pitch range: 50 Hz (MIDI 23) to 1000 Hz (MIDI 83)
        min_lag = int(sr / 1000)
        max_lag = int(sr / 50)

        if max_lag >= len(corr):
            return None

        # Search for highest peak in lag interval
        search_region = corr[min_lag:max_lag]
        if len(search_region) == 0:
            return None

        peak_offset = np.argmax(search_region)
        peak_lag = min_lag + peak_offset
        peak_val = corr[peak_lag]

        # Normalized autocorrelation confidence
        if corr[0] > 0 and (peak_val / corr[0]) > 0.4:
            f0 = sr / peak_lag
            midi_pitch = int(round(12 * math.log2(f0 / 440.0) + 69))
            return midi_pitch
        return None
