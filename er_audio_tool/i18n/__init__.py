"""Centralized internationalization (i18n) catalog and dynamic subscriber service."""
from __future__ import annotations
import locale
import os
import sys
from typing import Callable

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # App & Header
        "app_title": "er-audio-tool - Professional Audio Suite",
        "ready": "Ready",
        "recording": "Recording System Audio...",
        "paused": "Recording Paused",
        "encoding": "Encoding audio output...",
        "analyzing": "Analyzing audio...",
        "converting": "Converting audio files...",
        "stopped": "Recording stopped and saved.",
        "canceled": "Recording discarded.",
        "error": "Error",
        
        # Navigation Main & Submenus
        "nav_setup": "Setup & Codecs",
        "nav_codecs_install": "FFmpeg Codec Pack",
        "nav_record": "Record",
        "nav_rec_system": "System Audio",
        "nav_rec_app": "Application Audio",
        "nav_rec_browser": "Browser Tab",
        "nav_rec_test": "Recording Test",
        "nav_rec_history": "Recording History",
        
        "nav_convert": "Convert",
        "nav_conv_audio": "Audio Converter",
        "nav_conv_batch": "Batch Conversion",
        "nav_conv_history": "Conversion History",
        
        "nav_analyze": "Analyze",
        "nav_ana_audio": "Audio Analysis",
        "nav_ana_midi": "Audio to MIDI",
        "nav_ana_preview": "MIDI Preview",
        "nav_ana_render": "Render MIDI to Audio",
        
        "nav_library": "Library",
        "nav_lib_recordings": "Recordings",
        "nav_lib_converted": "Converted Files",
        "nav_lib_midi": "MIDI Files",
        "nav_lib_open": "Open Output Folder",
        
        "nav_devices": "Devices",
        "nav_dev_outputs": "Audio Outputs",
        "nav_dev_sources": "Recording Sources",
        "nav_dev_hwtest": "Hardware & Software Test",
        "nav_dev_browser": "Browser Connection",
        
        "nav_settings": "Settings",
        "nav_set_general": "General",
        "nav_set_codecs": "FFmpeg & Codecs",
        "nav_set_audio": "Audio Capture",
        "nav_set_conv": "Conversion",
        "nav_set_midi": "MIDI & Synth",
        "nav_set_privacy": "Privacy & Logs",
        
        "nav_help": "Help",
        "nav_help_topics": "Context Help",
        "nav_help_browser": "Browser Setup Guide",
        "nav_help_trouble": "Troubleshooting",
        "nav_help_about": "About & Licenses",
        
        # Actions & Buttons
        "btn_record": "Start Recording",
        "btn_pause": "Pause",
        "btn_resume": "Resume",
        "btn_stop": "Stop & Save",
        "btn_cancel": "Cancel",
        "btn_browse": "Browse...",
        "btn_open_file": "Open File",
        "btn_open_folder": "Open Folder",
        "btn_convert": "Start Conversion",
        "btn_analyze": "Analyze Audio",
        "btn_transcribe": "Transcribe to MIDI",
        "btn_render_midi": "Render to Audio",
        "btn_run_tests": "Run All Tests",
        "btn_copy_report": "Copy Report",
        "btn_save_settings": "Save Settings",
        
        # Formats & Parameters
        "source_label": "Capture Source:",
        "format_label": "Output Format:",
        "channels_label": "Channels:",
        "sample_rate_label": "Sample Rate:",
        "bitrate_label": "Bitrate:",
        "output_dir_label": "Output Directory:",
        "target_format_label": "Target Format:",
        "preset_label": "Conversion Preset:",
        "profile_label": "Transcription Profile:",
        
        # Audio Levels & Meters
        "level_title": "Live Audio Level Meter",
        "level_left": "Left: {val:.1f} dB",
        "level_right": "Right: {val:.1f} dB",
        "level_peak": "Peak: {val:.1f} dBFS",
        "level_rms": "RMS: {val:.1f} dBFS",
        "clipping_detected": "CLIPPING DETECTED! Reduce volume.",
        "no_signal_warning": "No audio signal detected. Verify playback on selected device.",
        
        # Legal & Privacy
        "legal_notice": "Notice: Only record content you have authorization to capture. er-audio-tool does not bypass protected media restrictions.",
        "privacy_guarantee": "Local-First: 100% offline. Zero telemetry or cloud transmission.",

        # Browser Connection
        "browser_pairing_title": "Companion Extension Setup & Pairing",
        "browser_pairing_desc": "Pair the Chrome or Edge companion extension to capture active browser tabs with explicit consent.",
        "browser_token_label": "Session Pairing Token:",
        "browser_token_masked": "••••••••••••••••••••••••••••••••",
        "btn_show_token": "Show Token",
        "btn_hide_token": "Hide Token",
        "btn_copy_token": "Copy Token",
        "btn_regen_token": "Regenerate Token",
        "browser_path_label": "Extension Directory (Load Unpacked):",
        "btn_copy_path": "Copy Path",
        "btn_open_folder": "Open Folder",
        "btn_reinstall_ext": "Reinstall / Update Extension",
        "token_copied_msg": "✓ Token copied to clipboard!",
        "path_copied_msg": "✓ Path copied to clipboard!",
        "ext_status_ready": "Status: Ready on loopback interface (127.0.0.1)",
        "ext_installed_msg": "✓ Extension files extracted and verified at persistent location.",
        
        # Codecs & FFmpeg Downloader
        "codecs_title": "FFmpeg & Audio Codec Pack Management",
        "codecs_desc": "FFmpeg is the media engine used for MP3/M4A/Opus encoding and format conversion. You can download and unpack a portable codec pack directly into a local 'temp_codecs' folder next to the app without needing administrative system install.",
        "codecs_status_label": "Current Status:",
        "codecs_status_system": "Detected in system PATH ({path})",
        "codecs_status_portable": "Active portable pack in temp_codecs ({path})",
        "codecs_status_missing": "Not found. (WAV & FLAC available; MP3/M4A conversion limited)",
        "codecs_scope_label": "Codec Scope:",
        "codecs_scope_essential": "Minimal / Audio Essentials (MP3, WAV, AAC, FLAC, OGG, Opus)",
        "codecs_scope_full": "Full Audio Codec Pack (Essentials + ALAC, AMR, AC3, DTS, WMA, AIFF, WebM)",
        "codecs_exit_policy_label": "When closing application:",
        "codecs_exit_ask": "Ask every time (Prompt to keep or delete temp_codecs)",
        "codecs_exit_keep": "Keep temporary folder for future runs (Recommended)",
        "codecs_exit_delete": "Always delete temporary codec folder on exit",
        "codecs_missing_banner": "⚠ Notice: FFmpeg codec pack is not installed yet. MP3 encoding and M4A/AAC conversion are limited until codecs are downloaded.",
        "btn_install_codecs_banner": "Install Codecs Now",
        "btn_download_codecs": "Download & Setup Codecs",
        "btn_purge_codecs": "Delete Local Codecs",
        "codecs_downloading": "Downloading codecs: {info}",
        "codecs_download_success": "Portable FFmpeg installed successfully!",
        "codecs_download_failed": "Download/Extraction failed: {err}",
        "codecs_purge_confirm": "Do you want to permanently delete the portable codecs directory ('temp_codecs')?",
        "codecs_purged": "Temporary codecs folder was deleted.",
        "codecs_exit_dialog_title": "Clean Up Temporary Codecs?",
        "codecs_exit_dialog_prompt": "A temporary FFmpeg codec pack is present in 'temp_codecs'.\n\nWould you like to delete it now, or keep it for the next run?",
        "btn_exit_keep": "Keep Codecs",
        "btn_exit_delete": "Delete Temporary Folder",
    },
    "de": {
        # App & Header
        "app_title": "er-audio-tool - Professionelle Audio-Suite",
        "ready": "Bereit",
        "recording": "System-Audioaufnahme läuft...",
        "paused": "Aufnahme pausiert",
        "encoding": "Audioausgabe wird kodiert...",
        "analyzing": "Analysiere Audio...",
        "converting": "Konvertiere Audiodateien...",
        "stopped": "Aufnahme beendet und gespeichert.",
        "canceled": "Aufnahme verworfen.",
        "error": "Fehler",
        
        # Navigation Main & Submenus
        "nav_setup": "Setup & Codecs",
        "nav_codecs_install": "FFmpeg Codec-Pack",
        "nav_record": "Aufnahme",
        "nav_rec_system": "System-Audio",
        "nav_rec_app": "Anwendungs-Audio",
        "nav_rec_browser": "Browser-Tab",
        "nav_rec_test": "Aufnahme-Test",
        "nav_rec_history": "Aufnahme-Verlauf",
        
        "nav_convert": "Konvertieren",
        "nav_conv_audio": "Audio-Konverter",
        "nav_conv_batch": "Stapelverarbeitung",
        "nav_conv_history": "Konvertierungs-Verlauf",
        
        "nav_analyze": "Analyse",
        "nav_ana_audio": "Audio-Analyse",
        "nav_ana_midi": "Audio zu MIDI",
        "nav_ana_preview": "MIDI-Vorschau",
        "nav_ana_render": "MIDI zu Audio rendern",
        
        "nav_library": "Bibliothek",
        "nav_lib_recordings": "Aufnahmen",
        "nav_lib_converted": "Konvertierte Dateien",
        "nav_lib_midi": "MIDI-Dateien",
        "nav_lib_open": "Ausgabeordner öffnen",
        
        "nav_devices": "Geräte",
        "nav_dev_outputs": "Audio-Ausgänge",
        "nav_dev_sources": "Aufnahme-Quellen",
        "nav_dev_hwtest": "Hardware- & Software-Test",
        "nav_dev_browser": "Browser-Verbindung",
        
        "nav_settings": "Einstellungen",
        "nav_set_general": "Allgemein",
        "nav_set_codecs": "FFmpeg & Codecs",
        "nav_set_audio": "Audio-Aufnahme",
        "nav_set_conv": "Konvertierung",
        "nav_set_midi": "MIDI & Synthesizer",
        "nav_set_privacy": "Datenschutz & Logs",
        
        "nav_help": "Hilfe",
        "nav_help_topics": "Kontext-Hilfe",
        "nav_help_browser": "Browser-Erweiterungsanleitung",
        "nav_help_trouble": "Fehlerbehebung",
        "nav_help_about": "Über & Lizenzen",
        
        # Actions & Buttons
        "btn_record": "Aufnahme starten",
        "btn_pause": "Pause",
        "btn_resume": "Fortsetzen",
        "btn_stop": "Stopp & Speichern",
        "btn_cancel": "Abbrechen",
        "btn_browse": "Durchsuchen...",
        "btn_open_file": "Datei öffnen",
        "btn_open_folder": "Ordner öffnen",
        "btn_convert": "Konvertierung starten",
        "btn_analyze": "Audio analysieren",
        "btn_transcribe": "In MIDI transkribieren",
        "btn_render_midi": "Als Audio rendern",
        "btn_run_tests": "Alle Tests ausführen",
        "btn_copy_report": "Bericht kopieren",
        "btn_save_settings": "Einstellungen speichern",
        
        # Formats & Parameters
        "source_label": "Aufnahmequelle:",
        "format_label": "Ausgabeformat:",
        "channels_label": "Kanäle:",
        "sample_rate_label": "Abtastrate:",
        "bitrate_label": "Bitrate:",
        "output_dir_label": "Ausgabe-Verzeichnis:",
        "target_format_label": "Zielformat:",
        "preset_label": "Konvertierungs-Profil:",
        "profile_label": "Transkriptions-Profil:",
        
        # Audio Levels & Meters
        "level_title": "Live-Audiopegel-Anzeige",
        "level_left": "Links: {val:.1f} dB",
        "level_right": "Rechts: {val:.1f} dB",
        "level_peak": "Peak: {val:.1f} dBFS",
        "level_rms": "RMS: {val:.1f} dBFS",
        "clipping_detected": "ÜBERSTEUERUNG (Clipping)! Bitte Lautstärke verringern.",
        "no_signal_warning": "Kein Audiosignal empfangen. Bitte Wiedergabe am ausgewählten Gerät prüfen.",
        
        # Legal & Privacy
        "legal_notice": "Hinweis: Bitte beachten Sie Urheberrechtsgesetze. er-audio-tool umgeht keinen Kopierschutz.",
        "privacy_guarantee": "Lokal-Zuerst: 100% offline. Keine Telemetrie oder Cloud-Übertragung.",

        # Browser Connection
        "browser_pairing_title": "Browser-Erweiterungs-Einrichtung & Kopplung",
        "browser_pairing_desc": "Koppeln Sie die Begleiterweiterung für Chrome oder Edge, um aktive Browser-Tabs mit expliziter Freigabe aufzunehmen.",
        "browser_token_label": "Sitzungs-Kopplungstoken:",
        "browser_token_masked": "••••••••••••••••••••••••••••••••",
        "btn_show_token": "Token anzeigen",
        "btn_hide_token": "Token verbergen",
        "btn_copy_token": "Token kopieren",
        "btn_regen_token": "Neues Token erzeugen",
        "browser_path_label": "Erweiterungsverzeichnis (Entpackte Erweiterung laden):",
        "btn_copy_path": "Pfad kopieren",
        "btn_open_folder": "Ordner öffnen",
        "btn_reinstall_ext": "Erweiterungsdateien neu installieren",
        "token_copied_msg": "✓ Token in die Zwischenablage kopiert!",
        "path_copied_msg": "✓ Pfad in die Zwischenablage kopiert!",
        "ext_status_ready": "Status: Bereit auf Loopback-Schnittstelle (127.0.0.1)",
        "ext_installed_msg": "✓ Erweiterungsdateien im persistenten Benutzerordner eingerichtet und verifiziert.",
        
        # Codecs & FFmpeg Downloader
        "codecs_title": "FFmpeg & Audio-Codec-Pack Verwaltung",
        "codecs_desc": "FFmpeg ist die Encoding-Engine für MP3/M4A/Opus-Export und Formatkonvertierung. Über diesen Assistenten kann ein portables Codec-Pack direkt in den temporären Ordner 'temp_codecs' neben der Anwendung geladen und entpackt werden – ganz ohne Administratorrechte oder Systeminstallation.",
        "codecs_status_label": "Aktueller Status:",
        "codecs_status_system": "Im System-PATH erkannt ({path})",
        "codecs_status_portable": "Aktives portables Pack in temp_codecs ({path})",
        "codecs_status_missing": "Nicht gefunden. (WAV & FLAC verfügbar; MP3/M4A eingeschränkt)",
        "codecs_scope_label": "Codec-Umfang:",
        "codecs_scope_essential": "Minimal / Audio-Essentials (MP3, WAV, AAC, FLAC, OGG, Opus)",
        "codecs_scope_full": "Vollständiges Audio-Codec-Pack (Essentials + ALAC, AMR, AC3, DTS, WMA, AIFF, WebM)",
        "codecs_exit_policy_label": "Beim Schließen der Anwendung:",
        "codecs_exit_ask": "Jedes Mal nachfragen (Temporären Ordner löschen oder behalten)",
        "codecs_exit_keep": "Temporären Ordner für nächsten Lauf behalten (Empfohlen)",
        "codecs_exit_delete": "Temporären Codec-Ordner beim Beenden immer löschen",
        "codecs_missing_banner": "⚠ Hinweis: FFmpeg Codec-Pack ist noch nicht installiert. MP3-Export und M4A/AAC-Konvertierung erfordern das Codec-Pack.",
        "btn_install_codecs_banner": "Codecs jetzt installieren",
        "btn_download_codecs": "Codecs herunterladen & einrichten",
        "btn_purge_codecs": "Lokale Codecs löschen",
        "codecs_downloading": "Lade Codecs herunter: {info}",
        "codecs_download_success": "Portables FFmpeg wurde erfolgreich eingerichtet!",
        "codecs_download_failed": "Download/Entpacken fehlgeschlagen: {err}",
        "codecs_purge_confirm": "Möchten Sie das portable Codec-Verzeichnis ('temp_codecs') wirklich unwiderruflich löschen?",
        "codecs_purged": "Temporärer Codec-Ordner wurde gelöscht.",
        "codecs_exit_dialog_title": "Temporäre Codecs bereinigen?",
        "codecs_exit_dialog_prompt": "Im Ordner 'temp_codecs' befindet sich ein portables FFmpeg Codec-Pack.\n\nMöchten Sie diesen temporären Ordner jetzt löschen oder für den nächsten Lauf behalten?",
        "btn_exit_keep": "Codecs behalten",
        "btn_exit_delete": "Temporären Ordner löschen",
    }
}


class LocalizationService:
    """Manages application language with dynamic observer notifications."""

    def __init__(self, initial_lang: str | None = None):
        if initial_lang in TRANSLATIONS:
            self.current_lang = initial_lang
        else:
            # Fallback to system locale detection
            try:
                sys_lang = locale.getlocale()[0]
                if sys_lang and sys_lang.startswith("de"):
                    self.current_lang = "de"
                else:
                    self.current_lang = "en"
            except Exception:
                self.current_lang = "en"

        self._subscribers: list[Callable[[], None]] = []

    def set_language(self, lang: str):
        if lang in TRANSLATIONS and lang != self.current_lang:
            self.current_lang = lang
            self.notify_all()

    def subscribe(self, callback: Callable[[], None]):
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[], None]):
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def notify_all(self):
        for cb in list(self._subscribers):
            try:
                cb()
            except Exception as ex:
                print(f"[i18n] Error updating subscriber: {ex}", file=sys.stderr)

    def t(self, key: str, **kwargs) -> str:
        text = TRANSLATIONS.get(self.current_lang, {}).get(key)
        if text is None:
            # Fallback to english
            text = TRANSLATIONS.get("en", {}).get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text


_service = LocalizationService()


def get_i18n() -> LocalizationService:
    return _service
