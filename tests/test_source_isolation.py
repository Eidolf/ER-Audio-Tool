import numpy as np
import pytest
from er_audio_tool.audio.buffer import AudioBuffer
from er_audio_tool.audio.interfaces import AudioDeviceInfo, AudioSourceType, BackendType, DeviceCapability
from er_audio_tool.audio.manager import DeviceManager
from er_audio_tool.audio.backends.browser_backend import BrowserTabCaptureBackend
from er_audio_tool.browser.server import BrowserServer

def test_source_isolation_backend_selection():
    server = BrowserServer(port=9876)
    manager = DeviceManager(browser_server=server)
    
    # Browser Tab source must yield BrowserTabCaptureBackend
    backend = manager.get_backend_for_source_type("rec_browser")
    assert isinstance(backend, BrowserTabCaptureBackend)
    
    # Must not permit fallback to microphone if unauthenticated
    device = AudioDeviceInfo(
        id="browser_stream",
        name="Browser Tab Stream",
        channels=2,
        sample_rate=48000,
        is_loopback=False,
        backend_type=BackendType.BROWSER_TAB,
        capability=DeviceCapability.BROWSER_STREAM,
    )
    # When server is listening but unauthenticated
    from er_audio_tool.browser.registry import BrowserConnectionRegistry
    test_reg = BrowserConnectionRegistry()
    test_reg.set_server_listening(True)
    server.registry = test_reg
    backend.registry = test_reg
    with pytest.raises(RuntimeError, match="not authenticated"):
        backend.start_capture(device, 48000, 2, lambda data: None)

def test_audio_buffer_stereo_level_separation():
    buf = AudioBuffer()
    buf.set_active_session("session-1")
    
    # Left channel has signal, Right channel has silence
    t = np.linspace(0, 0.1, 4800, endpoint=False, dtype=np.float32)
    left_signal = np.sin(2 * np.pi * 440 * t) * 0.8
    right_signal = np.zeros_like(left_signal)
    stereo_data = np.stack([left_signal, right_signal], axis=-1)
    
    buf.push(stereo_data, session_id="session-1")
    peak_l, peak_r, peak, rms, is_clip, frames = buf.get_stereo_levels()
    
    assert peak_l > -10.0  # Left has strong audio
    assert peak_r <= -60.0  # Right is silence/floor
    assert frames == 4800

def test_audio_buffer_rejects_stale_session_frames():
    buf = AudioBuffer()
    buf.set_active_session("session-2")
    
    data = np.ones((100, 2), dtype=np.float32) * 0.5
    # Push with mismatched session id
    buf.push(data, session_id="stale-session-1")
    
    peak_l, peak_r, peak, rms, is_clip, frames = buf.get_stereo_levels()
    # Frames must be rejected
    assert frames == 0
    assert peak <= -60.0

def test_synthetic_frequency_fixture_isolation():
    # Verify synthetic frequency isolation:
    # 440 Hz (Mic), 880 Hz (System), 1200 Hz (Browser)
    sr = 48000
    n = 4800
    t = np.linspace(0, n / sr, n, endpoint=False, dtype=np.float32)
    
    f_mic = 440.0
    f_sys = 880.0
    f_browser = 1200.0
    
    mic_audio = np.sin(2 * np.pi * f_mic * t)
    sys_audio = np.sin(2 * np.pi * f_sys * t)
    browser_audio = np.sin(2 * np.pi * f_browser * t)
    
    # FFT peak check
    def dominant_freq(signal):
        fft = np.abs(np.fft.rfft(signal))
        freqs = np.fft.rfftfreq(len(signal), 1.0 / sr)
        return freqs[np.argmax(fft)]
    
    assert abs(dominant_freq(browser_audio) - 1200.0) < 5.0
    assert abs(dominant_freq(sys_audio) - 880.0) < 5.0
    assert abs(dominant_freq(mic_audio) - 440.0) < 5.0
