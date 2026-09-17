"""Unit tests for DiagnosticRunner live audio capture pipeline."""
import numpy as np
import pytest

from er_audio_tool.audio.backends.mock_backend import MockAudioBackend
from er_audio_tool.audio.manager import DeviceManager
from er_audio_tool.diagnostics.runner import DiagnosticRunner, DiagnosticItem


def test_diagnostic_audio_capture_pipeline():
    """Verify test_audio_capture succeeds and reports frames and levels with MockAudioBackend."""
    # Ensure DeviceManager uses mock backend
    dm = DeviceManager()
    devs = dm.enumerate_all_devices("rec_system")
    assert len(devs) > 0

    item = DiagnosticRunner.test_audio_capture(duration_sec=0.15, device=devs[0])
    assert isinstance(item, DiagnosticItem)
    assert item.status == "PASSED"
    assert "blocks" in item.details
    assert "Peak:" in item.details or "Digital silence detected" in item.details


def test_run_all_tests_includes_audio_capture():
    """Verify run_all_tests includes Audio Capture Pipeline category."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        items = DiagnosticRunner.run_all_tests(tmpdir)
        categories = {it.category for it in items}
        assert "Audio Capture Pipeline" in categories or "Audio Capture" in categories
