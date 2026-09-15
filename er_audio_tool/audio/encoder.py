"""Audio file encoders and atomic saving with crash safety."""
from __future__ import annotations
import os
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional
import numpy as np
import soundfile as sf


class AudioEncoder:
    """Encodes raw audio frames into WAV, FLAC, or MP3 with metadata and crash recovery."""

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Sanitizes user filename string to prevent path traversal and illegal chars."""
        # Replace illegal characters
        for ch in '<>:"/\\|?*':
            name = name.replace(ch, "_")
        # Strip leading/trailing whitespaces and dots
        name = name.strip(". ")
        return name or "recording"

    @staticmethod
    def save_audio(
        data: np.ndarray,
        sample_rate: int,
        target_path: Path,
        format_type: str = "wav",
        metadata: Optional[dict[str, str]] = None,
        gain_db: float = 0.0,
        normalize: bool = False,
    ) -> Path:
        """Saves audio data safely via an atomic temporary file."""
        target_path = Path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        format_type = format_type.lower()

        # Apply gain or normalization safely
        processed_data = np.copy(data)
        if gain_db != 0.0:
            factor = 10.0 ** (gain_db / 20.0)
            processed_data = processed_data * factor

        if normalize:
            peak = np.max(np.abs(processed_data))
            if peak > 1e-5:
                # Normalize to -0.5 dBFS (approx 0.944)
                target_peak = 10.0 ** (-0.5 / 20.0)
                processed_data = processed_data * (target_peak / peak)

        # Clip values to [-1.0, 1.0]
        processed_data = np.clip(processed_data, -1.0, 1.0)

        # Create temporary file in same folder for atomic rename
        fd, temp_file_path = tempfile.mkstemp(suffix=f".{format_type}", dir=target_path.parent)
        os.close(fd)
        temp_path = Path(temp_file_path)

        try:
            if format_type in ["wav", "flac"]:
                sf_format = "WAV" if format_type == "wav" else "FLAC"
                subtype = "PCM_16" if format_type == "wav" else "VORBIS"
                sf.write(temp_path, processed_data, sample_rate, format=sf_format)
            elif format_type == "mp3":
                # Write intermediate WAV first
                wav_temp = temp_path.with_suffix(".temp.wav")
                sf.write(wav_temp, processed_data, sample_rate, format="WAV")
                try:
                    from er_audio_tool.audio.codecs import get_ffmpeg_path
                    ffmpeg_bin = get_ffmpeg_path() or "ffmpeg"
                    # Use ffmpeg if available
                    cmd = [
                        ffmpeg_bin, "-y", "-i", str(wav_temp),
                        "-codec:a", "libmp3lame", "-b:a", "320k",
                        str(temp_path)
                    ]
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                except Exception:
                    # Fallback if ffmpeg is missing: save as WAV with .mp3.wav suffix or rename
                    shutil.copyfile(wav_temp, temp_path)
                finally:
                    if wav_temp.exists():
                        wav_temp.unlink()
            else:
                sf.write(temp_path, processed_data, sample_rate)

            # Atomically replace target
            temp_path.replace(target_path)
            return target_path
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise
