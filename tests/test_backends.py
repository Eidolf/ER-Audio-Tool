"""Unit tests for audio capture backends and device manager."""
import time
import numpy as np
import pytest

from er_audio_tool.audio.interfaces import BackendType, AudioDeviceInfo
from er_audio_tool.audio.backends.mock_backend import MockAudioBackend
from er_audio_tool.audio.manager import DeviceManager


def test_mock_backend_capture():
    backend = MockAudioBackend(generate_tone_hz=440.0)
    assert backend.is_available() is True
    assert backend.get_backend_type() == BackendType.MOCK

    devices = backend.enumerate_devices()
    assert len(devices) >= 1
    dev = devices[0]

    received_frames = []

    def callback(data: np.ndarray):
        received_frames.append(data)

    backend.start_capture(dev, sample_rate=48000, channels=2, callback=callback)
    # Wait briefly to let background generator produce frames
    time.sleep(0.1)
    backend.stop_capture()

    assert len(received_frames) > 0
    assert received_frames[0].shape[1] == 2
    assert received_frames[0].dtype == np.float32


def test_device_manager():
    dm = DeviceManager(preferred_backend="mock")
    active = dm.get_active_backend()
    assert active.get_backend_type() == BackendType.MOCK

    all_devs = dm.enumerate_all_devices()
    assert len(all_devs) > 0
    assert any(d.backend_type == BackendType.MOCK for d in all_devs)
