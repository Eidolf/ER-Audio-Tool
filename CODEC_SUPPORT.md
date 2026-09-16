# Codec Capability Matrix

This document specifies the exact audio codecs and formats supported by er-audio-tool.

**Last Updated:** 2026-09-17  
**Version:** 1.3.7

---

## Overview

er-audio-tool supports various audio formats through different backends:

1. **Native Support** (always available via Python soundfile)
2. **FFmpeg Support** (requires FFmpeg installation)

---

## Native Support (No FFmpeg Required)

These formats are always supported without additional downloads:

| Format | Extension | Encoding | Decoding | Quality | Notes |
|--------|-----------|----------|----------|---------|-------|
| **WAV** | `.wav` | ✅ Yes | ✅ Yes | Lossless | PCM 16-bit, 24-bit, 32-bit float |
| **FLAC** | `.flac` | ✅ Yes | ✅ Yes | Lossless | Compressed, smaller than WAV |
| **OGG Vorbis** | `.ogg` | ✅ Yes | ✅ Yes | Lossy | Open format, good quality |

**Container/Codec Details:**

- **WAV:** PCM (Pulse Code Modulation)
  - Subformats: PCM_16, PCM_24, PCM_32, FLOAT32, FLOAT64
  - Uncompressed, highest quality, large file size
  - Standard for professional audio

- **FLAC:** Free Lossless Audio Codec
  - Compressed lossless (50-70% of WAV size)
  - Metadata support
  - Open source, patent-free

- **OGG Vorbis:**
  - Lossy compression (similar to MP3)
  - Open format
  - Adjustable quality (q0-q10)

---

## FFmpeg-Required Formats

These formats require FFmpeg installation (available via **Settings > Setup & Codecs**):

### MP3 (MPEG Audio Layer 3)

| Feature | Support | Details |
|---------|---------|---------|
| **Decoding** | ✅ Yes | All MP3 files (CBR, VBR, ABR) |
| **Encoding** | ✅ Yes | Via libmp3lame encoder |
| **Bitrates** | 64-320 kbps | Configurable |
| **Channels** | Mono, Stereo | Joint stereo supported |
| **Sample Rates** | 8-48 kHz | All standard rates |

**Notes:**
- Most widely compatible format
- Good quality at 320 kbps
- Patent-free as of 2017
- ID3 metadata support

### M4A (MPEG-4 Audio Container)

M4A is a container format that can hold different codecs:

#### M4A with AAC (Advanced Audio Coding)

| Feature | Support | Details |
|---------|---------|---------|
| **Decoding** | ✅ Yes | All AAC variants |
| **Encoding** | ✅ Yes | Via FFmpeg AAC encoder |
| **Bitrates** | 64-320 kbps | Configurable |
| **Profiles** | AAC-LC, HE-AAC | LC = Low Complexity (most common) |
| **Channels** | Mono to 5.1 | Stereo most common |

**Notes:**
- Default iTunes format
- Better quality than MP3 at same bitrate
- Native Apple format
- Metadata support (iTunes tags)

**Status:** ✅ **Verified** - AAC decoding and encoding tested and working

#### M4A with ALAC (Apple Lossless Audio Codec)

| Feature | Support | Details |
|---------|---------|---------|
| **Decoding** | ⚠️ Requires Testing | Should work with Full FFmpeg |
| **Encoding** | ⚠️ Requires Testing | Should work with Full FFmpeg |
| **Quality** | Lossless | Bit-perfect, 40-60% of WAV size |
| **Channels** | Up to 8 channels | Stereo most common |

**Notes:**
- Apple's lossless format
- Smaller than WAV, same quality
- Native macOS/iOS format
- **Requires "Full" codec pack**

**Status:** ⚠️ **REQUIRES VERIFICATION** - ALAC support claimed but not tested with real ALAC files

### Opus

| Feature | Support | Details |
|---------|---------|---------|
| **Decoding** | ✅ Yes | All Opus files |
| **Encoding** | ✅ Yes | Via libopus |
| **Bitrates** | 6-510 kbps | Typically 64-128 kbps |
| **Latency** | Low | Good for real-time |
| **Channels** | Mono to 255 channels | Stereo most common |

**Notes:**
- Modern open format
- Better quality than MP3 at lower bitrates
- Optimized for speech and music
- Used by WhatsApp, Discord, YouTube

### Additional Formats (Full Codec Pack Only)

These formats require the **Full** FFmpeg codec pack:

| Format | Extension | Decode | Encode | Notes |
|--------|-----------|--------|--------|-------|
| **AIFF** | `.aiff`, `.aif` | ✅ Yes | ✅ Yes | Apple audio format, uncompressed |
| **WMA** | `.wma` | ✅ Yes | ❌ No | Windows Media Audio (read-only) |
| **AC3** | `.ac3` | ✅ Yes | ⚠️ Limited | Dolby Digital (DVDs) |
| **AMR** | `.amr` | ✅ Yes | ✅ Yes | Narrowband speech codec |
| **DTS** | `.dts` | ✅ Yes | ❌ No | Digital Theater System (read-only) |

**Notes:**
- Full codec pack is larger download (~100-200 MB)
- Includes legacy and specialized formats
- Some formats support decoding only (no encoding)

---

## Codec Pack Comparison

### Essential Codec Pack (Recommended)

**Size:** ~50-80 MB

**Includes:**
- ✅ MP3 (decode + encode)
- ✅ AAC/M4A (decode + encode)
- ✅ WAV (always available)
- ✅ FLAC (always available)
- ✅ OGG Vorbis (always available)
- ✅ Opus (decode + encode)

**Best for:**
- Standard audio recording
- Music conversion
- Podcast production
- General use

### Full Codec Pack (Advanced)

**Size:** ~100-200 MB

**Includes:**
- ✅ Everything in Essential
- ✅ ALAC (Apple Lossless)
- ✅ AIFF (Apple audio)
- ✅ WMA (Windows Media)
- ✅ AC3 (Dolby Digital)
- ✅ AMR (speech codec)
- ✅ DTS (read-only)
- ✅ Legacy formats

**Best for:**
- Professional audio work
- Format archival
- Legacy file support
- Apple ecosystem users (ALAC)

---

## Recording Formats

### Available Recording Formats

When recording system audio, microphone, or browser tabs, you can output to:

| Format | Recommended | Quality | File Size (1 min stereo 44.1kHz) |
|--------|-------------|---------|-----------------------------------|
| **WAV** | ✅ Yes | Lossless | ~10 MB |
| **FLAC** | ✅ Yes | Lossless | ~5-7 MB |
| **MP3** | ✅ Yes (320 kbps) | Near-lossless | ~2.5 MB |
| **MP3** | ⚠️ OK (192 kbps) | Good | ~1.5 MB |
| **OGG Vorbis** | ⚠️ OK (q8) | Good | ~1-2 MB |

**Recommendations:**

- **Best quality:** WAV or FLAC (lossless)
- **Best size/quality balance:** MP3 320 kbps
- **Smallest size:** MP3 192 kbps or OGG Vorbis

**Note:** Recording always captures at full quality internally. Format selection only affects the saved file.

---

## Conversion Capabilities

### Supported Conversion Paths

**FROM any supported format TO:**

| To Format | Quality | Use Case |
|-----------|---------|----------|
| **WAV** | Lossless | Editing, archival |
| **FLAC** | Lossless | Compressed archival |
| **MP3 320k** | Near-lossless | Universal playback |
| **MP3 192k** | Good | Mobile devices |
| **OGG Vorbis** | Good | Open format preference |
| **Opus** | Excellent | Modern efficient format |

**Example conversions:**

```
M4A (AAC) → MP3 320k    ✅ Supported
M4A (ALAC) → FLAC       ⚠️ Requires verification
MP3 → WAV              ✅ Supported (but lossy source)
WAV → MP3              ✅ Supported
FLAC → MP3             ✅ Supported
OGG → WAV              ✅ Supported
```

### Batch Conversion

All supported input formats can be batch-converted to any supported output format.

**Limitations:**
- Protected/DRM files: ❌ Not supported (cannot bypass DRM)
- Corrupted files: ❌ Will fail with error
- Very large files (>2 GB): ⚠️ May be slow

---

## Sample Rate and Channel Support

### Recording

| Parameter | Supported Values | Recommended |
|-----------|------------------|-------------|
| **Sample Rate** | 8 kHz - 192 kHz | 44.1 kHz or 48 kHz |
| **Channels** | Mono (1), Stereo (2) | Stereo (2) |
| **Bit Depth** | 16-bit, 24-bit, 32-bit float | 16-bit (sufficient) |

**Notes:**
- Higher sample rates = larger files with no audible benefit for most use
- 44.1 kHz: CD quality, music
- 48 kHz: Professional video, broadcasting
- 96 kHz or higher: Unnecessary for typical use

### Conversion

Sample rate and channel count can be changed during conversion:

- **Upsampling:** 44.1 kHz → 48 kHz (no quality gain)
- **Downsampling:** 48 kHz → 44.1 kHz (safe, slight quality loss)
- **Stereo to Mono:** Averages channels
- **Mono to Stereo:** Duplicates channel

