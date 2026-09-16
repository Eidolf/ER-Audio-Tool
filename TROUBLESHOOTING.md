# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with er-audio-tool.

---

## Quick Diagnostics

Before troubleshooting specific issues, run the built-in diagnostics:

1. Launch er-audio-tool
2. Navigate to **Devices > Hardware and Software Test** or **Diagnostics**
3. Click **Run Full Diagnostics**
4. Review the results for any errors or warnings

The diagnostics will check:
- Operating system and architecture
- Audio backend availability
- Device enumeration
- File system permissions
- Browser connection status
- Codec capabilities

---

## Recording Issues

### No Audio Devices Found

**Symptoms:**
- Device list is empty
- "No audio devices available" message
- Can't start recording

**Possible Causes & Solutions:**

**Windows:**
1. **No audio drivers installed**
   - Install audio drivers for your sound card
   - Check Device Manager for audio devices

2. **WASAPI not available**
   - Ensure Windows Audio service is running
   - Check: Services → Windows Audio → Status should be "Running"

3. **Application running without audio permissions**
   - Some Windows configurations require explicit permissions
   - Try running as administrator (not recommended as permanent solution)

**Linux:**
1. **PipeWire/PulseAudio not running**
   - Check: `systemctl --user status pipewire` or `pulseaudio --check`
   - Start service: `systemctl --user start pipewire`

2. **Missing audio libraries**
   - Install: `sudo apt install libportaudio2 libsndfile1` (Ubuntu/Debian)
   - Install: `sudo dnf install portaudio libsndfile` (Fedora)

3. **User not in audio group**
   - Add yourself: `sudo usermod -a -G audio $USER`
   - Log out and back in for changes to take effect

---

### Recording Produces No Audio (Empty or Silent File)

**Symptoms:**
- Recording completes successfully
- File is created but contains silence
- File size is very small (header only)

**Diagnosis Steps:**

1. **Check live level meters during recording**
   - Meters should show activity (green/yellow bars)
   - If meters are flat (no movement), input source is not producing audio

2. **Verify output file**
   - Open the output file in diagnostic mode: **Help > Diagnostics > Validate Output File**
   - Classification will show: VALID_SIGNAL, DIGITAL_SILENCE, or NO_FRAMES

**Solutions by Scenario:**

**Scenario A: Level Meters Show No Activity**

*Cause: Wrong input source selected*

**Windows - System Output Mode:**
- Verify audio is actually playing from your speakers/headphones
- Check Windows Sound settings: ensure correct default playback device
- Try selecting a different output device in er-audio-tool
- Test by playing music during recording

**Windows - Application Audio Mode:**
- **Known Limitation:** Application-specific audio capture is currently unavailable
- Use **System Output** mode instead
- This captures all system audio (including the application)

**Browser Tab Mode:**
- Verify browser extension is connected (see Browser Extension section below)
- Ensure you selected the correct tab
- Start playing audio in the tab BEFORE starting recording
- Check that tab isn't muted in browser

**Microphone Mode:**
- Verify microphone is working (test in Windows Sound settings)
- Check microphone isn't muted
- Ensure correct microphone is selected in er-audio-tool

**Scenario B: Level Meters Show Activity but File is Silent**

*Cause: Writer/encoder failure*

1. Check application logs in `logs/` directory
2. Look for encoder errors
3. Try a different output format (WAV instead of MP3)
4. Check disk space (full disk prevents writing)
5. Verify output directory is writable

**Scenario C: NO_FRAMES Classification**

*Cause: Recording stopped immediately or backend failed*

1. Check for error messages during recording start
2. Review diagnostics output
3. Try a different audio device
4. Verify backend is available (WASAPI on Windows, PipeWire on Linux)

---

### System Output Recording Captures Microphone Instead

**This should NEVER happen.** If it does, it's a critical bug.

**Verify the issue:**
1. Play a specific audio source (e.g., music at 440 Hz or 880 Hz tone)
2. Record using **System Output** mode
3. Analyze recording: should contain only the played audio, not mic input

**If microphone is being captured:**
- This violates the strict source isolation architecture
- Report immediately as a P0 bug
- Include: OS version, audio device name, diagnostic output

**Workaround:**
- Physically mute or disconnect microphone during recording
- Use selective application recording if available

---

### Recording Cuts Off or Stutters

**Symptoms:**
- Recording starts but stops prematurely
- Audio has gaps or stutters
- Clicks or pops in recording

**Possible Causes & Solutions:**

1. **CPU overload**
   - Close other applications
   - Lower sample rate (44.1 kHz instead of 48 kHz)
   - Check CPU usage during recording

2. **Disk I/O bottleneck**
   - Record to fast local drive (not network drive)
   - Avoid recording to USB 2.0 drives
   - Check disk usage during recording

