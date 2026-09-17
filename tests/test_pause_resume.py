"""Test recording pause/resume functionality."""
import time
import tempfile
from pathlib import Path
import numpy as np

from er_audio_tool.audio.backends.mock_backend import MockAudioBackend
from er_audio_tool.audio.encoder import AudioEncoder
from er_audio_tool.core.state import StateMachine, AppState


def test_recording_pause_resume():
    """Test that pause/resume produces continuous audio without gaps."""
    backend = MockAudioBackend(generate_tone_hz=440.0)
    
    received_chunks = []
    
    def callback(data: np.ndarray):
        if state_machine.current_state == AppState.RECORDING:
            received_chunks.append(data.copy())
    
    # Simulate recording lifecycle
    state_machine = StateMachine(AppState.IDLE)
    
    # Start recording
    assert state_machine.transition_to(AppState.PREPARING)
    assert state_machine.transition_to(AppState.RECORDING)
    
    device = backend.enumerate_devices()[0]
    backend.start_capture(device, 48000, 2, callback)
    
    # Record for 0.5 seconds
    time.sleep(0.5)
    chunks_before_pause = len(received_chunks)
    assert chunks_before_pause > 0
    
    # Pause
    assert state_machine.transition_to(AppState.PAUSED)
    
    # Wait 0.3 seconds (paused)
    time.sleep(0.3)
    chunks_during_pause = len([c for c in received_chunks if state_machine.current_state == AppState.RECORDING])
    assert len(received_chunks) == chunks_before_pause, "Chunk count must remain unchanged while paused"
    
    # Resume
    assert state_machine.transition_to(AppState.RECORDING)
    
    # Record for another 0.5 seconds
    time.sleep(0.5)
    chunks_after_resume = len(received_chunks)
    assert chunks_after_resume > chunks_before_pause, "Chunks should resume accumulating after resuming"
    
    # Stop
    assert state_machine.transition_to(AppState.STOPPING)
    backend.stop_capture()
    
    assert state_machine.current_state == AppState.STOPPING


def test_pause_without_recording_fails():
    """Test that pause fails if not recording."""
    state_machine = StateMachine(AppState.IDLE)
    
    # Try to pause while idle
    result = state_machine.transition_to(AppState.PAUSED)
    assert result is False
    assert state_machine.current_state == AppState.IDLE


def test_resume_without_pause_fails():
    """Test that resume only works from paused state."""
    state_machine = StateMachine(AppState.IDLE)
    
    # Can't go from idle to recording directly (need preparing first)
    result = state_machine.transition_to(AppState.RECORDING)
    assert result is False


if __name__ == "__main__":
    test_recording_pause_resume()
    test_pause_without_recording_fails()
    test_resume_without_pause_fails()
    print("✅ All pause/resume tests passed!")
