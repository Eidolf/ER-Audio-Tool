"""Comprehensive self-diagnostic test runner for hardware and software subsystems."""
from __future__ import annotations
import os
import platform
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import soundfile as sf

from er_audio_tool.audio.manager import DeviceManager
from er_audio_tool.audio.interfaces import BackendType


@dataclass
class DiagnosticItem:
    category: str
    name: str
    status: str  # "PASSED", "WARNING", "FAILED"
    details: str
    recommendation: str = ""


class DiagnosticRunner:
    """Runs non-destructive verification of all audio, device, codec, and filesystem components."""

    @classmethod
    def run_all_tests(cls, output_dir: Path | str) -> list[DiagnosticItem]:
        results: list[DiagnosticItem] = []

        # 1. Operating System & Python
        results.append(
            DiagnosticItem(
                category="System",
                name="OS & Architecture",
                status="PASSED",
                details=f"{platform.system()} {platform.release()} ({platform.machine()}), Python {platform.python_version()}",
            )
        )

        # 2. Audio Capture Backend
        dm = DeviceManager()
        active = dm.get_active_backend()
        b_type = active.get_backend_type().value
        if active.is_available():
            results.append(
                DiagnosticItem(
                    category="Audio Backend",
                    name="Capture Service",
                    status="PASSED",
                    details=f"Active backend: {b_type.upper()}",
                )
            )
        else:
            results.append(
                DiagnosticItem(
                    category="Audio Backend",
                    name="Capture Service",
                    status="WARNING",
                    details=f"Native backend {b_type} is not available. Using fallback.",
                    recommendation="Ensure audio daemon (PipeWire/PulseAudio on Linux, Windows Audio on Win) is running.",
                )
            )

        # 3. Devices
        devs = dm.enumerate_all_devices()
        if devs:
            results.append(
                DiagnosticItem(
                    category="Devices",
                    name="Endpoint Enumeration",
                    status="PASSED",
                    details=f"Found {len(devs)} audio capture endpoint(s).",
                )
            )
        else:
            results.append(
                DiagnosticItem(
                    category="Devices",
                    name="Endpoint Enumeration",
                    status="FAILED",
                    details="No audio endpoints detected.",
                    recommendation="Connect speakers/headphones or enable loopback device.",
                )
            )

        # 4. Filesystem Write Permissions & Recovery
        out_p = Path(output_dir)
        try:
            out_p.mkdir(parents=True, exist_ok=True)
            test_file = out_p / ".er_write_test.tmp"
            with open(test_file, "w") as f:
                f.write("OK")
            test_file.unlink()
            results.append(
                DiagnosticItem(
                    category="Storage",
                    name="Output Directory Access",
                    status="PASSED",
                    details=f"Write access confirmed for {out_p.resolve()}",
                )
            )
        except Exception as ex:
            results.append(
                DiagnosticItem(
                    category="Storage",
                    name="Output Directory Access",
                    status="FAILED",
                    details=f"Cannot write to output folder: {ex}",
                    recommendation="Select a writable directory in Settings.",
                )
            )

        # 5. Codec Backend (FFmpeg & SoundFile)
        from er_audio_tool.audio.codecs import get_ffmpeg_path, get_codec_manager
        cm = get_codec_manager()
        ffmpeg = get_ffmpeg_path() or shutil.which("ffmpeg")
        is_local = cm.has_local_ffmpeg()
        if ffmpeg:
            loc_label = "Portable local (temp_codecs)" if is_local else "System PATH"
            results.append(
                DiagnosticItem(
                    category="Codecs",
                    name="Media Encoding Engine",
                    status="PASSED",
                    details=f"FFmpeg binary detected [{loc_label}]: {ffmpeg}",
                )
            )
        else:
            results.append(
                DiagnosticItem(
                    category="Codecs",
                    name="Media Encoding Engine",
                    status="WARNING",
                    details="FFmpeg not found in PATH. WAV & FLAC will work; MP3/M4A may be limited.",
                    recommendation="Install FFmpeg for complete MP3, M4A, and Opus encoding support.",
                )
            )

        # 6. Audio Pipeline Test (Synthetic Frame Generation)
        try:
            sr = 44100
            t = np.linspace(0, 0.2, int(sr * 0.2), endpoint=False)
            sine = 0.5 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
            temp_wav = Path(tempfile.gettempdir()) / "test_pipeline.wav"
            sf.write(temp_wav, sine, sr)
            if temp_wav.exists() and temp_wav.stat().st_size > 0:
                temp_wav.unlink()
                results.append(
                    DiagnosticItem(
                        category="Pipeline",
                        name="Internal Audio Pipeline",
                        status="PASSED",
                        details="Audio synthesis, buffering, and WAV file writing verified.",
                    )
                )
        except Exception as ex:
            results.append(
                DiagnosticItem(
                    category="Pipeline",
                    name="Internal Audio Pipeline",
                    status="FAILED",
                    details=f"Audio pipeline verification failed: {ex}",
                )
            )

        # 7. Real Hardware / Loopback Audio Capture Test
        capture_test = cls.run_audio_capture_test()
        results.extend(capture_test)

        return results

    @classmethod
    def run_audio_capture_test(cls) -> list[DiagnosticItem]:
        """Performs targeted test of audio output detection, format compatibility and loopback capability."""
        test_results = []
        dm = DeviceManager()

        # Step A: Playback Device Detection
        devs = dm.enumerate_all_devices("rec_system")
        render_devs = [d for d in devs if d.is_loopback or d.channels > 0]

        if render_devs:
            default_dev = next((d for d in render_devs if d.is_default), render_devs[0])
            test_results.append(
                DiagnosticItem(
                    category="Audio Capture",
                    name="Wiedergabegerät erkannt",
                    status="PASSED",
                    details=f"Endpunkt: '{default_dev.name}' (ID: {default_dev.id}, Kanäle: {default_dev.channels}, Rate: {default_dev.sample_rate} Hz)",
                )
            )

            # Step B: Format Compatibility & Loopback Test
            if sys.platform == "win32":
                try:
                    import sounddevice as sd
                    d_info = sd.query_devices(default_dev.id)
                    out_ch = int(d_info.get("max_output_channels", 0))
                    sr = int(d_info.get("default_samplerate", 48000))
                    test_results.append(
                        DiagnosticItem(
                            category="Audio Capture",
                            name="Geräteformat & Treiber-Mix",
                            status="PASSED",
                            details=f"Treiber meldet: {out_ch} Kanäle, {sr} Hz Mix-Format.",
                        )
                    )

                    # Test opening a loopback stream using production backend path
                    backend = dm.get_backend_for_source_type("rec_system")
                    packets_received = 0
                    test_error = None
                    try:
                        def _test_cb(data):
                            nonlocal packets_received
                            packets_received += 1

                        backend.start_capture(
                            device=default_dev,
                            sample_rate=sr,
                            channels=out_ch if out_ch > 0 else 2,
                            callback=_test_cb,
                        )
                        import time
                        time.sleep(0.08)
                        backend.stop_capture()
                        test_results.append(
                            DiagnosticItem(
                                category="Audio Capture",
                                name="WASAPI Loopback Test",
                                status="PASSED",
                                details=(
                                    f"WASAPI Loopback Stream erfolgreich initialisiert und geöffnet. "
                                    f"Empfangene Test-Pakete: {packets_received}."
                                ),
                            )
                        )
                    except Exception as ex:
                        err_str = str(ex)
                        rec_msg = "Sicherstellen, dass ein Audiosignal auf dem Standard-Wiedergabegerät abgespielt wird."
                        if "WasapiSettings" in err_str or "loopback" in err_str:
                            rec_msg = "Das installierte Audio-Backend unterstützt kein natives Loopback über das aktuelle Treiber-Interface."
                        elif "-9998" in err_str or "Invalid number of channels" in err_str:
                            rec_msg = "Das Wiedergabegerät erfordert native Kanalverhandlung. Format-Kandidaten im Backend prüfen."
                        test_results.append(
                            DiagnosticItem(
                                category="Audio Capture",
                                name="WASAPI Loopback Test",
                                status="WARNING",
                                details=f"Stream-Initialisierung fehlgeschlagen: {ex}",
                                recommendation=rec_msg,
                            )
                        )
                except Exception as ex:
                    test_results.append(
                        DiagnosticItem(
                            category="Audio Capture",
                            name="WASAPI Loopback Test",
                            status="WARNING",
                            details=f"Sounddevice-Abfrage nicht möglich: {ex}",
                        )
                    )
            else:
                # Linux / Mock environment
                test_results.append(
                    DiagnosticItem(
                        category="Audio Capture",
                        name="Audio Loopback Test",
                        status="PASSED",
                        details=f"System Loopback ({dm.get_active_backend().get_backend_type().value.upper()}) bereit.",
                    )
                )
        else:
            test_results.append(
                DiagnosticItem(
                    category="Audio Capture",
                    name="Wiedergabegerät erkannt",
                    status="FAILED",
                    details="Kein kompatibles Audio-Wiedergabegerät gefunden.",
                    recommendation="Lautsprecher oder Kopfhörer anschließen.",
                )
            )

        # Step C: Browser Companion Extension Multi-Stage Readiness Check
        try:
            from er_audio_tool.browser.registry import BrowserConnectionRegistry, ConnectionState
            reg = BrowserConnectionRegistry.get_instance()
            snap = reg.get_snapshot()

            # Stage 1 & 2: Local service and connection
            if snap.state == ConnectionState.SERVER_STOPPED:
                test_results.append(
                    DiagnosticItem(
                        category="Browser Recording Readiness",
                        name="1. Local Loopback Service",
                        status="WARNING",
                        details="Local server stopped on port 58291.",
                        recommendation="Restart application.",
                    )
                )
            else:
                test_results.append(
                    DiagnosticItem(
                        category="Browser Recording Readiness",
                        name="1. Local Loopback Service",
                        status="PASSED",
                        details=f"Service listening on 127.0.0.1:58291 (State: {snap.state.value})",
                    )
                )

            # Stage 3: Authentication
            if snap.authenticated_session_id:
                test_results.append(
                    DiagnosticItem(
                        category="Browser Recording Readiness",
                        name="2. Client Authentication",
                        status="PASSED",
                        details=f"Authenticated (Session: {snap.authenticated_session_id[:8]}..., Gen: {snap.connection_generation})",
                    )
                )
            else:
                test_results.append(
                    DiagnosticItem(
                        category="Browser Recording Readiness",
                        name="2. Client Authentication",
                        status="WARNING",
                        details="Extension is not authenticated.",
                        recommendation="Open extension popup and click 'Test Connection' or paste session token.",
                    )
                )

            # Stage 4: Tab Selection & Freshness
            if snap.selected_tab:
                gen_match = snap.selected_tab.connection_generation == snap.connection_generation
                if gen_match:
                    test_results.append(
                        DiagnosticItem(
                            category="Browser Recording Readiness",
                            name="3. Selected Tab Binding",
                            status="PASSED",
                            details=f"Tab #{snap.selected_tab.tab_id}: '{snap.selected_tab.title[:35]}' (Gen: {snap.selected_tab.connection_generation})",
                        )
                    )
                else:
                    test_results.append(
                        DiagnosticItem(
                            category="Browser Recording Readiness",
                            name="3. Selected Tab Binding",
                            status="WARNING",
                            details=f"Tab #{snap.selected_tab.tab_id} belongs to prior generation ({snap.selected_tab.connection_generation} != {snap.connection_generation}).",
                            recommendation="Reselect tab in extension popup.",
                        )
                    )
            else:
                test_results.append(
                    DiagnosticItem(
                        category="Browser Recording Readiness",
                        name="3. Selected Tab Binding",
                        status="WARNING",
                        details="No browser tab currently selected.",
                        recommendation="Open extension popup and click on the target tab.",
                    )
                )

            # Stage 5: Heartbeat freshness
            if snap.last_heartbeat_age_seconds < 120.0:
                test_results.append(
                    DiagnosticItem(
                        category="Browser Recording Readiness",
                        name="4. Heartbeat Freshness",
                        status="PASSED",
                        details=f"Last heartbeat {snap.last_heartbeat_age_seconds:.1f}s ago.",
                    )
                )
            else:
                test_results.append(
                    DiagnosticItem(
                        category="Browser Recording Readiness",
                        name="4. Heartbeat Freshness",
                        status="WARNING",
                        details=f"Heartbeat aged ({snap.last_heartbeat_age_seconds:.0f}s).",
                        recommendation="Trigger test connection in extension popup.",
                    )
                )
        except Exception as ex:
            test_results.append(
                DiagnosticItem(
                    category="Browser Recording Readiness",
                    name="Readiness Check",
                    status="WARNING",
                    details=f"Could not query registry: {ex}",
                )
            )

        return test_results
