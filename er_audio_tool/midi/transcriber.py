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

    PROFILE_CONFIGS = {
        "melody": {"min_pitch": 40, "max_pitch": 88, "min_freq": 80.0, "max_freq": 1100.0, "conf": 0.38, "min_dur": 0.08, "channel": 0},
        "piano": {"min_pitch": 21, "max_pitch": 108, "min_freq": 27.5, "max_freq": 4186.0, "conf": 0.32, "min_dur": 0.06, "channel": 1},
        "bass": {"min_pitch": 24, "max_pitch": 60, "min_freq": 32.0, "max_freq": 260.0, "conf": 0.40, "min_dur": 0.10, "channel": 2},
        "vocals": {"min_pitch": 45, "max_pitch": 84, "min_freq": 110.0, "max_freq": 1050.0, "conf": 0.42, "min_dur": 0.09, "channel": 3},
        "percussive": {"min_pitch": 35, "max_pitch": 81, "min_freq": 60.0, "max_freq": 900.0, "conf": 0.50, "min_dur": 0.04, "channel": 9},
    }

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

        prof = profile.lower()
        if prof == "full_arrangement":
            return cls._transcribe_full_arrangement(p)
        if prof == "percussive":
            return cls._transcribe_percussion(mono, sr)

        cfg = cls.PROFILE_CONFIGS.get(prof, cls.PROFILE_CONFIGS["melody"])
        conf_thresh = cfg["conf"]
        eff_min_duration = min_duration if min_duration != 0.08 else cfg["min_dur"]
        channel = cfg.get("channel", 0)

        notes: list[NoteEvent] = []

        # Analysis frame configuration
        hop_size = int(sr * 0.015)  # 15ms hops for sharper onset tracking
        window_size = int(sr * 0.06)  # 60ms window

        if len(mono) < window_size:
            return notes

        current_note: Optional[tuple[int, float]] = None  # (pitch, start_time)

        for i in range(0, len(mono) - window_size, hop_size):
            chunk = mono[i:i + window_size]
            t = i / sr

            # RMS energy threshold for silence
            rms = float(np.sqrt(np.mean(chunk**2)))
            if rms < 0.008:
                # Silence; close open note
                if current_note:
                    pitch, start_t = current_note
                    dur = t - start_t
                    if dur >= eff_min_duration:
                        notes.append(NoteEvent(pitch=pitch, start_time=start_t, duration=dur, channel=channel))
                    current_note = None
                continue

            # Estimate pitch via enhanced autocorrelation & harmonic filtering
            pitch = cls._detect_pitch(chunk, sr, cfg, conf_thresh)
            min_p = cfg["min_pitch"]
            max_p = cfg["max_pitch"]

            if pitch is not None and min_p <= pitch <= max_p:
                if current_note is None:
                    current_note = (pitch, t)
                elif current_note[0] != pitch:
                    # Note transition
                    old_pitch, start_t = current_note
                    dur = t - start_t
                    if dur >= eff_min_duration:
                        notes.append(NoteEvent(pitch=old_pitch, start_time=start_t, duration=dur, channel=channel))
                    current_note = (pitch, t)
            else:
                if current_note:
                    pitch, start_t = current_note
                    dur = t - start_t
                    if dur >= eff_min_duration:
                        notes.append(NoteEvent(pitch=pitch, start_time=start_t, duration=dur, channel=channel))
                    current_note = None

        if current_note:
            pitch, start_t = current_note
            dur = (len(mono) / sr) - start_t
            if dur >= eff_min_duration:
                notes.append(NoteEvent(pitch=pitch, start_time=start_t, duration=dur, channel=channel))

        return notes

    @classmethod
    def _transcribe_percussion(cls, mono: np.ndarray, sr: int) -> list[NoteEvent]:
        """Detects transient onsets and maps them to General MIDI drum channels (Channel 9/10)."""
        notes: list[NoteEvent] = []
        hop = int(sr * 0.02)
        if len(mono) < hop * 4:
            return notes

        # Spectral flux onset envelope
        rms_vals = [float(np.sqrt(np.mean(mono[i:i + hop]**2))) for i in range(0, len(mono) - hop, hop)]
        diffs = np.diff(rms_vals)
        threshold = max(0.015, float(np.mean(diffs) + 2.0 * np.std(diffs)))

        min_spacing_frames = int(0.08 / 0.02)  # 80ms minimum spacing
        last_onset = -999

        for idx, d in enumerate(diffs):
            if d > threshold and (idx - last_onset) >= min_spacing_frames:
                last_onset = idx
                t = idx * 0.02
                # Frequency analysis of transient chunk to map Kick (36) vs Snare (38) vs Hi-Hat (42)
                start_sample = idx * hop
                chunk = mono[start_sample:start_sample + int(sr * 0.04)]
                if len(chunk) > 0:
                    fft = np.abs(np.fft.rfft(chunk))
                    freqs = np.fft.rfftfreq(len(chunk), 1.0 / sr)
                    spectral_centroid = float(np.sum(freqs * fft) / (np.sum(fft) + 1e-6))
                    if spectral_centroid < 350:
                        drum_pitch = 36  # Bass Drum / Kick
                    elif spectral_centroid < 1500:
                        drum_pitch = 38  # Acoustic Snare
                    else:
                        drum_pitch = 42  # Closed Hi-Hat
                else:
                    drum_pitch = 38
                notes.append(NoteEvent(pitch=drum_pitch, start_time=t, duration=0.08, velocity=95, channel=9))

        return notes

    @staticmethod
    def _detect_pitch(chunk: np.ndarray, sr: int, cfg: dict, min_conf: float) -> Optional[int]:
        """Detects fundamental pitch using first-significant-peak autocorrelation."""
        win = np.hanning(len(chunk))
        windowed = chunk * win

        corr = np.correlate(windowed, windowed, mode="full")
        corr = corr[len(chunk) - 1:]

        min_freq = cfg.get("min_freq", 50.0)
        max_freq = cfg.get("max_freq", 1200.0)

        min_lag = max(1, int(sr / max_freq))
        max_lag = min(len(corr) - 1, int(sr / min_freq))

        if min_lag >= max_lag or max_lag >= len(corr) or corr[0] <= 0:
            return None

        # Search for peaks: we look for local maxima above the confidence threshold
        # Taking the FIRST prominent local maximum ensures we capture the fundamental (f0)
        # rather than submultiples (f0/2, f0/3) which also peak in periodic signals.
        norm_corr = corr / float(corr[0])

        best_lag = None
        for lag in range(min_lag, max_lag - 1):
            if norm_corr[lag] > min_conf:
                # Local maximum check
                if norm_corr[lag] >= norm_corr[lag - 1] and norm_corr[lag] >= norm_corr[lag + 1]:
                    best_lag = lag
                    break

        # Fallback to argmax if no discrete first local peak detected
        if best_lag is None:
            search_region = corr[min_lag:max_lag]
            if len(search_region) == 0:
                return None
            peak_offset = int(np.argmax(search_region))
            best_lag = min_lag + peak_offset
            if norm_corr[best_lag] < min_conf:
                return None

        f0 = sr / float(best_lag)
        if f0 <= 0:
            return None

        midi_pitch = int(round(12 * math.log2(f0 / 440.0) + 69))
        return midi_pitch

    @classmethod
    def _transcribe_full_arrangement(cls, audio_path: Path | str) -> list[NoteEvent]:
        """Performs 4-stem separation first, then transcribes stems into synchronized multitrack MIDI channels."""
        from er_audio_tool.analysis.separator import StemSeparator
        import tempfile

        p = Path(audio_path)
        all_notes: list[NoteEvent] = []

        with tempfile.TemporaryDirectory(prefix="er_arr_") as tmpdir:
            stems = StemSeparator.separate_file(p, tmpdir)
            # 1. Bass stem -> Bass profile (Channel 2)
            if "bass" in stems and stems["bass"].file_path.exists():
                all_notes.extend(cls.transcribe(stems["bass"].file_path, profile="bass"))
            # 2. Drums stem -> Percussive profile (Channel 9)
            if "drums" in stems and stems["drums"].file_path.exists():
                all_notes.extend(cls.transcribe(stems["drums"].file_path, profile="percussive"))
            # 3. Vocals stem -> Vocals profile (Channel 3)
            if "vocals" in stems and stems["vocals"].file_path.exists():
                all_notes.extend(cls.transcribe(stems["vocals"].file_path, profile="vocals"))
            # 4. Other stem -> Piano profile (Channel 1)
            if "other" in stems and stems["other"].file_path.exists():
                all_notes.extend(cls.transcribe(stems["other"].file_path, profile="piano"))

        # Sort all notes chronologically
        all_notes.sort(key=lambda n: n.start_time)
        return all_notes

