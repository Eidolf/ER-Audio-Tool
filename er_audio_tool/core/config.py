"""Versioned settings schema and migration manager."""
from __future__ import annotations
import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

CURRENT_SCHEMA_VERSION = 2


@dataclass
class AppConfig:
    version: int = CURRENT_SCHEMA_VERSION
    language: str = "en"  # "en" or "de"
    theme: str = "dark"
    # Audio capture settings
    backend: str = "auto"  # "auto", "wasapi", "pipewire", "pulseaudio", "alsa", "mock"
    device_id: int = -1  # -1 = system default
    sample_rate: int = 48000
    channels: int = 2
    format: str = "wav"  # "wav", "flac", "mp3"
    bitrate: int = 320  # kbps for MP3
    # Recording management
    output_dir: str = ""
    filename_template: str = "Recording_{date}_{time}"
    auto_split: bool = False
    split_interval_mins: int = 60
    silence_split: bool = False
    silence_threshold_db: float = -45.0
    silence_duration_secs: float = 3.0
    # Gain / Audio normalization
    gain_db: float = 0.0
    normalize_enabled: bool = False
    limiter_enabled: bool = True
    # Audio to MIDI
    transcription_profile: str = "melody"  # "melody", "polyphonic", "monophonic", "piano"
    confidence_threshold: float = 0.5
    # MIDI synthesis
    soundfont_path: str = ""
    synth_backend: str = "builtin"  # "builtin" or "fluidsynth"
    # Privacy & Updates
    check_for_updates: bool = False
    anonymize_metadata: bool = True
    include_url_metadata: bool = False
    portable_mode: bool = False


class ConfigManager:
    """Manages reading, validating, migrating, and writing application preferences."""

    def __init__(self, base_dir: Path | None = None):
        self.portable = False
        app_root = Path(__file__).resolve().parent.parent.parent

        # Check for portable mode indicator flag file
        if (app_root / "er-audio-tool.portable").exists():
            self.portable = True
            self.config_dir = app_root / "config"
        elif base_dir:
            self.config_dir = base_dir
        else:
            if os.name == "nt":
                self.config_dir = Path(os.getenv("APPDATA", "")) / "er-audio-tool"
            else:
                self.config_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "er-audio-tool"

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        self.config = self.load()

    def default_output_dir(self) -> str:
        if self.portable:
            out = Path(__file__).resolve().parent.parent.parent / "recordings"
        else:
            if os.name == "nt":
                out = Path(os.getenv("USERPROFILE", "")) / "Music" / "Recordings"
            else:
                out = Path.home() / "Music" / "Recordings"
        out.mkdir(parents=True, exist_ok=True)
        return str(out)

    def load(self) -> AppConfig:
        if not self.config_file.exists():
            cfg = AppConfig(portable_mode=self.portable)
            cfg.output_dir = self.default_output_dir()
            self.save(cfg)
            return cfg

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            migrated_data = self._migrate(raw_data)
            # Filter unknown keys to prevent crashes
            known_keys = {f.name for f in AppConfig.__dataclass_fields__.values()}
            filtered_data = {k: v for k, v in migrated_data.items() if k in known_keys}
            cfg = AppConfig(**filtered_data)
            if not cfg.output_dir:
                cfg.output_dir = self.default_output_dir()
            return cfg
        except Exception:
            # Create a backup of corrupt configuration
            backup_path = self.config_dir / "config.corrupt.json"
            if self.config_file.exists():
                shutil.copyfile(self.config_file, backup_path)
            cfg = AppConfig(portable_mode=self.portable)
            cfg.output_dir = self.default_output_dir()
            self.save(cfg)
            return cfg

    def _migrate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Performs version migrations on settings dictionary."""
        version = data.get("version", 1)

        # Migration from legacy Loopback Recorder (version 1 or no version)
        if version < 2:
            migrated = dict(data)
            migrated["version"] = 2
            # Map legacy keys if present
            if "format" in migrated and isinstance(migrated["format"], str):
                migrated["format"] = migrated["format"].lower()
            if "gain" in migrated and "gain_db" not in migrated:
                migrated["gain_db"] = float(migrated.pop("gain", 0.0))
            if "save_dir" in migrated and "output_dir" not in migrated:
                migrated["output_dir"] = migrated.pop("save_dir")
            return migrated

        return data

    def save(self, config: AppConfig) -> None:
        self.config = config
        tmp_file = self.config_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, indent=2)
        tmp_file.replace(self.config_file)