3. **Buffer underrun**
   - Increase audio buffer size (if setting available)
   - Close real-time audio applications (DAWs, games)

4. **Device disconnected**
   - Don't disconnect audio devices during recording
   - Use wired headphones instead of Bluetooth (lower latency)

---

### "Channel Negotiation Failed" or Error -9998

**This error should be fixed in current versions.**

**If you still see this error:**

**Symptoms:**
- Error: "Invalid number of channels [PaErrorCode -9998]"
- Recording won't start
- Channel mismatch message

**Cause:**
- Audio device doesn't support requested channel configuration

**Solutions:**

1. **Update er-audio-tool**
   - This issue was fixed with multi-candidate channel negotiation
   - Current version should try: native channels → stereo → mono

2. **Check device capabilities**
   - Navigate to **Devices > Hardware and Software Test**
   - Note the supported channels for your device
   - Try selecting stereo (2 channels) or mono (1 channel) explicitly

3. **Report if issue persists**
   - This indicates a regression or edge case
   - Include: device name, channels reported, diagnostic output

---

### WASAPI Error: "Unsupported loopback parameter"

**This error should NOT occur in current versions.**

**If you see this error:**

**Symptoms:**
- Error message mentions "WasapiSettings" or "loopback parameter"
- TypeError or AttributeError related to audio backend

**Cause:**
- Regression: Code is passing unsupported parameters to sounddevice

**Solution:**
- This is a critical regression (P0)
- Update to latest version
- If persists, report immediately with full error trace

**Current Architecture:**
- er-audio-tool uses FFmpeg native WASAPI loopback (primary method)
- Fallback to PortAudio with proper endpoint detection
- Does NOT pass `loopback=True` to WasapiSettings

---

## Conversion Issues

### M4A Files Won't Convert

**Symptoms:**
- "Unsupported format" error
- "Codec not available" message
- Conversion fails for .m4a files

**Cause:**
- FFmpeg not available or doesn't have AAC/ALAC codec support

**Solutions:**

1. **Install FFmpeg**
   - Navigate to **Settings > Setup & Codecs** or **Settings > FFmpeg & Codecs**
   - Select codec scope: "Essential" or "Full"
   - Click **Download FFmpeg**
   - Wait for download and extraction

2. **Verify FFmpeg availability**
   - Go to **Diagnostics**
   - Check "FFmpeg Status" section
   - Should show: "FFmpeg available: Yes" with version

3. **Check M4A codec**
   - M4A is a container format
   - Can contain AAC (compressed) or ALAC (lossless)
   - Essential codecs include AAC
   - Full codecs include ALAC
   - Check codec with: **Analyze > Audio File > [Select M4A]**

4. **Try conversion to WAV first**
   - WAV is always supported (uncompressed)
   - Convert: M4A → WAV → desired format

**ALAC Specific Issues:**

ALAC (Apple Lossless) support requires Full codec pack.

If ALAC conversion fails:
- Verify Full codecs installed
- Try converting with external tool first
- Report if issue persists (ALAC support needs verification)

---

### Conversion Produces Corrupted File

**Symptoms:**
- Output file won't open
- File size is 0 bytes or very small
- Media players show "format not recognized"

**Diagnosis:**

1. **Check input file integrity**
   - Can you play the input file in media player?
   - Try analyzing input file first: **Analyze > Audio File**

2. **Check output validation**
   - Converter should validate output automatically
   - Look for validation errors in status

**Solutions:**

1. **Disk space**
   - Ensure enough free space for output file
   - WAV files are large (1 min ≈ 10 MB stereo 44.1kHz)

2. **File permissions**
   - Check output directory is writable
   - Avoid system-protected directories

3. **Codec failure**
   - Try different output format
   - WAV format is most reliable (no codec needed)

4. **Input file issues**
   - If input is corrupted, output will be too
   - Try re-downloading or re-recording input

---

## Browser Extension Issues

See [BROWSER_EXTENSION_SETUP.md](BROWSER_EXTENSION_SETUP.md) for detailed browser extension troubleshooting.

**Quick checks:**

1. **Extension not connecting:**
   - Verify desktop app is running
   - Check token is correct
   - Try regenerating token

2. **Tab not recordable:**
   - Some browser internal pages can't be captured
   - Try YouTube or other media site

3. **Empty browser recording:**
   - Verify tab was playing audio
   - Check level meters during recording
   - Ensure correct tab selected

---

## MIDI Issues

### Audio to MIDI Produces No Notes

**Symptoms:**
- Transcription completes but MIDI file is empty
- No notes in piano roll

**Possible Causes:**

1. **Input audio too quiet**
   - Normalize audio before transcription
   - Or increase amplitude in analysis

