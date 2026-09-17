"""Test Multi-Track MIDI Export (SMF Format 1)."""
import tempfile
from pathlib import Path
import struct

from er_audio_tool.midi.model import NoteEvent, MidiExporter


def test_multitrack_midi_export():
    """Test that multi-channel notes export as SMF Format 1 (multi-track)."""
    notes = [
        # Channel 0 (Melody/Piano)
        NoteEvent(pitch=60, start_time=0.0, duration=0.5, velocity=80, channel=0),
        NoteEvent(pitch=64, start_time=0.5, duration=0.5, velocity=80, channel=0),

        # Channel 1 (Bass)
        NoteEvent(pitch=36, start_time=0.0, duration=1.0, velocity=90, channel=1),

        # Channel 9 (Drums)
        NoteEvent(pitch=36, start_time=0.0, duration=0.1, velocity=100, channel=9),  # Kick
        NoteEvent(pitch=42, start_time=0.5, duration=0.1, velocity=80, channel=9),   # HiHat
    ]

    track_programs = {
        0: 0,   # Acoustic Grand Piano
        1: 32,  # Acoustic Bass
        # Channel 9 is drums, no program change needed
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test_multitrack.mid"
        result = MidiExporter.export_midi(
            notes,
            output,
            bpm=120.0,
            track_programs=track_programs,
            multitrack=True
        )

        assert result.exists()
        assert result.stat().st_size > 0

        # Verify SMF Format 1
        with open(result, "rb") as f:
            header = f.read(14)
            assert header.startswith(b"MThd")

            # Parse header: magic(4), length(4), format(2), tracks(2), division(2)
            fmt = struct.unpack(">H", header[8:10])[0]
            num_tracks = struct.unpack(">H", header[10:12])[0]

            assert fmt == 1, f"Expected SMF Format 1, got {fmt}"
            assert num_tracks == 4, f"Expected exactly 4 tracks (tempo + 3 channels), got {num_tracks}"

        print(f"✓ Multi-track MIDI exported successfully")
        print(f"  Format: {fmt} (SMF Format 1)")
        print(f"  Tracks: {num_tracks}")
        print(f"  Size: {result.stat().st_size} bytes")


def test_single_channel_auto_format_0():
    """Test that single-channel notes auto-export as SMF Format 0."""
    notes = [
        NoteEvent(pitch=60, start_time=0.0, duration=0.5, velocity=80, channel=0),
        NoteEvent(pitch=64, start_time=0.5, duration=0.5, velocity=80, channel=0),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test_single.mid"
        result = MidiExporter.export_midi(notes, output, bpm=120.0, multitrack=None)

        assert result.exists()

        with open(result, "rb") as f:
            header = f.read(14)
            fmt = struct.unpack(">H", header[8:10])[0]
            num_tracks = struct.unpack(">H", header[10:12])[0]

            assert fmt == 0, f"Expected SMF Format 0 for single channel, got {fmt}"
            assert num_tracks == 1, f"Expected 1 track for Format 0, got {num_tracks}"

        print(f"✓ Single-channel auto-detected as Format 0")


def test_force_format_0_multitrack():
    """Test that multitrack=False forces Format 0 even with multiple channels."""
    notes = [
        NoteEvent(pitch=60, start_time=0.0, duration=0.5, channel=0),
        NoteEvent(pitch=36, start_time=0.0, duration=0.5, channel=1),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test_forced_format0.mid"
        result = MidiExporter.export_midi(notes, output, multitrack=False)

        with open(result, "rb") as f:
            header = f.read(14)
            fmt = struct.unpack(">H", header[8:10])[0]

            assert fmt == 0, f"Expected forced Format 0, got {fmt}"

        print(f"✓ Forced Format 0 with multitrack=False")


if __name__ == "__main__":
    test_multitrack_midi_export()
    test_single_channel_auto_format_0()
    test_force_format_0_multitrack()
    print("\n✅ All multi-track MIDI tests passed!")
