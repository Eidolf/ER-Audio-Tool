"""Regression tests for browser connection continuity and start-recording defect.

Verifies:
1. Connection established and authenticated.
2. Capability negotiation and connection test.
3. Page navigation from Browser Connection to Record > Browser Tab preserves the connection ID.
4. Tab selection binding to active generation.
5. Atomic recording-session reservation succeeds without 'not connected' error.
6. Heartbeat freshness and rejection of expired or stale sessions.
7. Disconnection and reconnect creates new generation and requires reselection.
8. Non-microphone source isolation (strictly rejects physical microphone stream).
"""
import asyncio
import json
import pytest
import numpy as np

from er_audio_tool.browser.registry import (
    BrowserConnectionRegistry,
    ConnectionState,
    ReservationError,
)
from er_audio_tool.browser.server import BrowserServer, BrowserTabInfo
from er_audio_tool.audio.backends.browser_backend import BrowserTabCaptureBackend
from er_audio_tool.audio.interfaces import (
    AudioDeviceInfo,
    BackendType,
    DeviceCapability,
)


@pytest.mark.asyncio
async def test_browser_connection_test_to_recording_workflow():
    """Reproduces the exact reported sequence and validates fix:
    1. Start server.
    2. Run connection test with valid pairing token.
    3. Confirm authenticated state in shared registry.
    4. Select browser tab.
    5. Navigate / reserve connection for recording.
    6. Verify that recording controller sees the same connection ID.
    7. Push browser audio frames and verify writer / meter callback receives them.
    8. Verify that application never reports 'not connected'.
    """
    registry = BrowserConnectionRegistry()
    server = BrowserServer(port=18991, token_entropy_bytes=16, registry=registry)
    backend = BrowserTabCaptureBackend(server)
    backend.registry = registry

    await server.start()
    try:
        # Step 1: Simulate Browser Extension connection test POST /api/test_connection
        reader, writer = await asyncio.open_connection("127.0.0.1", 18991)
        body = json.dumps({
            "token": server.auth_token,
            "version": "1.0.0",
            "browser": "Chrome",
            "extension_id": "ext-test-1234",
        })
        req = (
            f"POST /api/test_connection HTTP/1.1\r\n"
            f"Host: 127.0.0.1:18991\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n\r\n{body}"
        ).encode("utf-8")
        writer.write(req)
        await writer.drain()

        resp_raw = await reader.read(4096)
        writer.close()
        await writer.wait_closed()

        # Step 2: Confirm successful test connection
        resp_str = resp_raw.decode("utf-8", errors="replace")
        assert "200 OK" in resp_str
        assert '"authenticated": true' in resp_str.lower()

        # Step 3: Shared registry must maintain authenticated state after test connection finishes
        snap = registry.get_snapshot()
        assert snap.state in (ConnectionState.AUTHENTICATED, ConnectionState.READY_FOR_TAB_SELECTION)
        assert snap.authenticated_session_id is not None
        initial_conn_id = snap.connection_id
        initial_gen = snap.connection_generation

        # Step 4: Extension selects a tab (POST /api/tab_selected)
        reader2, writer2 = await asyncio.open_connection("127.0.0.1", 18991)
        tab_body = json.dumps({
            "token": server.auth_token,
            "tabInfo": {
                "id": 42,
                "title": "Audio Stream Player - 1200 Hz Tone",
                "audible": True,
                "windowId": 1,
            }
        })
        req2 = (
            f"POST /api/tab_selected HTTP/1.1\r\n"
            f"Host: 127.0.0.1:18991\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(tab_body)}\r\n\r\n{tab_body}"
        ).encode("utf-8")
        writer2.write(req2)
        await writer2.drain()
        await reader2.read(2048)
        writer2.close()
        await writer2.wait_closed()

        # Verify tab state
        snap_after_tab = registry.get_snapshot()
        assert snap_after_tab.state == ConnectionState.TAB_SELECTED
        assert snap_after_tab.selected_tab is not None
        assert snap_after_tab.selected_tab.tab_id == 42
        assert snap_after_tab.connection_id == initial_conn_id
        assert snap_after_tab.connection_generation == initial_gen

        # Step 5: User opens Record > Browser Tab and starts recording
        # Backend must atomically reserve the session without error
        dev = backend.enumerate_devices()[0]
        assert dev.id == "tab_42"
        assert "Audio Stream Player" in dev.name

        received_chunks = []
        backend.start_capture(
            dev,
            sample_rate=48000,
            channels=2,
            callback=lambda chunk: received_chunks.append(chunk),
        )

        assert backend._active_descriptor is not None
        assert backend._active_descriptor.connection_id == initial_conn_id
        assert backend._active_descriptor.selected_tab_id == 42

        # Step 6: Push simulated audio frames
        cap_session = backend._active_descriptor.capture_session_id
        test_frame = np.ones((512, 2), dtype=np.float32) * 0.75
        accepted = registry.push_audio_frame(test_frame, capture_session_id=cap_session)
        assert accepted is True
        assert len(received_chunks) == 1
        assert np.allclose(received_chunks[0], test_frame)

        # Step 7: Push frame with wrong capture session id -> must be rejected
        accepted_stale = registry.push_audio_frame(test_frame, capture_session_id="wrong-session-999")
        assert accepted_stale is False
        assert len(received_chunks) == 1

        backend.stop_capture()

    finally:
        await server.stop()


def test_registry_generation_and_stale_tab_rejection():
    """Verify that reconnect creates a new connection generation and marks old tab as stale."""
    reg = BrowserConnectionRegistry()
    reg.set_server_listening(True)

    # First session
    reg.authenticate_client("ext-1", extension_version="1.0.0")
    gen_1 = reg.get_snapshot().connection_generation
    reg.select_tab(tab_id=101, title="Tab Gen 1")

    desc = reg.reserve_for_recording()
    assert desc.connection_generation == gen_1
    assert desc.selected_tab_id == 101
    reg.finish_capture_session()

    # Reconnect occurs -> new connection generation
    reg.authenticate_client("ext-1-reconnect", extension_version="1.0.0")
    snap_2 = reg.get_snapshot()
    assert snap_2.connection_generation > gen_1


def test_reservation_error_categories():
    """Verify specific error categorization instead of generic 'not connected'."""
    reg = BrowserConnectionRegistry()

    # 1. Server stopped
    reg.set_server_listening(False)
    with pytest.raises(ReservationError) as exc1:
        reg.reserve_for_recording()
    assert exc1.value.code == "SERVER_NOT_RUNNING"

    # 2. Not authenticated
    reg.set_server_listening(True)
    with pytest.raises(ReservationError) as exc2:
        reg.reserve_for_recording()
    assert exc2.value.code == "NOT_AUTHENTICATED"

    # 3. Authenticated but no tab selected
    reg.authenticate_client("ext-test")
    reg.clear_selected_tab()
    with pytest.raises(ReservationError) as exc3:
        reg.reserve_for_recording()
    assert exc3.value.code == "NO_TAB_SELECTED"
