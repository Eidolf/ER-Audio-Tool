"""Centralized dynamic application version resolution."""
from __future__ import annotations
import os
import subprocess
from pathlib import Path

from er_audio_tool.utils.subprocess_helper import safe_run

# Fallback default if no Git or package metadata is present
FALLBACK_VERSION = "0.4.0"


def get_version() -> str:
    """Resolves application version from:
    1. APP_VERSION environment variable (set during CI/CD build or release packaging)
    2. Embedded _version.txt in application assets or bundle directory
    3. Python package metadata (importlib.metadata)
    4. Git tag via `git describe --tags` (during development)
    5. Fallback version constant
    """
    # 1. Environment variable (set during CI release builds)
    env_ver = os.environ.get("APP_VERSION", "").strip()
    if env_ver:
        return env_ver.lstrip("v")

    # 2. Embedded _version.txt file
    candidates = [
        Path(__file__).resolve().parent.parent / "_version.txt",
        Path(__file__).resolve().parent / "_version.txt",
        Path(__file__).resolve().parent.parent / "assets" / "_version.txt",
    ]
    # In PyInstaller bundle:
    if hasattr(os, "_MEIPASS"):
        candidates.insert(0, Path(getattr(os, "_MEIPASS")) / "_version.txt")
        candidates.insert(1, Path(getattr(os, "_MEIPASS")) / "assets" / "_version.txt")

    for p in candidates:
        if p.exists():
            try:
                v = p.read_text(encoding="utf-8").strip()
                if v:
                    return v.lstrip("v")
            except Exception:
                pass

    # 3. Git tag if in a Git repository
    try:
        git_dir = Path(__file__).resolve().parent.parent / ".git"
        if git_dir.exists():
            proc = safe_run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True,
                text=True,
                timeout=1.5,
                cwd=str(git_dir.parent),
            )
            if proc.returncode == 0 and proc.stdout.strip():
                tag = proc.stdout.strip().lstrip("v")
                if tag:
                    return tag
    except Exception:
        pass

    # 4. importlib.metadata
    try:
        from importlib.metadata import version
        v = version("er-audio-tool")
        if v and v != "0.0.0":
            return v.lstrip("v")
    except Exception:
        pass

    return FALLBACK_VERSION


__version__ = get_version()
