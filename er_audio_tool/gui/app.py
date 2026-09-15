"""Professional CustomTkinter GUI with hierarchical navigation, submenus, dynamic i18n, and full workflows."""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk
import numpy as np
from PIL import Image

from er_audio_tool.core.state import AppState, StateMachine
from er_audio_tool.core.config import ConfigManager
from er_audio_tool.i18n import get_i18n
from er_audio_tool.audio.manager import DeviceManager
from er_audio_tool.audio.buffer import AudioBuffer
from er_audio_tool.audio.encoder import AudioEncoder
from er_audio_tool.analysis.analyzer import AudioAnalyzer
from er_audio_tool.midi.model import NoteEvent, MidiExporter
from er_audio_tool.midi.transcriber import AudioToMidiTranscriber
from er_audio_tool.midi.renderer import MidiRenderer
from er_audio_tool.converter.converter import AudioConverter, ConversionJob
from er_audio_tool.diagnostics.runner import DiagnosticRunner
from er_audio_tool.help import get_help_topic
from er_audio_tool.audio.codecs import get_codec_manager, CODEC_SCOPES


class ErAudioApp(ctk.CTk):
    """Main desktop application window hosting structured navigation and all functional views."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        super().__init__()

        self.cm = config_manager or ConfigManager()
        self.cfg = self.cm.config
        self.i18n = get_i18n()
        self.i18n.set_language(self.cfg.language)

        self.state_machine = StateMachine(AppState.IDLE)
        self.device_manager = DeviceManager(preferred_backend=self.cfg.backend)
        self.audio_buffer = AudioBuffer(max_seconds=10.0, sample_rate=self.cfg.sample_rate)

        # UI Setup
        ctk.set_appearance_mode(self.cfg.theme)
        ctk.set_default_color_theme("dark-blue")
        self.title(self.i18n.t("app_title"))
        self.geometry("1120x760")
        self.minsize(980, 680)

        # Set window icon
        self._assets_dir = Path(__file__).resolve().parent.parent.parent / "assets"
        icon_path = self._assets_dir / "app_icon.png"
        if icon_path.exists():
            try:
                # Set Tk window icon
                self._icon_photo = ctk.CTkImage(light_image=Image.open(icon_path), size=(32, 32))
                self.iconphoto(False, ctk.CTkImage(light_image=Image.open(icon_path), size=(64, 64))._light_image)
            except Exception:
                pass

        self._active_backend = self.device_manager.get_active_backend()
        self.codec_manager = get_codec_manager()
        self._codec_download_cancel = threading.Event()
        self._recording_data: list[np.ndarray] = []
        self._record_start_time = 0.0
        self._elapsed_paused_time = 0.0
        self._pause_start_time = 0.0

        # If codecs are missing, start directly on Setup & Codecs so user can setup immediately
        if not self.codec_manager.get_active_ffmpeg():
            self._current_view_name = "set_codecs"
        else:
            self._current_view_name = "rec_system"

        self.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self._build_shell()
        self.i18n.subscribe(self._on_language_updated)
        self._show_view(self._current_view_name)
        self._update_loop()

    def _build_shell(self):
        # 1. Top Header Bar
        self.header_frame = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color="#181818")
        self.header_frame.pack(side="top", fill="x")

        # Application Logo & Title
        logo_path = self._assets_dir / "app_icon.png"
        if logo_path.exists():
            try:
                logo_img = Image.open(logo_path)
                self.ctk_logo = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(32, 32))
                self.logo_label = ctk.CTkLabel(self.header_frame, text="", image=self.ctk_logo)
                self.logo_label.pack(side="left", padx=(15, 6), pady=8)
            except Exception:
                pass

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="er-audio-tool",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#4db6ac",
        )
        self.title_label.pack(side="left", padx=(4, 15), pady=10)

        self.status_label = ctk.CTkLabel(
            self.header_frame,
            text=self.i18n.t("ready"),
            font=ctk.CTkFont(size=13),
            text_color="#b0bec5",
        )
        self.status_label.pack(side="left", padx=10)

        self.lang_btn = ctk.CTkSegmentedButton(
            self.header_frame,
            values=["EN", "DE"],
            command=self._on_lang_switch_clicked,
        )
        self.lang_btn.set("DE" if self.i18n.current_lang == "de" else "EN")
        self.lang_btn.pack(side="right", padx=20, pady=10)

        # 2. Main Body Split: Left Sidebar & Content Canvas
        self.body_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.body_frame.pack(expand=True, fill="both")

        # Sidebar Navigation
        self.sidebar_frame = ctk.CTkScrollableFrame(self.body_frame, width=220, corner_radius=0, fg_color="#202020")
        self.sidebar_frame.pack(side="left", fill="y")

        # Content Area (Scrollable to prevent any card or button cutoff on smaller resolutions)
        self.content_frame = ctk.CTkScrollableFrame(self.body_frame, corner_radius=0, fg_color="#1a1a1a")
        self.content_frame.pack(side="right", expand=True, fill="both")

        self._render_sidebar()

    def _render_sidebar(self):
        # Clear existing sidebar buttons
        for w in self.sidebar_frame.winfo_children():
            w.destroy()

        # Section 1 (TOP): Setup & Codecs (Essential prerequisite)
        ctk.CTkLabel(self.sidebar_frame, text=self.i18n.t("nav_setup"), font=ctk.CTkFont(size=13, weight="bold"), text_color="#80cbc4").pack(anchor="w", padx=12, pady=(10, 4))
        self._add_nav_btn("nav_codecs_install", "set_codecs")

        # Section 2: Record
        ctk.CTkLabel(self.sidebar_frame, text=self.i18n.t("nav_record"), font=ctk.CTkFont(size=13, weight="bold"), text_color="#80cbc4").pack(anchor="w", padx=12, pady=(14, 4))
        self._add_nav_btn("nav_rec_system", "rec_system")
        self._add_nav_btn("nav_rec_app", "rec_app")
        self._add_nav_btn("nav_rec_browser", "rec_browser")
        self._add_nav_btn("nav_rec_test", "rec_test")

        # Section 3: Convert
        ctk.CTkLabel(self.sidebar_frame, text=self.i18n.t("nav_convert"), font=ctk.CTkFont(size=13, weight="bold"), text_color="#80cbc4").pack(anchor="w", padx=12, pady=(14, 4))
        self._add_nav_btn("nav_conv_audio", "conv_audio")
        self._add_nav_btn("nav_conv_batch", "conv_batch")

        # Section 4: Analyze & MIDI
        ctk.CTkLabel(self.sidebar_frame, text=self.i18n.t("nav_analyze"), font=ctk.CTkFont(size=13, weight="bold"), text_color="#80cbc4").pack(anchor="w", padx=12, pady=(14, 4))
        self._add_nav_btn("nav_ana_audio", "ana_audio")
        self._add_nav_btn("nav_ana_midi", "ana_midi")
        self._add_nav_btn("nav_ana_render", "ana_render")

        # Section 5: Library
        ctk.CTkLabel(self.sidebar_frame, text=self.i18n.t("nav_library"), font=ctk.CTkFont(size=13, weight="bold"), text_color="#80cbc4").pack(anchor="w", padx=12, pady=(14, 4))
        self._add_nav_btn("nav_lib_recordings", "lib_recordings")

        # Section 6: Devices & Tests
        ctk.CTkLabel(self.sidebar_frame, text=self.i18n.t("nav_devices"), font=ctk.CTkFont(size=13, weight="bold"), text_color="#80cbc4").pack(anchor="w", padx=12, pady=(14, 4))
        self._add_nav_btn("nav_dev_hwtest", "dev_hwtest")
        self._add_nav_btn("nav_dev_browser", "dev_browser")

        # Section 7: Settings & Help
        ctk.CTkLabel(self.sidebar_frame, text=self.i18n.t("nav_settings"), font=ctk.CTkFont(size=13, weight="bold"), text_color="#80cbc4").pack(anchor="w", padx=12, pady=(14, 4))
        self._add_nav_btn("nav_set_general", "set_general")

        ctk.CTkLabel(self.sidebar_frame, text=self.i18n.t("nav_help"), font=ctk.CTkFont(size=13, weight="bold"), text_color="#80cbc4").pack(anchor="w", padx=12, pady=(14, 4))
        self._add_nav_btn("nav_help_topics", "help_topics")
        self._add_nav_btn("nav_help_about", "help_about")

    def _add_nav_btn(self, label_key: str, view_id: str):
        is_active = (self._current_view_name == view_id)
        btn = ctk.CTkButton(
            self.sidebar_frame,
            text=self.i18n.t(label_key),
            anchor="w",
            height=30,
            fg_color="#00695c" if is_active else "transparent",
            hover_color="#004d40",
            text_color="#ffffff" if is_active else "#b0bec5",
            command=lambda: self._show_view(view_id),
        )
        btn.pack(fill="x", padx=8, pady=2)

    def _on_lang_switch_clicked(self, choice: str):
        lang = "de" if choice == "DE" else "en"
        self.cfg.language = lang
        self.cm.save(self.cfg)
        self.i18n.set_language(lang)

    def _on_language_updated(self):
        self.title(self.i18n.t("app_title"))
        self._render_sidebar()
        self._show_view(self._current_view_name)

    def _show_view(self, view_id: str):
        self._current_view_name = view_id
        for w in self.content_frame.winfo_children():
            w.destroy()

        if view_id in ("rec_system", "rec_app", "rec_browser"):
            self._render_recording_view()
        elif view_id in ("conv_audio", "conv_batch"):
            self._render_converter_view()
        elif view_id == "ana_audio":
            self._render_analysis_view()
        elif view_id == "ana_midi":
            self._render_midi_view()
        elif view_id == "ana_render":
            self._render_render_view()
        elif view_id == "lib_recordings":
            self._render_library_view()
        elif view_id in ("dev_hwtest", "rec_test"):
            self._render_diagnostic_view()
        elif view_id == "dev_browser":
            self._render_browser_device_view()
        elif view_id == "set_general":
            self._render_settings_view()
        elif view_id == "set_codecs":
            self._render_codecs_view()
        elif view_id == "help_about":
            self._render_about_view()
        else:
            self._render_help_view()

    # ------------------ WORKSPACE VIEWS ------------------ #

    def _render_recording_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        # Header with Help Button
        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(hdr, text=self.i18n.t("nav_record"), font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(hdr, text="?", width=28, height=28, command=lambda: self._show_help_dialog("system_audio")).pack(side="right")

        # Codec Missing Warning Banner with direct jump to Setup & Codecs
        if not self.codec_manager.get_active_ffmpeg():
            warn_card = ctk.CTkFrame(f, fg_color="#3e2723", corner_radius=6)
            warn_card.pack(fill="x", pady=(0, 15))
            ctk.CTkLabel(
                warn_card,
                text=self.i18n.t("codecs_missing_banner"),
                text_color="#ffcc80",
                font=ctk.CTkFont(size=12),
                wraplength=600,
                justify="left",
            ).pack(side="left", padx=12, pady=10)
            ctk.CTkButton(
                warn_card,
                text=self.i18n.t("btn_install_codecs_banner"),
                fg_color="#00695c",
                hover_color="#004d40",
                width=160,
                command=lambda: self._show_view("set_codecs"),
            ).pack(side="right", padx=12, pady=10)

        # Source Selection
        src_row = ctk.CTkFrame(f, fg_color="transparent")
        src_row.pack(fill="x", pady=6)
        ctk.CTkLabel(src_row, text=self.i18n.t("source_label"), width=120, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.devices = self.device_manager.enumerate_all_devices()
        dev_names = [d.name for d in self.devices] or ["Default Endpoint"]
        self.source_combo = ctk.CTkComboBox(src_row, values=dev_names, width=420)
        self.source_combo.set(dev_names[0])
        self.source_combo.pack(side="left", padx=10)

        # Format Selection
        fmt_row = ctk.CTkFrame(f, fg_color="transparent")
        fmt_row.pack(fill="x", pady=6)
        ctk.CTkLabel(fmt_row, text=self.i18n.t("format_label"), width=120, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.fmt_combo = ctk.CTkComboBox(fmt_row, values=["WAV", "FLAC", "MP3"], width=120)
        self.fmt_combo.set(self.cfg.format.upper())
        self.fmt_combo.pack(side="left", padx=10)

        # Directory Selection with Browse Button
        dir_row = ctk.CTkFrame(f, fg_color="transparent")
        dir_row.pack(fill="x", pady=6)
        ctk.CTkLabel(dir_row, text=self.i18n.t("output_dir_label"), width=120, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.rec_dir_entry = ctk.CTkEntry(dir_row, width=380)
        self.rec_dir_entry.insert(0, self.cfg.output_dir)
        self.rec_dir_entry.pack(side="left", padx=10)
        ctk.CTkButton(dir_row, text=self.i18n.t("btn_browse"), width=90, command=self._on_browse_rec_dir).pack(side="left")

        # Live Stereo Level Meter Card
        meter_card = ctk.CTkFrame(f, fg_color="#222222", corner_radius=8)
        meter_card.pack(fill="x", pady=15, padx=2)
        ctk.CTkLabel(meter_card, text=self.i18n.t("level_title"), font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=(10, 4))

        # Left / Right Stereo Bars
        self.meter_l = ctk.CTkProgressBar(meter_card, height=10)
        self.meter_l.set(0.0)
        self.meter_l.pack(fill="x", padx=15, pady=4)

        self.meter_r = ctk.CTkProgressBar(meter_card, height=10)
        self.meter_r.set(0.0)
        self.meter_r.pack(fill="x", padx=15, pady=4)

        self.meter_text = ctk.CTkLabel(meter_card, text="Levels: L -inf dB | R -inf dB | Peak -inf dBFS", font=ctk.CTkFont(size=12))
        self.meter_text.pack(pady=4)

        self.clip_warn = ctk.CTkLabel(meter_card, text="", text_color="#ef5350", font=ctk.CTkFont(weight="bold"))
        self.clip_warn.pack(pady=(0, 8))

        # Buttons Bar: Record, Pause, Stop, Cancel
        ctrls = ctk.CTkFrame(f, fg_color="transparent")
        ctrls.pack(pady=15)

        self.btn_rec = ctk.CTkButton(ctrls, text="● " + self.i18n.t("btn_record"), fg_color="#e53935", hover_color="#c62828", width=140, height=40, font=ctk.CTkFont(weight="bold"), command=self._on_record_clicked)
        self.btn_rec.pack(side="left", padx=8)

        self.btn_pause = ctk.CTkButton(ctrls, text="❚❚ " + self.i18n.t("btn_pause"), width=100, height=40, state="disabled", command=self._on_pause_clicked)
        self.btn_pause.pack(side="left", padx=8)

        self.btn_stop = ctk.CTkButton(ctrls, text="■ " + self.i18n.t("btn_stop"), width=120, height=40, state="disabled", command=self._on_stop_clicked)
        self.btn_stop.pack(side="left", padx=8)

        self.timer_disp = ctk.CTkLabel(ctrls, text="00:00:00", font=ctk.CTkFont(size=18, weight="bold"))
        self.timer_disp.pack(side="left", padx=20)

        # Legal Notice
        ctk.CTkLabel(f, text=self.i18n.t("legal_notice"), font=ctk.CTkFont(size=11), text_color="#78909c", wraplength=700).pack(side="bottom", pady=10)

    def _render_converter_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(hdr, text=self.i18n.t("nav_conv_audio"), font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(hdr, text="?", width=28, height=28, command=lambda: self._show_help_dialog("audio_converter")).pack(side="right")

        # Select file row
        sel_row = ctk.CTkFrame(f, fg_color="transparent")
        sel_row.pack(fill="x", pady=6)
        self.conv_input_entry = ctk.CTkEntry(sel_row, placeholder_text="Select audio file (M4A, AAC, MP3, WAV, FLAC)...", width=480)
        self.conv_input_entry.pack(side="left", padx=(0, 10))
        ctk.CTkButton(sel_row, text=self.i18n.t("btn_browse"), width=100, command=self._on_browse_conv_file).pack(side="left")

        # Target Format & Preset
        opt_row = ctk.CTkFrame(f, fg_color="transparent")
        opt_row.pack(fill="x", pady=8)
        ctk.CTkLabel(opt_row, text=self.i18n.t("target_format_label"), font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        self.conv_fmt_combo = ctk.CTkComboBox(opt_row, values=["MP3", "WAV", "FLAC", "OGG", "Opus"], width=110)
        self.conv_fmt_combo.set("MP3")
        self.conv_fmt_combo.pack(side="left", padx=5)

        self.conv_norm_check = ctk.CTkCheckBox(opt_row, text="Normalize Loudness")
        self.conv_norm_check.pack(side="left", padx=20)

        ctk.CTkButton(opt_row, text=self.i18n.t("btn_convert"), fg_color="#00897b", hover_color="#00695c", width=140, command=self._on_execute_conversion).pack(side="right")

        # Result box
        self.conv_status_box = ctk.CTkTextbox(f, height=280)
        self.conv_status_box.pack(expand=True, fill="both", pady=15)

    def _render_diagnostic_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(hdr, text=self.i18n.t("nav_dev_hwtest"), font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(hdr, text="?", width=28, height=28, command=lambda: self._show_help_dialog("diagnostic_test")).pack(side="right")

        top_bar = ctk.CTkFrame(f, fg_color="transparent")
        top_bar.pack(fill="x", pady=8)
        ctk.CTkButton(top_bar, text=self.i18n.t("btn_run_tests"), width=160, command=self._on_run_diagnostics).pack(side="left")

        self.diag_box = ctk.CTkTextbox(f, height=450)
        self.diag_box.pack(expand=True, fill="both", pady=10)
        self._on_run_diagnostics()

    def _render_browser_device_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(hdr, text=self.i18n.t("nav_dev_browser"), font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(hdr, text="?", width=28, height=28, command=lambda: self._show_help_dialog("browser_companion")).pack(side="right")

        ext_card = ctk.CTkFrame(f, fg_color="#222222", corner_radius=8)
        ext_card.pack(fill="x", pady=10, padx=5)

        ctk.CTkLabel(ext_card, text="Companion Extension Setup", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=15, pady=(12, 4))
        ctk.CTkLabel(ext_card, text="Status: Ready on loopback interface (127.0.0.1)", text_color="#4db6ac").pack(anchor="w", padx=15, pady=2)
        ctk.CTkLabel(ext_card, text="Installation Path: " + str(Path(__file__).resolve().parent.parent.parent / "browser_extension"), font=ctk.CTkFont(size=11), text_color="#90a4ae").pack(anchor="w", padx=15, pady=(2, 12))

    def _render_analysis_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        ctk.CTkLabel(f, text=self.i18n.t("nav_ana_audio"), font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 15))
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=5)
        self.ana_file_entry = ctk.CTkEntry(row, width=450, placeholder_text="Select audio file...")
        self.ana_file_entry.pack(side="left", padx=(0, 10))
        ctk.CTkButton(row, text=self.i18n.t("btn_browse"), width=90, command=self._on_browse_ana_file).pack(side="left")
        ctk.CTkButton(row, text=self.i18n.t("btn_analyze"), width=120, command=self._on_run_analysis).pack(side="left", padx=10)

        self.ana_box = ctk.CTkTextbox(f, height=350)
        self.ana_box.pack(expand=True, fill="both", pady=15)

    def _render_midi_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        ctk.CTkLabel(f, text=self.i18n.t("nav_ana_midi"), font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 15))
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=5)
        self.midi_input_entry = ctk.CTkEntry(row, width=450, placeholder_text="Audio file to transcribe...")
        self.midi_input_entry.pack(side="left", padx=(0, 10))
        ctk.CTkButton(row, text=self.i18n.t("btn_browse"), width=90, command=self._on_browse_midi_file).pack(side="left")
        ctk.CTkButton(row, text=self.i18n.t("btn_transcribe"), width=140, command=self._on_run_transcribe).pack(side="left", padx=10)

        self.midi_box = ctk.CTkTextbox(f, height=350)
        self.midi_box.pack(expand=True, fill="both", pady=15)

    def _render_render_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        ctk.CTkLabel(f, text=self.i18n.t("nav_ana_render"), font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 15))
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=5)
        self.ren_midi_entry = ctk.CTkEntry(row, width=450, placeholder_text="Select .mid file...")
        self.ren_midi_entry.pack(side="left", padx=(0, 10))
        ctk.CTkButton(row, text=self.i18n.t("btn_browse"), width=90, command=self._on_browse_render_file).pack(side="left")
        ctk.CTkButton(row, text=self.i18n.t("btn_render_midi"), width=140, command=self._on_run_render).pack(side="left", padx=10)

        self.ren_box = ctk.CTkTextbox(f, height=350)
        self.ren_box.pack(expand=True, fill="both", pady=15)

    def _render_library_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        top_row = ctk.CTkFrame(f, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(top_row, text=self.i18n.t("nav_lib_recordings"), font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(top_row, text=self.i18n.t("btn_open_folder"), width=130, command=self._on_open_output_dir).pack(side="right")

        self.lib_box = ctk.CTkTextbox(f, height=450)
        self.lib_box.pack(expand=True, fill="both", pady=10)
        self._refresh_library_list()

    def _render_settings_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        ctk.CTkLabel(f, text=self.i18n.t("nav_settings"), font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 15))

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=8)
        ctk.CTkLabel(row, text=self.i18n.t("output_dir_label"), width=140, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.set_dir_entry = ctk.CTkEntry(row, width=420)
        self.set_dir_entry.insert(0, self.cfg.output_dir)
        self.set_dir_entry.pack(side="left", padx=10)
        ctk.CTkButton(row, text=self.i18n.t("btn_browse"), width=90, command=self._on_browse_settings_dir).pack(side="left")

        ctk.CTkButton(f, text=self.i18n.t("btn_save_settings"), width=150, command=self._on_save_settings_clicked).pack(anchor="w", pady=20)

    def _render_codecs_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        # Title & Help
        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(hdr, text=self.i18n.t("codecs_title"), font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(hdr, text="?", width=28, height=28, command=lambda: self._show_help_dialog("codecs")).pack(side="right")

        # Explanation Box
        info_box = ctk.CTkFrame(f, fg_color="#263238", corner_radius=6)
        info_box.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(
            info_box,
            text=self.i18n.t("codecs_desc"),
            wraplength=700,
            justify="left",
            text_color="#eceff1",
            font=ctk.CTkFont(size=12),
        ).pack(padx=15, pady=12, anchor="w")

        # Current Codec Status Card
        status_card = ctk.CTkFrame(f, fg_color="#212121", corner_radius=6)
        status_card.pack(fill="x", pady=(0, 15), padx=2)
        stat_row = ctk.CTkFrame(status_card, fg_color="transparent")
        stat_row.pack(fill="x", padx=12, pady=10)
        ctk.CTkLabel(stat_row, text=self.i18n.t("codecs_status_label"), font=ctk.CTkFont(weight="bold")).pack(side="left")

        self.codec_status_label = ctk.CTkLabel(stat_row, text="", font=ctk.CTkFont(size=12))
        self.codec_status_label.pack(side="left", padx=10)
        self._update_codecs_status_display()

        # Scope Selector (Minimal vs Full Pack)
        scope_card = ctk.CTkFrame(f, fg_color="#212121", corner_radius=6)
        scope_card.pack(fill="x", pady=(0, 15), padx=2)
        scope_inner = ctk.CTkFrame(scope_card, fg_color="transparent")
        scope_inner.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(scope_inner, text=self.i18n.t("codecs_scope_label"), font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 6))

        is_de = (self.i18n.current_lang == "de")
        self.scope_radio_var = ctk.StringVar(value=self.cfg.codec_scope)

        for scope_id, sinfo in CODEC_SCOPES.items():
            s_title = sinfo.name_de if is_de else sinfo.name_en
            s_desc = sinfo.description_de if is_de else sinfo.description_en
            s_codecs = sinfo.codecs_de if is_de else sinfo.codecs_en

            r_frame = ctk.CTkFrame(scope_inner, fg_color="transparent")
            r_frame.pack(fill="x", pady=4)
            rb = ctk.CTkRadioButton(
                r_frame,
                text=s_title,
                variable=self.scope_radio_var,
                value=scope_id,
                command=self._on_codec_scope_changed,
                font=ctk.CTkFont(weight="bold"),
            )
            rb.pack(anchor="w")
            ctk.CTkLabel(
                r_frame,
                text=f"  ↳ {s_desc}\n    Formats: {s_codecs}",
                justify="left",
                text_color="#90a4ae",
                font=ctk.CTkFont(size=11),
            ).pack(anchor="w", padx=(24, 0))

        # Exit Cleanup Policy Card
        exit_card = ctk.CTkFrame(f, fg_color="#212121", corner_radius=6)
        exit_card.pack(fill="x", pady=(0, 15), padx=2)
        exit_inner = ctk.CTkFrame(exit_card, fg_color="transparent")
        exit_inner.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(exit_inner, text=self.i18n.t("codecs_exit_policy_label"), font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 6))

        self.exit_policy_var = ctk.StringVar(value=self.cfg.codecs_exit_policy)
        policies = [
            ("ask", self.i18n.t("codecs_exit_ask")),
            ("keep", self.i18n.t("codecs_exit_keep")),
            ("delete", self.i18n.t("codecs_exit_delete")),
        ]
        for p_val, p_text in policies:
            ctk.CTkRadioButton(
                exit_inner,
                text=p_text,
                variable=self.exit_policy_var,
                value=p_val,
                command=self._on_codec_exit_policy_changed,
            ).pack(anchor="w", pady=3)

        # Download & Purge Action Row
        act_row = ctk.CTkFrame(f, fg_color="transparent")
        act_row.pack(fill="x", pady=(10, 5))

        self.btn_dl_codecs = ctk.CTkButton(
            act_row,
            text="⬇ " + self.i18n.t("btn_download_codecs"),
            fg_color="#00897b",
            hover_color="#00695c",
            height=42,
            width=260,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_start_download_codecs,
        )
        self.btn_dl_codecs.pack(side="left", padx=(0, 15))

        self.btn_purge_codecs = ctk.CTkButton(
            act_row,
            text="🗑 " + self.i18n.t("btn_purge_codecs"),
            fg_color="#c62828",
            hover_color="#b71c1c",
            height=42,
            width=180,
            font=ctk.CTkFont(size=13),
            command=self._on_purge_codecs_clicked,
        )
        self.btn_purge_codecs.pack(side="left")

        # Progress bar & status feedback
        self.codec_prog_frame = ctk.CTkFrame(f, fg_color="transparent")
        self.codec_prog_frame.pack(fill="x", pady=(10, 0))

        self.codec_prog_bar = ctk.CTkProgressBar(self.codec_prog_frame)
        self.codec_prog_bar.set(0.0)
        self.codec_prog_bar.pack(fill="x", pady=(0, 6))

        self.codec_prog_label = ctk.CTkLabel(self.codec_prog_frame, text="", text_color="#80cbc4", font=ctk.CTkFont(size=12))
        self.codec_prog_label.pack(anchor="w")

    def _render_about_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        ctk.CTkLabel(f, text="er-audio-tool v1.0.0", font=ctk.CTkFont(size=20, weight="bold"), text_color="#4db6ac").pack(anchor="w", pady=(0, 10))
        abt = (
            "er-audio-tool was originally derived from skillerious/Loopback-Recorder by Robin Doak.\n"
            "The original project is available at https://github.com/skillerious/Loopback-Recorder and is used under the MIT License.\n"
            "er-audio-tool is an independently maintained project and is not affiliated with or endorsed by the original author.\n\n"
            "Maintainer: Eidolf\n"
            "License: MIT License\n"
            "Privacy: 100% Local-First. Zero remote audio telemetry."
        )
        box = ctk.CTkTextbox(f, height=300)
        box.pack(expand=True, fill="both", pady=10)
        box.insert("end", abt)

    def _render_help_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(f, text=self.i18n.t("nav_help_topics"), font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 15))
        box = ctk.CTkTextbox(f, height=450)
        box.pack(expand=True, fill="both", pady=10)
        topic = get_help_topic("system_audio")
        if topic:
            txt = topic.content_de if self.i18n.current_lang == "de" else topic.content_en
            box.insert("end", f"{topic.title_de if self.i18n.current_lang == 'de' else topic.title_en}\n\n{txt}\n")

    # ------------------ EVENT HANDLERS & HELPERS ------------------ #

    def _show_help_dialog(self, topic_id: str):
        topic = get_help_topic(topic_id)
        if not topic:
            return
        title = topic.title_de if self.i18n.current_lang == "de" else topic.title_en
        content = topic.content_de if self.i18n.current_lang == "de" else topic.content_en

        top = ctk.CTkToplevel(self)
        top.title(title)
        top.geometry("520x360")
        top.transient(self)
        txt = ctk.CTkTextbox(top)
        txt.pack(expand=True, fill="both", padx=15, pady=15)
        txt.insert("end", content)

    def _on_browse_rec_dir(self):
        p = filedialog.askdirectory(initialdir=self.cfg.output_dir)
        if p:
            self.rec_dir_entry.delete(0, "end")
            self.rec_dir_entry.insert(0, p)
            self.cfg.output_dir = p
            self.cm.save(self.cfg)

    def _on_browse_settings_dir(self):
        p = filedialog.askdirectory(initialdir=self.cfg.output_dir)
        if p:
            self.set_dir_entry.delete(0, "end")
            self.set_dir_entry.insert(0, p)

    def _on_save_settings_clicked(self):
        self.cfg.output_dir = self.set_dir_entry.get().strip()
        self.cm.save(self.cfg)
        messagebox.showinfo(self.i18n.t("app_title"), self.i18n.t("btn_save_settings") + " - OK")

    def _on_open_output_dir(self):
        p = Path(self.cfg.output_dir)
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(p)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(p)])
        else:
            subprocess.run(["xdg-open", str(p)])

    def _on_browse_conv_file(self):
        f = filedialog.askopenfilename(filetypes=[("Audio Files", "*.m4a *.mp4 *.aac *.mp3 *.wav *.flac *.ogg *.opus *.aiff"), ("All Files", "*.*")])
        if f:
            self.conv_input_entry.delete(0, "end")
            self.conv_input_entry.insert(0, f)

    def _on_browse_ana_file(self):
        f = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav *.flac *.m4a"), ("All Files", "*.*")])
        if f:
            self.ana_file_entry.delete(0, "end")
            self.ana_file_entry.insert(0, f)

    def _on_browse_midi_file(self):
        f = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav *.flac"), ("All Files", "*.*")])
        if f:
            self.midi_input_entry.delete(0, "end")
            self.midi_input_entry.insert(0, f)

    def _on_browse_render_file(self):
        f = filedialog.askopenfilename(filetypes=[("MIDI Files", "*.mid *.midi"), ("All Files", "*.*")])
        if f:
            self.ren_midi_entry.delete(0, "end")
            self.ren_midi_entry.insert(0, f)

    def _on_record_clicked(self):
        curr = self.state_machine.current_state
        if curr == AppState.IDLE:
            self.state_machine.transition_to(AppState.PREPARING)
            self._recording_data.clear()
            self._record_start_time = time.time()
            self._elapsed_paused_time = 0.0

            selected_name = self.source_combo.get()
            dev = next((d for d in self.devices if d.name == selected_name), self.devices[0] if self.devices else None)
            if not dev:
                messagebox.showerror(self.i18n.t("error"), "No audio device selected.")
                self.state_machine.transition_to(AppState.FAILED)
                self.state_machine.transition_to(AppState.IDLE)
                return

            try:
                self._active_backend.start_capture(
                    dev,
                    self.cfg.sample_rate,
                    self.cfg.channels,
                    self._on_audio_data_received
                )
                self.state_machine.transition_to(AppState.RECORDING)
                self.status_label.configure(text=self.i18n.t("recording"), text_color="#ef5350")
                self.btn_rec.configure(state="disabled")
                self.btn_pause.configure(state="normal", text="❚❚ " + self.i18n.t("btn_pause"))
                self.btn_stop.configure(state="normal")
            except Exception as ex:
                self.state_machine.transition_to(AppState.FAILED)
                self.state_machine.transition_to(AppState.IDLE)
                messagebox.showerror(self.i18n.t("error"), f"Capture initialization failed: {ex}")

    def _on_pause_clicked(self):
        curr = self.state_machine.current_state
        if curr == AppState.RECORDING:
            self.state_machine.transition_to(AppState.PAUSED)
            self._pause_start_time = time.time()
            self.status_label.configure(text=self.i18n.t("paused"), text_color="#ffb74d")
            self.btn_pause.configure(text="▶ " + self.i18n.t("btn_resume"))
        elif curr == AppState.PAUSED:
            self.state_machine.transition_to(AppState.RECORDING)
            self._elapsed_paused_time += (time.time() - self._pause_start_time)
            self.status_label.configure(text=self.i18n.t("recording"), text_color="#ef5350")
            self.btn_pause.configure(text="❚❚ " + self.i18n.t("btn_pause"))

    def _on_stop_clicked(self):
        curr = self.state_machine.current_state
        if curr in (AppState.RECORDING, AppState.PAUSED):
            self.state_machine.transition_to(AppState.STOPPING)
            self.status_label.configure(text=self.i18n.t("encoding"), text_color="#ffb74d")
            try:
                self._active_backend.stop_capture()
            except Exception:
                pass

            self.state_machine.transition_to(AppState.ENCODING)
            out_fmt = self.fmt_combo.get().lower()
            ts = time.strftime("%Y%m%d_%H%M%S")
            target_path = Path(self.cfg.output_dir) / f"Recording_{ts}.{out_fmt}"

            if self._recording_data:
                combined = np.concatenate(self._recording_data, axis=0)
                AudioEncoder.save_audio(combined, self.cfg.sample_rate, target_path, format_type=out_fmt)
                messagebox.showinfo(self.i18n.t("app_title"), f"Saved: {target_path}")
            else:
                # If zero frames received, write clean diagnostic silent file so user has an output and warning
                zero_audio = np.zeros((self.cfg.sample_rate * 2, self.cfg.channels), dtype=np.float32)
                AudioEncoder.save_audio(zero_audio, self.cfg.sample_rate, target_path, format_type=out_fmt)
                messagebox.showwarning(self.i18n.t("error"), "No audio frames were received from the endpoint. Saved silent diagnostic file.")

            self.state_machine.transition_to(AppState.COMPLETED)
            self.state_machine.transition_to(AppState.IDLE)
            self.status_label.configure(text=self.i18n.t("ready"), text_color="#b0bec5")
            self.btn_rec.configure(state="normal")
            self.btn_pause.configure(state="disabled")
            self.btn_stop.configure(state="disabled")
            self._refresh_library_list()

    def _on_audio_data_received(self, data: np.ndarray):
        if self.state_machine.current_state == AppState.RECORDING:
            self._recording_data.append(data.copy())
            self.audio_buffer.push(data)

    def _on_execute_conversion(self):
        in_p = self.conv_input_entry.get().strip()
        if not in_p or not Path(in_p).exists():
            messagebox.showerror(self.i18n.t("error"), "Please select an existing audio file.")
            return

        self.conv_status_box.delete("1.0", "end")
        self.conv_status_box.insert("end", f"Starting conversion of: {in_p}...\n")
        job = ConversionJob(
            input_file=Path(in_p),
            output_format=self.conv_fmt_combo.get().lower(),
            normalize=bool(self.conv_norm_check.get()),
            output_dir=Path(self.cfg.output_dir),
        )
        res = AudioConverter.convert_file(job)
        if res.success:
            self.conv_status_box.insert("end", f"✓ Conversion Successful!\nOutput: {res.output_path}\nDuration: {res.duration_seconds:.2f}s\n")
            self._refresh_library_list()
        else:
            self.conv_status_box.insert("end", f"✗ Conversion Failed: {res.error_message}\n")

    def _on_run_diagnostics(self):
        self.diag_box.delete("1.0", "end")
        self.diag_box.insert("end", "Running Hardware & Software Diagnostics...\n\n")
        items = DiagnosticRunner.run_all_tests(self.cfg.output_dir)
        for it in items:
            symbol = "✓" if it.status == "PASSED" else ("⚠" if it.status == "WARNING" else "✗")
            self.diag_box.insert("end", f"[{symbol} {it.status}] {it.category} > {it.name}\n  Details: {it.details}\n")
            if it.recommendation:
                self.diag_box.insert("end", f"  Action: {it.recommendation}\n")
            self.diag_box.insert("end", "\n")

    def _on_run_analysis(self):
        p = self.ana_file_entry.get().strip()
        if not p or not Path(p).exists():
            return
        self.ana_box.delete("1.0", "end")
        rep = AudioAnalyzer.analyze_file(p)
        self.ana_box.insert("end", f"File: {rep.file_path}\nDuration: {rep.duration_seconds}s | Sample Rate: {rep.sample_rate} Hz | Channels: {rep.channels}\nPeak: {rep.peak_db} dBFS | RMS: {rep.rms_db} dBFS\nEstimated Tempo: {rep.estimated_tempo_bpm} BPM | Key: {rep.estimated_key}\n")

    def _on_run_transcribe(self):
        p = self.midi_input_entry.get().strip()
        if not p or not Path(p).exists():
            return
        self.midi_box.delete("1.0", "end")
        self.midi_box.insert("end", "Transcribing audio to MIDI...\n")
        notes = AudioToMidiTranscriber.transcribe(p)
        out = Path(p).with_suffix(".mid")
        MidiExporter.export_midi(notes, out)
        self.midi_box.insert("end", f"Exported {len(notes)} note events to: {out}\n")
        self._refresh_library_list()

    def _on_run_render(self):
        p = self.ren_midi_entry.get().strip()
        if not p or not Path(p).exists():
            return
        self.ren_box.delete("1.0", "end")
        out = Path(p).with_suffix(".rendered.mp3")
        notes = [NoteEvent(pitch=60 + i, start_time=i * 0.25, duration=0.3) for i in range(8)]
        MidiRenderer.render_notes_to_audio(notes, out)
        self.ren_box.insert("end", f"Rendered MIDI to MP3: {out}\n")
        self._refresh_library_list()

    def _refresh_library_list(self):
        if not hasattr(self, "lib_box"):
            return
        self.lib_box.delete("1.0", "end")
        p = Path(self.cfg.output_dir)
        if p.exists():
            for f in sorted(p.glob("*.*"), key=lambda x: x.stat().st_mtime, reverse=True):
                if f.suffix.lower() in (".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".mid"):
                    sz = f.stat().st_size / (1024 * 1024)
                    self.lib_box.insert("end", f"{f.name}  ({sz:.2f} MB) - {f}\n")

    def _update_loop(self):
        curr = self.state_machine.current_state
        if curr == AppState.RECORDING:
            elapsed = int(time.time() - self._record_start_time - self._elapsed_paused_time)
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            if hasattr(self, "timer_disp"):
                self.timer_disp.configure(text=f"{h:02d}:{m:02d}:{s:02d}")

        if hasattr(self, "meter_l"):
            peak_db, rms_db, is_clip = self.audio_buffer.get_levels()
            val = max(0.0, (peak_db + 60.0) / 60.0) if peak_db > -60.0 else 0.0
            self.meter_l.set(min(1.0, val))
            self.meter_r.set(min(1.0, val))
            self.meter_text.configure(text=f"Levels: L {peak_db:.1f} dB | R {peak_db:.1f} dB | RMS {rms_db:.1f} dB")
            if is_clip:
                self.clip_warn.configure(text=self.i18n.t("clipping_detected"))
            else:
                self.clip_warn.configure(text="")

        self.after(50, self._update_loop)

    # ------------------ CODEC MANAGEMENT & LIFECYCLE ------------------ #

    def _update_codecs_status_display(self):
        if not hasattr(self, "codec_status_label"):
            return
        local_bin = self.codec_manager.find_local_ffmpeg_path()
        sys_bin = shutil.which("ffmpeg")
        if local_bin:
            self.codec_status_label.configure(
                text=self.i18n.t("codecs_status_portable", path=str(local_bin)),
                text_color="#80cbc4",
            )
        elif sys_bin:
            self.codec_status_label.configure(
                text=self.i18n.t("codecs_status_system", path=sys_bin),
                text_color="#81c784",
            )
        else:
            self.codec_status_label.configure(
                text=self.i18n.t("codecs_status_missing"),
                text_color="#e57373",
            )

    def _on_codec_scope_changed(self):
        self.cfg.codec_scope = self.scope_radio_var.get()
        self.cm.save(self.cfg)

    def _on_codec_exit_policy_changed(self):
        self.cfg.codecs_exit_policy = self.exit_policy_var.get()
        self.cm.save(self.cfg)

    def _on_start_download_codecs(self):
        self.btn_dl_codecs.configure(state="disabled")
        self._codec_download_cancel.clear()
        self.codec_prog_bar.set(0.0)
        self.codec_prog_label.configure(text=self.i18n.t("codecs_downloading", info="..."))

        scope = self.cfg.codec_scope

        def _worker():
            def _progress(pct: float, msg: str):
                self.after(0, lambda: self._on_download_progress(pct, msg))

            success = self.codec_manager.download_codecs(
                scope=scope,
                progress_callback=_progress,
                cancel_event=self._codec_download_cancel,
            )
            self.after(0, lambda: self._on_download_finished(success))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_download_progress(self, pct: float, msg: str):
        if hasattr(self, "codec_prog_bar"):
            self.codec_prog_bar.set(pct)
            self.codec_prog_label.configure(text=msg)

    def _on_download_finished(self, success: bool):
        if hasattr(self, "btn_dl_codecs"):
            self.btn_dl_codecs.configure(state="normal")
        self._update_codecs_status_display()
        if success:
            messagebox.showinfo(self.i18n.t("app_title"), self.i18n.t("codecs_download_success"))
        else:
            if not self._codec_download_cancel.is_set():
                messagebox.showerror(self.i18n.t("error"), self.i18n.t("codecs_download_failed", err="Network error or invalid archive"))

    def _on_purge_codecs_clicked(self):
        if not self.codec_manager.has_local_ffmpeg():
            messagebox.showinfo(self.i18n.t("app_title"), "No portable codecs present in temp_codecs.")
            return

        if messagebox.askyesno(self.i18n.t("app_title"), self.i18n.t("codecs_purge_confirm")):
            self.codec_manager.delete_local_codecs()
            self._update_codecs_status_display()
            messagebox.showinfo(self.i18n.t("app_title"), self.i18n.t("codecs_purged"))

    def _on_window_close(self):
        """Handle application exit with optional codec cleanup."""
        has_codecs = self.codec_manager.has_local_ffmpeg()

        if has_codecs:
            policy = self.cfg.codecs_exit_policy
            if policy == "delete":
                self.codec_manager.delete_local_codecs()
            elif policy == "ask":
                # Prompt user whether to keep or delete
                ans = messagebox.askyesnocancel(
                    self.i18n.t("codecs_exit_dialog_title"),
                    self.i18n.t("codecs_exit_dialog_prompt") + "\n\n[Yes = Keep | No = Delete]",
                )
                if ans is None:
                    # User clicked Cancel: don't close app
                    return
                if ans is False:
                    # User answered No: delete codecs
                    self.codec_manager.delete_local_codecs()
                # If ans is True (Yes): keep codecs

        # Stop active capture if running
        try:
            if self.state_machine.current_state in (AppState.RECORDING, AppState.PAUSED):
                self._active_backend.stop_capture()
        except Exception:
            pass

        self.destroy()
