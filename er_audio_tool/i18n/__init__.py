"""Internationalization (i18n) module for er-audio-tool."""
from __future__ import annotations

TRANSLATIONS = {
    "en": {
        "app_title": "er-audio-tool - Professional Desktop Audio Suite",
        "tab_recorder": "Recorder",
        "tab_library": "Recordings",
        "tab_analysis": "Audio Analysis",
        "tab_midi": "Audio to MIDI",
        "tab_render": "MIDI Preview & Render",
        "tab_settings": "Settings",
        "tab_diagnostics": "Diagnostics",
        "tab_about": "About & Licenses",
        "record": "Record",
        "pause": "Pause",
        "resume": "Resume",
        "stop": "Stop",
        "status_idle": "Ready",
        "status_recording": "Recording System Audio",
        "status_paused": "Recording Paused",
        "status_encoding": "Encoding Audio...",
        "status_transcribing": "Transcribing Audio to MIDI...",
        "status_rendering": "Rendering MIDI to MP3...",
        "source_label": "Capture Source:",
        "format_label": "Output Format:",
        "legal_reminder": "Privacy & Legal Notice: Please respect copyright and privacy laws. Only record audio you have explicit authorization to capture.",
        "clipping_warning": "WARNING: Input signal is clipping! Reduce source volume or disable boost.",
    },
    "de": {
        "app_title": "er-audio-tool - Professionelle Desktop-Audio-Suite",
        "tab_recorder": "Aufnahme",
        "tab_library": "Bibliothek",
        "tab_analysis": "Audio-Analyse",
        "tab_midi": "Audio zu MIDI",
        "tab_render": "MIDI-Vorschau & Render",
        "tab_settings": "Einstellungen",
        "tab_diagnostics": "Diagnose",
        "tab_about": "Über & Lizenzen",
        "record": "Aufnehmen",
        "pause": "Pause",
        "resume": "Fortsetzen",
        "stop": "Stopp",
        "status_idle": "Bereit",
        "status_recording": "System-Audioaufnahme läuft",
        "status_paused": "Aufnahme pausiert",
        "status_encoding": "Audio wird kodiert...",
        "status_transcribing": "Transkribiere Audio zu MIDI...",
        "status_rendering": "Rendere MIDI zu MP3...",
        "source_label": "Aufnahmequelle:",
        "format_label": "Ausgabeformat:",
        "legal_reminder": "Datenschutz & Rechtlicher Hinweis: Bitte beachten Sie Urheberrechts- und Datenschutzgesetze. Zeichnen Sie nur Audio auf, für das Sie autorisiert sind.",
        "clipping_warning": "WARNUNG: Eingangssignal übersteuert (Clipping)! Bitte Lautstärke reduzieren.",
    }
}


class I18n:
    def __init__(self, lang: str = "en"):
        self.lang = lang if lang in TRANSLATIONS else "en"

    def set_language(self, lang: str):
        if lang in TRANSLATIONS:
            self.lang = lang

    def t(self, key: str, **kwargs) -> str:
        text = TRANSLATIONS.get(self.lang, {}).get(key, TRANSLATIONS["en"].get(key, key))
        if kwargs:
            return text.format(**kwargs)
        return text


_global_i18n = I18n()


def get_i18n() -> I18n:
    return _global_i18n
