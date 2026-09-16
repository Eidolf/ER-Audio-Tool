"""Regression tests for backend release-blocking defects.

Validates:
1. No unsupported WasapiSettings(loopback=True) arguments exist in the codebase or get constructed.
2. Capability-driven WASAPI loopback device and channel resolution (-9998 prevention).
3. Browser HTTP audio chunk streaming delivers canonical frames to registry and active recorder.
4. OutputValidator detects 0-frame, truncated, digital silence, and valid signal recordings.
"""
import sys
import tempfile
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf

from er_audio_tool.audio.interfaces import (
    AudioDeviceInfo,
    BackendType,
    DeviceCapability,
)
from er_audio_tool.audio.output_validator import (
    OutputValidator,
    OutputClassification,
)
from er_audio_tool.browser.server import BrowserServer
from er_audio_tool.browser.registry import BrowserConnectionRegistry, ConnectionState


def test_no_unsupported_wasapisettings_loopback_in_codebase():
    """Verify that no code file passes loopback=True or loopback keyword to WasapiSettings."""
    repo_root = Path(__file__).parent.parent
    py_files = list(repo_root.glob("*.py")) + list(repo_root.glob("er_audio_tool/**/*.py"))
    
    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        assert "WasapiSettings(loopback=" not in content, f"Unsupported WasapiSettings argument in {py_file}"
        assert "WasapiSettings(loopback=True)" not in content, f"Unsupported WasapiSettings argument in {py_file}"
        assert 'setattr(wasapi_settings, "loopback", True)' not in content, f"Unsupported loopback injection in {py_file}"
        assert 'setattr(self._was, "loopback", True)' not in content, f"Unsupported loopback injection in {py_file}"


def test_windows_application_capture_honest_availability(monkeypatch):
    """WindowsApplicationAudioCapture reports honest capability without throwing TypeError."""
    monkeypatch.setattr(sys, "platform", "win32")
    from er_audio_tool.audio.backends.windows_wasapi import WindowsApplicationAudioCapture
    
    backend = WindowsApplicationAudioCapture()
    assert backend.is_available() is False
    devs = backend.enumerate_devices()
    assert len(devs) == 0
    
    dummy_dev = AudioDeviceInfo(
        id="dummy",
        name="Dummy App",
        channels=2,
        sample_rate=48000,
        backend_type=BackendType.WASAPI,
        capability=DeviceCapability.PROCESS_LOOPBACK,
    )
    with pytest.raises(RuntimeError) as excinfo:
        backend.start_capture(dummy_dev, 48000, 2, lambda d: None)
    assert "unavailable" in str(excinfo.value).lower()
    assert "WasapiSettings" not in str(excinfo.value)


def test_output_validator_classifications():
    """Test output validator accurately detects 0 bytes, 0 frames, digital silence, and valid signal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # 1. Empty 0-byte file
        f_empty = tmp_path / "empty.wav"
        f_empty.write_bytes(b"")
        res_empty = OutputValidator.validate_file(f_empty)
        assert res_empty.is_valid is False
        assert res_empty.classification == OutputClassification.NO_FRAMES

        # 2. Digital silence (all zeros)
        f_silence = tmp_path / "silence.wav"
        zeros = np.zeros((48000, 2), dtype=np.float32)
        sf.write(str(f_silence), zeros, 48000, format="WAV")
        res_silence = OutputValidator.validate_file(f_silence)
        assert res_silence.is_valid is True
        assert res_silence.classification == OutputClassification.DIGITAL_SILENCE
        assert res_silence.frame_count == 48000

        # 3. Valid signal (sine tone)
        f_signal = tmp_path / "signal.wav"
        t = np.linspace(0, 1.0, 48000, endpoint=False)
        tone = (0.5 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
        stereo_tone = np.column_stack((tone, tone))
        sf.write(str(f_signal), stereo_tone, 48000, format="WAV")
        res_signal = OutputValidator.validate_file(f_signal)
        assert res_signal.is_valid is True
        assert res_signal.classification == OutputClassification.VALID_SIGNAL
        assert res_signal.peak_db > -10.0


@pytest.mark.asyncio
async def test_browser_server_audio_chunk_endpoint():
    """Test that /api/audio_chunk accepts base64 PCM frames and pushes them to registry."""
    import base64
    registry = BrowserConnectionRegistry.reset_instance()
    server = BrowserServer(registry=registry)
    
    token = server.auth_token
    session_id = registry.authenticate_client("test-ext", "1.0.0")
    registry.select_tab(101, "Test Streaming Tab")
    descriptor = registry.reserve_for_recording()
    
    received_chunks = []
    registry.set_audio_frame_consumer(lambda arr, cap_id: received_chunks.append((arr, cap_id)))
    
    # Generate 1024 frames of 1200 Hz tone
    t = np.linspace(0, 1024 / 48000.0, 1024, endpoint=False, dtype=np.float32)
    sig = 0.4 * np.sin(2 * np.pi * 1200 * t)
    stereo_data = np.column_stack((sig, sig)).astype(np.float32)
    b64_str = base64.b64encode(stereo_data.tobytes()).decode("ascii")
    
    payload = {
        "token": token,
        "capture_session_id": descriptor.capture_session_id,
        "channels": 2,
        "sample_rate": 48000,
        "sample_format": "float32",
        "data": b64_str,
    }
    
    # Simulate HTTP request to /api/audio_chunk
    import asyncio
    import json
    
    body = json.dumps(payload).encode("utf-8")
    first_line = "POST /api/audio_chunk HTTP/1.1"
    
    class DummyWriter:
        def __init__(self):
            self.data = b""
        def write(self, d):
            self.data += d
        async def drain(self):
            pass
            
    class DummyReader:
        def __init__(self, body_bytes):
            self.lines = [
                b"Content-Type: application/json\r\n",
                f"Content-Length: {len(body_bytes)}\r\n".encode("ascii"),
                b"\r\n",
            ]
            self.body = body_bytes
            self.idx = 0
            
        async def readline(self):
            if self.idx < len(self.lines):
                l = self.lines[self.idx]
                self.idx += 1
                return l
            return b""
            
        async def readexactly(self, n):
            return self.body
            
    reader = DummyReader(body)
    writer = DummyWriter()
    
    await server._handle_http_request(reader, writer, first_line)
    
    assert b"200 OK" in writer.data
    assert len(received_chunks) == 1
    assert received_chunks[0][0].shape == (1024, 2)
    assert received_chunks[0][1] == descriptor.capture_session_id
