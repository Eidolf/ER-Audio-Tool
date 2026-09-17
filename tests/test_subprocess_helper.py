"""Unit tests for centralized subprocess helper functions."""
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
from er_audio_tool.utils.subprocess_helper import (
    safe_popen,
    safe_run,
    safe_check_output,
    _prepare_windows_subprocess_kwargs,
)


def test_prepare_windows_subprocess_kwargs_on_win32():
    """Verify that on win32, STARTUPINFO and CREATE_NO_WINDOW are applied."""
    class MockStartupInfo:
        def __init__(self):
            self.dwFlags = 0
            self.wShowWindow = -1

    with patch("sys.platform", "win32"), \
         patch.object(subprocess, "STARTUPINFO", MockStartupInfo, create=True), \
         patch.object(subprocess, "STARTF_USESHOWWINDOW", 1, create=True), \
         patch.object(subprocess, "SW_HIDE", 0, create=True), \
         patch.object(subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True):
        kwargs = {}
        out = _prepare_windows_subprocess_kwargs(kwargs)
        assert "startupinfo" in out
        si = out["startupinfo"]
        assert si.dwFlags & 1
        assert si.wShowWindow == 0
        assert out.get("creationflags", 0) & 0x08000000


def test_prepare_windows_subprocess_kwargs_on_linux():
    """Verify that on linux, kwargs remain untouched."""
    with patch("sys.platform", "linux"):
        kwargs = {"custom": 123}
        out = _prepare_windows_subprocess_kwargs(kwargs)
        assert out == {"custom": 123}
        assert "startupinfo" not in out
        assert "creationflags" not in out


def test_safe_run_execution():
    """Verify safe_run executes basic commands correctly."""
    result = safe_run([sys.executable, "-c", "print('hello_safe_run')"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "hello_safe_run" in result.stdout


def test_safe_check_output_execution():
    """Verify safe_check_output returns expected text output."""
    out = safe_check_output([sys.executable, "-c", "print('check_output_ok')"], text=True)
    assert "check_output_ok" in out


def test_safe_popen_execution():
    """Verify safe_popen launches process and reads stdout."""
    proc = safe_popen([sys.executable, "-c", "print('popen_ok')"], stdout=subprocess.PIPE, text=True)
    stdout, _ = proc.communicate(timeout=2.0)
    assert proc.returncode == 0
    assert "popen_ok" in stdout
