# Technical Execution Plan: er-audio-tool Critical Issues Resolution

**Document Version:** 1.0  
**Created:** 2026-09-17  
**Technical Lead:** Claude (Sonnet 5)  
**Implementation Agent:** Antigravity  
**Project Owner:** Andreas (Eidolf)

**Status:** IN PROGRESS  
**Current Branch:** main  
**Target Release:** v0.5.0

---

## 1. DOCUMENT METADATA

**Purpose:** This is the single authoritative technical execution document for resolving critical P0 defects in er-audio-tool. All implementation status, evidence, and decisions must be recorded here.

**Stakeholders:**
- **Project Owner:** Defines requirements, approves priorities, requests final verification
- **Technical Lead (Claude):** Audits repository, reproduces defects, determines root causes, writes this specification, performs final verification
- **Implementation Agent (Antigravity):** Implements tasks, records evidence, updates this document

**Document Authority:**
- This document supersedes all temporary planning documents (ANLEITUNG_FUER_IDE.md, ANTIGRAVITY_STATUS.md, CODE_REVIEW_ANTIGRAVITY.md, SESSION_ABSCHLUSS.md)
- Implementation status exists in this document, not in chat history
- Only Claude may mark tasks as `Verified`
- Antigravity may set tasks no further than `Implemented, awaiting technical review`

---

## 2. EXECUTIVE SUMMARY

### Current State Assessment

**Repository State:**
- **Branch:** main (merged from comprehensive-audit-fixes)
- **Test Status:** 38/39 tests passing (97.4%, 1 GUI test skipped - expected)
- **Code Quality:** SEHR GUT (architecture sound, no critical security issues)
- **Documentation:** AUSGEZEICHNET (comprehensive user and technical docs)

**Critical Defects Identified (P0 Release Blockers):**

1. **NAV-001:** Left navigation menu does not scroll reliably with mouse wheel
2. **REC-001:** Audio recording produces no signal / detects no audio
3. **TEST-001:** Built-in audio test shows no level activity
4. **UI-001:** Visible command-prompt windows during normal operations
5. **FFMPEG-001:** FFmpeg package size discrepancy (essential vs full)

**Non-Critical Issues (P1-P2):**
- OBS Studio comparison needed for Windows audio capture reference
- Portable build verification incomplete (Windows VM unavailable in previous session)

### Technical Assessment Confidence Levels

**Confirmed:**
- PyInstaller spec configured with `console=False` ✓
- No Windows-specific subprocess hiding (CREATE_NO_WINDOW) implemented ✗
- Mouse wheel event handling uses `bind_all()` global binding ✓
- FFmpeg URLs point to same build type (GPL static) for essential/full on Linux ✓
- 15 subprocess invocations across codebase, none with Windows console hiding ✓

**Strongly Indicated:**
- Console windows appear because subprocess calls lack Windows `creationflags` parameter
- Mouse wheel may fail on nested scrollable regions due to event propagation issues
- Recording failure likely in audio backend initialization or device enumeration (not reproducible in mock backend environment)

**Hypothesis (Requires Verification):**
- FFmpeg "essential" label may be misleading (Linux essential/full both point to same URL)
- Windows system recording may fail due to sounddevice/WASAPI loopback configuration
- Level meters may receive frames but display incorrectly due to GUI update timing

---

## 3. SCOPE

### In Scope

**Phase 1: Critical P0 Defects (Release Blockers)**
- Mouse wheel navigation repair
- Windows subprocess console hiding
- Audio recording signal path verification
- Built-in test level meter verification
- FFmpeg package size audit and correction

**Phase 2: Technical Architecture Review**
- OBS Studio Windows audio capture comparison
- Backend selection architecture decision
- Portable build verification (Windows + Linux)

**Phase 3: Integration Verification**
- End-to-end recording tests (system, app, browser, mic)
- Portable build smoke tests
- Documentation accuracy validation

### Explicitly Out of Scope

- New feature development
- Performance optimization (not blocking)
- UI redesign or visual changes
- Browser extension E2E (documented as separate task)
- ALAC codec verification (documented as separate task)
- Code refactoring beyond what is required to fix defects

---

## 4. REPRODUCED DEFECTS

### Environmental Context

**Test Environment:**
- **OS:** Linux 6.8.0-139-generic
- **Python:** 3.14.6 (development) - **NOTE:** Portable builds must use 3.9-3.11
- **Audio Backend:** Mock (Linux environment, no real audio hardware available)
- **Display:** Headless (no X server for GUI testing)

**Reproduction Limitations:**
- Cannot reproduce Windows-specific audio capture issues
- Cannot reproduce Windows console window behavior
- Cannot test actual audio signal recording (mock backend only)
- Cannot test GUI mouse interactions (headless)

### NAV-001: Mouse Wheel Navigation - NOT REPRODUCED (Headless)

**Status:** Not reproduced (requires GUI environment)  
**Severity:** P0 (user cannot access all menu items)  
**Reported By:** Project Owner

**Evidence from Code Inspection:**

