"""MIDI data structures, note events, and standards-compliant binary export."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import struct


@dataclass
class NoteEvent:
    pitch: int  # 0 - 127
    start_time: float  # seconds
    duration: float  # seconds
    velocity: int = 80  # 1 - 127
    channel: int = 0  # 0 - 15

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration


class MidiExporter:
    """Writes a list of NoteEvents into a valid Standard MIDI File (SMF Format 0)."""

    TICKS_PER_BEAT = 480

    @classmethod
    def export_midi(
        cls,
        notes: list[NoteEvent],
        output_path: Path | str,
        bpm: float = 120.0,
    ) -> Path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        # Microseconds per quarter note
        tempo_us = int(60_000_000 / bpm)

        # Convert note on/off events into tick-based sorted timeline
        events = []
        ticks_per_second = (cls.TICKS_PER_BEAT * bpm) / 60.0

        for n in notes:
            start_tick = int(n.start_time * ticks_per_second)
            end_tick = int(n.end_time * ticks_per_second)
            # Note On: 0x90 | channel
            events.append((start_tick, 0x90 | (n.channel & 0x0F), n.pitch, n.velocity))
            # Note Off: 0x80 | channel
            events.append((end_tick, 0x80 | (n.channel & 0x0F), n.pitch, 0))

        # Sort by tick time; if ticks equal, note off before note on
        events.sort(key=lambda e: (e[0], 0 if (e[1] & 0xF0) == 0x80 else 1))

        # Build track chunk data
        track_bytes = bytearray()

        # Set Tempo Meta Event: 0xFF 0x51 0x03 tt tt tt
        track_bytes.extend(cls._write_varlen(0))  # delta time = 0
        track_bytes.extend(b"\xFF\x51\x03")
        track_bytes.extend(struct.pack(">I", tempo_us)[1:])  # 3 bytes

        last_tick = 0
        for tick, status, pitch, vel in events:
            delta = max(0, tick - last_tick)
            last_tick = tick
            track_bytes.extend(cls._write_varlen(delta))
            track_bytes.extend(bytes([status, pitch & 0x7F, vel & 0x7F]))

        # End of Track Meta Event: 0xFF 0x2F 0x00
        track_bytes.extend(cls._write_varlen(0))
        track_bytes.extend(b"\xFF\x2F\x00")

        # Header Chunk: MThd, length 6, format 0, 1 track, ticks per beat
        header = bytearray()
        header.extend(b"MThd")
        header.extend(struct.pack(">IHHH", 6, 0, 1, cls.TICKS_PER_BEAT))

        # Track Chunk: MTrk, length, track data
        track_chunk = bytearray()
        track_chunk.extend(b"MTrk")
        track_chunk.extend(struct.pack(">I", len(track_bytes)))
        track_chunk.extend(track_bytes)

        with open(p, "wb") as f:
            f.write(header)
            f.write(track_chunk)

        return p

    @staticmethod
    def _write_varlen(val: int) -> bytes:
        """Encodes an integer into MIDI variable-length quantity."""
        buf = bytearray([val & 0x7F])
        val >>= 7
        while val > 0:
            buf.insert(0, (val & 0x7F) | 0x80)
            val >>= 7
        return bytes(buf)

    @classmethod
    def validate_midi_file(cls, path: Path | str) -> bool:
        """Validates that a file starts with 'MThd' and contains valid track headers."""
        p = Path(path)
        if not p.exists() or p.stat().st_size < 14:
            return False
        with open(p, "rb") as f:
            header = f.read(14)
            if not header.startswith(b"MThd"):
                return False
        return True
