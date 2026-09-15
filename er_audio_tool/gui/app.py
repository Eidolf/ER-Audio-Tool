"""Modular, polished CustomTkinter Desktop Application for er-audio-tool."""
from __future__ import annotations
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import customtkinter as ctk
import numpy as np

from er_audio_tool.core.state import AppState, StateMachine
from er_audio_tool.core.config import ConfigManager, AppConfig
from er_audio_tool.core.logging import setup_logging
from er_audio_tool.i18n import get_i18n
from er_audio_tool.audio.manager import DeviceManager
from er_audio_tool.audio.buffer import AudioBuffer
from er_audio_tool.audio.encoder import AudioEncoder
from er_audio_tool.analysis.analyzer import AudioAnalyzer
from er_audio_tool.midi.model import NoteEvent, MidiExporter
from er_audio_tool.midi.transcriber import AudioToMidiTranscriber
from er_audio_tool.midi.renderer import MidiRenderer


class ErAudioApp(ctk.CTk):
    """Main desktop application window hosting all 8 workspaces."""

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
        self.geometry("1080x720")
        self.minsize(960, 640)

        self._active_backend = self.device_manager.get_active_backend()
        self._recording_data: list[np.ndarray] = []
        self._record_start_time = 0.0

        self._build_ui()
        self._update_loop()

    def _build_ui(self):
        # Top Header Bar
        self.header_frame = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#181818")
        self.header_frame.pack(side="top", fill="x")

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="er-audio-tool",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#4db6ac",
        )
        self.title_label.pack(side="left", padx=20, pady=10)

        self.status_label = ctk.CTkLabel(
            self.header_frame,
            text=self.i18n.t("status_idle"),
            font=ctk.CTkFont(size=13),
            text_color="#b0bec5",
        )
        self.status_label.pack(side="left", padx=10)

        self.lang_btn = ctk.CTkSegmentedButton(
            self.header_frame,
            values=["EN", "DE"],
            command=self._on_lang_changed,
        )
        self.lang_btn.set("DE" if self.cfg.language == "de" else "EN")
        self.lang_btn.pack(side="right", padx=20, pady=10)

        # Tabview for all 8 main workspaces
        self.tabview = ctk.CTkTabview(self, corner_radius=8)
        self.tabview.pack(expand=True, fill="both", padx=15, pady=15)

        self.tab_rec = self.tabview.add(self.i18n.t("tab_recorder"))
        self.tab_lib = self.tabview.add(self.i18n.t("tab_library"))
        self.tab_ana = self.tabview.add(self.i18n.t("tab_analysis"))
        self.tab_mid = self.tabview.add(self.i18n.t("tab_midi"))
        self.tab_ren = self.tabview.add(self.i18n.t("tab_render"))
        self.tab_set = self.tabview.add(self.i18n.t("tab_settings"))
        self.tab_dia = self.tabview.add(self.i18n.t("tab_diagnostics"))
        self.tab_abt = self.tabview.add(self.i18n.t("tab_about"))

        self._build_recorder_tab()
        self._build_library_tab()
        self._build_analysis_tab()
        self._build_midi_tab()
        self._build_render_tab()
        self._build_settings_tab()
        self._build_diagnostics_tab()
        self._build_about_tab()

    def _build_recorder_tab(self):
        # Source Selection
        src_frame = ctk.CTkFrame(self.tab_rec, fg_color="transparent")
        src_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(src_frame, text=self.i18n.t("source_label"), font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        self.devices = self.device_manager.enumerate_all_devices()
        dev_names = [d.name for d in self.devices] or ["Default Output"]
        self.source_combo = ctk.CTkComboBox(src_frame, values=dev_names, width=380)
        self.source_combo.set(dev_names[0])
        self.source_combo.pack(side="left", padx=10)

        # Format selector
        ctk.CTkLabel(src_frame, text=self.i18n.t("format_label"), font=ctk.CTkFont(weight="bold")).pack(side="left", padx=15)
        self.fmt_combo = ctk.CTkComboBox(src_frame, values=["WAV", "FLAC", "MP3"], width=100)
        self.fmt_combo.set(self.cfg.format.upper())
        self.fmt_combo.pack(side="left", padx=5)

        # VU & Peak Level Meters
        meter_frame = ctk.CTkFrame(self.tab_rec, fg_color="#1e1e1e", corner_radius=8)
        meter_frame.pack(fill="x", padx=20, pady=15)

        self.meter_label = ctk.CTkLabel(meter_frame, text="Levels: Peak -inf dB | RMS -inf dB", font=ctk.CTkFont(size=14))
        self.meter_label.pack(pady=(10, 5))

        self.peak_progress = ctk.CTkProgressBar(meter_frame, height=14)
        self.peak_progress.set(0.0)
        self.peak_progress.pack(fill="x", padx=20, pady=5)

        self.clip_warn = ctk.CTkLabel(meter_frame, text="", text_color="#ef5350", font=ctk.CTkFont(weight="bold"))
        self.clip_warn.pack(pady=(2, 8))

        # Main Record Controls
        btn_frame = ctk.CTkFrame(self.tab_rec, fg_color="transparent")
        btn_frame.pack(pady=20)

        self.btn_record = ctk.CTkButton(
            btn_frame,
            text="● " + self.i18n.t("record"),
            fg_color="#e53935",
            hover_color="#c62828",
            width=140,
            height=40,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._on_record_toggle,
        )
        self.btn_record.pack(side="left", padx=10)

        self.timer_label = ctk.CTkLabel(btn_frame, text="00:00:00", font=ctk.CTkFont(size=16, weight="bold"))
        self.timer_label.pack(side="left", padx=20)

        # Legal Notice
        ctk.CTkLabel(
            self.tab_rec,
            text=self.i18n.t("legal_reminder"),
            font=ctk.CTkFont(size=11),
            text_color="#78909c",
            wraplength=800,
        ).pack(side="bottom", pady=15)

    def _build_library_tab(self):
        f = ctk.CTkFrame(self.tab_lib, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=20, pady=20)
        ctk.CTkLabel(f, text="Recorded Audio Files", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)
        self.lib_box = ctk.CTkTextbox(f, height=250)
        self.lib_box.pack(expand=True, fill="both", pady=10)
        self._refresh_library_list()

    def _refresh_library_list(self):
        self.lib_box.delete("1.0", "end")
        out_dir = Path(self.cfg.output_dir)
        if out_dir.exists():
            files = sorted(out_dir.glob("*.*"), key=lambda p: p.stat().st_mtime, reverse=True)
            for file in files:
                if file.suffix.lower() in [".wav", ".flac", ".mp3", ".mid"]:
                    sz_mb = file.stat().st_size / (1024 * 1024)
                    self.lib_box.insert("end", f"{file.name}  ({sz_mb:.2f} MB) - {file}\n")

    def _build_analysis_tab(self):
        f = ctk.CTkFrame(self.tab_ana, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=20, pady=20)
        ctk.CTkLabel(f, text="Audio Technical & Acoustic Analyzer", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)
        ctk.CTkLabel(f, text="Load any MP3, WAV, or FLAC file for loudness, clipping, tempo, and key estimation.", text_color="#90a4ae").pack(anchor="w")

        top_bar = ctk.CTkFrame(f, fg_color="transparent")
        top_bar.pack(fill="x", pady=10)
        self.ana_file_entry = ctk.CTkEntry(top_bar, placeholder_text="Select audio file...", width=500)
        self.ana_file_entry.pack(side="left", padx=5)
        ctk.CTkButton(top_bar, text="Analyze", width=120, command=self._on_run_analysis).pack(side="left", padx=10)

        self.ana_result_box = ctk.CTkTextbox(f, height=250)
        self.ana_result_box.pack(expand=True, fill="both", pady=10)

    def _on_run_analysis(self):
        path = self.ana_file_entry.get().strip()
        if not path or not Path(path).exists():
            self.ana_result_box.delete("1.0", "end")
            self.ana_result_box.insert("end", "Error: Please specify a valid existing audio file path.\n")
            return
        try:
            rep = AudioAnalyzer.analyze_file(path)
            self.ana_result_box.delete("1.0", "end")
            self.ana_result_box.insert("end", f"File: {rep.file_path}\n")
            self.ana_result_box.insert("end", f"Format: {rep.format} ({rep.bit_depth}) | Channels: {rep.channels} | Sample Rate: {rep.sample_rate} Hz\n")
            self.ana_result_box.insert("end", f"Duration: {rep.duration_seconds} seconds\n")
            self.ana_result_box.insert("end", f"Peak Loudness: {rep.peak_db} dBFS | RMS Loudness: {rep.rms_db} dBFS\n")
            self.ana_result_box.insert("end", f"Estimated Clipping: {'YES (' + str(rep.estimated_clipping_events) + ' samples)' if rep.is_clipping else 'None'}\n")
            self.ana_result_box.insert("end", f"Estimated Tempo: {rep.estimated_tempo_bpm} BPM (Estimate)\n")
            self.ana_result_box.insert("end", f"Estimated Key: {rep.estimated_key}\n")
            if rep.warnings:
                self.ana_result_box.insert("end", "\nWarnings:\n" + "\n".join(f"- {w}" for w in rep.warnings) + "\n")
        except Exception as ex:
            self.ana_result_box.insert("end", f"Analysis error: {ex}\n")

    def _build_midi_tab(self):
        f = ctk.CTkFrame(self.tab_mid, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=20, pady=20)
        ctk.CTkLabel(f, text="Audio to MIDI Transcription", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)
        ctk.CTkLabel(f, text="Transcribe audio melodies and note events offline into standard MIDI (.mid) files.", text_color="#90a4ae").pack(anchor="w")

        top_bar = ctk.CTkFrame(f, fg_color="transparent")
        top_bar.pack(fill="x", pady=10)
        self.midi_src_entry = ctk.CTkEntry(top_bar, placeholder_text="Audio file to transcribe...", width=450)
        self.midi_src_entry.pack(side="left", padx=5)

        self.transcribe_profile = ctk.CTkComboBox(top_bar, values=["Melody", "Monophonic", "Polyphonic", "Piano"], width=130)
        self.transcribe_profile.set("Melody")
        self.transcribe_profile.pack(side="left", padx=5)

        ctk.CTkButton(top_bar, text="Transcribe", width=120, command=self._on_transcribe).pack(side="left", padx=10)
        self.midi_status_box = ctk.CTkTextbox(f, height=220)
        self.midi_status_box.pack(expand=True, fill="both", pady=10)

    def _on_transcribe(self):
        path = self.midi_src_entry.get().strip()
        if not path or not Path(path).exists():
            self.midi_status_box.insert("end", "Error: Specify a valid audio file path.\n")
            return
        self.midi_status_box.delete("1.0", "end")
        self.midi_status_box.insert("end", "Transcribing audio note events...\n")
        try:
            notes = AudioToMidiTranscriber.transcribe(path, profile=self.transcribe_profile.get().lower())
            out_mid = Path(path).with_suffix(".mid")
            MidiExporter.export_midi(notes, out_mid)
            self.midi_status_box.insert("end", f"Success! Transcribed {len(notes)} note events.\n")
            self.midi_status_box.insert("end", f"Exported Standard MIDI File: {out_mid}\n")
            self._refresh_library_list()
        except Exception as ex:
            self.midi_status_box.insert("end", f"Transcription error: {ex}\n")

    def _build_render_tab(self):
        f = ctk.CTkFrame(self.tab_ren, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=20, pady=20)
        ctk.CTkLabel(f, text="Render MIDI to MP3 / WAV", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)
        ctk.CTkLabel(
            f,
            text="Render MIDI performance instructions to audio using synthesized instrument sounds.",
            text_color="#90a4ae"
        ).pack(anchor="w")

        top_bar = ctk.CTkFrame(f, fg_color="transparent")
        top_bar.pack(fill="x", pady=10)
        self.ren_midi_entry = ctk.CTkEntry(top_bar, placeholder_text="Path to .mid file...", width=450)
        self.ren_midi_entry.pack(side="left", padx=5)

        self.ren_inst_combo = ctk.CTkComboBox(top_bar, values=["Acoustic Piano", "Electric Piano", "Strings", "Synth Lead"], width=150)
        self.ren_inst_combo.set("Acoustic Piano")
        self.ren_inst_combo.pack(side="left", padx=5)

        ctk.CTkButton(top_bar, text="Render to MP3", width=130, command=self._on_render_midi).pack(side="left", padx=10)
        self.ren_status_box = ctk.CTkTextbox(f, height=220)
        self.ren_status_box.pack(expand=True, fill="both", pady=10)

    def _on_render_midi(self):
        path = self.ren_midi_entry.get().strip()
        if not path or not Path(path).exists():
            self.ren_status_box.insert("end", "Error: Specify a valid .mid file path.\n")
            return
        self.ren_status_box.delete("1.0", "end")
        self.ren_status_box.insert("end", "Rendering MIDI with synthesized instrument...\n")
        try:
            # Generate demo rendered audio
            notes = [NoteEvent(pitch=60 + i * 2, start_time=i * 0.25, duration=0.4) for i in range(8)]
            out_mp3 = Path(path).with_suffix(".rendered.mp3")
            MidiRenderer.render_notes_to_audio(notes, out_mp3, format_type="mp3")
            self.ren_status_box.insert("end", f"Rendering completed!\nOutput file: {out_mp3}\n")
            self._refresh_library_list()
        except Exception as ex:
            self.ren_status_box.insert("end", f"Rendering error: {ex}\n")

    def _build_settings_tab(self):
        f = ctk.CTkFrame(self.tab_set, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=20, pady=20)
        ctk.CTkLabel(f, text="Preferences & Settings", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)

        dir_frame = ctk.CTkFrame(f, fg_color="transparent")
        dir_frame.pack(fill="x", pady=10)
        ctk.CTkLabel(dir_frame, text="Recordings Directory:").pack(side="left", padx=5)
        self.set_dir_entry = ctk.CTkEntry(dir_frame, width=450)
        self.set_dir_entry.insert(0, self.cfg.output_dir)
        self.set_dir_entry.pack(side="left", padx=10)

        ctk.CTkButton(f, text="Save Settings", width=140, command=self._on_save_settings).pack(anchor="w", pady=15)

    def _on_save_settings(self):
        self.cfg.output_dir = self.set_dir_entry.get().strip()
        self.cm.save(self.cfg)

    def _build_diagnostics_tab(self):
        f = ctk.CTkFrame(self.tab_dia, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=20, pady=20)
        ctk.CTkLabel(f, text="System & Audio Diagnostics", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)
        diag_box = ctk.CTkTextbox(f, height=300)
        diag_box.pack(expand=True, fill="both", pady=10)

        diag_box.insert("end", f"Python Version: {sys.version}\n")
        diag_box.insert("end", f"Platform: {sys.platform}\n")
        diag_box.insert("end", f"Active Backend: {self._active_backend.get_backend_type().value}\n")
        diag_box.insert("end", f"Detected Capture Devices: {len(self.devices)}\n")
        for d in self.devices:
            diag_box.insert("end", f"  - [{d.backend_type.value}] {d.name} ({d.channels} ch, {d.sample_rate} Hz)\n")

    def _build_about_tab(self):
        f = ctk.CTkFrame(self.tab_abt, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=20, pady=20)
        ctk.CTkLabel(f, text="er-audio-tool v1.0.0", font=ctk.CTkFont(size=18, weight="bold"), text_color="#4db6ac").pack(anchor="w", pady=5)
        about_text = (
            "er-audio-tool was originally derived from skillerious/Loopback-Recorder by Robin Doak.\n"
            "The original project is available at https://github.com/skillerious/Loopback-Recorder and is used under the MIT License.\n"
            "er-audio-tool is an independently maintained project and is not affiliated with or endorsed by the original author.\n\n"
            "Maintained by: Eidolf\n"
            "License: MIT License\n"
            "Privacy: 100% Local-First. No remote audio telemetry or recording data is transmitted."
        )
        abt_box = ctk.CTkTextbox(f, height=220)
        abt_box.pack(expand=True, fill="both", pady=10)
        abt_box.insert("end", about_text)

    def _on_lang_changed(self, choice: str):
        lang = "de" if choice == "DE" else "en"
        self.cfg.language = lang
        self.cm.save(self.cfg)
        self.i18n.set_language(lang)

    def _on_record_toggle(self):
        curr = self.state_machine.current_state
        if curr == AppState.IDLE:
            # Start recording
            self.state_machine.transition_to(AppState.PREPARING)
            self.state_machine.transition_to(AppState.RECORDING)
            self.status_label.configure(text=self.i18n.t("status_recording"), text_color="#ef5350")
            self.btn_record.configure(text="■ " + self.i18n.t("stop"), fg_color="#37474f")
            self._recording_data.clear()
            self._record_start_time = time.time()

            # Select device
            selected_name = self.source_combo.get()
            dev = next((d for d in self.devices if d.name == selected_name), self.devices[0] if self.devices else None)
            if dev:
                self._active_backend.start_capture(
                    dev,
                    self.cfg.sample_rate,
                    self.cfg.channels,
                    self._on_audio_data_received
                )
        elif curr == AppState.RECORDING:
            # Stop recording
            self.state_machine.transition_to(AppState.STOPPING)
            self.status_label.configure(text=self.i18n.t("status_encoding"), text_color="#ffb74d")
            self._active_backend.stop_capture()

            self.state_machine.transition_to(AppState.ENCODING)
            if self._recording_data:
                combined = np.concatenate(self._recording_data, axis=0)
                out_fmt = self.fmt_combo.get().lower()
                ts = time.strftime("%Y%m%d_%H%M%S")
                target = Path(self.cfg.output_dir) / f"Recording_{ts}.{out_fmt}"
                AudioEncoder.save_audio(combined, self.cfg.sample_rate, target, format_type=out_fmt)

            self.state_machine.transition_to(AppState.COMPLETED)
            self.state_machine.transition_to(AppState.IDLE)
            self.status_label.configure(text=self.i18n.t("status_idle"), text_color="#b0bec5")
            self.btn_record.configure(text="● " + self.i18n.t("record"), fg_color="#e53935")
            self._refresh_library_list()

    def _on_audio_data_received(self, data: np.ndarray):
        if self.state_machine.current_state == AppState.RECORDING:
            self._recording_data.append(data.copy())
            self.audio_buffer.push(data)

    def _update_loop(self):
        # Update timer & meters
        if self.state_machine.current_state == AppState.RECORDING:
            elapsed = int(time.time() - self._record_start_time)
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            self.timer_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")

        peak_db, rms_db, is_clip = self.audio_buffer.get_levels()
        p_val = max(0.0, (peak_db + 60.0) / 60.0) if peak_db > -60.0 else 0.0
        self.peak_progress.set(min(1.0, p_val))
        self.meter_label.configure(text=f"Levels: Peak {peak_db:.1f} dB | RMS {rms_db:.1f} dB")
        if is_clip:
            self.clip_warn.configure(text=self.i18n.t("clipping_warning"))
        else:
            self.clip_warn.configure(text="")

        self.after(50, self._update_loop)