2. **Wrong profile selected**
   - "Melody" profile: for monophonic melodies (single note at a time)
   - "Piano" profile: for polyphonic piano (chords)
   - "Bass" profile: for low-frequency bass lines
   - Try different profiles

3. **Input is percussion/noise**
   - Pitch detection works for tonal instruments
   - Percussion requires "Percussive" profile

**Solutions:**

1. **Adjust confidence threshold**
   - Lower threshold produces more notes (may include false positives)
   - Higher threshold produces fewer notes (more accurate)
   - Default: 0.5 (50%)

2. **Adjust minimum note duration**
   - Very short notes may be filtered out
   - Lower minimum duration for faster passages

3. **Pre-process audio**
   - Use stem separation to isolate instrument
   - Remove background noise
   - Normalize volume

---

### MIDI Rendering Produces No Sound

**Symptoms:**
- MIDI to MP3 conversion completes
- Output file exists but is silent

**Possible Causes:**

1. **No SoundFont installed**
   - MIDI rendering requires SoundFont (.sf2) file
   - Check if SoundFont is configured in settings

2. **Wrong MIDI channel**
   - Ensure MIDI notes are on channels 0-15
   - Channel 9 is reserved for drums

3. **Instrument not in SoundFont**
   - Selected instrument (Program Change) not available
   - Falls back to piano

**Solutions:**

1. **Install SoundFont**
   - Download General MIDI SoundFont (e.g., FluidR3_GM.sf2)
   - Configure in **Settings > MIDI**
   - Public domain SoundFonts available online

2. **Verify MIDI file**
   - Open MIDI in external MIDI player to verify notes exist
   - Check that notes are audible in preview

3. **Check instrument assignments**
   - Verify Program Change events in MIDI file
   - Default to piano (Program 0) if unsure

---

### "Invalid command name" Error During MIDI Rendering

**This error was fixed in current versions.**

**Symptoms:**
- Error: "Synthesis failed: invalid command name '...!ctktextbox.!text'"
- MIDI rendering fails with Tk widget error

**Cause:**
- Background synthesis process tried to update destroyed GUI widget
- Job state was incorrectly tied to page lifecycle

**Solution:**
- Update to latest version (fix implemented)
- This should not occur in current release

**If error persists:**
- Report as regression
- Workaround: Keep MIDI page open during rendering

---

## Performance Issues

### Application Slow or Unresponsive

**Symptoms:**
- UI freezes during operations
- Long delay when switching pages
- Sluggish navigation

**Possible Causes & Solutions:**

1. **Large audio files**
   - Loading very large files (>100 MB) can be slow
   - Wait for operation to complete
   - Consider splitting large files

2. **Analysis with visualization**
   - Spectrum and waveform generation is CPU-intensive
   - Disable real-time visualization if slow

3. **Low-end hardware**
   - Close other applications
   - Reduce sample rate
   - Avoid stem separation on very old CPUs

4. **Memory leak (potential bug)**
   - If performance degrades over time
   - Restart application
   - Report with: OS, version, operations performed

---

### Long Recordings Fail or Crash

**Symptoms:**
- Application crashes after recording for extended period
- Out of memory error
- Recording stops unexpectedly

**Limits:**

- **Memory:** Audio is buffered in RAM during recording
- **Disk:** Ensure enough free space for output file
- **Duration:** No artificial limit, but practical limit depends on available RAM

**Solutions:**

1. **Monitor memory usage**
   - Long recordings consume RAM
   - Check available memory before long sessions

2. **Close other applications**
   - Free up RAM for recording

3. **Use compressed format**
   - MP3 output files are smaller than WAV
   - But recording still buffers uncompressed audio in memory

4. **Split recordings**
   - Record in multiple shorter sessions
   - Combine files later if needed

**Expected performance:**

- 1 hour stereo 48kHz: ~10 MB RAM, ~600 MB WAV file
- 2 hours stereo 48kHz: ~20 MB RAM, ~1.2 GB WAV file

If crashes occur with shorter recordings, report as bug.

---

## Installation & Portability Issues

### Portable Build Won't Launch

**Symptoms:**
- Double-clicking executable does nothing
- Executable opens and closes immediately
- "Missing DLL" error (Windows)
- "Library not found" error (Linux)

**Windows:**

1. **Missing Visual C++ Redistributable**
   - Download from Microsoft: VC++ Redistributable (x64)
   - Install and restart

2. **Antivirus blocking**
   - Some antivirus software blocks unsigned executables
   - Add exception for er-audio-tool
   - Or download from trusted source

3. **Corrupted download**
   - Re-download executable
   - Verify checksum if provided

**Linux:**

1. **Missing system libraries**
   - Install: `sudo apt install libportaudio2 libsndfile1 libasound2`
   - Or: `sudo dnf install portaudio libsndfile alsa-lib`

