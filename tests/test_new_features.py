"""Comprehensive unit and integration tests for converter, i18n completeness, and diagnostics."""
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
