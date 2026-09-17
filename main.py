#!/usr/bin/env python3
"""ER-Audio-Tool root entry point.

Delegates execution to the modular package implementation in er_audio_tool.cli.
"""
from er_audio_tool.cli import main

if __name__ == "__main__":
    main()
