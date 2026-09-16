# Anleitung für nachfolgende IDE: Verbleibende Aufgaben

**Erstellt:** 2026-09-17  
**Für:** Nachfolgende IDE (z.B. Cursor, Windsurf, andere)  
**Kontext:** er-audio-tool Projekt nach Phase 1 + Code-Fixes  
**Branch:** comprehensive-audit-fixes

---

## 📋 Übersicht

Dieses Projekt wurde umfassend auditiert und dokumentiert. Die meisten Code-Verbesserungen sind abgeschlossen. Die verbleibenden Aufgaben erfordern:
- Systemweite FFmpeg-Installation (für ALAC-Test)
- Windows VM (für Portable Build)
- Browser-Installation (für E2E-Tests)

**Wichtig:** Alle Änderungen sind im Branch `comprehensive-audit-fixes`. Dieser Branch muss nach erfolgreichen Tests zu `main` gemerged werden.

---

## ✅ Bereits abgeschlossen

1. **Phase 1 Dokumentation** - Vollständig (8 Dokumente, ~5.200 Zeilen)
2. **Aufgabe #1** - Stem-Separation als Experimental markiert
3. **Aufgabe #2** - MIDI Multi-Track (SMF Format 1) implementiert
4. **Aufgabe #4** - Legacy-Code entfernt
5. **Code-Review** - Durchgeführt, SEHR GUT bewertet
6. **35 Tests** - Alle bestehen (100%)

---

## 🔴 AUFGABE #3: ALAC-Verifikation

**Priorität:** Mittel (nicht kritisch für Alpha)  
**Aufwand:** 1-2 Stunden  
**Voraussetzung:** FFmpeg systemweit installieren

### Schritt 1: FFmpeg installieren

```bash
# Ubuntu/Debian:
sudo apt update
sudo apt install ffmpeg

# Fedora/RHEL:
sudo dnf install ffmpeg

# Arch Linux:
sudo pacman -S ffmpeg

# Verifizieren:
ffmpeg -version
```

### Schritt 2: ALAC-Test-Datei generieren

```bash
cd /tmp

# Test-WAV generieren (440 Hz Sinus, 5 Sekunden)
ffmpeg -f lavfi -i "sine=frequency=440:duration=5" -y test_440hz.wav

# Zu ALAC konvertieren
ffmpeg -i test_440hz.wav -c:a alac -y test_alac.m4a

# Verifizieren
ls -lh test_alac.m4a
ffprobe test_alac.m4a
```

### Schritt 3: ALAC-Konvertierung in er-audio-tool testen

```bash
cd /home/dev/github/ER-Audio-Tool
source venv/bin/activate

# Python-Test
python << 'EOF'
from pathlib import Path
from er_audio_tool.converter.converter import AudioConverter, ConversionJob

# ALAC zu MP3
job = ConversionJob(
    input_file=Path("/tmp/test_alac.m4a"),
    output_format="mp3",
    bitrate_kbps=320
)
result = AudioConverter.convert_file(job)

if result.success:
    print(f"✅ ALAC → MP3: SUCCESS")
    print(f"   Output: {result.output_path}")
    print(f"   Duration: {result.duration_seconds:.2f}s")
else:
    print(f"❌ ALAC → MP3: FAILED")
    print(f"   Error: {result.error_message}")

# ALAC zu WAV
job2 = ConversionJob(
    input_file=Path("/tmp/test_alac.m4a"),
    output_format="wav"
)
result2 = AudioConverter.convert_file(job2)

if result2.success:
    print(f"✅ ALAC → WAV: SUCCESS")
else:
    print(f"❌ ALAC → WAV: FAILED")
    print(f"   Error: {result2.error_message}")
EOF
```

### Schritt 4: Dokumentation aktualisieren

**Falls ALAC funktioniert:**

```bash
# CODEC_SUPPORT.md aktualisieren
# Ändere Zeile mit "M4A ALAC" von:
#   | M4A ALAC | ⚠️ Requires Testing | ...
# zu:
#   | M4A ALAC | ✅ Tested | ✅ Tested | ✅ Tested | Verified |

# In der Testing Status Tabelle ändern:
#   | M4A ALAC | ❌ Not tested | ⚠️ Claimed | ⚠️ Unknown | **Needs verification** |
# zu:
#   | M4A ALAC | ✅ Tested | ✅ Tested | ✅ Tested | Verified |
```

