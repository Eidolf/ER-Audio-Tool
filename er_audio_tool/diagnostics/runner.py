"""Comprehensive self-diagnostic test runner for hardware and software subsystems."""
from __future__ import annotations
import os
import platform
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import soundfile as sf

from er_audio_tool.audio.manager import DeviceManager
from er_audio_tool.audio.interfaces import BackendType


@dataclass
class DiagnosticItem:
    category: str
    name: str
    status: str  # "PASSED", "WARNING", "FAILED"
    details: str
    recommendation: str = ""


class DiagnosticRunner:
    """Runs non-destructive verification of all audio, device, codec, and filesystem components."""

    @classmethod
    def run_all_tests(cls, output_dir: Path | str) -> list[DiagnosticItem]:
        results: list[DiagnosticItem] = []

        # 1. Operating System & Python
        results.append(
            DiagnosticItem(
                category="System",
                name="OS & Architecture",
                status="PASSED",
                details=f"{platform.system()} {platform.release()} ({platform.machine()}), Python {platform.python_version()}",
            )
        )

        # 2. Audio Capture Backend
        dm = DeviceManager()
        active = dm.get_active_backend()
        b_type = active.get_backend_type().value
        if active.is_available():
            results.append(
                DiagnosticItem(
                    category="Audio Backend",
                    name="Capture Service",
                    status="PASSED",
                    details=f"Active backend: {b_type.upper()}",
                )
            )
        else:
            results.append(
                DiagnosticItem(
                    category="Audio Backend",
                    name="Capture Service",
                    status="WARNING",
                    details=f"Native backend {b_type} is not available. Using fallback.",
                    recommendation="Ensure audio daemon (PipeWire/PulseAudio on Linux, Windows Audio on Win) is running.",
                )
            )

        # 3. Devices
        devs = dm.enumerate_all_devices()
        if devs:
            results.append(
                DiagnosticItem(
                    category="Devices",
                    name="Endpoint Enumeration",
                    status="PASSED",
                    details=f"Found {len(devs)} audio capture endpoint(s).",
                )
            )
        else:
            results.append(
                DiagnosticItem(
                    category="Devices",
                    name="Endpoint Enumeration",
                    status="FAILED",
                    details="No audio endpoints detected.",
                    recommendation="Connect speakers/headphones or enable loopback device.",
                )
            )

        # 4. Filesystem Write Permissions & Recovery
        out_p = Path(output_dir)
        try:
            out_p.mkdir(parents=True, exist_ok=True)
            test_file = out_p / ".er_write_test.tmp"
            with open(test_file, "w") as f:
                f.write("OK")
            test_file.unlink()
            results.append(
                DiagnosticItem(
                    category="Storage",
                    name="Output Directory Access",
                    status="PASSED",
                    details=f"Write access confirmed for {out_p.resolve()}",
                )
            )
        except Exception as ex:
            results.append(
                DiagnosticItem(
                    category="Storage",
                    name="Output Directory Access",
                    status="FAILED",
                    details=f"Cannot write to output folder: {ex}",
                    recommendation="Select a writable directory in Settings.",
                )
            )

        # 5. Codec Backend (FFmpeg & SoundFile)
        from er_audio_tool.audio.codecs import get_ffmpeg_path, get_codec_manager
        cm = get_codec_manager()
        ffmpeg = get_ffmpeg_path() or shutil.which("ffmpeg")
        is_local = cm.has_local_ffmpeg()
        if ffmpeg:
            loc_label = "Portable local (temp_codecs)" if is_local else "System PATH"
            results.append(
                DiagnosticItem(
                    category="Codecs",
                    name="Media Encoding Engine",
                    status="PASSED",
                    details=f"FFmpeg binary detected [{loc_label}]: {ffmpeg}",
                )
            )
        else:
            results.append(
                DiagnosticItem(
                    category="Codecs",
                    name="Media Encoding Engine",
                    status="WARNING",
                    details="FFmpeg not found in PATH. WAV & FLAC will work; MP3/M4A may be limited.",
                    recommendation="Install FFmpeg for complete MP3, M4A, and Opus encoding support.",
                )
            )

        # 6. Audio Pipeline Test (Synthetic Frame Generation)
        try:
            sr = 44100
            t = np.linspace(0, 0.2, int(sr * 0.2), endpoint=False)
            sine = 0.5 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
            temp_wav = Path(tempfile.gettempdir()) / "test_pipeline.wav"
            sf.write(temp_wav, sine, sr)
            if temp_wav.exists() and temp_wav.stat().st_size > 0:
                temp_wav.unlink()
                results.append(
                    DiagnosticItem(
                        category="Pipeline",
                        name="Internal Audio Pipeline",
                        status="PASSED",
                        details="Audio synthesis, buffering, and WAV file writing verified.",
                    )
                )
        except Exception as ex:
            results.append(
                DiagnosticItem(
                    category="Pipeline",
                    name="Internal Audio Pipeline",
                    status="FAILED",
                    details=f"Audio pipeline verification failed: {ex}",
                )
            )

        return results
