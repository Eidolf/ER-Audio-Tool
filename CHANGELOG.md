# Changelog

All notable changes to er-audio-tool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-09-17

### Added
- Complete architecture migration to modular `er_audio_tool` package
- Portable standalone build verification for Windows & Linux
- Command line arguments (`--version`, `--diagnostics`) in root launcher and binary
- Standard MIDI File (SMF) Format 1 multi-track export
- Real ALAC (Apple Lossless) decoding, conversion, and analysis verification
- Automated pause/resume test suite
- Comprehensive documentation suite and user guides

### Changed
- Reset versioning baseline to 0.4.0 (pre-release alpha consolidation)
- Retired legacy monolithic scripts (`main.py`, `settings.py`, `about.py`) into `legacy/`

## [1.3.7] - 2026-09-16

### Fixed
- Audio capture initialization failures
- Sidebar highlight state persistence
- Live input level monitor reactivity

## [1.3.6] - 2026-09-15

### Added
- Native FFmpeg WASAPI loopback capture engine (Windows)
- OBS-like system output capture with render endpoint enumeration
- Enhanced live stereo level meters with L/R separation

### Fixed
- WASAPI loopback channel negotiation
- Browser extension heartbeat mechanism
- Robust browser tab audio stream delivery

## [1.3.5] - 2026-09-15

### Added
- Authoritative browser connection registry with atomic reservation
- Explicit browser tab selection with connection generation tracking
- Live stereo level meters with peak hold and clipping detection

### Fixed
- Browser connection lifecycle management
- Tab selection state persistence
- Audio stream capture session isolation

## [1.3.4] - 2026-09-15

### Added
- Strict source isolation with dedicated backends per capture mode
- Dynamic release versioning from git tags and CI metadata
- Browser connection diagnostics with actionable error messages
- Menu scrolling support for nested CustomTkinter scroll areas

### Fixed
- Audio capture fallback behavior (no implicit microphone)
- Windows loopback capture with OBS-like architecture

## [1.3.3] - 2026-09-15

### Fixed
- PortAudio channel negotiation for render endpoints
- Browser extension token display and authentication flow
- Persistent browser extension installation directory
- Stem mixer lifecycle and canvas destruction
- MIDI synthesizer widget lifecycle management

## [1.3.2] - 2026-09-14

### Added
- Edge browser manifest variant
- Enhanced WASAPI loopback device detection
- MIDI synthesizer with instrument selection
- Comprehensive diagnostics feedback system

### Fixed
- GUI import of missing modules
- WASAPI -9998 channel error
- Project logo and CI badge display

## [1.3.1] - 2026-09-14

### Added
- On-demand portable FFmpeg downloader with scope selection
- Automatic session cleanup for temporary codec files
- M4A (AAC/ALAC) conversion support

## [1.3.0] - 2026-09-13

### Added
- Dynamic internationalization (German/English) with live switching
- Hierarchical navigation with scrollable sidebar
- Audio converter with M4A container support
- Diagnostic runner framework
- Context-sensitive help system
- Codec capability detection and FFmpeg integration

### Changed
- Migrated to modular er_audio_tool package architecture
- Separated recording backends by source type
- Unified browser connection management

## [1.2.0] - 2026-09-13

### Added
- Automated portable release builds for Windows and Linux
- Separate CI pipeline and release workflow
- Python 3.14 compatibility

### Changed
- Migrated from monolithic to modular architecture

## [1.0.0] - 2026-09-13

### Added
- Initial release of er-audio-tool
- Windows WASAPI loopback recording
- Linux PipeWire/PulseAudio recording
- Browser tab audio capture via Manifest V3 extension
- Audio format conversion (MP3, WAV, FLAC)
- Audio analysis (waveform, spectrum, loudness)
- Audio-to-MIDI transcription
- MIDI-to-MP3 rendering
- German and English localization

---

## Version History Note

er-audio-tool is derived from [skillerious/Loopback-Recorder](https://github.com/skillerious/Loopback-Recorder) by Robin Doak.

The original project is available under the MIT License. er-audio-tool is an independently maintained fork with significant architectural changes and is not affiliated with or endorsed by the original author.