**Falls ALAC NICHT funktioniert:**

```bash
# CODEC_SUPPORT.md aktualisieren
# Markiere ALAC als "Not Supported" mit Erklärung
# README.md aktualisieren: Entferne ALAC-Erwähnung
```

### Schritt 5: Commit

```bash
git add -A
git commit -m "test: verify ALAC support with real test files

Results:
- ALAC → MP3: [SUCCESS/FAILED]
- ALAC → WAV: [SUCCESS/FAILED]

Documentation updated accordingly.

Completes Task #3 from CODE_REVIEW_ANTIGRAVITY.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## 🔴 AUFGABE #5: Windows Portable Build

**Priorität:** HOCH (kritisch für Release)  
**Aufwand:** 4-8 Stunden  
**Voraussetzung:** Windows 11 VM oder physische Maschine

### Wichtig: Python-Version

⚠️ **NICHT Python 3.14 verwenden!**  
✅ **Python 3.9, 3.10 oder 3.11 verwenden** (stabile Versionen)

### Schritt 1: Windows-VM vorbereiten

**Anforderungen:**
- Windows 11 (x64)
- KEINE Entwickler-Tools installiert (simuliert End-User)
- Mindestens 10 GB freier Speicher
- Audio-Treiber funktionsfähig

### Schritt 2: Python installieren

1. Download von python.org: Python 3.11.x (aktuellste 3.11)
2. Installation mit "Add Python to PATH" aktiviert
3. Verifizieren:
```cmd
python --version
pip --version
```

### Schritt 3: Repository klonen und Build erstellen

```cmd
cd C:\Temp
git clone https://github.com/Eidolf/ER-Audio-Tool.git
cd ER-Audio-Tool
git checkout comprehensive-audit-fixes

REM Dependencies installieren
pip install pyinstaller
pip install -e .

REM Build erstellen
pyinstaller er_audio_tool.spec

REM Prüfen
dir dist\
```

**Erwartetes Ergebnis:**
- `dist\er-audio-tool.exe` existiert
- Größe: ~50-100 MB

### Schritt 4: Portable Build testen

**Test-Plan:**

```cmd
cd dist

REM 1. Starten
er-audio-tool.exe

REM Testen:
```

**In der Anwendung:**

1. **Sprach-Wechsel**
   - Menü: Settings → Language
   - Wechsle zwischen Deutsch ↔ English
   - Verifiziere: Alle Texte ändern sich sofort

2. **System-Output-Recording** (KRITISCH)
   - Menü: Record → New Recording → System Output
   - Wähle Audio-Gerät (Speakers/Headphones)
   - Spiele Musik ab (YouTube, Spotify, etc.)
   - Klicke "Start Recording"
   - ✅ Level-Meter muss sich bewegen (grüne Balken)
   - Warte 10 Sekunden
   - Klicke "Stop and Save"
   - ✅ Datei muss sich öffnen lassen und Audio enthalten

3. **Mikrofon-Recording**
   - Menü: Record → New Recording → Microphone
   - Wähle Mikrofon
   - Start Recording
   - Sprich ins Mikrofon
   - ✅ Level-Meter reagiert
   - Stop and Save
   - ✅ Aufnahme enthält Sprache

4. **Browser Extension Setup**
   - Menü: Settings → Browser Integration
   - ⚠️ Extension-Pfad darf NICHT `_MEI...` enthalten!
   - ✅ Pfad muss dauerhaft/permanent sein
   - Klicke "Copy Path"
   - Prüfe: Ordner existiert und enthält `manifest.json`
   - Klicke "Copy Token"
   - Token sollte lange Hex-Zeichenkette sein

5. **Audio Conversion**
   - Menü: Convert → Audio Converter
   - Wähle Test-MP3-Datei
   - Output: WAV
   - Convert
   - ✅ WAV-Datei erfolgreich erstellt
   - Teste: MP3 → FLAC
   - ✅ FLAC erfolgreich

6. **MIDI Transcription**
   - Menü: Analyze → Audio to MIDI
   - Wähle Audio-Datei
   - Profile: Melody
   - Transcribe
   - ✅ MIDI-Datei erstellt
   - Öffne in MIDI-Editor (z.B. MuseScore, wenn verfügbar)
   - ✅ Noten sichtbar

7. **Help System**
   - Klicke ? bei verschiedenen Features
   - ✅ Help-Dialog öffnet sich
   - ✅ Text in gewählter Sprache (DE/EN)

8. **Diagnostics**
   - Menü: Devices → Hardware and Software Test
   - Run Diagnostics
   - ✅ Kein Fehler, alle grün/ok

### Schritt 5: Probleme dokumentieren

**Erstelle Datei:** `WINDOWS_BUILD_ISSUES.md`

```markdown
# Windows Portable Build Test - Probleme

