# Architecture of er-audio-tool

## High-Level Design

`er-audio-tool` is structured as a modular, local-first Python application designed for portability, testability, and responsiveness. Audio streaming and heavy numerical operations run completely asynchronously from the UI thread.

```
+-------------------------------------------------------------+
|                     CustomTkinter GUI                       |
|   (Recorder | Library | Analysis | MIDI | Render | Diags)   |
+-------------------------------------------------------------+
       |                        |                      |
+---------------+       +---------------+      +---------------+
| State Machine |       | ConfigManager |      |  I18n Manager |
+---------------+       +---------------+      +---------------+
       |
+-------------------------------------------------------------+
|                     Audio Device Manager                    |
+-------------------------------------------------------------+
   |                  |                    |                |
+--------+       +----------+         +----------+     +----------+
| WASAPI |       | PipeWire |         |PulseAudio|     | Mock / CI|
+--------+       +----------+         +----------+     +----------+
       \              |                    |                /
        +--------------------------------------------------+
                                 |
                        +-----------------+
                        |  Audio Buffer   |
                        | (Meters, Peaks) |
                        +-----------------+
                                 |
                        +-----------------+
                        |  Audio Encoder  |
                        | (WAV, FLAC, MP3)|
                        +-----------------+
```

## Security & Privacy Model

1. **Loopback-Only Extension Server**: The companion extension connects exclusively to `127.0.0.1`.
2. **Cryptographic Handshake**: High-entropy tokens protect against unauthorized local applications.
3. **Log Redaction**: Automatic stripping of session credentials and audio data.
4. **No Telemetry**: No network calls outside localhost.
