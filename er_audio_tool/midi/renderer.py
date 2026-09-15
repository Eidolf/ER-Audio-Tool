"""Local MIDI to MP3 / WAV synthesizer and rendering engine."""
from __future__ import annotations
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import numpy as np
import soundfile as sf
from er_audio_tool.midi.model import NoteEvent


class MidiRenderer:
    """Renders MIDI files or note events to audio using internal wavetable or fluidsynth."""

    @classmethod
    def render_notes_to_audio(
        cls,
        notes: list[NoteEvent],
        output_path: Path | str,
        sample_rate: int = 44100,
        instrument: str = "acoustic_piano",
        format_type: str = "mp3",
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not notes:
            total_duration = 1.0
        else:
            total_duration = max(n.end_time for n in notes) + 0.5

        total_samples = int(total_duration * sample_rate)
        audio = np.zeros(total_samples, dtype=np.float32)

        for n in notes:
            # Frequency from MIDI pitch
            freq = 440.0 * (2.0 ** ((n.pitch - 69) / 12.0))
            start_sample = int(n.start_time * sample_rate)
            dur_samples = int(n.duration * sample_rate)
            end_sample = min(total_samples, start_sample + dur_samples)

            length = end_sample - start_sample
            if length <= 0:
                continue

            t = np.arange(length) / sample_rate
            # Additive synthesis with harmonics for richer acoustic tone
            wave = (
                0.6 * np.sin(2 * np.pi * freq * t) +
                0.25 * np.sin(2 * np.pi * (freq * 2) * t) +
                0.1 * np.sin(2 * np.pi * (freq * 3) * t) +
                0.05 * np.sin(2 * np.pi * (freq * 4) * t)
            )

            # ADSR envelope (Attack, Decay, Sustain, Release)
            attack_len = min(length, int(0.01 * sample_rate))
            decay_len = min(length - attack_len, int(0.05 * sample_rate))
            sustain_level = 0.7

            envelope = np.ones(length, dtype=np.float32) * sustain_level
            if attack_len > 0:
                envelope[:attack_len] = np.linspace(0.0, 1.0, attack_len)
            if decay_len > 0:
                envelope[attack_len:attack_len + decay_len] = np.linspace(1.0, sustain_level, decay_len)

            # Release tail
            rel_len = min(length, int(0.05 * sample_rate))
            if rel_len > 0:
                envelope[-rel_len:] *= np.linspace(1.0, 0.0, rel_len)

            gain = (n.velocity / 127.0) * 0.4
            audio[start_sample:end_sample] += (wave * envelope * gain).astype(np.float32)

        # Normalize and prevent clipping
        peak = np.max(np.abs(audio))
        if peak > 0.95:
            audio = audio * (0.95 / peak)

        # Stereo
        stereo = np.column_stack((audio, audio))

        # Save to file
        temp_wav = output_path.with_suffix(".temp.wav")
        sf.write(temp_wav, stereo, sample_rate, format="WAV")

        from er_audio_tool.audio.codecs import get_ffmpeg_path
        ffmpeg_bin = get_ffmpeg_path() or shutil.which("ffmpeg")

        if format_type.lower() == "mp3" and ffmpeg_bin:
            try:
                cmd = [
                    ffmpeg_bin, "-y", "-i", str(temp_wav),
                    "-codec:a", "libmp3lame", "-b:a", "256k",
                    str(output_path)
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            except Exception:
                # Fallback to copy wav
                shutil.copyfile(temp_wav, output_path)
            finally:
                if temp_wav.exists():
                    temp_wav.unlink()
        else:
            shutil.move(temp_wav, output_path)

        return output_path