2. **Permissions**
   - Make executable: `chmod +x er-audio-tool`
   - Or: `chmod +x er-audio-tool.AppImage`

3. **FUSE required (AppImage)**
   - Install: `sudo apt install fuse libfuse2`

---

### "Extension Directory Not Found" Error

**Symptoms:**
- Browser extension setup shows temporary path (_MEI...)
- Extension files not accessible after closing app

**Cause:**
- Extension directory not properly extracted from portable build

**Solution:**

1. **Extract extension manually:**
   - Look for `browser_extension/` in application directory
   - If not present, this is a packaging bug

2. **Workaround:**
   - Run application
   - Navigate to extension setup
   - Copy files from temporary directory to permanent location
   - Use permanent location for browser extension

3. **Report issue:**
   - This is a packaging defect
   - Include: OS, portable vs installed, error message

---

## Localization Issues

### Language Switch Doesn't Work

**Symptoms:**
- Selecting German/English has no effect
- UI remains in current language

**Solution:**

1. **Restart application**
   - Language switch should be immediate (bug if not)
   - Try restarting as workaround

2. **Check language files**
   - Navigate to installation directory
   - Verify `er_audio_tool/i18n/` directory exists
   - Should contain translation files

3. **Report if persists**
   - This was fixed in current version
   - If still occurs, it's a regression

---

### Mixed Language UI

**Symptoms:**
- Some text in German, some in English
- Untranslated strings

**Cause:**
- Incomplete translation coverage
- Missing translation keys

**Solution:**

1. **Report missing translations**
   - Note which strings are untranslated
   - Report with screenshot

2. **Workaround:**
   - Switch to English (more complete)

---

## Diagnostic Steps

### Collecting Diagnostic Information

If you need to report a bug:

1. **Run diagnostics:**
   - Navigate to **Devices > Hardware and Software Test**
   - Click **Run Full Diagnostics**
   - Click **Export Report**
   - Save to file

2. **Check logs:**
   - Logs are in `logs/` directory (development) or `er-audio-tool/logs/` (portable)
   - Latest log: `loopback.log`
   - Include relevant portions (sanitize private paths)

3. **System information:**
   - OS and version
   - er-audio-tool version (shown in title bar)
   - Audio hardware
   - Browser and version (if extension issue)

4. **Steps to reproduce:**
   - Describe exactly what you did
   - Include settings/configuration
   - Note when error occurred

---

## Getting Help

If your issue isn't covered here:

1. **Check documentation:**
   - README.md
   - BROWSER_EXTENSION_SETUP.md
   - Architecture documentation

2. **Search existing issues:**
   - https://github.com/Eidolf/ER-Audio-Tool/issues

3. **Report new issue:**
   - Include diagnostic output
   - Include steps to reproduce
   - Sanitize private information (paths, names)

4. **Community support:**
   - (If forums/Discord exist, add here)

---

## Known Limitations

### Windows Application Audio

**Status:** Currently unavailable

**Reason:** Standard sounddevice/PortAudio library doesn't expose Windows process-specific loopback capture API.

**Workaround:** Use **System Output** mode to capture all system audio (includes target application).

**Future:** May be implemented with native Windows Audio API extension or alternative library.

### Stem Separation

**Status:** Placeholder implementation (no ML model)

**Reason:** Requires large ML model (hundreds of MB) with licensing and dependencies.

**Workaround:** Use external tools for stem separation, then import results.

**Future:** Under consideration for future release.

### Full MIDI Arrangement

**Status:** Partial implementation (not true multitrack)

**Current:** Single MIDI track output with all notes

**Expected:** Multiple synchronized tracks with separate instruments

**Future:** Planned enhancement.

---

## Common Error Messages

| Error | Meaning | Solution |
|-------|---------|----------|
| "WASAPI not available" | Windows Audio API not accessible | Check Windows Audio service running |
| "No audio devices found" | No capture devices detected | Install audio drivers, check backend |
| "Channel negotiation failed" | Device doesn't support requested channels | Update to latest version (should auto-negotiate) |
| "Invalid token" | Browser extension auth token mismatch | Copy token from desktop app again |
| "Not authenticated" | Browser extension not connected | Paste pairing token in extension |
| "No tab selected" | Browser recording started without tab selection | Select tab in extension first |
| "Output validation failed: NO_FRAMES" | Recording file contains no audio | Check source was playing, verify level meters |
| "FFmpeg not available" | Codec conversion requires FFmpeg | Install FFmpeg via Settings > Codecs |
| "Unsupported format" | File format not recognized | Install FFmpeg or use supported format |

---

**Still having issues? Report them on GitHub with diagnostic output!**
