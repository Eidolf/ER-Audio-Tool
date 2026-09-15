"""Unit tests for er-audio-tool core components."""
import os
import tempfile
from pathlib import Path
import numpy as np
import pytest

from er_audio_tool.core.state import AppState, StateMachine
from er_audio_tool.core.config import ConfigManager, AppConfig
from er_audio_tool.audio.buffer import AudioBuffer
from er_audio_tool.audio.encoder import AudioEncoder
from er_audio_tool.analysis.analyzer import AudioAnalyzer
from er_audio_tool.midi.model import NoteEvent, MidiExporter
from er_audio_tool.midi.transcriber import AudioToMidiTranscriber
from er_audio_tool.midi.renderer import MidiRenderer


def test_state_machine():
    sm = StateMachine(AppState.IDLE)
    assert sm.current_state == AppState.IDLE

    # Valid transition
    assert sm.transition_to(AppState.PREPARING) is True
    assert sm.current_state == AppState.PREPARING
    assert sm.transition_to(AppState.RECORDING) is True

    # Invalid transition directly from RECORDING to IDLE
    assert sm.transition_to(AppState.IDLE) is False
    assert sm.current_state == AppState.RECORDING

    assert sm.transition_to(AppState.STOPPING) is True
    assert sm.transition_to(AppState.ENCODING) is True
    assert sm.transition_to(AppState.COMPLETED) is True
    assert sm.transition_to(AppState.IDLE) is True


def test_config_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = ConfigManager(base_dir=Path(tmpdir))
        cfg = cm.config
        assert cfg.version == 2
        assert cfg.language == "en"

        cfg.language = "de"
        cfg.sample_rate = 44100
        cm.save(cfg)

        # Reload
        cm2 = ConfigManager(base_dir=Path(tmpdir))
        assert cm2.config.language == "de"
        assert cm2.config.sample_rate == 44100


def test_audio_buffer():
    buf = AudioBuffer(max_seconds=1.0, sample_rate=1000, channels=2)
    # Generate 100 samples
    samples = np.ones((100, 2), dtype=np.float32) * 0.5
    buf.push(samples)

    peak, rms, is_clip = buf.get_levels()
    assert peak > -10.0
    assert not is_clip

    # Trigger clipping
    clip_samples = np.ones((50, 2), dtype=np.float32) * 1.0
    buf.push(clip_samples)
    _, _, is_clip = buf.get_levels()
    assert is_clip is True


def test_audio_encoder_and_analyzer():
    with tempfile.TemporaryDirectory() as tmpdir:
        sr = 44100
        t = np.linspace(0, 1, sr, endpoint=False)
        # 440 Hz A4 tone
        sine = 0.5 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
        stereo = np.column_stack((sine, sine))

        out_wav = Path(tmpdir) / "test.wav"
        AudioEncoder.save_audio(stereo, sr, out_wav, format_type="wav")

        assert out_wav.exists()
        assert out_wav.stat().st_size > 0

        # Analyze file
        rep = AudioAnalyzer.analyze_file(out_wav)
        assert rep.sample_rate == sr
        assert rep.channels == 2
        assert rep.duration_seconds == 1.0
        assert not rep.is_clipping


def test_midi_export_and_transcription():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test notes
        notes = [
            NoteEvent(pitch=69, start_time=0.0, duration=0.5, velocity=80),  # A4
            NoteEvent(pitch=71, start_time=0.5, duration=0.5, velocity=80),  # B4
        ]
        midi_path = Path(tmpdir) / "test.mid"
        MidiExporter.export_midi(notes, midi_path, bpm=120.0)

        assert midi_path.exists()
        assert MidiExporter.validate_midi_file(midi_path) is True

        # Render notes to audio
        audio_out = Path(tmpdir) / "rendered.wav"
        MidiRenderer.render_notes_to_audio(notes, audio_out, sample_rate=22050, format_type="wav")
        assert audio_out.exists()
        assert audio_out.stat().st_size > 0

        # Transcribe the rendered audio back to MIDI
        transcribed_notes = AudioToMidiTranscriber.transcribe(audio_out, min_duration=0.05)
        assert len(transcribed_notes) > 0
        # Pitch should be close to A4 (69) or B4 (71)
        pitches = [n.pitch for n in transcribed_notes]
        assert 69 in pitches or 71 in pitches
