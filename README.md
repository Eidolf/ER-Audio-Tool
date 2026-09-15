# er-audio-tool

[![CI](https://github.com/skillerious/Loopback-Recorder/actions/workflows/ci.yml/badge.svg)](https://github.com/skillerious/Loopback-Recorder/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A privacy-conscious, local-first desktop audio suite for Windows and Linux. Record system audio, process streams, and browser tabs with zero telemetry, analyze acoustic properties, transcribe audio to standard MIDI, and render MIDI back to MP3 using synthesized instruments.

---

## Key Features

1. **Native WASAPI Loopback Capture (Windows)**  
   - Direct render endpoint capture without requiring "Stereo Mix" or virtual drivers.
   - Enumerate audio render devices and active application process sessions.

2. **PipeWire & PulseAudio Desktop Capture (Linux)**  
   - Native `pw-record` and PulseAudio monitor source capture.
   - Operates without root privileges and respects desktop portal boundaries.

3. **Consent-Based Browser Tab Audio (Chrome / Edge Companion)**  
   - Dedicated Manifest V3 companion extension.
   - Cryptographically authenticated loopback bridge (`127.0.0.1`).
   - Keeps local tab audio audible during capture; clear active recording badge.

4. **Technical Audio Analysis**  
   - Local inspection of MP3, WAV, and FLAC files.
   - Measured peak dBFS, RMS loudness, clipping counter, silence segmentation.
   - Musical estimates for tempo (BPM) and tonal key center.

5. **Audio to MIDI Transcription**  
   - Offline pitch tracking and note onset detection.
   - Exports standards-compliant SMF Type 0 `.mid` files.

6. **MIDI to MP3 Rendering**  
   - Synthesizes MIDI notes into WAV and MP3 audio.
   - SoundFont and instrument preset choices.

7. **Privacy & Local-First Integrity**  
   - Zero telemetry, cloud uploads, or tracking.
   - Redacted logs (credentials and secrets stripped).

---

## Supported Platforms

- **Windows**: Windows 10 (19041+) and Windows 11 (x64 / ARM64 ready).
- **Linux**: Ubuntu 22.04+, Debian 12+, Fedora 38+, Arch Linux (PipeWire or PulseAudio).

---

## Architecture Overview

```
er_audio_tool/
├── core/             # State machine, versioned settings, redacted logging
├── audio/            # Capture backends (WASAPI, PipeWire, PulseAudio, Mock)
│   ├── backends/
│   ├── buffer.py     # Thread-safe ring buffer, level/clipping meter
│   └── encoder.py    # Atomic crash-safe file exporter
├── browser/          # Loopback-only companion service (127.0.0.1)
├── analysis/         # Audio loudness, clipping, tempo & key analyzer
├── midi/             # Pitch tracker, MIDI exporter, and MP3 synthesizer
├── gui/              # CustomTkinter 8-workspace interface
└── i18n/             # English and German translations
```

---

## Quick Start & Installation

### Requirements
- Python 3.9+ (or use portable standalone release binary)
- FFmpeg (optional, recommended for MP3 conversion)

### Install via pip:
```bash
git clone https://github.com/skillerious/Loopback-Recorder.git er-audio-tool
cd er-audio-tool
pip install -e .
er-audio-tool
```

---

## Browser Companion Setup

1. Open `chrome://extensions` in Chrome, Edge, or Brave.
2. Enable **Developer Mode** (top-right toggle).
3. Click **Load unpacked** and select the `browser_extension/` directory.
4. Copy your local session token from **Settings / Browser** in `er-audio-tool` into the extension popup.

---

## Attribution and Lineage

> **Notice**: er-audio-tool was originally derived from [skillerious/Loopback-Recorder](https://github.com/skillerious/Loopback-Recorder) by Robin Doak. The original project is available under the MIT License. er-audio-tool is an independently maintained project and is not affiliated with or endorsed by the original author.

---

## License

er-audio-tool is licensed under the [MIT License](LICENSE).  
Copyright (c) 2025 Robin Doak (Original Lineage)  
Copyright (c) 2026 Eidolf (er-audio-tool Maintainer)
