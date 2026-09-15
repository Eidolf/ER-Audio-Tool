"""Offline Context-Sensitive Help Registry for er-audio-tool."""
from __future__ import annotations
from dataclasses import dataclass
from er_audio_tool.i18n import get_i18n


@dataclass
class HelpTopic:
    topic_id: str
    title_en: str
    title_de: str
    content_en: str
    content_de: str


HELP_REGISTRY: dict[str, HelpTopic] = {
    "system_audio": HelpTopic(
        topic_id="system_audio",
        title_en="Help: System Audio Recording",
        title_de="Hilfe: System-Audioaufnahme",
        content_en=(
            "Captures what you hear directly from your computer's speakers or headphones.\n\n"
            "• Windows 11: Uses native WASAPI loopback without requiring Stereo Mix.\n"
            "• Linux: Uses modern PipeWire desktop capture or PulseAudio monitor sources.\n\n"
            "Steps:\n"
            "1. Select the output device you are listening to.\n"
            "2. Choose your output format (WAV, FLAC, or MP3).\n"
            "3. Click 'Start Recording'. Real-time audio levels will move as audio plays.\n"
            "4. Use 'Pause' to temporarily suspend capture, and 'Stop & Save' to finalize."
        ),
        content_de=(
            "Nimmt direkt das auf, was über Ihre Lautsprecher oder Kopfhörer wiedergegeben wird.\n\n"
            "• Windows 11: Nutzt natives WASAPI Loopback ohne 'Stereo Mix' Voraussetzung.\n"
            "• Linux: Nutzt PipeWire Desktop-Aufnahme oder PulseAudio Monitor-Quellen.\n\n"
            "Schritte:\n"
            "1. Wählen Sie das Ausgabegerät, über das Sie hören.\n"
            "2. Wählen Sie das gewünschte Format (WAV, FLAC oder MP3).\n"
            "3. Klicken Sie auf 'Aufnahme starten'. Der Pegelmesser schlägt bei Ton aus.\n"
            "4. Mit 'Pause' können Sie unterbrechen, mit 'Stopp & Speichern' beenden."
        ),
    ),
    "audio_converter": HelpTopic(
        topic_id="audio_converter",
        title_en="Help: Audio Converter",
        title_de="Hilfe: Audio-Konverter",
        content_en=(
            "Converts existing audio files into MP3, WAV, FLAC, OGG, or Opus formats.\n\n"
            "• Full M4A Support: Handles AAC and ALAC audio streams within M4A/MP4 containers.\n"
            "• Batch Processing: Add multiple files to queue and convert them concurrently.\n"
            "• Non-destructive: Original input files are preserved and never overwritten."
        ),
        content_de=(
            "Konvertiert bestehende Audiodateien in MP3, WAV, FLAC, OGG oder Opus.\n\n"
            "• Vollständige M4A-Unterstützung: Verarbeitet AAC- und ALAC-Streams in M4A/MP4.\n"
            "• Stapelverarbeitung: Fügen Sie mehrere Dateien der Warteschlange hinzu.\n"
            "• Sicher: Ursprungsdateien bleiben unverändert erhalten."
        ),
    ),
    "diagnostic_test": HelpTopic(
        topic_id="diagnostic_test",
        title_en="Help: Hardware & Software Test",
        title_de="Hilfe: Hardware- & Software-Test",
        content_en=(
            "Performs self-diagnostics to verify:\n"
            "• Audio service and WASAPI / PipeWire backend availability.\n"
            "• Live incoming audio frame reception.\n"
            "• Directory write permissions and atomic file writing.\n"
            "• Local codec availability (MP3, WAV, FLAC, M4A)."
        ),
        content_de=(
            "Führt Systemtests durch zur Überprüfung von:\n"
            "• Audiodiensten und WASAPI / PipeWire Verfügbarkeit.\n"
            "• Empfang von Live-Audioframes.\n"
            "• Schreibberechtigungen im Zielordner.\n"
            "• Vorhandenen Codecs (MP3, WAV, FLAC, M4A)."
        ),
    ),
    "browser_companion": HelpTopic(
        topic_id="browser_companion",
        title_en="Help: Browser Tab Capture Companion",
        title_de="Hilfe: Browser-Tab Audio-Erweiterung",
        content_en=(
            "Captures isolated audio from a single browser tab in Chrome, Edge, or Brave.\n\n"
            "1. Install the extension from 'browser_extension/' via chrome://extensions.\n"
            "2. Copy the session token displayed in Devices > Browser Connection.\n"
            "3. Paste into the extension popup and click 'Record Active Tab'."
        ),
        content_de=(
            "Nimmt isoliert den Ton eines einzelnen Browser-Tabs in Chrome, Edge oder Brave auf.\n\n"
            "1. Erweiterung aus 'browser_extension/' über chrome://extensions laden.\n"
            "2. Sitzungs-Token unter 'Geräte > Browser-Verbindung' kopieren.\n"
            "3. Im Erweiterungs-Popup einfügen und 'Record Active Tab' anklicken."
        ),
    ),
    "codecs": HelpTopic(
        topic_id="codecs",
        title_en="Help: FFmpeg & Audio Codecs",
        title_de="Hilfe: FFmpeg & Audio-Codecs",
        content_en=(
            "FFmpeg provides high-performance audio encoding, decoding, and muxing.\n\n"
            "• Minimal / Audio Essentials: Includes MP3 (LAME), WAV (PCM), AAC/M4A, FLAC, OGG, and Opus.\n"
            "• Full Codec Pack: Adds exotic & legacy audio formats like ALAC, AMR, AC3, DTS, WMA, AIFF, and WebM.\n"
            "• Portable Execution: Unpacked into a local 'temp_codecs' folder next to the app.\n"
            "• Lifecycle: Choose whether to keep this folder for future runs or delete it on application exit."
        ),
        content_de=(
            "FFmpeg ermöglicht Audio-Encoding, Decoding und Container-Verarbeitung.\n\n"
            "• Minimal / Audio-Essentials: Enthält MP3 (LAME), WAV (PCM), AAC/M4A, FLAC, OGG und Opus.\n"
            "• Vollständiges Codec-Pack: Ergänzt Formate wie ALAC, AMR, AC3, DTS, WMA, AIFF und WebM.\n"
            "• Portable Ausführung: Liegt direkt im Ordner 'temp_codecs' neben der App.\n"
            "• Bereinigung: Sie können festlegen, ob der Ordner beim Beenden behalten oder gelöscht wird."
        ),
    ),
}


def get_help_topic(topic_id: str) -> HelpTopic | None:
    return HELP_REGISTRY.get(topic_id)