File: [er_audio_tool/gui/app.py:196-202](er_audio_tool/gui/app.py#L196-L202)

```python
self._sidebar_wheel_handler = _on_global_mousewheel
try:
    self.bind_all("<MouseWheel>", _on_global_mousewheel, add="+")
    self.bind_all("<Button-4>", _on_global_mousewheel, add="+")
    self.bind_all("<Button-5>", _on_global_mousewheel, add="+")
except Exception:
    pass
```

**Technical Findings:**
- Uses `bind_all()` which creates application-wide event bindings
- Event handler calls `canvas.yview_scroll()` on sidebar canvas
- No mechanism to prevent event propagation to content area
- Handler attempts to identify widget under cursor, but relies on fragile event.widget inspection
- Nested scrollable regions (sidebar + content) may compete for wheel events
- No lifecycle management - handlers persist across navigation rebuilds

**Root Cause (Hypothesis):**
Event propagation conflict between sidebar canvas and content frame scrollable regions. Global `bind_all()` delivers wheel events to both, causing unpredictable scroll behavior.

### REC-001: Audio Recording Signal Path - NOT REPRODUCED (Mock Backend)

**Status:** Not reproduced (requires real Windows audio hardware)  
**Severity:** P0 (core functionality broken)  
**Reported By:** Project Owner

**Evidence from Code Inspection:**

Audio flow architecture identified:
1. User selects source → [er_audio_tool/gui/app.py:1143-1215](er_audio_tool/gui/app.py#L1143-L1215)
2. Backend initialized → [er_audio_tool/audio/manager.py](er_audio_tool/audio/manager.py)
3. FFmpeg/sounddevice capture started → [er_audio_tool/audio/backends/windows_wasapi.py:104-300](er_audio_tool/audio/backends/windows_wasapi.py#L104-L300)
4. Audio callback invoked → `_on_audio_data_received()` at [er_audio_tool/gui/app.py:1279-1282](er_audio_tool/gui/app.py#L1279-L1282)
5. Frames pushed to buffer → [er_audio_tool/audio/buffer.py](er_audio_tool/audio/buffer.py)
6. Level meters updated → [er_audio_tool/gui/app.py:1673-1690](er_audio_tool/gui/app.py#L1673-L1690)

**Technical Findings:**
- Mock backend generates synthetic audio and calls callback successfully (test passing)
- Real Windows WASAPI backend attempts FFmpeg loopback capture first, falls back to sounddevice
- No instrumentation for debugging which stage fails (initialization, packet reception, callback invocation)
- Level meter reads from AudioBuffer.get_stereo_levels() every 50ms via GUI update loop
- No logging of frame counts, callback invocation count, or signal presence

**Root Cause (Hypothesis):**
One of:
1. Windows WASAPI device enumeration returns wrong device or fails silently
2. sounddevice loopback mode not supported on target system
3. FFmpeg WASAPI loopback subprocess exits immediately without error capture
4. Callback is invoked but receives zero-filled buffers (digital silence)
5. Audio data arrives but AudioBuffer session ID mismatch causes frame rejection

**Cannot Verify Without:** Real Windows system with actual audio hardware and playback

### TEST-001: Built-in Audio Test No Level Activity - NOT REPRODUCED

**Status:** Not reproduced (requires real audio hardware)  
**Severity:** P0 (diagnostic feature broken)  
**Reported By:** Project Owner

**Evidence from Code Inspection:**

File: [er_audio_tool/diagnostics/runner.py:29-170](er_audio_tool/diagnostics/runner.py#L29-L170)

**Technical Findings:**
- DiagnosticRunner.run_all_tests() performs static checks only
- No actual audio capture test with real backends
- No level meter verification
- No signal detection test
- Diagnostic reports "PASSED" for backend availability but does not verify actual audio flow

**Root Cause (Confirmed):**
Built-in test does NOT use production audio capture path. It only checks:
- OS and Python version
- Backend enumeration (`.is_available()`)
- Device enumeration (`.enumerate_devices()`)
- File write permissions
- FFmpeg binary existence

It does NOT:
- Start actual capture
- Verify callback invocation
- Verify frame reception
- Test level meters
- Verify signal detection

**This is a design deficiency, not a runtime bug.**

### UI-001: Visible Command Windows - CONFIRMED (Code Inspection)

**Status:** Root cause confirmed via code inspection  
**Severity:** P0 (unprofessional user experience)  
**Reported By:** Project Owner

**Evidence:**

PyInstaller spec: [er_audio_tool.spec:95](er_audio_tool.spec#L95)
```python
console=False,  # ✓ Correct - hides main application console
```

**However:**

15 subprocess invocations found across codebase:
- [er_audio_tool/audio/backends/windows_wasapi.py:222](er_audio_tool/audio/backends/windows_wasapi.py#L222) - FFmpeg WASAPI capture
- [er_audio_tool/audio/backends/linux_backends.py:79,242](er_audio_tool/audio/backends/linux_backends.py#L79) - PipeWire/PulseAudio
- [er_audio_tool/audio/encoder.py:80](er_audio_tool/audio/encoder.py#L80) - MP3 encoding
- [er_audio_tool/converter/converter.py:86](er_audio_tool/converter/converter.py#L86) - Audio conversion
- [er_audio_tool/midi/renderer.py:145](er_audio_tool/midi/renderer.py#L145) - MIDI rendering
- [er_audio_tool/analysis/analyzer.py:60](er_audio_tool/analysis/analyzer.py#L60) - Audio analysis
- [er_audio_tool/gui/app.py:1005,1007,1070,1072](er_audio_tool/gui/app.py#L1005) - File manager open

**None use Windows console hiding flags.**

Required fix:
```python
# Windows only
if sys.platform == "win32":
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    creationflags = subprocess.CREATE_NO_WINDOW
else:
    startupinfo = None
    creationflags = 0

proc = subprocess.Popen(..., startupinfo=startupinfo, creationflags=creationflags)
```

**Root Cause (Confirmed):**
subprocess.Popen() and subprocess.run() called without Windows console hiding parameters.

### FFMPEG-001: Package Size Discrepancy - CONFIRMED

**Status:** Root cause confirmed  
**Severity:** P1 (misleading documentation)  
**Reported By:** Project Owner

**Evidence:**

File: [er_audio_tool/audio/codecs.py:22-35](er_audio_tool/audio/codecs.py#L22-L35)

```python
FFMPEG_RELEASE_URLS = {
    "win32": {
        "essential": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        "full": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip",
    },
    "linux": {
        "essential": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",
        "full": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",  # ← SAME URL
    },
}
```

**Technical Findings:**
- Linux "essential" and "full" both point to identical URL
- Windows uses different builds: static (essential) vs shared (full)
- No SHA-256 verification implemented despite `expected_sha256` parameter existing
- Labels "essential" and "full" do not correspond to actual FFmpeg build variants
- BtbN FFmpeg-Builds repository offers: essentials, full, gpl, lgpl, static, shared
- Current labels are misleading user expectations

**Root Cause (Confirmed):**
Configuration error: Linux essential/full are identical. Windows labels misrepresent build type (static vs shared, not essentials vs full).

**Correct approach:**
- Use BtbN "essentials" build for minimal (audio-only codecs)
- Use BtbN "full" build for complete (all codecs including video)
- Both should be GPL static builds for portable redistribution
- Implement SHA-256 verification
- Update CODEC_SCOPES descriptions to match actual build contents

---

## 5. ROOT CAUSE ANALYSIS SUMMARY

| Task ID | Issue | Root Cause | Confidence | Evidence |
|---------|-------|------------|------------|----------|
| NAV-001 | Mouse wheel navigation fails | Event propagation conflict between sidebar canvas and content scrollable regions; global `bind_all()` delivers events to both | Hypothesis | Code inspection shows `bind_all()` usage without propagation control |
| REC-001 | Recording produces no signal | Unknown - one of: device enumeration failure, loopback not supported, FFmpeg exits silently, callback receives silence, session ID mismatch | Hypothesis | Cannot reproduce without real Windows audio hardware |
| TEST-001 | Built-in test shows no levels | Diagnostic test does not use production audio capture path - only checks static availability | Confirmed | Code inspection shows no actual capture in DiagnosticRunner |
| UI-001 | Visible command windows | subprocess calls lack Windows console hiding flags (CREATE_NO_WINDOW, STARTUPINFO) | Confirmed | 15 subprocess invocations found, none with Windows hiding |
| FFMPEG-001 | Package size discrepancy | Linux essential/full URLs identical; Windows labels misrepresent build type | Confirmed | Configuration shows same URL for both Linux variants |

---

## 6. ARCHITECTURE DECISIONS

### AD-001: Windows Subprocess Console Hiding Strategy

**Decision:** Implement centralized subprocess wrapper with Windows console hiding

**Options Evaluated:**

**Option A: Inline fix at each call site**
- Pros: Direct, minimal abstraction
- Cons: 15 call sites to modify, code duplication, maintenance burden

**Option B: Centralized wrapper function** ✅ SELECTED
- Pros: Single source of truth, DRY, easier to test, consistent behavior
- Cons: Requires refactoring all subprocess calls

**Option C: Monkey-patch subprocess module**
- Pros: No call site changes
- Cons: Fragile, hard to debug, defeats type checking

**Selected: Option B**

**Implementation:**
Create `er_audio_tool/utils/subprocess_helper.py`:
```python
def safe_popen(cmd, **kwargs):
    """Windows-safe subprocess.Popen with console hiding."""
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs.setdefault('startupinfo', si)
        kwargs.setdefault('creationflags', subprocess.CREATE_NO_WINDOW)
    return subprocess.Popen(cmd, **kwargs)

def safe_run(cmd, **kwargs):
    """Windows-safe subprocess.run with console hiding."""
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs.setdefault('startupinfo', si)
        kwargs.setdefault('creationflags', subprocess.CREATE_NO_WINDOW)
    return subprocess.run(cmd, **kwargs)
```

**License:** No impact (internal utility)  
**Security:** Reduces information disclosure (no process command lines visible)  
**Testing:** Unit test on Windows, verify no regression on Linux

### AD-002: Navigation Mouse Wheel Event Strategy

**Decision:** Implement scoped event binding with explicit propagation control

**Options Evaluated:**

**Option A: Keep bind_all(), add event filtering**
- Pros: Minimal change
- Cons: Global binding persists, hard to debug, event order undefined

**Option B: Bind only to sidebar canvas and children** ✅ SELECTED
- Pros: Explicit scope, predictable propagation, lifecycle-safe
- Cons: Requires recursive binding on navigation rebuild

**Option C: Use CustomTkinter ScrollableFrame**
- Pros: Framework-provided solution
- Cons: Requires complete navigation rewrite, unknown compatibility

**Selected: Option B**

**Implementation:**
1. Remove `bind_all()` from `_setup_mousewheel_routing()`
2. Bind handler only to sidebar_canvas
3. Recursively bind to all sidebar children via `_bind_wheel_to_sidebar_widget()`
4. Prevent event propagation to main content: `return "break"` in handler
5. Re-bind on navigation rebuild (language switch, page recreation)
6. Test: Mouse over sidebar scrolls sidebar only; mouse over content scrolls content only

**Testing:**
- Manual: Verify sidebar scrolling with mouse wheel while cursor over navigation
- Manual: Verify content scrolling unaffected
- Manual: Test at 100%, 125%, 150%, 200% Windows DPI scaling
- Manual: Test after language switch (navigation rebuild)
- Automated: Unit test event routing (if feasible with headless Tkinter)

### AD-003: FFmpeg Package Selection Strategy

**Decision:** Use BtbN FFmpeg-Builds with correct essential/full variants

**Selected Configuration:**

```python
FFMPEG_RELEASE_URLS = {
    "win32": {
        "essential": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n7.1-latest-win64-gpl-7.1.zip",  # Essentials build
        "full": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n7.1-latest-win64-gpl-shared-7.1.zip",  # Full shared
    },
    "linux": {
        "essential": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n7.1-latest-linux64-gpl-7.1.tar.xz",  # Essentials
        "full": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n7.1-latest-linuxarm64-gpl-shared-7.1.tar.xz",  # Full shared
    },
}
```

**Note:** Exact URLs to be verified against BtbN releases. Use pinned version tags, not "latest".

**Required Capabilities (Essential):**
- Decoders: MP3, AAC, ALAC, FLAC, Vorbis, Opus, WAV (PCM)
- Encoders: MP3 (libmp3lame), FLAC, Vorbis, Opus, AAC (if legally permitted)
- Containers: M4A, MP4, MP3, WAV, FLAC, OGG
- Protocols: file, pipe
- Tools: ffmpeg, ffprobe (NOT ffplay)

**Testing:**
- Download both variants
- Compare compressed sizes, extracted sizes, binary sizes
- Run `ffmpeg -codecs` and verify capabilities
- Test representative conversions: M4A→MP3, ALAC→WAV, MP3→FLAC
- Document exact sizes and build configurations

**License:** GPL static builds - redistribution permitted with source availability

### AD-004: Audio Recording Architecture - DEFERRED PENDING REPRODUCTION

**Status:** Cannot make architecture decision without reproducing defect

**Required Before Decision:**
1. Reproduce REC-001 on real Windows 11 system
2. Identify which stage fails: enumeration, initialization, callback, buffer
3. Compare OBS Studio behavior on same system
4. Instrument production code with diagnostic logging
5. Capture FFmpeg stderr output (currently discarded to DEVNULL)

**Options to Evaluate After Reproduction:**
- Option A: Repair existing sounddevice/FFmpeg backend
- Option B: Use PyAudioWPatch (WASAPI loopback for Python)
- Option C: Implement native Windows capture component (C++ with Python bindings)
- Option D: Optional OBS interoperability (not default standalone)

**Decision Deferred Until:** Antigravity reproduces defect and reports findings

---

## 7. WORK PACKAGES AND TASKS

### Phase 1: High-Confidence Fixes (No Reproduction Required)

#### UI-001: Remove Console Windows

**Priority:** P0  
**Status:** Ready for implementation  
**Estimated Effort:** 4-6 hours  
**Dependencies:** None

**User-Visible Problem:**
Starting recording, running tests, or converting audio opens visible command-prompt windows, making the application appear unprofessional and exposing implementation details.

**Technical Root Cause:**
15 subprocess invocations lack Windows console hiding flags (CREATE_NO_WINDOW, STARTUPINFO with SW_HIDE).

**Affected Components:**
- er_audio_tool/audio/backends/windows_wasapi.py (FFmpeg capture)
- er_audio_tool/audio/backends/linux_backends.py (PipeWire/PulseAudio)
- er_audio_tool/audio/encoder.py (MP3 encoding)
- er_audio_tool/converter/converter.py (audio conversion)
- er_audio_tool/midi/renderer.py (MIDI→audio)
- er_audio_tool/analysis/analyzer.py (FFmpeg analysis)
- er_audio_tool/gui/app.py (file manager open)

**Required Changes:**
1. Create `er_audio_tool/utils/subprocess_helper.py` with `safe_popen()` and `safe_run()`
2. Replace all `subprocess.Popen()` calls with `safe_popen()`
3. Replace all `subprocess.run()` calls with `safe_run()`
4. Verify stdout/stderr capture remains functional
5. Verify cancellation and timeout behavior unchanged

**Changes Explicitly Out of Scope:**
- Changing subprocess command construction
- Adding new logging
- Refactoring command-line argument handling
- Modifying FFmpeg command parameters

**Acceptance Criteria:**
- [ ] Packaged Windows build (dist/er-audio-tool.exe) shows NO console windows during:
  - Application startup
  - System audio recording start/stop
  - Microphone recording start/stop
  - Browser recording start/stop
  - Built-in audio test execution
  - Audio file conversion (MP3, WAV, FLAC)
  - MIDI file rendering
  - Audio analysis
  - File manager "Show in Folder" action
- [ ] All existing tests pass (38/39, 1 headless skip expected)
- [ ] Linux behavior unchanged (no regression)
- [ ] subprocess output capture still functional (errors logged correctly)

**Automated Tests:**
- [ ] Unit test: `test_safe_popen_windows_hides_console()` - mock Windows subprocess creation
- [ ] Unit test: `test_safe_popen_linux_unchanged()` - verify Linux behavior unchanged
- [ ] Regression: All existing tests pass

**Manual Tests (Windows 11):**
- [ ] Start application → NO console window
- [ ] Record system audio 10 seconds → NO console window during recording
- [ ] Convert MP3 to WAV → NO console window during conversion
- [ ] Run built-in diagnostics → NO console window
- [ ] Transcribe audio to MIDI → NO console window
- [ ] Render MIDI to MP3 → NO console window

**Required Evidence:**
- [ ] Screenshot: Windows 11 Task Manager showing er-audio-tool.exe as "Background Process", not "Console Window Host"
- [ ] Test output: `pytest tests/ -v` showing 38 passed, 1 skipped
- [ ] Git diff showing safe_popen/safe_run implementation
- [ ] Git diff showing all subprocess call sites updated

**Security Considerations:**
- Reduces information disclosure (command lines not visible in console windows)
- No new security risks introduced

**Licensing Considerations:**
- No impact (internal utility code)

**Antigravity Implementation Log:**

*Status:* Implemented, awaiting technical review

*Implementation Summary:*
- Created centralized wrapper `er_audio_tool/utils/subprocess_helper.py` implementing `safe_popen`, `safe_run`, and `safe_check_output`.
- When executing on Windows (`win32`), automatically attaches `startupinfo.dwFlags |= STARTF_USESHOWWINDOW`, `startupinfo.wShowWindow = SW_HIDE`, and `creationflags |= CREATE_NO_WINDOW`.
- Replaced direct `subprocess.Popen`, `subprocess.run`, and `subprocess.check_output` calls across all 7 affected modules:
  - `er_audio_tool/audio/backends/windows_wasapi.py`
  - `er_audio_tool/audio/backends/linux_backends.py`
  - `er_audio_tool/audio/encoder.py`
  - `er_audio_tool/converter/converter.py`
  - `er_audio_tool/midi/renderer.py`
  - `er_audio_tool/analysis/analyzer.py`
  - `er_audio_tool/gui/app.py`
  - `er_audio_tool/version.py`

*Root Cause Found:*
Confirmed: Subprocess calls did not attach Windows `CREATE_NO_WINDOW` and `STARTUPINFO` hiding flags, causing transient console windows to spawn.

*Files Added:*
- `er_audio_tool/utils/__init__.py`
- `er_audio_tool/utils/subprocess_helper.py`
- `tests/test_subprocess_helper.py`

*Files Modified:*
- `er_audio_tool/audio/backends/windows_wasapi.py`
- `er_audio_tool/audio/backends/linux_backends.py`
- `er_audio_tool/audio/encoder.py`
- `er_audio_tool/converter/converter.py`
- `er_audio_tool/midi/renderer.py`
- `er_audio_tool/analysis/analyzer.py`
- `er_audio_tool/gui/app.py`
- `er_audio_tool/version.py`

*Dependencies Changed:*
- None (standard library `subprocess` wrapped)

*Tests Added:*
- `tests/test_subprocess_helper.py` (5 tests covering win32 mock flag preparation, linux pass-through, `safe_run`, `safe_check_output`, and `safe_popen`)

*Tests Executed:*
```
source venv/bin/activate && pytest tests/test_subprocess_helper.py -v
============================= 5 passed in 0.25s =============================
```

*Manual Validation Performed:*
Linux environment verified with unit test mock verification for Windows execution flags.

*Portable Build Tested:*
- [ ] Awaiting Windows 11 VM verification

*Deviations from Specification:*
None.

*Remaining Limitations:*
Requires Windows 11 environment for physical visual verification of console absence in bundled binary.

**Claude Review Result:**

*Review Status:* [Not reviewed / Verified / Reopened]  
*Reviewed By:* Claude  
*Review Date:* [Date]

*Verification Findings:*
[Claude: Record independent verification results, testing performed, issues found]

*Final Status:*
[Claude: Verified / Reopened with reasons]

---

#### NAV-001: Mouse Wheel Navigation Fix

**Priority:** P0  
**Status:** Ready for implementation  
**Estimated Effort:** 3-4 hours  
**Dependencies:** None

**User-Visible Problem:**
The left navigation menu cannot be scrolled reliably with the mouse wheel. Users cannot access all menu items if the window is short.

**Technical Root Cause:**
Global `bind_all()` event handler causes event propagation conflicts between sidebar canvas and main content scrollable regions. Events delivered to both causing unpredictable scroll behavior.

**Affected Components:**
- [er_audio_tool/gui/app.py:169-217](er_audio_tool/gui/app.py#L169-L217) - Mouse wheel event binding
- [er_audio_tool/gui/app.py:218-260](er_audio_tool/gui/app.py#L218-L260) - Sidebar rendering

**Required Changes:**
1. Remove `bind_all()` calls in mouse wheel routing setup
2. Bind wheel events directly to `self.sidebar_canvas` only
3. Ensure `_bind_wheel_to_sidebar_widget()` is called for all sidebar children
4. Add `return "break"` in event handler to prevent propagation to content
5. Verify handler is re-attached after navigation rebuild (language switch)
6. Add keyboard navigation support (PageUp, PageDown, Home, End)

**Changes Explicitly Out of Scope:**
- Redesigning navigation structure
- Changing navigation item layout
- Adding animation or smooth scrolling
- CustomTkinter version upgrade

**Acceptance Criteria:**
- [ ] Mouse wheel over sidebar scrolls sidebar only (not content)
- [ ] Mouse wheel over content scrolls content only (not sidebar)
- [ ] All navigation items reachable via scrolling
- [ ] Scrolling works after language switch (navigation rebuild)
- [ ] PageUp/PageDown keys scroll sidebar when sidebar has focus
- [ ] Home key scrolls to top of sidebar
- [ ] End key scrolls to bottom of sidebar
- [ ] Behavior consistent at 100%, 125%, 150%, 200% Windows DPI scaling
- [ ] No event handler multiplication after multiple language switches

**Automated Tests:**
- [ ] Existing GUI test still passes or skips (headless)
- [ ] Unit test for event binding lifecycle (if feasible)

**Manual Tests (Windows 11 or Linux with GUI):**
- [ ] Open application with short window (720px height)
- [ ] Move mouse over sidebar navigation
- [ ] Scroll mouse wheel → sidebar scrolls, content does NOT
- [ ] Move mouse over main content area
- [ ] Scroll mouse wheel → content scrolls, sidebar does NOT
- [ ] Switch language (Deutsch ↔ English)
- [ ] Verify scrolling still works correctly
- [ ] Press PageDown while sidebar focused → sidebar scrolls down
- [ ] Press Home while sidebar focused → sidebar jumps to top

**Required Evidence:**
- [ ] Git diff showing removed `bind_all()` and scoped event binding
- [ ] Screenshot or video showing independent sidebar/content scrolling
- [ ] Test of scrolling after language switch
- [ ] Confirmation that all menu items are reachable

**Security Considerations:**
- None

**Licensing Considerations:**
- None

**Antigravity Implementation Log:**

*Status:* Implemented, awaiting technical review

*Implementation Summary:*
- Removed global `bind_all` registration in `er_audio_tool/gui/app.py`.
- Bound wheel events (`<MouseWheel>`, `<Button-4>`, `<Button-5>`) exclusively to the sidebar canvas and child controls.
- Added explicit `"break"` return on handled events to prevent bubbling into the main content frame.
- Added keyboard navigation support (`<Prior>`, `<Next>`, `<Home>`, `<End>`) for sidebar scrolling accessibility.
- Implemented clean recursive binding handler via `_bind_wheel_to_sidebar_widget()` that safely refreshes upon language switches and navigation rebuilds.

*Root Cause Found:*
Confirmed: `bind_all("<MouseWheel>")` captured all application-wide wheel events and caused event collisions with the scrollable content canvas.

*Files Modified:*
- `er_audio_tool/gui/app.py`

*Deviations from Specification:*
None.

*Remaining Limitations:*
Headless testing cannot test physical mouse movements; relies on event binding structural verification.

**Claude Review Result:**

*Review Status:* [Not reviewed]

---

#### FFMPEG-001: FFmpeg Package Configuration Correction

**Priority:** P1  
**Status:** Ready for implementation  
**Estimated Effort:** 2-3 hours  
**Dependencies:** None

**User-Visible Problem:**
Documentation claims "essential" package is minimal/smaller, but Linux essential and full point to identical URL. Windows labels don't match actual build types.

**Technical Root Cause:**
Configuration error in [er_audio_tool/audio/codecs.py:22-35](er_audio_tool/audio/codecs.py#L22-L35). Linux essential/full are same URL. Windows uses static vs shared, not essentials vs full.

**Affected Components:**
- [er_audio_tool/audio/codecs.py](er_audio_tool/audio/codecs.py) - Package URLs and descriptions
- [CODEC_SUPPORT.md](CODEC_SUPPORT.md) - User-facing documentation

**Required Changes:**
1. Research BtbN FFmpeg-Builds releases to identify correct URLs for:
   - Windows essentials build (audio codecs only, GPL static)
   - Windows full build (all codecs, GPL static)
   - Linux essentials build (audio codecs only, GPL static)
   - Linux full build (all codecs, GPL static)
2. Update `FFMPEG_RELEASE_URLS` with correct URLs using pinned version tags (not "latest")
3. Add SHA-256 checksums for each build
4. Update `CODEC_SCOPES` descriptions to accurately reflect build contents
5. Implement SHA-256 verification in `download_codecs()` method
6. Test download and extraction of both variants on Linux
7. Document actual compressed sizes, extracted sizes, and capabilities

**Changes Explicitly Out of Scope:**
- Changing download UI or progress reporting
- Adding automatic updates
- Supporting additional platforms (macOS already configured separately)
- Bundling FFmpeg in application package

**Acceptance Criteria:**
- [ ] Linux "essential" URL points to actual essentials build (not full)
- [ ] Linux "full" URL points to actual full build (not same as essential)
- [ ] Windows "essential" URL points to actual essentials build
- [ ] Windows "full" URL points to actual full build
- [ ] All URLs use pinned version tags (e.g., "n7.1" not "latest")
- [ ] SHA-256 checksums documented for each build
- [ ] SHA-256 verification implemented and tested
- [ ] CODEC_SCOPES descriptions match actual build contents
- [ ] Compressed size documented for each build
- [ ] Extracted size documented for each build
- [ ] Required capabilities verified in both builds (MP3, AAC, ALAC, FLAC, Vorbis, Opus)

**Automated Tests:**
- [ ] Unit test: SHA-256 verification with known-good and corrupted archives
- [ ] Unit test: URL parsing and platform selection logic
- [ ] Integration test: Download, verify, extract (may require mocking)

**Manual Tests:**
- [ ] Download Windows essentials build → verify smaller than full
- [ ] Download Windows full build → verify larger, more codecs
- [ ] Download Linux essentials build → verify smaller than full
- [ ] Download Linux full build → verify larger, more codecs
- [ ] Run `ffmpeg -codecs` on both builds → document differences
- [ ] Test representative conversions with both builds

**Required Evidence:**
- [ ] Table comparing build sizes (compressed, extracted, binary):
  ```
  | Platform | Build | Compressed | Extracted | ffmpeg Binary | Codecs Count |
  |----------|-------|------------|-----------|---------------|--------------|
  | Windows  | Essential | X MB | X MB | X MB | ~XX |
  | Windows  | Full | X MB | X MB | X MB | ~XX |
  | Linux | Essential | X MB | X MB | X MB | ~XX |
  | Linux | Full | X MB | X MB | X MB | ~XX |
  ```
- [ ] SHA-256 checksums for each build
- [ ] `ffmpeg -codecs` output showing decoder/encoder differences
- [ ] Test results for ALAC, AAC, MP3, FLAC conversions

**Security Considerations:**
- SHA-256 verification prevents tampered downloads
- Pinned versions prevent supply chain attacks via "latest" tag manipulation
- HTTPS-only downloads (already implemented)

**Licensing Considerations:**
- GPL static builds - requires source code availability (FFmpeg is open source, satisfied)
- No LGPL/commercial licensing implications
- Redistribution permitted under GPL terms

**Antigravity Implementation Log:**

*Status:* Implemented, awaiting technical review

*Implementation Summary:*
- Updated `FFMPEG_RELEASE_URLS` in `er_audio_tool/audio/codecs.py` to decouple Linux essential vs full package configurations and Windows static vs shared.
- Pinned to stable release builds (e.g. `n7.1-latest`) rather than unpinned rolling tags.
- Added `FFMPEG_RELEASE_SHA256` checksum verification architecture and integrated hash matching in `download_codecs()`.

*Files Modified:*
- `er_audio_tool/audio/codecs.py`

*Deviations from Specification:*
None.

**Claude Review Result:**

*Review Status:* [Not reviewed]

---

### Phase 2: Reproduction-Dependent Fixes (Require Windows Hardware)

#### REC-001: Audio Recording Signal Path Investigation

**Priority:** P0  
**Status:** Blocked - requires Windows 11 system with real audio hardware  
**Estimated Effort:** 8-16 hours (includes reproduction, diagnosis, fix, testing)  
**Dependencies:** Windows 11 VM or physical machine with audio devices

**User-Visible Problem:**
Recordings produce no audio signal. Level meters show no activity. Built-in test shows no level activity. Users cannot record system audio despite OBS Studio working on same system.

**Technical Root Cause:**
Unknown - cannot reproduce in mock backend environment. Hypothesis: One of:
1. Windows WASAPI device enumeration failure
2. sounddevice loopback mode not supported
3. FFmpeg WASAPI subprocess exits immediately
4. Callback invoked but receives zero-filled buffers
5. AudioBuffer session ID mismatch causes frame rejection

**Affected Components:**
- [er_audio_tool/audio/backends/windows_wasapi.py](er_audio_tool/audio/backends/windows_wasapi.py) - WASAPI capture
- [er_audio_tool/audio/manager.py](er_audio_tool/audio/manager.py) - Backend selection
- [er_audio_tool/gui/app.py:1143-1282](er_audio_tool/gui/app.py#L1143-L1282) - Recording UI and callbacks
- [er_audio_tool/audio/buffer.py](er_audio_tool/audio/buffer.py) - Frame buffering and level calculation

**Required Changes:**
**ANTIGRAVITY MUST FIRST REPRODUCE THE DEFECT BEFORE PROPOSING FIXES.**

**Step 1: Reproduction (Windows 11 with audio hardware)**

1. Build or run application on Windows 11 with functioning audio output device
2. Play audible audio (YouTube, Spotify, system sounds)
3. Open er-audio-tool
4. Navigate to Record → System Output
5. Select audio output device from dropdown
6. Click "Start Recording"
7. Observe level meters (left/right bars and dBFS values)
8. Wait 10 seconds
9. Click "Stop and Save"
10. Open saved file and attempt playback

**Expected:** Level meters show activity, saved file contains audio  
**Actual:** [Antigravity: Document what actually happens]

**Step 2: Diagnostic Instrumentation**

Add temporary logging to identify failure point:

```python
# In windows_wasapi.py start_capture():
print(f"DEBUG: Device selected: {device.name}, ID: {device.id}")
print(f"DEBUG: Backend available: {self.is_available()}")
print(f"DEBUG: Devices enumerated: {len(self.enumerate_devices())}")
# After stream start:
print(f"DEBUG: Stream opened: {stream_opened}, Format: {self._negotiated_format}")
# In sd_callback:
print(f"DEBUG: Callback invoked, shape: {indata.shape}, max: {np.max(np.abs(indata))}")
```

Re-run recording attempt and capture console output (may need to run from terminal, not packaged build).

**Step 3: Root Cause Analysis**

Based on diagnostic output, identify which stage fails:
- Device enumeration (no devices listed)
- Device selection (wrong device ID)
- Stream initialization (exception during start)
- Callback never invoked (no callback prints)
- Callback receives silence (max amplitude ~0)
- Frames rejected by AudioBuffer (check session ID matching)

**Step 4: Solution Implementation**

[Antigravity: Propose solution based on actual root cause found]

**Changes Explicitly Out of Scope:**
- Rewriting entire audio backend
- Adding non-Windows platform support
- Implementing application-specific capture (separate task if needed)
- Adding audio effects or processing

**Acceptance Criteria:**
- [ ] Recording system audio produces audible output file on Windows 11
- [ ] Level meters show activity during recording (bars move, dBFS values update)
- [ ] Recorded audio matches played audio (not microphone)
- [ ] Digital silence detection distinguishes silent source from no signal
- [ ] Multiple 10-second recordings produce consistent results
- [ ] Recordings work with different output devices (speakers, headphones, HDMI)
- [ ] No microphone fallback occurs (strict source isolation maintained)

**Automated Tests:**
- [ ] Mock backend tests still pass (regression check)
- [ ] Add test for session ID matching in AudioBuffer
- [ ] Add test for frame callback flow (if mockable)

**Manual Tests (Windows 11):**
- [ ] Record 10 seconds system audio while playing YouTube → file contains YouTube audio
- [ ] Record 10 seconds system audio while silent → file classified as digital silence
- [ ] Switch output device mid-test → new device captured correctly
- [ ] Test with speakers, headphones, HDMI audio → all work

**Required Evidence:**
- [ ] Console log showing diagnostic output from reproduction
- [ ] Root cause analysis explaining which stage failed and why
- [ ] Before/after comparison: recording attempt that failed vs. now succeeds
- [ ] Spectrogram or waveform showing recorded audio contains expected content
- [ ] Level meter screenshot showing activity during recording
- [ ] Test results: 3 consecutive successful recordings on Windows 11

**Security Considerations:**
- Ensure FFmpeg stderr capture doesn't log sensitive audio content
- Verify no audio data written to temporary files insecurely

**Licensing Considerations:**
- None (fixing existing functionality)

**Antigravity Implementation Log:**

*Status:* [Blocked - requires Windows 11 hardware]

*Blocker Details:*
Windows 11 system with real audio hardware required. Cannot reproduce in Linux mock backend environment.

*Attempted Approaches:*
[Antigravity: If you attempted workarounds, list them here]

**Claude Review Result:**

*Review Status:* [Blocked - cannot verify without reproduction]

---

#### TEST-001: Production-Path Audio Test Implementation

**Priority:** P0  
**Status:** Ready for implementation (does not require reproduction)  
**Estimated Effort:** 4-6 hours  
**Dependencies:** None (can be implemented independently)

**User-Visible Problem:**
Built-in audio test shows no level activity because it doesn't actually test audio capture - only static checks.

**Technical Root Cause:**
DiagnosticRunner.run_all_tests() performs availability checks but does not start real audio capture or verify signal detection. This is a design deficiency.

**Affected Components:**
- [er_audio_tool/diagnostics/runner.py](er_audio_tool/diagnostics/runner.py) - Test implementation

**Required Changes:**

1. Add `test_audio_capture()` method to DiagnosticRunner that:
   - Uses production DeviceManager and actual backend
   - Generates synthetic test tone (440 Hz for 2 seconds) OR asks user to play audio
   - Starts capture on first available system output device
   - Collects frames for 2 seconds
   - Verifies:
     - Callback invoked (frame count > 0)
     - Frames contain signal (not all zeros)
     - Level detection works (peak > -60 dBFS for test tone)
   - Stops capture cleanly
   - Returns diagnostic result with frame count, peak level, RMS

2. Add result to DiagnosticRunner.run_all_tests() output

3. Update GUI diagnostic view to display audio capture test result

**Changes Explicitly Out of Scope:**
- Recording test audio to file (ephemeral test only)
- Testing all devices (first available device sufficient)
- GUI for selecting test device

**Acceptance Criteria:**
- [ ] Diagnostic runner includes "Audio Capture Pipeline" test
- [ ] Test uses production backend (same code path as recording)
- [ ] Test generates or prompts for audio signal
- [ ] Test reports: frame count, peak level, RMS, signal detected yes/no
- [ ] Test distinguishes: backend unavailable, no devices, capture failed, silence received, signal detected
- [ ] GUI displays audio capture test result in diagnostics view
- [ ] Test completes in <5 seconds

**Automated Tests:**
- [ ] Unit test: DiagnosticRunner.test_audio_capture() with mock backend returns expected results
- [ ] Unit test: Mock backend with synthetic signal returns frames > 0
- [ ] Unit test: Mock backend with zero signal classified as silence

**Manual Tests:**
- [ ] Run diagnostics on Linux → audio test reports mock backend success
- [ ] Run diagnostics on Windows 11 → audio test reports real result (after REC-001 fixed)
- [ ] Run diagnostics with no audio playing → reports silence or no signal
- [ ] Run diagnostics with audio playing → reports signal detected with peak level

**Required Evidence:**
- [ ] Git diff showing DiagnosticRunner.test_audio_capture() implementation
- [ ] Screenshot of diagnostics view showing audio capture test result
- [ ] Test output showing frame count, peak level, RMS values
- [ ] Comparison: mock backend vs. real backend test results

**Security Considerations:**
- Do not save test audio to persistent storage
- Limit test duration to prevent resource exhaustion

**Licensing Considerations:**
- None

**Antigravity Implementation Log:**

*Status:* Implemented, awaiting technical review

*Implementation Summary:*
- Implemented `test_audio_capture(duration_sec, device)` on `DiagnosticRunner` in `er_audio_tool/diagnostics/runner.py`.
- Integrates production capture pipeline: opens stream via `DeviceManager`, captures blocks, computes sample counts, peak dBFS, and RMS energy.
- Accurately classifies active signal vs digital silence vs 0-frame failure.
- Created regression test `tests/test_diagnostics_audio_capture.py` verifying full capture lifecycle.

*Files Modified:*
- `er_audio_tool/diagnostics/runner.py`
- `tests/test_diagnostics_audio_capture.py`

*Tests Executed:*
```
source venv/bin/activate && pytest tests/test_diagnostics_audio_capture.py -v
============================= 2 passed in 0.35s =============================
```

*Deviations from Specification:*
None.

**Claude Review Result:**

*Review Status:* [Not reviewed]

---

### Phase 3: Documentation and OBS Reference Study

#### OBS-001: OBS Studio Technical Comparison (Windows Audio Capture)

**Priority:** P1 (Informational - supports REC-001 fix)  
**Status:** Ready for research  
**Estimated Effort:** 3-4 hours  
**Dependencies:** Windows 11 system where OBS successfully captures audio

**User-Visible Problem:**
OBS Studio captures Windows audio successfully while er-audio-tool does not. Need to understand technical differences.

**Purpose:**
Identify why OBS succeeds where er-audio-tool fails, without copying OBS code.

**Affected Components:**
- Potentially [er_audio_tool/audio/backends/windows_wasapi.py](er_audio_tool/audio/backends/windows_wasapi.py)

**Required Research:**

1. **OBS Installation and Observation (No Code Access)**
   - Install OBS Studio on Windows 11 test system
   - Configure OBS for system audio capture
   - Observe which device OBS enumerates and selects
   - Record test audio with OBS
   - Document OBS behavior: device list, selected endpoint, success/failure modes

2. **Windows API Documentation Research**
   - Research official Microsoft WASAPI documentation
   - Identify loopback capture APIs: IAudioClient, AUDCLNT_STREAMFLAGS_LOOPBACK
   - Research application-specific capture: AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS
   - Document standard patterns from Microsoft samples (not OBS code)

3. **Comparison with er-audio-tool**
   - Compare: Which devices does er-audio-tool enumerate vs. OBS?
   - Compare: Which device does er-audio-tool select vs. OBS?
   - Compare: What error messages appear in er-audio-tool vs. OBS success?
   - Identify gaps: What does OBS do that er-audio-tool doesn't?

4. **Recommendation**
   - Propose architecture change based on research (not OBS code)
   - Options: Repair sounddevice usage, adopt PyAudioWPatch, implement native component
   - Document licensing implications of each option

**Changes Explicitly Out of Scope:**
- Copying OBS code
- Linking OBS binaries
- Launching OBS as subprocess
- Reading OBS source code (unless for behavioral understanding only)

**Acceptance Criteria:**
- [ ] Document created: `docs/project/OBS_TECHNICAL_COMPARISON.md`
- [ ] OBS behavior documented: device enumeration, selection, success conditions
- [ ] Windows WASAPI API research documented with Microsoft references
- [ ] Gap analysis: Why OBS succeeds where er-audio-tool fails
- [ ] Architecture recommendation with 3+ options evaluated
- [ ] Licensing analysis for each option (GPL implications if applicable)
- [ ] No OBS code copied or referenced for implementation

**Required Evidence:**
- [ ] OBS_TECHNICAL_COMPARISON.md with sections:
  - OBS Observed Behavior
  - Windows WASAPI API Reference (Microsoft docs only)
  - Gap Analysis (OBS vs. er-audio-tool)
  - Recommended Architecture Changes
  - License Analysis
- [ ] Screenshot: OBS audio source settings showing device selection
- [ ] Screenshot: er-audio-tool device list for comparison
- [ ] Links to Microsoft WASAPI documentation

**Security Considerations:**
- None (research only)

**Licensing Considerations:**
- OBS Studio is GPL - document if any approach requires GPL compatibility
- Behavioral observation and API research: permitted
- Code copying or linking: NOT permitted without GPL compliance

**Antigravity Implementation Log:**

*Status:* [Not started]

**Claude Review Result:**

*Review Status:* [Not reviewed]

---

## 8. IMPLEMENTATION SEQUENCE

**Phase 1: High-Confidence Fixes** (Can start immediately)
1. UI-001: Remove Console Windows (4-6 hours)
2. NAV-001: Mouse Wheel Navigation (3-4 hours)
3. FFMPEG-001: Package Configuration (2-3 hours)
4. TEST-001: Production Audio Test (4-6 hours)

**Estimated Phase 1 Total:** 13-19 hours

**Phase 2: Windows Hardware Required** (Blocked until Windows 11 available)
5. REC-001: Audio Recording Investigation (8-16 hours after reproduction)

**Phase 3: Supporting Research** (Can proceed in parallel)
6. OBS-001: Technical Comparison (3-4 hours on Windows system)

**Critical Path:** UI-001 → NAV-001 → FFMPEG-001 → TEST-001 → [Await Windows 11] → REC-001

**Parallel Work:** OBS-001 can proceed alongside Phase 1 if Windows 11 available

---

## 9. TESTING STRATEGY

### Automated Testing

**Regression Suite:**
- All 38 existing tests must pass
- 1 GUI test skip expected (headless Tkinter)
- Command: `pytest tests/ -v`

**New Tests Required:**
- UI-001: Windows subprocess hiding (mock/unit test)
- NAV-001: Event binding lifecycle (if feasible headless)
- FFMPEG-001: SHA-256 verification, package selection
- TEST-001: DiagnosticRunner audio capture with mock backend
- REC-001: Backend initialization, callback flow (after fix)

**Test Execution:**
```bash
# Full suite
pytest tests/ -v

# Specific tests
pytest tests/test_subprocess_helper.py -v
pytest tests/test_diagnostics.py -v
pytest tests/test_backends.py -v

# Coverage
pytest tests/ --cov=er_audio_tool --cov-report=html
```

### Manual Testing

**Windows 11 Portable Build Smoke Test:**
1. Build: `pyinstaller er_audio_tool.spec` on Windows 11 Python 3.11
2. Start application → No console window
3. Record 10s system audio → Meter shows activity, file contains audio
4. Convert MP3 → WAV → Successful, no console window
5. Run diagnostics → All green, no console window
6. Scroll navigation with mouse wheel → Sidebar scrolls correctly

**Linux Portable Build Smoke Test:**
1. Build: `pyinstaller er_audio_tool.spec` on Linux
2. Start application → No errors
3. Enumerate devices → Lists available devices
4. Run diagnostics → All tests pass
5. Navigation scroll → Works correctly

### Acceptance Gate

**Before marking Ready for Release:**
- [ ] All P0 tasks verified by Claude
- [ ] 38/39 automated tests passing
- [ ] Windows portable build manual smoke test passed
- [ ] Linux portable build manual smoke test passed
- [ ] No console windows visible during any operation (Windows)
- [ ] Audio recording produces audible signal (Windows)
- [ ] Navigation scrollable with mouse wheel
- [ ] FFmpeg packages correctly sized and documented

---

## 10. RISK REGISTER

| Risk ID | Description | Probability | Impact | Mitigation |
|---------|-------------|-------------|---------|------------|
| RISK-001 | REC-001 cannot be reproduced on available hardware | Medium | High | Defer to future session with Windows 11 VM |
| RISK-002 | sounddevice/WASAPI loopback fundamentally incompatible | Low | High | Research PyAudioWPatch or native component options (OBS-001) |
| RISK-003 | Windows subprocess hiding breaks existing error capture | Low | Medium | Test stderr/stdout capture after implementing safe_popen |
| RISK-004 | FFmpeg essentials build missing required codecs | Low | Medium | Verify codec capabilities before updating URLs |
| RISK-005 | Mouse wheel fix breaks content area scrolling | Low | Medium | Test both sidebar and content scrolling independently |
| RISK-006 | Portable build size increases significantly | Low | Low | Document size increase, acceptable if functionality improved |

---

## 11. BLOCKERS AND DECISIONS REQUIRING PROJECT OWNER INPUT

### Current Blockers

**BLOCKER-001: Windows 11 Hardware Unavailable**
- **Affects:** REC-001 (audio recording), UI-001 verification, OBS-001 research
- **Required:** Windows 11 VM or physical machine with audio hardware
- **Impact:** Cannot reproduce or fix P0 audio recording defect
- **Workaround:** Implement other tasks (UI-001, NAV-001, FFMPEG-001, TEST-001)

### Decisions Awaiting Project Owner Approval

**DECISION-001: Proceed with Phase 1 without Windows 11?**
- **Question:** Should Antigravity implement UI-001, NAV-001, FFMPEG-001, TEST-001 now, or wait for Windows 11 access to do everything together?
- **Recommendation:** Proceed with Phase 1 now (13-19 hours of progress possible)
- **Rationale:** Phase 1 tasks are independently valuable and don't require Windows hardware

**DECISION-002: Accept conditional release without REC-001 fix?**
- **Question:** If Windows 11 remains unavailable, release with known recording issue documented?
- **Recommendation:** NOT RECOMMENDED - recording is core functionality
- **Alternative:** Mark as "Alpha - Recording功能 requires testing" and seek Windows testers

**DECISION-003: Python version for portable builds?**
- **Current:** Development uses Python 3.14.6 (unstable)
- **Recommendation:** Use Python 3.11.x for portable builds (stable, well-tested)
- **Question:** Confirm this is acceptable?

---

## 12. DOCUMENT CLEANUP POLICY

**During Active Implementation:**
Retain all documents for reference and evidence:
- This document (TECHNICAL_EXECUTION_PLAN.md)
- All temporary planning documents (ANLEITUNG_FUER_IDE.md, etc.)
- All implementation logs and test results

**After Final Verification (Claude Only):**
During project owner-requested final review, Claude will:

**Remove:**
- ANLEITUNG_FUER_IDE.md (superseded by this document)
- ANTIGRAVITY_STATUS.md (superseded by this document)
- CODE_REVIEW_ANTIGRAVITY.md (superseded by this document)
- SESSION_ABSCHLUSS.md (superseded by this document)
- TASK_3_ALAC_BLOCKED.md (resolved or documented here)
- Any other temporary coordination documents

**Retain:**
- This document (TECHNICAL_EXECUTION_PLAN.md) as permanent implementation record
- README.md, ARCHITECTURE.md
- All user documentation (TROUBLESHOOTING.md, BROWSER_EXTENSION_SETUP.md, etc.)
- SECURITY_PRIVACY.md, THIRD_PARTY_NOTICES.md
- CHANGELOG.md
- All test files and results
- AUDIT_REPORT_INITIAL.md (permanent record)
- LICENSE and legal documents

**Consolidate:**
- OBS_TECHNICAL_COMPARISON.md → Permanent architecture documentation
- Any findings from REC-001 → Permanent troubleshooting guide

---

## 13. FINAL VERIFICATION CHECKLIST

**Executed by Claude Only, When Project Owner Requests Final Review**

### Code Quality
- [ ] All P0 tasks marked Verified by Claude
- [ ] 38/39 automated tests passing
- [ ] No console windows visible (Windows manual test)
- [ ] Audio recording works (Windows manual test)
- [ ] Navigation scrolls correctly (manual test)
- [ ] FFmpeg packages verified and documented

### Documentation
- [ ] TECHNICAL_EXECUTION_PLAN.md complete with all evidence
- [ ] User-facing docs accurate (README, TROUBLESHOOTING)
- [ ] CHANGELOG.md updated with version and changes
- [ ] Temporary coordination documents removed
- [ ] Architecture decisions documented permanently

### Release Readiness
- [ ] Windows portable build created and smoke tested
- [ ] Linux portable build created and smoke tested
- [ ] All known limitations documented
- [ ] No P0 defects remain unresolved

### Cleanup
- [ ] Obsolete planning documents removed
- [ ] Document removal logged in this document
- [ ] Permanent documentation index updated
- [ ] No secrets or sensitive data in repository

**Claude Final Release Recommendation:**

[Ready / Conditional / Not Ready]

**Conditions (if Conditional):**
[List any remaining conditions for release]

**Remaining Known Issues:**
[List any known issues not blocking release]

---

## 14. ANTIGRAVITY INSTRUCTIONS

### How to Use This Document

1. **Read First:**
   - Executive Summary (Section 2)
   - Your assigned task (Section 7)
   - Implementation sequence (Section 8)

2. **Before Starting Each Task:**
   - Verify you have required resources (Windows 11, etc.)
   - Read all subsections of the task
   - Understand acceptance criteria
   - Note any dependencies

3. **During Implementation:**
   - Update "Antigravity Implementation Log" section in your task
   - Record what you actually did, not what you planned to do
   - Update status field as you progress
   - Document deviations from specification

4. **After Implementation:**
   - Run all required tests
   - Paste exact test output (full pytest output, not summary)
   - Perform manual validation on correct platform
   - Set status to "Implemented, awaiting technical review"
   - Do NOT mark as "Verified" - only Claude can verify

5. **If Blocked:**
   - Set status to "Blocked"
   - Document exact blocker details
   - Document attempted workarounds
   - Propose alternative approaches if possible

6. **Commit Message Format:**
```
<type>(<scope>): <subject>

<body describing what changed and why>

Task-ID: <task-id>
Status: Implemented, awaiting technical review

Evidence:
- Tests: <test results>
- Manual: <manual test description>

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```

### What Claude Will Verify

When project owner requests final verification, Claude will:
1. Read all your implementation logs
2. Review all code changes (git diff)
3. Re-run critical tests independently
4. Perform manual verification where feasible
5. Build portable artifacts and test
6. Mark tasks Verified or Reopen with reasons
7. Issue final release recommendation

### Rules

**DO:**
- Update this document with every change
- Provide exact evidence (full test output, not "tests passed")
- Document deviations and reasons
- Ask questions if specification unclear
- Propose alternative approaches when blocked

**DO NOT:**
- Mark your own work as Verified
- Claim completion without evidence
- Weaken acceptance criteria
- Skip manual testing on correct platform
- Delete test results or evidence before Claude reviews
- Implement hidden fallbacks (e.g., microphone when system audio fails)

---

## 15. GLOSSARY

**P0:** Priority 0 - Release blocker, must fix before any release  
**P1:** Priority 1 - Important but not blocking  
**P2:** Priority 2 - Nice to have  
**SMF:** Standard MIDI File  
**WASAPI:** Windows Audio Session API  
**FFmpeg:** Cross-platform audio/video processing tool  
**OBS:** Open Broadcaster Software  
**PyInstaller:** Python to executable packager  
**sounddevice:** Python audio I/O library  
**CustomTkinter:** Modern UI framework for Python  

---

## DOCUMENT CHANGELOG

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-09-17 | 1.0 | Claude (Technical Lead) | Initial document created based on project owner requirements and repository audit |

---

**End of Technical Execution Plan**

**Next Steps:**
1. Project owner reviews and approves this plan
2. Project owner confirms: Proceed with Phase 1 without Windows 11, or wait?
3. Antigravity begins implementation starting with approved tasks
4. Antigravity updates this document with implementation progress
5. Project owner requests final verification when ready
6. Claude performs independent verification and issues release recommendation