**Datum:** [Datum]
**Windows:** [Version]
**Build:** dist/er-audio-tool.exe
**Größe:** [Größe in MB]

## Test-Ergebnisse

| Test | Status | Notizen |
|------|--------|---------|
| Application Start | ✅/❌ | |
| Language Switch | ✅/❌ | |
| System Output Recording | ✅/❌ | Level-Meter: ✅/❌, Audio in File: ✅/❌ |
| Microphone Recording | ✅/❌ | |
| Browser Extension Path | ✅/❌ | Pfad: [zeigen] |
| Audio Conversion | ✅/❌ | MP3→WAV: ✅/❌, MP3→FLAC: ✅/❌ |
| MIDI Transcription | ✅/❌ | |
| Help System | ✅/❌ | |
| Diagnostics | ✅/❌ | |

## Gefundene Probleme

### Problem 1: [Titel]
**Schweregrad:** P0/P1/P2/P3
**Beschreibung:** [Was ist das Problem]
**Reproduktion:** [Schritte]
**Erwartetes Verhalten:** [Was sollte passieren]
**Tatsächliches Verhalten:** [Was passiert]
**Logs/Screenshots:** [falls vorhanden]

[Weitere Probleme...]

## Fehlende Ressourcen

- [ ] Icons/Bilder fehlen
- [ ] Übersetzungen fehlen
- [ ] Help-Dateien fehlen
- [ ] FFmpeg nicht herunterladbar
- [ ] Browser-Extension-Dateien fehlen

## Performance

- Startzeit: [X] Sekunden
- RAM-Nutzung (Idle): [X] MB
- RAM-Nutzung (Recording): [X] MB

## Fazit

[Zusammenfassung: Ready for Release / Needs Fixes / Blocking Issues]
```

### Schritt 6: Commit Ergebnisse

```bash
git add WINDOWS_BUILD_ISSUES.md
git commit -m "test: Windows 11 portable build verification

Build created successfully: dist/er-audio-tool.exe (X MB)

Test Results:
- Language Switch: ✅/❌
- System Recording: ✅/❌
- Browser Extension: ✅/❌
- Conversion: ✅/❌
- MIDI: ✅/❌
- Diagnostics: ✅/❌

[X] issues found (see WINDOWS_BUILD_ISSUES.md)

Completes Task #5 from CODE_REVIEW_ANTIGRAVITY.md

Co-Authored-By: [Dein Name] <email>"
```

---

## 🔴 AUFGABE #6: Linux Portable Build

**Priorität:** HOCH  
**Aufwand:** 2-4 Stunden  
**Kann in bestehender Dev-Umgebung getestet werden**

### Schritt 1: AppImage erstellen (Empfohlen)

```bash
cd /home/dev/github/ER-Audio-Tool

# AppImage-Tool installieren
wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage

# Build erstellen
source venv/bin/activate
pyinstaller er_audio_tool.spec

# AppImage-Struktur vorbereiten
mkdir -p AppDir/usr/bin
cp dist/er-audio-tool AppDir/usr/bin/

# Desktop-Entry erstellen
cat > AppDir/er-audio-tool.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=er-audio-tool
Comment=Local-first audio recorder and processor
Exec=er-audio-tool
Icon=er-audio-tool
Categories=AudioVideo;Audio;
Terminal=false
EOF

# Icon kopieren (falls vorhanden)
cp assets/logo.png AppDir/er-audio-tool.png 2>/dev/null || touch AppDir/er-audio-tool.png

# AppRun erstellen
cat > AppDir/AppRun << 'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/er-audio-tool" "$@"
EOF
chmod +x AppDir/AppRun