---

## Metadata Support

| Format | Metadata Standard | Supported Fields |
|--------|-------------------|------------------|
| **WAV** | RIFF INFO | Title, Artist, Album (limited) |
| **FLAC** | Vorbis Comments | Full tags supported |
| **MP3** | ID3v2 | Title, Artist, Album, Year, Genre, Cover Art |
| **M4A/AAC** | iTunes Tags | Full iTunes metadata |
| **OGG Vorbis** | Vorbis Comments | Full tags supported |
| **Opus** | Vorbis Comments | Full tags supported |

**er-audio-tool metadata capabilities:**
- ✅ Preserves existing metadata during conversion
- ✅ Reads metadata for display in analysis
- ⚠️ Manual metadata editing: Limited (use dedicated tools)

---

## Limitations and Known Issues

### Format-Specific Limitations

**M4A ALAC:**
- ⚠️ Support claimed but **not verified with real ALAC files**
- Requires Full FFmpeg codec pack
- If ALAC conversion fails, report as bug

**WMA:**
- Read-only (decoding only)
- Windows-specific format
- Convert to open format recommended

**DTS/AC3:**
- Primarily for DVD/Blu-ray audio
- Multi-channel formats
- Conversion to stereo may lose surround information

### Platform-Specific Notes

**Windows:**
- ✅ All formats supported
- ✅ Native WASAPI recording

**Linux:**
- ✅ All formats supported via FFmpeg
- ✅ PipeWire/PulseAudio recording

**macOS:**
- ⚠️ Not officially tested
- Should work (similar to Linux)

---

## Testing Status

| Format | Recording | Conversion | Analysis | Status |
|--------|-----------|------------|----------|--------|
| WAV | ✅ Tested | ✅ Tested | ✅ Tested | Verified |
| FLAC | ✅ Tested | ✅ Tested | ✅ Tested | Verified |
| MP3 | ✅ Tested | ✅ Tested | ✅ Tested | Verified |
| OGG Vorbis | ✅ Tested | ✅ Tested | ✅ Tested | Verified |
| M4A AAC | ⚠️ Basic | ✅ Tested | ✅ Tested | Verified |
| M4A ALAC | ❌ Not tested | ⚠️ Claimed | ⚠️ Unknown | **Needs verification** |
| Opus | ⚠️ Basic | ⚠️ Basic | ⚠️ Basic | Functional |
| AIFF | ❌ Not tested | ⚠️ Claimed | ⚠️ Unknown | Needs verification |

**Legend:**
- ✅ Tested: Verified with multiple test files
- ⚠️ Basic/Claimed: Should work but not extensively tested
- ❌ Not tested: No testing performed

---

## Verification and Testing

### How to Verify Codec Support

1. **Check FFmpeg availability:**
   - Navigate to **Diagnostics** in er-audio-tool
   - Look for "FFmpeg Status" section
   - Should show version and available codecs

2. **Test conversion:**
   - Convert a known-good file to desired format
   - Open converted file in media player
   - Compare with original (lossy formats will differ)

3. **Test recording:**
   - Record short test (10-30 seconds)
   - Verify file opens and plays
   - Check file size is reasonable

### Reporting Codec Issues

If a format doesn't work as documented:

1. Note the exact error message
2. Try with different input file
3. Verify FFmpeg is installed and updated
4. Check diagnostics output
5. Report issue with:
   - Input format and source
   - Desired output format
   - FFmpeg version
   - Error message

---

## Future Codec Support

### Under Consideration

- **AAC+** (HE-AAC v2): Low-bitrate streaming
- **aptX**: Bluetooth audio codec
- **LDAC**: Sony high-quality Bluetooth

### Not Planned

- **Proprietary formats requiring licensing:** Dolby TrueHD encoding, DTS-HD encoding
- **DRM-protected formats:** iTunes DRM, WMA DRM (cannot bypass protection)
- **Obsolete formats:** Real Audio, MPC (no longer widely used)

---

## Summary

**Always Available (No FFmpeg):**
- WAV, FLAC, OGG Vorbis

**Essential FFmpeg Pack:**
- MP3, AAC/M4A, Opus

**Full FFmpeg Pack:**
- ALAC, AIFF, WMA (read), AC3, AMR, DTS (read)

**Recommended Workflow:**
1. Record in WAV or FLAC (lossless)
2. Convert to MP3 320k for distribution
3. Keep lossless master for archival

**For most users: Essential pack is sufficient.**

---

**Questions about codec support? Check diagnostics or report an issue.**
