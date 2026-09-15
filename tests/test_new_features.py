"""Comprehensive unit and integration tests for converter, i18n completeness, and diagnostics."""
import sys
import tempfile
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf

from er_audio_tool.i18n import get_i18n, TRANSLATIONS
from er_audio_tool.converter.converter import AudioConverter, ConversionJob
from er_audio_tool.diagnostics.runner import DiagnosticRunner
from er_audio_tool.help import HELP_REGISTRY


def test_i18n_completeness_and_dynamic_switch():
    i18n = get_i18n()
    en_keys = set(TRANSLATIONS["en"].keys())
    de_keys = set(TRANSLATIONS["de"].keys())

    # Every key in English must also exist in German
    missing_in_de = en_keys - de_keys
    assert not missing_in_de, f"Missing German translation keys: {missing_in_de}"

    # Test dynamic observer notification
    updated = []
    callback = lambda: updated.append(True)
    i18n.subscribe(callback)

    i18n.set_language("de")
    assert i18n.current_lang == "de"
    assert len(updated) == 1
    assert i18n.t("btn_record") == "Aufnahme starten"

    i18n.set_language("en")
    assert i18n.current_lang == "en"
    assert len(updated) == 2
    assert i18n.t("btn_record") == "Start Recording"

    i18n.unsubscribe(callback)


def test_help_registry_bilingual():
    for topic_id, topic in HELP_REGISTRY.items():
        assert topic.title_en and topic.title_de
        assert topic.content_en and topic.content_de


def test_audio_converter_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Create a synthetic WAV
        sr = 44100
        t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
        sine = 0.5 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
        in_wav = tmp / "sample.wav"
        sf.write(in_wav, sine, sr)

        # Convert to FLAC
        job = ConversionJob(input_file=in_wav, output_format="flac", output_dir=tmp)
        res = AudioConverter.convert_file(job)
        assert res.success is True
        assert Path(res.output_path).exists()
        assert Path(res.output_path).suffix.lower() == ".flac"


def test_diagnostic_runner():
    with tempfile.TemporaryDirectory() as tmpdir:
        results = DiagnosticRunner.run_all_tests(tmpdir)
        assert len(results) >= 5
        categories = {r.category for r in results}
        assert "System" in categories
        assert "Storage" in categories


def test_codec_manager_and_exit_lifecycle():
    from er_audio_tool.audio.codecs import CodecManager, CODEC_SCOPES
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        cm = CodecManager(base_dir=base)
        assert cm.get_codecs_dir() == base / "temp_codecs"
        assert cm.has_local_ffmpeg() is False

        # Verify scopes definition
        assert "essential" in CODEC_SCOPES
        assert "full" in CODEC_SCOPES
        assert "MP3" in CODEC_SCOPES["essential"].codecs_en
        assert "ALAC" in CODEC_SCOPES["full"].codecs_en

        # Simulate local binary extraction
        bin_dir = cm.get_codecs_dir() / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        fake_bin = bin_dir / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
        fake_bin.write_text("#!/bin/sh\necho ffmpeg version 7.0")
        fake_bin.chmod(0o755)

        assert cm.has_local_ffmpeg() is True
        assert cm.find_local_ffmpeg_path() == fake_bin
        assert cm.get_active_ffmpeg() == str(fake_bin)

        # Test deletion / cleanup on exit
        assert cm.delete_local_codecs() is True
        assert cm.has_local_ffmpeg() is False
        assert not cm.get_codecs_dir().exists()


def test_midi_parser_and_instrument_renderer():
    from er_audio_tool.midi.model import MidiExporter, MidiParser, NoteEvent
    from er_audio_tool.midi.renderer import MidiRenderer
    from er_audio_tool.midi.transcriber import AudioToMidiTranscriber

    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "scale.mid"
        test_notes = [
            NoteEvent(pitch=60, start_time=0.0, duration=0.2),
            NoteEvent(pitch=64, start_time=0.25, duration=0.2),
            NoteEvent(pitch=67, start_time=0.5, duration=0.3),
        ]
        MidiExporter.export_midi(test_notes, p)
        assert p.exists()

        # Parse .mid
        parsed_notes = MidiParser.parse_midi_file(p)
        assert len(parsed_notes) == 3
        assert [n.pitch for n in parsed_notes] == [60, 64, 67]

        # Render with different instruments
        for inst in ["acoustic_piano", "strings", "synth_lead", "bass"]:
            out_audio = Path(tmpdir) / f"{inst}.wav"
            MidiRenderer.render_file_to_audio(
                p, out_audio, sample_rate=22050, instrument=inst, format_type="wav"
            )
            assert out_audio.exists()
            assert out_audio.stat().st_size > 0

        # Transcribe with profile
        piano_audio = Path(tmpdir) / "acoustic_piano.wav"
        transcribed = AudioToMidiTranscriber.transcribe(piano_audio, profile="piano")
        assert len(transcribed) > 0