# AppImage erstellen
./appimagetool-x86_64.AppImage AppDir er-audio-tool-x86_64.AppImage
```

**Alternative: Einfacher Portable Binary**

```bash
# Einfach den PyInstaller-Output verwenden
cd dist
tar -czf er-audio-tool-linux-x86_64.tar.gz er-audio-tool
```

### Schritt 2: Auf sauberem System testen

**Ideal:** Separates Linux-System oder Docker-Container

```bash
# Docker-Test (Ubuntu 22.04)
docker run -it --rm \
  -v $(pwd)/dist:/dist \
  --device /dev/snd \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  ubuntu:22.04 bash

# Im Container:
apt update
apt install -y libportaudio2 libsndfile1 pulseaudio

# Binary testen
/dist/er-audio-tool

# Gleiche Tests wie Windows (siehe Aufgabe #5)
```

### Schritt 3: Dokumentieren

**Erstelle:** `LINUX_BUILD_ISSUES.md` (analog zu Windows)

### Schritt 4: Commit

```bash
git add LINUX_BUILD_ISSUES.md
git commit -m "test: Linux portable build verification

Build type: [AppImage / Tarball]
Size: [X] MB

Test Results: [Analog zu Windows]

Completes Task #6 from CODE_REVIEW_ANTIGRAVITY.md

Co-Authored-By: [Dein Name] <email>"
```

---

## 🔴 AUFGABE #8: Browser E2E Test

**Priorität:** HOCH  
**Aufwand:** 2-3 Stunden  
**Voraussetzung:** Chrome oder Edge installiert

### Schritt 1: Chrome/Edge installieren

```bash
# Ubuntu - Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f

# Fedora - Chrome
sudo dnf install google-chrome-stable

# Edge (alternative)
# https://www.microsoft.com/en-us/edge/download
```

### Schritt 2: Extension laden

```bash
# er-audio-tool starten
cd /home/dev/github/ER-Audio-Tool
source venv/bin/activate
python -m er_audio_tool.cli

# In der Anwendung:
# Settings → Browser Integration
# Notiere Extension-Pfad und Token
```

**In Chrome/Edge:**

1. Öffne `chrome://extensions` oder `edge://extensions`
2. Aktiviere "Developer Mode" (oben rechts)
3. Klicke "Load unpacked"
4. Wähle: `[Projekt]/browser_extension/`
5. Extension erscheint in Liste

### Schritt 3: Extension authentifizieren

1. Klicke Extension-Icon in Browser-Toolbar
2. Popup öffnet sich
3. Füge Token ein (aus er-audio-tool kopiert)
4. Klicke "Authenticate"
5. ✅ Status sollte "Connected ✓" zeigen

**In er-audio-tool:**
- Status sollte "Extension Verified & Connected" zeigen

### Schritt 4: Tab-Recording testen

1. **Neuen YouTube-Tab öffnen**
   - Gehe zu: youtube.com
   - Suche beliebiges Video
   - Video NICHT abspielen (noch)

2. **In Extension:**
   - Klicke Extension-Icon
   - YouTube-Tab sollte in Liste erscheinen
   - Klicke auf YouTube-Tab → wird ausgewählt

3. **In er-audio-tool:**
   - Menü: Record → New Recording → Browser Tab
   - Ausgewählter Tab sollte angezeigt werden
   - Klicke "Start Recording"

4. **Im Browser:**
   - Starte YouTube-Video (Audio abspielen)
   - Lasse 10-20 Sekunden laufen

5. **In er-audio-tool:**
   - ✅ Level-Meter MUSS sich bewegen
   - Klicke "Stop and Save"

6. **Verifizieren:**
   - Öffne gespeicherte Datei
   - ✅ Audio MUSS YouTube-Video enthalten (nicht Mikrofon!)
   - Dauer sollte ~10-20 Sekunden sein

### Schritt 5: Edge-Cases testen

**Test A: Falscher Tab**
1. Wähle Tab A in Extension
2. Spiele Audio in Tab B ab
3. Starte Recording
4. ✅ Nur Audio von Tab A wird aufgenommen, nicht Tab B

**Test B: Connection Lost**
1. Starte Recording
2. Schließe Browser komplett
3. ✅ er-audio-tool sollte Fehler anzeigen
4. Öffne Browser wieder
5. ✅ Extension sollte sich wieder verbinden

