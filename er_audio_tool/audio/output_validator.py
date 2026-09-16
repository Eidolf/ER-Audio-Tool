"""Output audio verification and empty/silent recording validation."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
import numpy as np
import soundfile as sf


class OutputClassification(str, Enum):
    VALID_SIGNAL = "VALID_SIGNAL"
    DIGITAL_SILENCE = "DIGITAL_SILENCE"
    NO_FRAMES = "NO_FRAMES"
    TRUNCATED = "TRUNCATED"
    DECODE_FAILURE = "DECODE_FAILURE"


@dataclass
class OutputValidationResult:
    is_valid: bool
    classification: OutputClassification
    file_path: Path
    file_size_bytes: int
    duration_seconds: float
    frame_count: int
    channels: int
    sample_rate: int
    peak_db: float
    rms_db: float
    error_message: Optional[str] = None


class OutputValidator:
    """Validates recorded audio files post-finalization to detect empty or silent output."""

    @staticmethod
    def validate_file(file_path: Path | str) -> OutputValidationResult:
        path = Path(file_path)
        if not path.exists():
            return OutputValidationResult(
                is_valid=False,
                classification=OutputClassification.DECODE_FAILURE,
                file_path=path,
                file_size_bytes=0,
                duration_seconds=0.0,
                frame_count=0,
                channels=0,
                sample_rate=0,
                peak_db=-100.0,
                rms_db=-100.0,
                error_message=f"File not found: {path}",
            )

        file_size = path.stat().st_size
        if file_size == 0:
            return OutputValidationResult(
                is_valid=False,
                classification=OutputClassification.NO_FRAMES,
                file_path=path,
                file_size_bytes=0,
                duration_seconds=0.0,
                frame_count=0,
                channels=0,
                sample_rate=0,
                peak_db=-100.0,
                rms_db=-100.0,
                error_message="File is 0 bytes (empty container)",
            )

        try:
            info = sf.info(str(path))
        except Exception as ex:
            return OutputValidationResult(
                is_valid=False,
                classification=OutputClassification.DECODE_FAILURE,
                file_path=path,
                file_size_bytes=file_size,
                duration_seconds=0.0,
                frame_count=0,
                channels=0,
                sample_rate=0,
                peak_db=-100.0,
                rms_db=-100.0,
                error_message=f"Failed to read audio container header: {ex}",
            )

        if info.frames <= 0 or info.duration <= 0.0:
            return OutputValidationResult(
                is_valid=False,
                classification=OutputClassification.NO_FRAMES,
                file_path=path,
                file_size_bytes=file_size,
                duration_seconds=0.0,
                frame_count=0,
                channels=info.channels,
                sample_rate=info.samplerate,
                peak_db=-100.0,
                rms_db=-100.0,
                error_message="Container header valid but contains 0 audio frames",
            )

        # Read samples to verify content signal vs digital silence
        try:
            data, sr = sf.read(str(path), dtype="float32")
            if data.ndim == 1:
                data = data.reshape(-1, 1)

            peak = float(np.max(np.abs(data))) if len(data) > 0 else 0.0
            rms = float(np.sqrt(np.mean(data**2))) if len(data) > 0 else 0.0

            peak_db = 20.0 * np.log10(peak) if peak > 1e-6 else -100.0
            rms_db = 20.0 * np.log10(rms) if rms > 1e-6 else -100.0

            if peak < 1e-5:
                classification = OutputClassification.DIGITAL_SILENCE
            else:
                classification = OutputClassification.VALID_SIGNAL

            return OutputValidationResult(
                is_valid=True,
                classification=classification,
                file_path=path,
                file_size_bytes=file_size,
                duration_seconds=info.duration,
                frame_count=info.frames,
                channels=info.channels,
                sample_rate=info.samplerate,
                peak_db=peak_db,
                rms_db=rms_db,
            )
        except Exception as ex:
            return OutputValidationResult(
                is_valid=False,
                classification=OutputClassification.DECODE_FAILURE,
                file_path=path,
                file_size_bytes=file_size,
                duration_seconds=info.duration,
                frame_count=info.frames,
                channels=info.channels,
                sample_rate=info.samplerate,
                peak_db=-100.0,
                rms_db=-100.0,
                error_message=f"Failed reading audio frames: {ex}",
            )
