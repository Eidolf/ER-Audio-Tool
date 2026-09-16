# Third-Party Notices & Licenses

er-audio-tool incorporates open-source libraries and components under various permissive licenses:

## Core Dependencies

### 1. Loopback-Recorder (Original Upstream)
- **Author**: Robin Doak
- **License**: MIT License
- **URL**: https://github.com/skillerious/Loopback-Recorder
- **Usage**: Original codebase foundation

### 2. CustomTkinter
- **Author**: Tom Schimansky
- **License**: Creative Commons Zero v1.0 Universal / MIT
- **URL**: https://github.com/TomSchimansky/CustomTkinter
- **Usage**: GUI framework

### 3. NumPy
- **License**: BSD 3-Clause
- **URL**: https://numpy.org
- **Usage**: Numerical operations and audio sample processing

### 4. SoundFile & libsndfile
- **License**: BSD 3-Clause / LGPL 2.1+
- **URL**: https://github.com/bastibe/python-soundfile
- **Usage**: Audio file I/O (WAV, FLAC, OGG)

### 5. SoundDevice & PortAudio
- **License**: MIT License
- **URL**: https://github.com/spatialaudio/python-sounddevice
- **Usage**: Cross-platform audio device access

### 6. Pillow (PIL Fork)
- **License**: HPND (Historical Permission Notice and Disclaimer)
- **URL**: https://python-pillow.org/
- **Usage**: Image loading and icon handling

## Optional Full Feature Dependencies

### 7. Matplotlib
- **License**: PSF-based (Python Software Foundation style)
- **URL**: https://matplotlib.org
- **Usage**: Audio waveform and spectrum visualization

### 8. Mutagen
- **License**: GNU GPL v2
- **URL**: https://github.com/quodlibet/mutagen
- **Usage**: Audio metadata reading and writing
- **Note**: GPL dependency - users who distribute binaries must comply with GPL terms

### 9. SciPy
- **License**: BSD 3-Clause
- **URL**: https://scipy.org
- **Usage**: Signal processing, tempo and key detection

## External Binaries (Optional Runtime Downloads)

### 10. FFmpeg
- **License**: LGPL 2.1+ or GPL 2+ (depending on build configuration)
- **URL**: https://ffmpeg.org
- **Download Source**: https://github.com/BtbN/FFmpeg-Builds
- **Usage**: Audio codec conversion, M4A (AAC/ALAC) support, native WASAPI loopback
- **Note**: GPL builds used - source code availability required for distribution

## Development Dependencies

### 11. pytest
- **License**: MIT License
- **URL**: https://pytest.org
- **Usage**: Testing framework

### 12. pytest-asyncio
- **License**: Apache License 2.0
- **URL**: https://github.com/pytest-dev/pytest-asyncio
- **Usage**: Async test support

### 13. pytest-cov / Coverage.py
- **License**: Apache License 2.0
- **URL**: https://github.com/pytest-dev/pytest-cov
- **Usage**: Code coverage measurement

### 14. Ruff
- **License**: MIT License
- **URL**: https://github.com/astral-sh/ruff
- **Usage**: Python linter and code formatter

### 15. mypy
- **License**: MIT License
- **URL**: https://mypy-lang.org
- **Usage**: Static type checking

## License Compatibility

er-audio-tool is licensed under the MIT License. All core dependencies are compatible with MIT licensing.

**Important Notes:**

1. **Mutagen (GPL)**: The optional Mutagen library is licensed under GPL v2. Users who distribute er-audio-tool binaries with Mutagen must comply with GPL requirements.

2. **FFmpeg (GPL/LGPL)**: er-audio-tool downloads FFmpeg GPL builds for codec support. Distributors must:
   - Provide access to FFmpeg source code
   - Comply with GPL licensing terms
   - Alternatively, use LGPL-only FFmpeg builds (limited codecs)

3. **libsndfile (LGPL)**: Dynamically linked, no special requirements for binary distribution.

## Acknowledgments

Special thanks to all open-source contributors whose work makes er-audio-tool possible.

## Full License Texts

For complete license texts of all dependencies, see their respective repositories and documentation.
