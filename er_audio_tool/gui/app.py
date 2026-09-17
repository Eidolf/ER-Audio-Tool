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

from er_audio_tool.utils.subprocess_helper import safe_run

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
from er_audio_tool.browser.server import BrowserServer
from er_audio_tool.browser.registry import BrowserConnectionRegistry, ConnectionState, ConnectionSnapshot
from er_audio_tool.version import get_version


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
        self.geometry("1240x840")
        self.minsize(1060, 720)

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
        self._monitoring_active = False

        # If codecs are missing, start directly on Setup & Codecs so user can setup immediately
        if not self.codec_manager.get_active_ffmpeg():
            self._current_view_name = "set_codecs"
        else:
            self._current_view_name = "rec_system"

        self.browser_registry = BrowserConnectionRegistry.get_instance()
        self.browser_server = BrowserServer(registry=self.browser_registry)
        self.device_manager.set_browser_server(self.browser_server)
        self.browser_server.start_background()
        self._token_visible = False
        self._current_session_id = None
        self._current_source_type = None

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
            text=f"er-audio-tool v{get_version()}",
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

        self._attach_sidebar_wheel_scrolling()
        self._render_sidebar()

    def _attach_sidebar_wheel_scrolling(self):
        """Attaches reliable mouse-wheel and keyboard routing to the sidebar canvas and child controls."""
        def _scroll_sidebar(delta):
            canvas = getattr(self.sidebar_frame, "_parent_canvas", None)
            if canvas and canvas.winfo_exists() and delta != 0:
                canvas.yview_scroll(delta, "units")

        def _on_sidebar_mousewheel(event):
            try:
                if sys.platform.startswith("win"):
                    raw_delta = getattr(event, "delta", 0)
                    delta = -int(raw_delta / 40) if raw_delta != 0 else 0
                    if delta == 0 and raw_delta > 0:
                        delta = -1
                    elif delta == 0 and raw_delta < 0:
                        delta = 1
                elif getattr(event, "num", None) == 4:
                    delta = -2
                elif getattr(event, "num", None) == 5:
                    delta = 2
                else:
                    raw_delta = getattr(event, "delta", 0)
                    delta = -int(raw_delta) if raw_delta != 0 else 1

                _scroll_sidebar(delta)
            except Exception:
                pass
            return "break"

        def _on_sidebar_key(event):
            try:
                canvas = getattr(self.sidebar_frame, "_parent_canvas", None)
                if not canvas or not canvas.winfo_exists():
                    return
                keysym = getattr(event, "keysym", "")
                if keysym in ("Prior", "Page_Up"):
                    canvas.yview_scroll(-5, "units")
                    return "break"
                elif keysym in ("Next", "Page_Down"):
                    canvas.yview_scroll(5, "units")
                    return "break"
                elif keysym == "Home":
                    canvas.yview_moveto(0.0)
                    return "break"
                elif keysym == "End":
                    canvas.yview_moveto(1.0)
                    return "break"
            except Exception:
                pass

        self._sidebar_wheel_handler = _on_sidebar_mousewheel
        self._sidebar_key_handler = _on_sidebar_key

        # Bind directly to sidebar frame and its internal canvas
        try:
            self._bind_wheel_to_sidebar_widget(self.sidebar_frame)
            canvas = getattr(self.sidebar_frame, "_parent_canvas", None)
            if canvas:
                self._bind_wheel_to_sidebar_widget(canvas)
        except Exception:
            pass

    def _bind_wheel_to_sidebar_widget(self, widget):
        """Recursively binds mouse-wheel and keyboard routing to any widget added to the sidebar."""
        w_handler = getattr(self, "_sidebar_wheel_handler", None)
        k_handler = getattr(self, "_sidebar_key_handler", None)
        if not widget:
            return
        try:
            if w_handler:
                widget.bind("<MouseWheel>", w_handler, add="+")
                widget.bind("<Button-4>", w_handler, add="+")
                widget.bind("<Button-5>", w_handler, add="+")
            if k_handler:
                widget.bind("<Prior>", k_handler, add="+")
                widget.bind("<Next>", k_handler, add="+")
                widget.bind("<Home>", k_handler, add="+")
                widget.bind("<End>", k_handler, add="+")
            for ch in widget.winfo_children():
                self._bind_wheel_to_sidebar_widget(ch)
        except Exception:
            pass

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
        self._bind_wheel_to_sidebar_widget(btn)

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
        if self._monitoring_active:
            self._stop_monitoring()
        self._current_view_name = view_id
        # Re-render sidebar so the active-highlight follows the current selection
        self._render_sidebar()
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

        # Source Mode Label and Description
        mode_hdr = "System Output Loopback"
        mode_desc = "Capture all audio playing through your speakers, headphones, or virtual audio endpoints."
        if self._current_view_name == "rec_app":
            mode_hdr = "Application Audio Capture"
            mode_desc = "Capture dedicated application audio streams or virtual application loopback devices."
        elif self._current_view_name == "rec_browser":
            mode_hdr = "Browser Tab Companion Capture"
            mode_desc = "Capture individual browser tabs streamed through the er-audio-tool companion extension."

        mode_card = ctk.CTkFrame(f, fg_color="#1b2831", corner_radius=6)
        mode_card.pack(fill="x", pady=(0, 12))
        
        m_row = ctk.CTkFrame(mode_card, fg_color="transparent")
        m_row.pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(m_row, text=mode_hdr, font=ctk.CTkFont(size=14, weight="bold"), text_color="#80deea").pack(side="left")
        if self._current_view_name == "rec_browser":
            b_btn_frame = ctk.CTkFrame(m_row, fg_color="transparent")
            b_btn_frame.pack(side="right")
            ctk.CTkButton(
                b_btn_frame,
                text="🔄 " + self.i18n.t("btn_recheck_readiness"),
                width=140,
                height=26,
                fg_color="#00695c",
                hover_color="#004d40",
                command=self._on_test_browser_connection_clicked,
            ).pack(side="right", padx=(6, 0))
            ctk.CTkButton(
                b_btn_frame,
                text="🔌 " + self.i18n.t("btn_test_conn"),
                width=120,
                height=26,
                fg_color="#00897b",
                hover_color="#00695c",
                command=lambda: self._show_view("dev_browser"),
            ).pack(side="right")

        ctk.CTkLabel(mode_card, text=mode_desc, font=ctk.CTkFont(size=11), text_color="#b0bec5").pack(anchor="w", padx=12, pady=(0, 4))
        if self._current_view_name == "rec_browser":
            snap = self.browser_registry.get_snapshot()
            st_text = f"• State: {snap.state.value} | Tab: {snap.selected_tab.title if snap.selected_tab else 'None'} | Gen: {snap.connection_generation} | Heartbeat: {snap.last_heartbeat_age_seconds:.0f}s ago"
            self.lbl_rec_browser_status = ctk.CTkLabel(mode_card, text=st_text, font=ctk.CTkFont(size=11, weight="bold"), text_color="#80deea" if snap.authenticated_session_id else "#ffb74d")
            self.lbl_rec_browser_status.pack(anchor="w", padx=12, pady=(0, 6))

        # Source Selection
        src_row = ctk.CTkFrame(f, fg_color="transparent")
        src_row.pack(fill="x", pady=6)
        ctk.CTkLabel(src_row, text=self.i18n.t("source_label"), width=120, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.devices = self.device_manager.enumerate_all_devices(self._current_view_name)

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

        # Live Stereo Level Meter Card with Monitor Toggle
        meter_card = ctk.CTkFrame(f, fg_color="#222222", corner_radius=8)
        meter_card.pack(fill="x", pady=15, padx=2)

        meter_hdr = ctk.CTkFrame(meter_card, fg_color="transparent")
        meter_hdr.pack(fill="x", padx=15, pady=(10, 4))
        ctk.CTkLabel(meter_hdr, text=self.i18n.t("level_title"), font=ctk.CTkFont(weight="bold")).pack(side="left")

        # Live Monitor Toggle Button in meter card
        self.btn_monitor = ctk.CTkButton(
            meter_hdr,
            text="🎧 " + self.i18n.t("btn_monitor_stop" if self._monitoring_active else "btn_monitor_start"),
            width=170,
            height=26,
            fg_color="#00695c" if self._monitoring_active else "#37474f",
            hover_color="#004d40" if self._monitoring_active else "#455a64",
            command=self._on_toggle_monitor_clicked,
        )
        self.btn_monitor.pack(side="right")

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
        self.diag_btn = ctk.CTkButton(top_bar, text=self.i18n.t("btn_run_tests"), width=160, command=self._on_run_diagnostics)
        self.diag_btn.pack(side="left")

        self.diag_capture_btn = ctk.CTkButton(
            top_bar,
            text=self.i18n.t("btn_test_capture"),
            fg_color="#00897b",
            hover_color="#00695c",
            width=160,
            command=self._on_run_capture_test_only,
        )
        self.diag_capture_btn.pack(side="left", padx=10)

        self.diag_status_lbl = ctk.CTkLabel(top_bar, text="Ready", text_color="#90a4ae", font=ctk.CTkFont(size=12))
        self.diag_status_lbl.pack(side="left", padx=15)

        self.diag_progress = ctk.CTkProgressBar(f, height=6)
        self.diag_progress.pack(fill="x", pady=(2, 8))
        self.diag_progress.set(0.0)

        self.diag_box = ctk.CTkTextbox(f, height=430)
        self.diag_box.pack(expand=True, fill="both", pady=5)
        self._on_run_diagnostics()

    def _render_browser_device_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(hdr, text=self.i18n.t("browser_pairing_title"), font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(hdr, text="?", width=28, height=28, command=lambda: self._show_help_dialog("browser_companion")).pack(side="right")

        # Persistent Extension Installation Card
        ext_p = self.cm.install_or_update_extension()
        ext_card = ctk.CTkFrame(f, fg_color="#222222", corner_radius=8)
        ext_card.pack(fill="x", pady=10)

        ctk.CTkLabel(ext_card, text=self.i18n.t("browser_path_label"), font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(12, 6))

        path_row = ctk.CTkFrame(ext_card, fg_color="transparent")
        path_row.pack(fill="x", padx=15, pady=(0, 8))
        self.browser_path_entry = ctk.CTkEntry(path_row, width=420)
        self.browser_path_entry.insert(0, str(ext_p.resolve()))
        self.browser_path_entry.configure(state="readonly")
        self.browser_path_entry.pack(side="left", padx=(0, 8))

        ctk.CTkButton(path_row, text=self.i18n.t("btn_copy_path"), width=100, command=self._on_copy_browser_path).pack(side="left", padx=4)
        ctk.CTkButton(path_row, text=self.i18n.t("btn_open_folder"), width=100, command=self._on_open_browser_folder).pack(side="left", padx=4)
        ctk.CTkButton(path_row, text=self.i18n.t("btn_reinstall_ext"), width=160, command=self._on_reinstall_extension).pack(side="left", padx=4)

        self.browser_path_status = ctk.CTkLabel(ext_card, text=self.i18n.t("ext_installed_msg"), font=ctk.CTkFont(size=11), text_color="#4db6ac")
        self.browser_path_status.pack(anchor="w", padx=15, pady=(2, 12))

        # Pairing Token Card
        token_card = ctk.CTkFrame(f, fg_color="#222222", corner_radius=8)
        token_card.pack(fill="x", pady=10)

        ctk.CTkLabel(token_card, text=self.i18n.t("browser_token_label"), font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(12, 6))

        tok_row = ctk.CTkFrame(token_card, fg_color="transparent")
        tok_row.pack(fill="x", padx=15, pady=(0, 8))

        self.browser_token_entry = ctk.CTkEntry(tok_row, width=420)
        curr_token = self.browser_server.auth_token if self.browser_server else "ready"
        self.browser_token_entry.insert(0, curr_token if self._token_visible else self.i18n.t("browser_token_masked"))
        self.browser_token_entry.configure(state="readonly")
        self.browser_token_entry.pack(side="left", padx=(0, 8))

        self.btn_toggle_tok = ctk.CTkButton(
            tok_row,
            text=self.i18n.t("btn_show_token") if not self._token_visible else self.i18n.t("btn_hide_token"),
            width=110,
            command=self._on_toggle_token_visibility,
        )
        self.btn_toggle_tok.pack(side="left", padx=4)

        ctk.CTkButton(tok_row, text=self.i18n.t("btn_copy_token"), width=110, command=self._on_copy_browser_token).pack(side="left", padx=4)
        ctk.CTkButton(tok_row, text=self.i18n.t("btn_regen_token"), width=150, command=self._on_regen_browser_token).pack(side="left", padx=4)

        self.browser_tok_status = ctk.CTkLabel(token_card, text=self.i18n.t("ext_status_ready"), font=ctk.CTkFont(size=11), text_color="#80cbc4")
        self.browser_tok_status.pack(anchor="w", padx=15, pady=(2, 12))

        # Live Extension Verification Status Card
        conn_card = ctk.CTkFrame(f, fg_color="#1a2327", corner_radius=8)
        conn_card.pack(fill="x", pady=10)
        
        c_hdr = ctk.CTkFrame(conn_card, fg_color="transparent")
        c_hdr.pack(fill="x", padx=15, pady=(12, 6))
        ctk.CTkLabel(c_hdr, text="Connection & Selected Tab Verification", font=ctk.CTkFont(size=14, weight="bold"), text_color="#80deea").pack(side="left")
        ctk.CTkButton(
            c_hdr,
            text="🔌 " + self.i18n.t("btn_test_conn"),
            width=140,
            fg_color="#00897b",
            hover_color="#00695c",
            command=self._on_test_browser_connection_clicked,
        ).pack(side="right")

        ext_state = "Connected & Authenticated" if self.browser_server.is_authenticated else ("Connected (Unauthenticated)" if self.browser_server.is_connected else "Waiting for Extension Connection")
        ext_color = "#4db6ac" if self.browser_server.is_authenticated else ("#ffb74d" if self.browser_server.is_connected else "#90a4ae")
        tab_info_str = f"{self.browser_server.selected_tab.title} (Tab ID: {self.browser_server.selected_tab.tab_id})" if self.browser_server.selected_tab else "None selected yet (Open extension popup to pick a tab)"

        v_inner = ctk.CTkFrame(conn_card, fg_color="transparent")
        v_inner.pack(fill="x", padx=15, pady=(0, 10))
        self.lbl_ext_handshake = ctk.CTkLabel(v_inner, text=f"• Extension Handshake: {ext_state}", text_color=ext_color, font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_ext_handshake.pack(anchor="w", pady=2)
        self.lbl_ext_tab = ctk.CTkLabel(v_inner, text=f"• Selected Browser Tab: {tab_info_str}", text_color="#eceff1", font=ctk.CTkFont(size=11))
        self.lbl_ext_tab.pack(anchor="w", pady=2)
        self.lbl_ext_frames = ctk.CTkLabel(v_inner, text=f"• Received Audio Frames: {self.browser_server.received_frames_count}", text_color="#b0bec5", font=ctk.CTkFont(size=11))
        self.lbl_ext_frames.pack(anchor="w", pady=2)

        # Setup Instructions Guide
        guide_card = ctk.CTkFrame(f, fg_color="#1e272c", corner_radius=8)
        guide_card.pack(fill="x", pady=10)
        ctk.CTkLabel(guide_card, text="Setup Guide (Chrome / Microsoft Edge)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#80deea").pack(anchor="w", padx=15, pady=(10, 4))
        
        guide_text = (
            "1. Click 'Copy Path' above to copy the stable extension directory.\n"
            "2. In your browser, open edge://extensions or chrome://extensions.\n"
            "3. Enable 'Developer mode' (switch in sidebar or top bar).\n"
            "4. Click 'Load unpacked' and select the copied directory.\n"
            "5. Open the extension popup, paste the Session Token, select the target tab from the list, and click Record."
        )
        ctk.CTkLabel(guide_card, text=guide_text, justify="left", font=ctk.CTkFont(size=12), text_color="#cfd8dc").pack(anchor="w", padx=15, pady=(0, 12))


    def _render_analysis_view(self):
        f = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        ctk.CTkLabel(f, text=self.i18n.t("nav_ana_audio"), font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 10))
        
        # Audio File Picker
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=5)
        self.ana_file_entry = ctk.CTkEntry(row, width=450, placeholder_text="Select audio file...")
        self.ana_file_entry.pack(side="left", padx=(0, 10))
        ctk.CTkButton(row, text=self.i18n.t("btn_browse"), width=90, command=self._on_browse_ana_file).pack(side="left")
        ctk.CTkButton(row, text=self.i18n.t("btn_analyze"), width=120, command=self._on_run_analysis).pack(side="left", padx=10)

        self.ana_box = ctk.CTkTextbox(f, height=130)
        self.ana_box.pack(fill="x", pady=10)

        # Deep Source Separation & Stem Mixer Section (Experimental/Roadmap)
        sep_hdr = ctk.CTkFrame(f, fg_color="#2c2416", corner_radius=6)
        sep_hdr.pack(fill="x", pady=(10, 8), padx=2)
        sep_hdr_inner = ctk.CTkFrame(sep_hdr, fg_color="transparent")
        sep_hdr_inner.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(sep_hdr_inner, text="Stem Separation (Experimental - Basic Quality)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#ffa726").pack(side="left")

        # Warning info box
        warning_frame = ctk.CTkFrame(f, fg_color="#2d2416", corner_radius=4)
        warning_frame.pack(fill="x", pady=6, padx=10)
        warning_text = (
            "⚠️ Current implementation uses frequency filtering, not ML-based separation.\n"
            "For professional stem separation, use external tools (Demucs, Spleeter).\n"
            "ML-based separation is planned for future release."
        )
        ctk.CTkLabel(
            warning_frame,
            text=warning_text,
            font=ctk.CTkFont(size=10),
            text_color="#ffb74d",
            justify="left",
        ).pack(padx=10, pady=8)

        self.btn_separate = ctk.CTkButton(
            f,
            text="⚡ Extract Stems (Experimental)",
            fg_color="#5a5a2a",
            hover_color="#6a6a3a",
            command=self._on_run_stem_separation,
        )
        self.btn_separate.pack(pady=6)

        self.sep_progress = ctk.CTkProgressBar(f, height=6)
        self.sep_progress.pack(fill="x", pady=(2, 6))
        self.sep_progress.set(0.0)

        self.sep_status_lbl = ctk.CTkLabel(f, text="Experimental feature: Uses frequency filtering only.", text_color="#90a4ae", font=ctk.CTkFont(size=11))
        self.sep_status_lbl.pack(anchor="w", pady=(0, 10))

        # Container for Stem Mixer Lanes
        self.stem_mixer_container = ctk.CTkFrame(f, fg_color="transparent")
        self.stem_mixer_container.pack(fill="x", pady=5)
        self._stem_mixer_widgets = {}

    def _render_midi_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        ctk.CTkLabel(f, text=self.i18n.t("nav_ana_midi"), font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 15))
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=5)
        self.midi_input_entry = ctk.CTkEntry(row, width=400, placeholder_text="Audio file to transcribe...")
        self.midi_input_entry.pack(side="left", padx=(0, 10))
        ctk.CTkButton(row, text=self.i18n.t("btn_browse"), width=90, command=self._on_browse_midi_file).pack(side="left")

        opt_row = ctk.CTkFrame(f, fg_color="transparent")
        opt_row.pack(fill="x", pady=8)
        ctk.CTkLabel(opt_row, text="Profile:").pack(side="left", padx=(0, 5))
        self.midi_profile_combo = ctk.CTkComboBox(
            opt_row,
            values=["melody", "piano", "bass", "vocals", "percussive", "full_arrangement"],
            width=160,
        )
        self.midi_profile_combo.set("melody")
        self.midi_profile_combo.pack(side="left", padx=(0, 15))

        ctk.CTkButton(opt_row, text=self.i18n.t("btn_transcribe"), width=150, command=self._on_run_transcribe).pack(side="left")

        self.midi_box = ctk.CTkTextbox(f, height=330)
        self.midi_box.pack(expand=True, fill="both", pady=15)

    def _render_render_view(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)

        ctk.CTkLabel(f, text=self.i18n.t("nav_ana_render"), font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 15))
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=5)
        self.ren_midi_entry = ctk.CTkEntry(row, width=400, placeholder_text="Select .mid file...")
        self.ren_midi_entry.pack(side="left", padx=(0, 10))
        ctk.CTkButton(row, text=self.i18n.t("btn_browse"), width=90, command=self._on_browse_render_file).pack(side="left")

        opt_row = ctk.CTkFrame(f, fg_color="transparent")
        opt_row.pack(fill="x", pady=8)
        ctk.CTkLabel(opt_row, text="Instrument:").pack(side="left", padx=(0, 5))
        self.ren_inst_combo = ctk.CTkComboBox(
            opt_row,
            values=["acoustic_piano", "electric_piano", "strings", "synth_lead", "bass"],
            width=150,
        )
        self.ren_inst_combo.set("acoustic_piano")
        self.ren_inst_combo.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(opt_row, text="Format:").pack(side="left", padx=(0, 5))
        self.ren_fmt_combo = ctk.CTkComboBox(
            opt_row,
            values=["mp3", "wav", "flac"],
            width=100,
        )
        self.ren_fmt_combo.set("mp3")
        self.ren_fmt_combo.pack(side="left", padx=(0, 15))

        ctk.CTkButton(opt_row, text=self.i18n.t("btn_render_midi"), width=150, command=self._on_run_render).pack(side="left")

        self.ren_box = ctk.CTkTextbox(f, height=330)
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

        ctk.CTkLabel(f, text=f"er-audio-tool v{get_version()}", font=ctk.CTkFont(size=20, weight="bold"), text_color="#4db6ac").pack(anchor="w", pady=(0, 10))
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

    def _on_copy_browser_path(self):
        p = str(self.cm.get_extension_dir().resolve())
        self.clipboard_clear()
        self.clipboard_append(p)
        if hasattr(self, "browser_path_status") and self.browser_path_status.winfo_exists():
            self.browser_path_status.configure(text=self.i18n.t("path_copied_msg"), text_color="#4db6ac")

    def _on_open_browser_folder(self):
        p = self.cm.get_extension_dir()
        p.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(p))
            elif sys.platform == "darwin":
                safe_run(["open", str(p)])
            else:
                safe_run(["xdg-open", str(p)])
        except Exception as ex:
            messagebox.showerror(self.i18n.t("error"), f"Could not open directory: {ex}")

    def _on_reinstall_extension(self):
        ext_p = self.cm.install_or_update_extension()
        if hasattr(self, "browser_path_entry") and self.browser_path_entry.winfo_exists():
            self.browser_path_entry.configure(state="normal")
            self.browser_path_entry.delete(0, "end")
            self.browser_path_entry.insert(0, str(ext_p.resolve()))
            self.browser_path_entry.configure(state="readonly")
        if hasattr(self, "browser_path_status") and self.browser_path_status.winfo_exists():
            self.browser_path_status.configure(text=self.i18n.t("ext_installed_msg"), text_color="#4db6ac")

    def _on_toggle_token_visibility(self):
        self._token_visible = not self._token_visible
        curr_token = self.browser_server.auth_token if self.browser_server else ""
        if hasattr(self, "browser_token_entry") and self.browser_token_entry.winfo_exists():
            self.browser_token_entry.configure(state="normal")
            self.browser_token_entry.delete(0, "end")
            self.browser_token_entry.insert(0, curr_token if self._token_visible else self.i18n.t("browser_token_masked"))
            self.browser_token_entry.configure(state="readonly")
        if hasattr(self, "btn_toggle_tok") and self.btn_toggle_tok.winfo_exists():
            self.btn_toggle_tok.configure(text=self.i18n.t("btn_hide_token") if self._token_visible else self.i18n.t("btn_show_token"))

    def _on_copy_browser_token(self):
        token = self.browser_server.auth_token if self.browser_server else ""
        self.clipboard_clear()
        self.clipboard_append(token)
        if hasattr(self, "browser_tok_status") and self.browser_tok_status.winfo_exists():
            self.browser_tok_status.configure(text=self.i18n.t("token_copied_msg"), text_color="#4db6ac")

    def _on_regen_browser_token(self):
        if self.browser_server:
            import secrets
            self.browser_server.auth_token = secrets.token_urlsafe(32)
            curr_token = self.browser_server.auth_token
            if hasattr(self, "browser_token_entry") and self.browser_token_entry.winfo_exists():
                self.browser_token_entry.configure(state="normal")
                self.browser_token_entry.delete(0, "end")
                self.browser_token_entry.insert(0, curr_token if self._token_visible else self.i18n.t("browser_token_masked"))
                self.browser_token_entry.configure(state="readonly")
            if hasattr(self, "browser_tok_status") and self.browser_tok_status.winfo_exists():
                self.browser_tok_status.configure(text="✓ New Token Generated", text_color="#80cbc4")

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
            safe_run(["open", str(p)])
        else:
            safe_run(["xdg-open", str(p)])

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

    def _on_toggle_monitor_clicked(self):
        """Toggles real-time audio input level monitoring without recording to disk."""
        if self._monitoring_active:
            self._stop_monitoring()
        else:
            self._start_monitoring()

    def _start_monitoring(self):
        curr = self.state_machine.current_state
        if curr != AppState.IDLE:
            return

        backend = self.device_manager.get_backend_for_source_type(self._current_view_name)
        self._active_backend = backend

        selected_name = self.source_combo.get() if hasattr(self, "source_combo") else ""
        dev = next((d for d in self.devices if d.name == selected_name), self.devices[0] if self.devices else None)
        if not dev:
            messagebox.showerror(self.i18n.t("error"), "No audio device selected for monitoring.")
            return

        import uuid
        self._current_session_id = f"monitor_{uuid.uuid4()}"
        self.audio_buffer.set_active_session(self._current_session_id)

        try:
            backend.start_capture(
                dev,
                self.cfg.sample_rate,
                self.cfg.channels,
                self._on_monitor_data_received,
            )
            self._monitoring_active = True
            if hasattr(self, "btn_monitor") and self.btn_monitor.winfo_exists():
                self.btn_monitor.configure(
                    text="■ " + self.i18n.t("btn_monitor_stop"),
                    fg_color="#00695c",
                    hover_color="#004d40",
                )
            self.status_label.configure(text=self.i18n.t("monitor_active_hint"), text_color="#80deea")
        except Exception as ex:
            self._monitoring_active = False
            messagebox.showerror(self.i18n.t("error"), f"Failed to start input monitor:\n\n{ex}")

    def _stop_monitoring(self):
        if not self._monitoring_active:
            return
        self._monitoring_active = False
        try:
            if self._active_backend:
                self._active_backend.stop_capture()
        except Exception:
            pass
        if hasattr(self, "btn_monitor") and self.btn_monitor.winfo_exists():
            self.btn_monitor.configure(
                text="🎧 " + self.i18n.t("btn_monitor_start"),
                fg_color="#37474f",
                hover_color="#455a64",
            )
        if self.state_machine.current_state == AppState.IDLE:
            self.status_label.configure(text=self.i18n.t("ready"), text_color="#b0bec5")

    def _on_monitor_data_received(self, data: np.ndarray):
        if self._monitoring_active and self.state_machine.current_state == AppState.IDLE:
            self.audio_buffer.push(data, session_id=self._current_session_id)

    def _on_record_clicked(self):
        # If input monitoring is running, stop it cleanly before beginning capture to disk
        if self._monitoring_active:
            self._stop_monitoring()

        curr = self.state_machine.current_state
        if curr == AppState.IDLE:
            self.state_machine.transition_to(AppState.PREPARING)
            self._recording_data.clear()
            self._record_start_time = time.time()
            self._elapsed_paused_time = 0.0

            import uuid
            self._current_session_id = str(uuid.uuid4())
            self.audio_buffer.set_active_session(self._current_session_id)

            backend = self.device_manager.get_backend_for_source_type(self._current_view_name)
            self._active_backend = backend

            selected_name = self.source_combo.get()
            dev = next((d for d in self.devices if d.name == selected_name), self.devices[0] if self.devices else None)
            if not dev:
                messagebox.showerror(self.i18n.t("error"), "No audio device selected.")
                self.state_machine.transition_to(AppState.FAILED)
                self.state_machine.transition_to(AppState.IDLE)
                return

            try:
                backend.start_capture(
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
                err_str = str(ex)
                if self._current_view_name == "rec_browser":
                    messagebox.showerror(
                        self.i18n.t("error"),
                        f"Browser-Tab Aufnahme fehlgeschlagen:\n\n{err_str}\n\n"
                        f"Aktion: Überprüfen Sie bitte 'Geräte > Browser-Verbindung' oder öffnen Sie das Erweiterungs-Popup.",
                    )
                else:
                    messagebox.showerror(self.i18n.t("error"), f"Capture initialization failed:\n\n{err_str}")


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
                from er_audio_tool.audio.output_validator import OutputValidator, OutputClassification
                val = OutputValidator.validate_file(target_path)
                if val.classification == OutputClassification.VALID_SIGNAL:
                    messagebox.showinfo(self.i18n.t("app_title"), f"Saved: {target_path}\nDuration: {val.duration_seconds:.2f}s | Peak: {val.peak_db:.1f} dBFS")
                elif val.classification == OutputClassification.DIGITAL_SILENCE:
                    messagebox.showwarning(
                        self.i18n.t("app_title"),
                        f"Saved file contains digital silence (no audible audio signal detected):\n{target_path}\n"
                        f"Duration: {val.duration_seconds:.2f}s | Frames: {val.frame_count}\n"
                        f"Hinweis: Stellen Sie sicher, dass Audio auf dem ausgewählten Gerät abgespielt wird."
                    )
                else:
                    messagebox.showerror(
                        self.i18n.t("error"),
                        f"Recording validation warning: {val.error_message or val.classification.value}"
                    )
            else:
                messagebox.showerror(
                    self.i18n.t("error"),
                    "No audio frames were received during the recording session.\n"
                    "No empty file was created. Please verify device or browser connection."
                )

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
            self.audio_buffer.push(data, session_id=self._current_session_id)

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
        if not hasattr(self, "diag_box"):
            return
        self.diag_box.delete("1.0", "end")
        self.diag_box.insert("end", "Initializing Hardware & Software Diagnostics...\n\n")
        if hasattr(self, "diag_btn"):
            self.diag_btn.configure(state="disabled")
        if hasattr(self, "diag_status_lbl"):
            self.diag_status_lbl.configure(text="Running tests...", text_color="#ffb74d")
        if hasattr(self, "diag_progress"):
            self.diag_progress.set(0.1)

        def worker():
            import time
            steps = [0.25, 0.5, 0.75, 0.95]
            for s in steps:
                time.sleep(0.08)
                self.after(0, lambda val=s: self.diag_progress.set(val) if hasattr(self, "diag_progress") else None)

            items = DiagnosticRunner.run_all_tests(self.cfg.output_dir)

            def update_ui():
                self.diag_box.delete("1.0", "end")
                for it in items:
                    symbol = "✓" if it.status == "PASSED" else ("⚠" if it.status == "WARNING" else "✗")
                    self.diag_box.insert("end", f"[{symbol} {it.status}] {it.category} > {it.name}\n  Details: {it.details}\n")
                    if it.recommendation:
                        self.diag_box.insert("end", f"  Action: {it.recommendation}\n")
                    self.diag_box.insert("end", "\n")

                if hasattr(self, "diag_progress"):
                    self.diag_progress.set(1.0)
                if hasattr(self, "diag_status_lbl"):
                    self.diag_status_lbl.configure(text="✓ Diagnostics Complete", text_color="#4db6ac")
                if hasattr(self, "diag_btn"):
                    self.diag_btn.configure(state="normal")
                if hasattr(self, "diag_capture_btn"):
                    self.diag_capture_btn.configure(state="normal")

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _on_run_capture_test_only(self):
        if not hasattr(self, "diag_box"):
            return
        self.diag_box.delete("1.0", "end")
        self.diag_box.insert("end", "Prüfe Audio Capture & WASAPI Loopback Endpunkte...\n\n")
        if hasattr(self, "diag_capture_btn"):
            self.diag_capture_btn.configure(state="disabled")
        if hasattr(self, "diag_status_lbl"):
            self.diag_status_lbl.configure(text="Teste Audio Capture...", text_color="#ffb74d")
        if hasattr(self, "diag_progress"):
            self.diag_progress.set(0.3)

        def worker():
            items = DiagnosticRunner.run_audio_capture_test()

            def update_ui():
                self.diag_box.delete("1.0", "end")
                self.diag_box.insert("end", "=== Audio Capture & Endpunkt-Diagnosetest ===\n\n")
                all_ok = True
                for it in items:
                    symbol = "✓" if it.status == "PASSED" else ("⚠" if it.status == "WARNING" else "✗")
                    if it.status != "PASSED":
                        all_ok = False
                    self.diag_box.insert("end", f"[{symbol} {it.status}] {it.name}\n  Details: {it.details}\n")
                    if it.recommendation:
                        self.diag_box.insert("end", f"  Empfehlung: {it.recommendation}\n")
                    self.diag_box.insert("end", "\n")

                if hasattr(self, "diag_progress"):
                    self.diag_progress.set(1.0)
                if hasattr(self, "diag_status_lbl"):
                    stat_txt = "✓ Capture-Test bestanden" if all_ok else "⚠ Capture-Test mit Hinweisen"
                    stat_col = "#4db6ac" if all_ok else "#ffb74d"
                    self.diag_status_lbl.configure(text=stat_txt, text_color=stat_col)
                if hasattr(self, "diag_capture_btn"):
                    self.diag_capture_btn.configure(state="normal")

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_browser_connection_clicked(self):
        snap = self.browser_registry.get_snapshot()
        ext_state = snap.state.value
        ext_color = "#4db6ac" if snap.authenticated_session_id else ("#ffb74d" if snap.state != ConnectionState.SERVER_STOPPED else "#90a4ae")
        tab_info_str = f"{snap.selected_tab.title} (Tab ID: {snap.selected_tab.tab_id})" if snap.selected_tab else "None selected yet (Open extension popup to pick a tab)"

        if hasattr(self, "lbl_ext_handshake") and self.lbl_ext_handshake.winfo_exists():
            self.lbl_ext_handshake.configure(text=f"• Extension Handshake: {ext_state}", text_color=ext_color)
        if hasattr(self, "lbl_ext_tab") and self.lbl_ext_tab.winfo_exists():
            self.lbl_ext_tab.configure(text=f"• Selected Browser Tab: {tab_info_str}")
        if hasattr(self, "lbl_ext_frames") and self.lbl_ext_frames.winfo_exists():
            self.lbl_ext_frames.configure(text=f"• Received Audio Frames: {snap.received_frames_count}")

        if hasattr(self, "lbl_rec_browser_status") and self.lbl_rec_browser_status.winfo_exists():
            st_text = f"• State: {snap.state.value} | Tab: {snap.selected_tab.title if snap.selected_tab else 'None'} | Gen: {snap.connection_generation} | Heartbeat: {snap.last_heartbeat_age_seconds:.0f}s ago"
            self.lbl_rec_browser_status.configure(text=st_text, text_color=ext_color)

        # Refresh device dropdown so newly selected tab appears immediately
        if self._current_view_name == "rec_browser":
            self.devices = self.device_manager.enumerate_all_devices(self._current_view_name)
            dev_names = [d.name for d in self.devices] or ["Default Endpoint"]
            if hasattr(self, "source_combo") and self.source_combo.winfo_exists():
                self.source_combo.configure(values=dev_names)
                if dev_names:
                    self.source_combo.set(dev_names[0])

        if snap.authenticated_session_id:
            messagebox.showinfo(
                self.i18n.t("app_title"),
                f"✓ Browser-Erweiterung ist erfolgreich verbunden und authentifiziert!\n\n"
                f"Status: {snap.state.value}\n"
                f"Aktiver Tab: {tab_info_str}\n"
                f"Verbindungs-Generation: {snap.connection_generation}\n"
                f"Empfangene Frames: {snap.received_frames_count}",
            )
        else:
            messagebox.showinfo(
                self.i18n.t("app_title"),
                f"Status der Browser-Kopplung:\n\n"
                f"• Handshake: {snap.state.value}\n"
                f"• Server lauscht auf: 127.0.0.1:58291\n"
                f"• Token bereitgestellt: Ja\n\n"
                f"Hinweis: Bitte öffnen Sie das Erweiterungs-Popup im Browser und klicken Sie dort auf 'Verbindung testen'.",
            )

    def _on_run_analysis(self):
        p = self.ana_file_entry.get().strip()
        if not p or not Path(p).exists():
            return
        self.ana_box.delete("1.0", "end")
        rep = AudioAnalyzer.analyze_file(p)
        self.ana_box.insert("end", f"File: {rep.file_path}\nDuration: {rep.duration_seconds}s | Sample Rate: {rep.sample_rate} Hz | Channels: {rep.channels}\nPeak: {rep.peak_db} dBFS | RMS: {rep.rms_db} dBFS\nEstimated Tempo: {rep.estimated_tempo_bpm} BPM | Key: {rep.estimated_key}\n")

    def _on_run_stem_separation(self):
        p = self.ana_file_entry.get().strip()
        if not p or not Path(p).exists():
            messagebox.showerror(self.i18n.t("error"), "Please select an existing audio file.")
            return

        if hasattr(self, "btn_separate"):
            self.btn_separate.configure(state="disabled")
        if hasattr(self, "sep_status_lbl"):
            self.sep_status_lbl.configure(text="Extracting 4 stems (Vocals, Drums, Bass, Other)...", text_color="#ffb74d")
        if hasattr(self, "sep_progress"):
            self.sep_progress.set(0.05)

        out_stem_dir = Path(self.cfg.output_dir) / "stems"

        def progress_cb(pct: float, msg: str):
            def update():
                if hasattr(self, "sep_progress") and self.sep_progress.winfo_exists():
                    self.sep_progress.set(pct)
                if hasattr(self, "sep_status_lbl") and self.sep_status_lbl.winfo_exists():
                    self.sep_status_lbl.configure(text=f"[{int(pct*100)}%] {msg}", text_color="#ffb74d")
            self.after(0, update)

        def worker():
            from er_audio_tool.analysis.separator import StemSeparator
            try:
                stems = StemSeparator.separate_file(p, out_stem_dir, progress_cb=progress_cb)
                err = None
            except Exception as ex:
                stems = {}
                err = str(ex)

            def update_done():
                if hasattr(self, "btn_separate") and self.btn_separate.winfo_exists():
                    self.btn_separate.configure(state="normal")
                if err:
                    if hasattr(self, "sep_status_lbl") and self.sep_status_lbl.winfo_exists():
                        self.sep_status_lbl.configure(text=f"✗ Separation failed: {err}", text_color="#e57373")
                    return

                if hasattr(self, "sep_status_lbl") and self.sep_status_lbl.winfo_exists():
                    self.sep_status_lbl.configure(text="✓ 4 Stems extracted successfully! Use mixer below to audition or send stems to MIDI.", text_color="#4db6ac")
                if hasattr(self, "sep_progress") and self.sep_progress.winfo_exists():
                    self.sep_progress.set(1.0)

                self._build_stem_mixer_ui(stems)
                self._refresh_library_list()

            self.after(0, update_done)

        threading.Thread(target=worker, daemon=True).start()

    def _build_stem_mixer_ui(self, stems: dict):
        if not hasattr(self, "stem_mixer_container") or not self.stem_mixer_container.winfo_exists():
            return
        for w in self.stem_mixer_container.winfo_children():
            w.destroy()

        colors = {
            "vocals": "#ab47bc",
            "drums": "#ef5350",
            "bass": "#42a5f5",
            "other": "#26a69a",
        }

        for stem_name in ("vocals", "drums", "bass", "other"):
            sinfo = stems.get(stem_name)
            if not sinfo:
                continue

            lane = ctk.CTkFrame(self.stem_mixer_container, fg_color="#212121", corner_radius=6)
            lane.pack(fill="x", pady=4, padx=2)

            # Left badge & stats
            left_f = ctk.CTkFrame(lane, fg_color="transparent")
            left_f.pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(
                left_f,
                text=stem_name.upper(),
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=colors.get(stem_name, "#ffffff"),
                width=80,
                anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                left_f,
                text=f"RMS: {sinfo.rms_db:.1f} dB | Peak: {sinfo.peak_db:.1f} dB",
                font=ctk.CTkFont(size=10),
                text_color="#90a4ae",
            ).pack(anchor="w")

            # Middle: Volume Slider
            mid_f = ctk.CTkFrame(lane, fg_color="transparent")
            mid_f.pack(side="left", fill="x", expand=True, padx=15)
            vol_slider = ctk.CTkSlider(mid_f, from_=0.0, to=1.5, number_of_steps=30)
            vol_slider.set(1.0)
            vol_slider.pack(fill="x")

            # Controls: Mute, Solo, Send to MIDI
            ctrl_f = ctk.CTkFrame(lane, fg_color="transparent")
            ctrl_f.pack(side="right", padx=12)

            mute_btn = ctk.CTkButton(ctrl_f, text="Mute", width=55, height=28, fg_color="#37474f", hover_color="#263238")
            solo_btn = ctk.CTkButton(ctrl_f, text="Solo", width=55, height=28, fg_color="#37474f", hover_color="#263238")

            def toggle_mute(b=mute_btn):
                curr = b.cget("text")
                b.configure(text="MUTED" if curr == "Mute" else "Mute", fg_color="#c62828" if curr == "Mute" else "#37474f")

            def toggle_solo(b=solo_btn):
                curr = b.cget("text")
                b.configure(text="SOLOED" if curr == "Solo" else "Solo", fg_color="#f57f17" if curr == "Solo" else "#37474f")

            mute_btn.configure(command=toggle_mute)
            solo_btn.configure(command=toggle_solo)
            mute_btn.pack(side="left", padx=4)
            solo_btn.pack(side="left", padx=4)

            # Send to MIDI Button
            send_midi_btn = ctk.CTkButton(
                ctrl_f,
                text="➔ Send to MIDI",
                width=115,
                height=28,
                fg_color="#00695c",
                hover_color="#004d40",
                command=lambda p=str(sinfo.file_path), prof=stem_name: self._send_stem_to_midi(p, prof),
            )
            send_midi_btn.pack(side="left", padx=6)

    def _send_stem_to_midi(self, stem_path: str, stem_name: str):
        self._show_view("ana_midi")
        if hasattr(self, "midi_input_entry"):
            self.midi_input_entry.delete(0, "end")
            self.midi_input_entry.insert(0, stem_path)
        if hasattr(self, "midi_profile_combo"):
            # Map stem to profile
            prof_map = {"vocals": "vocals", "drums": "percussive", "bass": "bass", "other": "piano"}
            self.midi_profile_combo.set(prof_map.get(stem_name, "melody"))


    def _on_run_transcribe(self):
        p = self.midi_input_entry.get().strip()
        if not p or not Path(p).exists():
            messagebox.showerror(self.i18n.t("error"), "Please select an existing audio file.")
            return
        prof_c = getattr(self, "midi_profile_combo", None)
        profile = prof_c.get().lower() if prof_c else "melody"

        self.midi_box.delete("1.0", "end")
        self.midi_box.insert("end", f"Transcribing audio to MIDI with profile '{profile}'...\n")
        notes = AudioToMidiTranscriber.transcribe(p, profile=profile)
        out = Path(p).with_suffix(".mid")
        MidiExporter.export_midi(notes, out)
        self.midi_box.insert("end", f"✓ Exported {len(notes)} note events to: {out}\n")
        self._refresh_library_list()

    def _on_run_render(self):
        p = self.ren_midi_entry.get().strip()
        if not p or not Path(p).exists():
            messagebox.showerror(self.i18n.t("error"), "Please select an existing .mid file.")
            return
        inst = getattr(self, "ren_inst_combo", None)
        instrument = inst.get() if inst else "acoustic_piano"
        fmt_c = getattr(self, "ren_fmt_combo", None)
        format_type = fmt_c.get().lower() if fmt_c else "mp3"

        if hasattr(self, "ren_box") and self.ren_box.winfo_exists():
            self.ren_box.delete("1.0", "end")
            self.ren_box.insert("end", f"Rendering MIDI file: {Path(p).name}...\nInstrument: {instrument} | Format: {format_type.upper()}\n")

        out = Path(p).with_suffix(f".rendered.{format_type}")
        
        def render_worker():
            try:
                rendered = MidiRenderer.render_file_to_audio(
                    p,
                    out,
                    sample_rate=self.cfg.sample_rate,
                    instrument=instrument,
                    format_type=format_type,
                )
                success = rendered.exists() and rendered.stat().st_size > 0
                sz = (rendered.stat().st_size / (1024 * 1024)) if success else 0.0
            except Exception as render_ex:
                rendered = None
                success = False
                render_err = str(render_ex)
            else:
                render_err = None

            def ui_update():
                if success:
                    try:
                        if hasattr(self, "ren_box") and self.ren_box.winfo_exists():
                            self.ren_box.insert("end", f"✓ Successfully synthesized MIDI to audio!\nOutput: {rendered} ({sz:.2f} MB)\n")
                        self._refresh_library_list()
                    except Exception:
                        pass
                else:
                    try:
                        if hasattr(self, "ren_box") and self.ren_box.winfo_exists():
                            self.ren_box.insert("end", f"✗ Synthesis failed: {render_err}\n")
                    except Exception:
                        pass

            self.after(0, ui_update)

        threading.Thread(target=render_worker, daemon=True).start()

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

        if hasattr(self, "meter_l") and self.meter_l.winfo_exists():
            pk_l, pk_r, pk, rms, is_clip, frames = self.audio_buffer.get_stereo_levels()
            val_l = max(0.0, (pk_l + 60.0) / 60.0) if pk_l > -60.0 else 0.0
            val_r = max(0.0, (pk_r + 60.0) / 60.0) if pk_r > -60.0 else 0.0
            self.meter_l.set(min(1.0, val_l))
            self.meter_r.set(min(1.0, val_r))

            pk_l_str = f"{pk_l:.1f} dB" if pk_l > -95.0 else "-inf dB"
            pk_r_str = f"{pk_r:.1f} dB" if pk_r > -95.0 else "-inf dB"
            pk_str = f"{pk:.1f} dBFS" if pk > -95.0 else "-inf dBFS"
            rms_str = f"{rms:.1f} dBFS" if rms > -95.0 else "-inf dBFS"

            sig_state = "Signal Detected" if pk > -55.0 else ("Receiving Frames" if frames > 0 else "Idle / Silent")
            self.meter_text.configure(text=f"Levels: L {pk_l_str} | R {pk_r_str} | Peak {pk_str} | RMS {rms_str} [{sig_state}]")
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

        # Stop active capture or monitoring if running
        try:
            if self._monitoring_active:
                self._stop_monitoring()
            if self.state_machine.current_state in (AppState.RECORDING, AppState.PAUSED):
                self._active_backend.stop_capture()
        except Exception:
            pass

        self.destroy()
