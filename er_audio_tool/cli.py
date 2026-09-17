import argparse
import sys
from er_audio_tool.version import get_version
from er_audio_tool.core.config import ConfigManager
from er_audio_tool.core.logging import setup_logging


def main():
    parser = argparse.ArgumentParser(
        prog="er-audio-tool",
        description="Local-first desktop audio suite for recording, analysis, conversion, and MIDI transcription.",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {get_version()}")
    parser.add_argument("--diagnostics", action="store_true", help="Run system diagnostics in CLI mode and exit")
    args = parser.parse_args()

    cm = ConfigManager()
    log_dir = cm.config_dir / "logs"
    setup_logging(log_dir)

    if args.diagnostics:
        from er_audio_tool.diagnostics.runner import DiagnosticRunner
        items = DiagnosticRunner.run_all_tests(cm.config.output_dir)
        print("=== ER-Audio-Tool Diagnostic Report ===")
        for item in items:
            print(f"[{item.status}] {item.category} - {item.name}: {item.details}")
            if item.recommendation:
                print(f"  -> Recommendation: {item.recommendation}")
        sys.exit(0)

    from er_audio_tool.gui.app import ErAudioApp
    app = ErAudioApp(config_manager=cm)
    app.mainloop()


if __name__ == "__main__":
    main()

