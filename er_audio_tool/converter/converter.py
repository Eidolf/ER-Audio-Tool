"""Comprehensive Audio Converter supporting M4A (AAC/ALAC), MP3, WAV, FLAC, OGG, and Opus."""
from __future__ import annotations
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
import numpy as np
import soundfile as sf


@dataclass
class ConversionJob:
    input_file: Path
    output_format: str = "mp3"
    bitrate_kbps: int = 320
    normalize: bool = False
    output_dir: Optional[Path] = None


@dataclass
class ConversionResult:
    input_path: str
    output_path: Optional[str]
    success: bool
    error_message: Optional[str] = None
    duration_seconds: float = 0.0


class AudioConverter:
    """Decodes and encodes audio with container and codec detection."""

    SUPPORTED_INPUT_EXTENSIONS = {
        ".m4a", ".mp4", ".aac", ".mp3", ".wav", ".flac", ".ogg", ".opus", ".aiff", ".wma"
    }
    SUPPORTED_OUTPUT_FORMATS = {"mp3", "wav", "flac", "ogg", "opus"}

    @classmethod
    def convert_file(
        cls,
        job: ConversionJob,
        progress_cb: Optional[Callable[[float], None]] = None,
    ) -> ConversionResult:
        in_path = Path(job.input_file)
        if not in_path.exists():
            return ConversionResult(str(in_path), None, False, "Input file does not exist.")

        out_dir = job.output_dir or in_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        out_format = job.output_format.lower()
        target_name = f"{in_path.stem}.{out_format}"
        out_path = out_dir / target_name

        # Prevent overwriting input file
        if out_path.resolve() == in_path.resolve():
            target_name = f"{in_path.stem}_converted.{out_format}"
            out_path = out_dir / target_name

        from er_audio_tool.audio.codecs import get_ffmpeg_path
        ffmpeg = get_ffmpeg_path() or shutil.which("ffmpeg")

        # 1. Direct ffmpeg conversion if available (handles all containers including M4A AAC/ALAC)
        if ffmpeg:
            try:
                cmd = [
                    ffmpeg, "-y", "-i", str(in_path)
                ]
                if job.normalize:
                    cmd.extend(["-filter:a", "loudnorm"])

                if out_format == "mp3":
                    cmd.extend(["-codec:a", "libmp3lame", "-b:a", f"{job.bitrate_kbps}k"])
                elif out_format == "flac":
                    cmd.extend(["-codec:a", "flac"])
                elif out_format == "wav":
                    cmd.extend(["-codec:a", "pcm_s16le"])
                elif out_format == "ogg":
                    cmd.extend(["-codec:a", "libvorbis", "-q:a", "6"])
                elif out_format == "opus":
                    cmd.extend(["-codec:a", "libopus", "-b:a", "128k"])

                cmd.append(str(out_path))

                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

                # Validate output
                if out_path.exists() and out_path.stat().st_size > 0:
                    info = sf.info(out_path)
                    return ConversionResult(str(in_path), str(out_path), True, duration_seconds=info.duration)
            except Exception as ex:
                pass

        # 2. SoundFile fallback (for WAV, FLAC, OGG)
        try:
            data, sr = sf.read(in_path, always_2d=True, dtype="float32")
            if job.normalize:
                peak = np.max(np.abs(data))
                if peak > 1e-5:
                    data = data * (0.95 / peak)

            sf_format = "WAV" if out_format == "wav" else ("FLAC" if out_format == "flac" else "OGG")
            sf.write(out_path, data, sr, format=sf_format)

            info = sf.info(out_path)
            return ConversionResult(str(in_path), str(out_path), True, duration_seconds=info.duration)
        except Exception as ex:
            return ConversionResult(
                str(in_path), None, False,
                f"Conversion failed: {ex}. (Ensure FFmpeg is installed for M4A/MP3 codecs.)"
            )

    @classmethod
    def batch_convert(
        cls,
        files: list[Path],
        output_format: str,
        output_dir: Path,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> list[ConversionResult]:
        results = []
        total = len(files)
        for idx, file in enumerate(files):
            job = ConversionJob(input_file=file, output_format=output_format, output_dir=output_dir)
            res = cls.convert_file(job)
            results.append(res)
            if progress_cb:
                progress_cb(idx + 1, total)
        return results