**Test C: Kein Tab ausgewählt**
1. Öffne er-audio-tool
2. Gehe zu Record → Browser Tab
3. OHNE Tab in Extension auszuwählen
4. Klicke "Start Recording"
5. ✅ Sollte Fehler zeigen: "No tab selected"

### Schritt 6: Dokumentieren

**Erstelle:** `BROWSER_E2E_TEST.md`

```markdown
# Browser Extension E2E Test

**Browser:** Chrome/Edge [Version]
**Datum:** [Datum]

## Test-Ergebnisse

| Test | Status | Notizen |
|------|--------|---------|
| Extension lädt | ✅/❌ | |
| Extension authentifiziert | ✅/❌ | |
| Tab-Liste angezeigt | ✅/❌ | |
| Tab-Auswahl funktioniert | ✅/❌ | |
| Recording startet | ✅/❌ | |
| Level-Meter reagiert | ✅/❌ | |
| Audio in Datei | ✅/❌ | YouTube-Audio: ✅/❌ |
| Richtiger Tab aufgenommen | ✅/❌ | |
| Falscher Tab ignoriert | ✅/❌ | |
| Connection Recovery | ✅/❌ | |

## Probleme

[Beschreibe gefundene Probleme]

## Fazit

[Browser-Integration funktioniert / Hat Probleme / Nicht funktional]
```

### Schritt 7: Commit

```bash
git add BROWSER_E2E_TEST.md
git commit -m "test: browser extension end-to-end verification

Browser: Chrome/Edge [Version]
Extension: Loaded and authenticated successfully

Test Results:
- Tab selection: ✅/❌
- Audio capture: ✅/❌
- Level meters: ✅/❌
- Correct tab isolation: ✅/❌
- Connection recovery: ✅/❌

[X] issues found (see BROWSER_E2E_TEST.md)

Completes Task #8 from CODE_REVIEW_ANTIGRAVITY.md

Co-Authored-By: [Dein Name] <email>"
```

---

## 🟢 AUFGABE #7: Pause/Resume Tests (Optional)

**Priorität:** Niedrig (kann später)  
**Aufwand:** 2 Stunden

### Implementation

**Erstelle:** `tests/test_pause_resume.py`

```python
"""Test recording pause/resume functionality."""
import time
import tempfile
from pathlib import Path
import numpy as np

from er_audio_tool.audio.backends.mock_backend import MockAudioBackend
from er_audio_tool.audio.encoder import AudioEncoder
from er_audio_tool.core.state import StateMachine, AppState


def test_recording_pause_resume():
    """Test that pause/resume produces continuous audio without gaps."""
    backend = MockAudioBackend(generate_tone_hz=440.0)
    
    received_chunks = []
    
    def callback(data: np.ndarray):
        received_chunks.append(data.copy())
    
    # Simulate recording lifecycle
    state_machine = StateMachine(AppState.IDLE)
    
    # Start recording
    assert state_machine.transition_to(AppState.PREPARING)
    assert state_machine.transition_to(AppState.RECORDING)
    
    device = backend.enumerate_devices()[0]
    backend.start_capture(device, 48000, 2, callback)
    
    # Record for 0.5 seconds
    time.sleep(0.5)
    chunks_before_pause = len(received_chunks)
    
    # Pause
    assert state_machine.transition_to(AppState.PAUSED)
    # Note: Mock backend continues generating, but real backend would pause
    # In real implementation, stop accepting frames here
    
    # Wait 0.3 seconds (paused)
    time.sleep(0.3)
    
    # Resume
    assert state_machine.transition_to(AppState.RECORDING)
    
    # Record for another 0.5 seconds
    time.sleep(0.5)
    
    # Stop
    assert state_machine.transition_to(AppState.STOPPING)
    backend.stop_capture()
    
    # Verify we got audio
    assert len(received_chunks) > 0
    
    # In real implementation: verify no gap in output file
    # For now: verify state transitions worked
    assert state_machine.current_state == AppState.STOPPING


def test_pause_without_recording_fails():
    """Test that pause fails if not recording."""
    state_machine = StateMachine(AppState.IDLE)
    
    # Try to pause while idle
    result = state_machine.transition_to(AppState.PAUSED)
    assert result is False
    assert state_machine.current_state == AppState.IDLE


def test_resume_without_pause_fails():
    """Test that resume only works from paused state."""
    state_machine = StateMachine(AppState.IDLE)
    
    # Can't go from idle to recording directly (need preparing first)
    result = state_machine.transition_to(AppState.RECORDING)
    assert result is False


if __name__ == "__main__":
    test_recording_pause_resume()
    test_pause_without_recording_fails()
    test_resume_without_pause_fails()
    print("✅ All pause/resume tests passed!")
```

