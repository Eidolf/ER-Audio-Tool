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


class MidiParser:
    """Parses Standard MIDI Files (Format 0 and Format 1) into playable NoteEvents."""

    @classmethod
    def parse_midi_file(cls, path: Path | str) -> list[NoteEvent]:
        p = Path(path)
        if not p.exists():
            return []

        with open(p, "rb") as f:
            raw = f.read()

        if len(raw) < 14 or not raw.startswith(b"MThd"):
            return []

        # Header: magic (4s), length (I=6), format (H), ntrks (H), division (H)
        magic, hlen, fmt, ntrks, division = struct.unpack(">4sIHHH", raw[:14])
        ticks_per_beat = division if (division & 0x8000) == 0 else 480
        default_tempo_us = 500_000  # 120 BPM

        notes: list[NoteEvent] = []
        offset = 14

        for _ in range(ntrks):
            if offset + 8 > len(raw):
                break
            chunk_type = raw[offset:offset + 4]
            chunk_len = struct.unpack(">I", raw[offset + 4:offset + 8])[0]
            offset += 8
            track_end = offset + chunk_len
            if chunk_type != b"MTrk":
                offset = track_end
                continue

            # Parse track events
            current_tick = 0
            open_notes: dict[tuple[int, int], tuple[int, int]] = {}  # (channel, pitch) -> (start_tick, velocity)
            running_status = 0
            tempo_us = default_tempo_us

            while offset < track_end and offset < len(raw):
                # Variable length delta time
                delta = 0
                while offset < len(raw):
                    b = raw[offset]
                    offset += 1
                    delta = (delta << 7) | (b & 0x7F)
                    if not (b & 0x80):
                        break

                current_tick += delta
                if offset >= len(raw):
                    break

                status = raw[offset]
                if status & 0x80:
                    running_status = status
                    offset += 1
                else:
                    status = running_status

                event_type = status & 0xF0
                channel = status & 0x0F

                if status == 0xFF:
                    # Meta event
                    if offset >= len(raw):
                        break
                    meta_type = raw[offset]
                    offset += 1
                    meta_len = 0
                    while offset < len(raw):
                        mb = raw[offset]
                        offset += 1
                        meta_len = (meta_len << 7) | (mb & 0x7F)
                        if not (mb & 0x80):
                            break
                    meta_data = raw[offset:offset + meta_len]
                    offset += meta_len

                    if meta_type == 0x51 and len(meta_data) == 3:  # Set Tempo
                        tempo_us = int.from_bytes(meta_data, "big")
                    elif meta_type == 0x2F:  # End of track
                        break

                elif status in (0xF0, 0xF7):
                    # SysEx
                    sysex_len = 0
                    while offset < len(raw):
                        sb = raw[offset]
                        offset += 1
                        sysex_len = (sysex_len << 7) | (sb & 0x7F)
                        if not (sb & 0x80):
                            break
                    offset += sysex_len

                elif event_type in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
                    # 2 data bytes
                    if offset + 1 >= len(raw):
                        break
                    d1 = raw[offset]
                    d2 = raw[offset + 1]
                    offset += 2

                    if event_type == 0x90 and d2 > 0:
                        # Note On
                        open_notes[(channel, d1)] = (current_tick, d2)
                    elif event_type == 0x80 or (event_type == 0x90 and d2 == 0):
                        # Note Off
                        if (channel, d1) in open_notes:
                            start_tick, vel = open_notes.pop((channel, d1))
                            sec_per_tick = (tempo_us / 1_000_000.0) / ticks_per_beat
                            start_time = start_tick * sec_per_tick
                            dur = max(0.05, (current_tick - start_tick) * sec_per_tick)
                            notes.append(NoteEvent(pitch=d1, start_time=start_time, duration=dur, velocity=vel, channel=channel))

                elif event_type in (0xC0, 0xD0):
                    # 1 data byte
                    offset += 1

            # Close dangling notes
            for (channel, pitch), (start_tick, vel) in open_notes.items():
                sec_per_tick = (tempo_us / 1_000_000.0) / ticks_per_beat
                start_time = start_tick * sec_per_tick
                dur = max(0.05, (current_tick - start_tick) * sec_per_tick)
                notes.append(NoteEvent(pitch=pitch, start_time=start_time, duration=dur, velocity=vel, channel=channel))

        # Sort notes chronologically
        notes.sort(key=lambda n: n.start_time)
        return notes
