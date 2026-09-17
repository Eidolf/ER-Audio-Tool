"""Centralized subprocess wrapper for Windows console window suppression and cross-platform execution."""
from __future__ import annotations

import subprocess
import sys
from typing import Any


def _prepare_windows_subprocess_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Inject Windows-specific flags to prevent console window flashing if on win32."""
    if sys.platform == "win32":
        # Configure startupinfo to hide window
        startupinfo = kwargs.get("startupinfo")
        startupinfo_cls = getattr(subprocess, "STARTUPINFO", None)
        if startupinfo is None and startupinfo_cls is not None:
            startupinfo = startupinfo_cls()
        if startupinfo is not None:
            startf_useshowwindow = getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
            sw_hide = getattr(subprocess, "SW_HIDE", 0)
            startupinfo.dwFlags |= startf_useshowwindow
            startupinfo.wShowWindow = sw_hide
            kwargs["startupinfo"] = startupinfo

        # Enforce CREATE_NO_WINDOW
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        creationflags = kwargs.get("creationflags", 0)
        creationflags |= create_no_window
        kwargs["creationflags"] = creationflags
    return kwargs


def safe_popen(cmd: Any, **kwargs: Any) -> subprocess.Popen:
    """Execute subprocess.Popen with Windows console window suppression."""
    kwargs = _prepare_windows_subprocess_kwargs(kwargs)
    return subprocess.Popen(cmd, **kwargs)


def safe_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess:
    """Execute subprocess.run with Windows console window suppression."""
    kwargs = _prepare_windows_subprocess_kwargs(kwargs)
    return subprocess.run(cmd, **kwargs)


def safe_check_output(cmd: Any, **kwargs: Any) -> Any:
    """Execute subprocess.check_output with Windows console window suppression."""
    kwargs = _prepare_windows_subprocess_kwargs(kwargs)
    return subprocess.check_output(cmd, **kwargs)
