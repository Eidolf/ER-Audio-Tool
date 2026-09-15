"""Command line entrypoint for er-audio-tool."""
from __future__ import annotations
import sys
from pathlib import Path
from er_audio_tool.core.config import ConfigManager
from er_audio_tool.core.logging import setup_logging
from er_audio_tool.gui.app import ErAudioApp


def main():
    cm = ConfigManager()
    log_dir = cm.config_dir / "logs"
    setup_logging(log_dir)

    app = ErAudioApp(config_manager=cm)
    app.mainloop()


if __name__ == "__main__":
    main()