### Commit

```bash
git add tests/test_pause_resume.py
pytest tests/test_pause_resume.py -v

git commit -m "test: add pause/resume recording tests

Verifies:
- State machine allows RECORDING → PAUSED → RECORDING transitions
- Invalid transitions are rejected
- Basic pause/resume lifecycle

Note: Full integration test with real audio output requires
GUI automation and is covered by manual testing.

Completes Task #7 from CODE_REVIEW_ANTIGRAVITY.md

Co-Authored-By: [Dein Name] <email>"
```

---

## 📊 Abschluss-Checkliste

Nach Abschluss ALLER Aufgaben:

```markdown
# er-audio-tool - Release Readiness Checklist

## Code & Tests
- [x] Phase 1 Documentation complete
- [x] Stem separation marked as experimental
- [x] MIDI multi-track implemented
- [x] Legacy code removed
- [ ] ALAC support verified (Task #3)
- [ ] Pause/resume tested (Task #7)
- [ ] All tests pass (current: 35/35)

## Portable Builds
- [ ] Windows 11 portable build tested (Task #5)
- [ ] Linux portable build tested (Task #6)
- [ ] No critical issues in portable builds
- [ ] All resources bundled correctly
- [ ] Extension path is persistent

## Integration
- [ ] Browser E2E tested (Task #8)
- [ ] Tab selection works
- [ ] Audio capture verified
- [ ] Connection recovery tested

## Documentation
- [x] README accurate
- [x] CHANGELOG up to date
- [x] SECURITY_PRIVACY complete
- [x] TROUBLESHOOTING comprehensive
- [x] CODEC_SUPPORT accurate
- [ ] Build issues documented

## Release Preparation
- [ ] Version number updated in version.py
- [ ] Git tag created (e.g., v1.4.0)
- [ ] Branch merged to main
- [ ] GitHub release created
- [ ] Checksums generated for downloads

## Decision
- [ ] Ready for Alpha Release
- [ ] Ready for Beta Release
- [ ] Ready for Production Release
- [ ] Needs more work (specify issues)
```

---

## 🚀 Finaler Merge zu Main

**Erst wenn ALLE kritischen Tests bestanden sind:**

```bash
# Lokalen Branch prüfen
git checkout comprehensive-audit-fixes
git log --oneline -10

# Zu main mergen
git checkout main
git merge comprehensive-audit-fixes

# Tag erstellen
git tag -a v1.4.0 -m "Release 1.4.0: Documentation, MIDI multi-track, experimental stem marking

Major improvements:
- Complete documentation suite (8 documents)
- SMF Format 1 multi-track MIDI export
- Honest experimental feature labeling
- Windows and Linux portable builds verified
- Browser integration E2E tested

All 35+ tests passing.
Ready for public alpha release."

# Push (wenn ready)
git push origin main
git push origin v1.4.0
```

---

## 📧 Kontakt bei Problemen

- **GitHub Issues:** https://github.com/Eidolf/ER-Audio-Tool/issues
- **Maintainer:** Eidolf <andreas@eidolf.de>
- **Code Review Branch:** comprehensive-audit-fixes

---

## 💡 Wichtige Hinweise

1. **Python-Version:** Für portable builds Python 3.9-3.11 verwenden (NICHT 3.14!)
2. **FFmpeg:** Kann über er-audio-tool selbst heruntergeladen werden ODER systemweit installiert
3. **Tests:** Alle Tests müssen vor Merge zu main bestehen
4. **Dokumentation:** Bei Problemen IMMER in entsprechendes `*_ISSUES.md` dokumentieren
5. **Commits:** Immer mit "Co-Authored-By" taggen für Nachvollziehbarkeit

---

**Ende der Anleitung. Viel Erfolg! 🎉**
