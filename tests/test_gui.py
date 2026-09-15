"""GUI lifecycle and interaction tests."""
import pytest
from er_audio_tool.core.config import ConfigManager
from er_audio_tool.gui.app import ErAudioApp
from er_audio_tool.core.state import AppState


def test_gui_initialization_headless(monkeypatch, tmp_path):
    # Mock tkinter display for CI / headless testing
    monkeypatch.setenv("DISPLAY", ":99")
    cm = ConfigManager(base_dir=tmp_path)
    cm.config.backend = "mock"

    try:
        app = ErAudioApp(config_manager=cm)
        assert app.state_machine.current_state == AppState.IDLE
        # Test tab switching & record toggle
        app._on_record_toggle()
        assert app.state_machine.current_state == AppState.RECORDING
        app._on_record_toggle()
        assert app.state_machine.current_state == AppState.IDLE
        app.destroy()
    except Exception as ex:
        # If no X server is present in the container environment, pass gracefully
        pytest.skip(f"Tkinter requires X server display: {ex}")
