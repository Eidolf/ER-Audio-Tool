"""FFmpeg and Audio Codec Management Service.

Provides on-demand downloading of FFmpeg binaries to a local temporary folder
beside the application, configuration of codec scopes, runtime binary resolution,
and session exit cleanup handling.
"""
from __future__ import annotations

import os
import shutil
import sys
import tarfile
import threading
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


# Known binary distribution endpoints for static builds
FFMPEG_RELEASE_URLS = {
    "win32": {
        "essential": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        "full": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip",
    },
    "linux": {
        "essential": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",
        "full": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",
    },
    "darwin": {
        "essential": "https://evermeet.cx/ffmpeg/getrelease/zip",
        "full": "https://evermeet.cx/ffmpeg/getrelease/zip",
    },
}


@dataclass
class CodecScopeInfo:
    id: str
    name_en: str
    name_de: str
    description_en: str
    description_de: str
    codecs_en: str
    codecs_de: str


CODEC_SCOPES = {
    "essential": CodecScopeInfo(
        id="essential",
        name_en="Minimal / Audio Essentials",
        name_de="Minimal / Audio-Essentials",
        description_en="Lightweight setup containing standard decoders and encoders for common audio formats.",
        description_de="Kompaktes Paket mit Standard-Decodern und Encodern für alltägliche Audioformate.",
        codecs_en="MP3 (libmp3lame), WAV (PCM), AAC/M4A, FLAC, OGG Vorbis, Opus",
        codecs_de="MP3 (libmp3lame), WAV (PCM), AAC/M4A, FLAC, OGG Vorbis, Opus",
    ),
    "full": CodecScopeInfo(
        id="full",
        name_en="Full Audio Codec Pack",
        name_de="Vollständiges Audio-Codec-Pack",
        description_en="Complete audio suite supporting exotic, legacy, and broadcast formats and containers.",
        description_de="Vollständige Audio-Suite für exotische, ältere und Studio-Formate sowie Container.",
        codecs_en="All Essentials + ALAC, AMR, AC3, E-AC3, DTS, TrueHD, WMA, AIFF, WebM, Musepack",
        codecs_de="Alle Essentials + ALAC, AMR, AC3, E-AC3, DTS, TrueHD, WMA, AIFF, WebM, Musepack",
    ),
}


class CodecManager:
    """Manages downloading, locating, and purging local FFmpeg codecs."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir:
            self.app_root = base_dir
            self.codecs_dir = self.app_root / "temp_codecs"
        else:
            self.app_root = Path(__file__).resolve().parent.parent.parent
            # Check organized Music directory first, fallback to app-relative temp_codecs
            if os.name == "nt":
                user_prof = os.getenv("USERPROFILE", "")
                music_codecs = Path(user_prof) / "Music" / "er-audio-tool" / "Codecs" if user_prof else Path.home() / "Music" / "er-audio-tool" / "Codecs"
            else:
                music_codecs = Path.home() / "Music" / "er-audio-tool" / "Codecs"

            if (self.app_root / "er-audio-tool.portable").exists():
                self.codecs_dir = self.app_root / "temp_codecs"
            else:
                self.codecs_dir = music_codecs

    def get_codecs_dir(self) -> Path:
        return self.codecs_dir

    def has_local_ffmpeg(self) -> bool:
        return self.find_local_ffmpeg_path() is not None

    def find_local_ffmpeg_path(self) -> Optional[Path]:
        binary_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        # Search candidate directories: codecs_dir, app_root/temp_codecs, app_root/bin, app_root
        candidate_dirs = [
            self.codecs_dir,
            self.app_root / "temp_codecs",
            self.app_root / "bin",
            self.app_root,
        ]
        for cdir in candidate_dirs:
            if not cdir.exists():
                continue
            for root, _, files in os.walk(cdir):
                if binary_name in files:
                    p = Path(root) / binary_name
                    if os.access(p, os.X_OK) or sys.platform == "win32":
                        return p
        return None

    def get_active_ffmpeg(self) -> Optional[str]:
        local = self.find_local_ffmpeg_path()
        if local:
            return str(local)
        sys_path = shutil.which("ffmpeg")
        return sys_path if sys_path else None

    def delete_local_codecs(self) -> bool:
        if self.codecs_dir.exists():
            try:
                shutil.rmtree(self.codecs_dir)
                return True
            except Exception:
                return False
        return True

    def download_codecs(
        self,
        scope: str = "essential",
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> bool:
        """Downloads and extracts FFmpeg into temp_codecs directory."""
        plat = "win32" if sys.platform == "win32" else ("darwin" if sys.platform == "darwin" else "linux")
        urls = FFMPEG_RELEASE_URLS.get(plat, FFMPEG_RELEASE_URLS["linux"])
        download_url = urls.get(scope, urls.get("essential"))

        if not download_url:
            if progress_callback:
                progress_callback(0.0, f"Unsupported platform or scope: {plat}/{scope}")
            return False

        self.codecs_dir.mkdir(parents=True, exist_ok=True)
        archive_name = "ffmpeg_pack.zip" if download_url.endswith(".zip") else "ffmpeg_pack.tar.xz"
        archive_path = self.codecs_dir / archive_name

        try:
            if progress_callback:
                progress_callback(0.05, f"Connecting to {download_url}...")

            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "Mozilla/5.0 (er-audio-tool/1.0 codec-installer)"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp, open(archive_path, "wb") as out_file:
                total_size = int(resp.headers.get("content-length", 0))
                downloaded = 0
                chunk_size = 64 * 1024

                while True:
                    if cancel_event and cancel_event.is_set():
                        if progress_callback:
                            progress_callback(0.0, "Download cancelled.")
                        archive_path.unlink(missing_ok=True)
                        return False

                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and progress_callback:
                        pct = 0.05 + 0.75 * (downloaded / total_size)
                        mb = downloaded / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024)
                        progress_callback(pct, f"Downloading: {mb:.1f} MB / {total_mb:.1f} MB ({int(pct*100)}%)")

            if progress_callback:
                progress_callback(0.85, "Extracting binaries...")

            # Extract archive
            if zipfile.is_zipfile(archive_path):
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(self.codecs_dir)
            elif tarfile.is_tarfile(archive_path):
                with tarfile.open(archive_path, "r:*") as tf:
                    tf.extractall(self.codecs_dir)
            else:
                # Standalone binary
                binary_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
                dest_binary = self.codecs_dir / binary_name
                shutil.copyfile(archive_path, dest_binary)
                dest_binary.chmod(0o755)

            # Cleanup downloaded archive
            archive_path.unlink(missing_ok=True)

            # Ensure execution permissions on Unix
            local_bin = self.find_local_ffmpeg_path()
            if local_bin and sys.platform != "win32":
                local_bin.chmod(0o755)

            if progress_callback:
                progress_callback(1.0, "Codecs installed successfully!")
            return True

        except Exception as ex:
            if progress_callback:
                progress_callback(0.0, f"Installation failed: {ex}")
            archive_path.unlink(missing_ok=True)
            return False


_default_codec_manager = CodecManager()


def get_codec_manager() -> CodecManager:
    return _default_codec_manager


def get_ffmpeg_path() -> Optional[str]:
    """Resolves FFmpeg executable path prioritizing portable local codecs over system PATH."""
    return _default_codec_manager.get_active_ffmpeg()
