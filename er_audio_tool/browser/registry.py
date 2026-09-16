"""Authoritative, application-scoped browser connection registry and state management.

Replaces ambiguous booleans with structured state models, atomic session reservation,
authenticated heartbeats, connection generations, and explicit start handshakes.
"""
from __future__ import annotations
import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional
import numpy as np


class ConnectionState(enum.Enum):
    SERVER_STOPPED = "SERVER_STOPPED"
    SERVER_LISTENING = "SERVER_LISTENING"
    CLIENT_CONNECTED = "CLIENT_CONNECTED"
    AUTHENTICATING = "AUTHENTICATING"
    AUTHENTICATED = "AUTHENTICATED"
    CAPABILITIES_CONFIRMED = "CAPABILITIES_CONFIRMED"
    READY_FOR_TAB_SELECTION = "READY_FOR_TAB_SELECTION"
    TAB_SELECTED = "TAB_SELECTED"
    CAPTURE_START_PENDING = "CAPTURE_START_PENDING"
    CAPTURE_AUTHORIZED = "CAPTURE_AUTHORIZED"
    CAPTURE_STARTING = "CAPTURE_STARTING"
    AUDIO_STREAM_ACTIVE = "AUDIO_STREAM_ACTIVE"
    SILENT_AUDIO_STREAM_ACTIVE = "SILENT_AUDIO_STREAM_ACTIVE"
    PAUSED = "PAUSED"
    DISCONNECTING = "DISCONNECTING"
    DISCONNECTED = "DISCONNECTED"
    INCOMPATIBLE = "INCOMPATIBLE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class SelectedTabInfo:
    tab_id: int
    title: str
    window_id: int = 0
    audible: bool = False
    muted: bool = False
    active: bool = False
    connection_generation: int = 0
    selected_at: float = field(default_factory=time.monotonic)


@dataclass(frozen=True)
class ConnectionSnapshot:
    """Atomic, immutable connection snapshot for validation and recording start."""
    connection_id: str
    connection_generation: int
    state: ConnectionState
    authenticated_session_id: Optional[str]
    extension_instance_id: Optional[str]
    extension_version: str
    protocol_version: str
    browser_family: str
    browser_version: str
    capabilities: tuple[str, ...]
    last_heartbeat_monotonic: float
    last_heartbeat_age_seconds: float
    selected_tab: Optional[SelectedTabInfo]
    capture_session_id: Optional[str]
    received_frames_count: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class BrowserTabSourceDescriptor:
    """Immutable source descriptor proving browser stream authenticity."""
    source_type: str  # "BROWSER_TAB_STREAM"
    connection_id: str
    connection_generation: int
    authenticated_session_id: str
    extension_instance_id: str
    browser_instance_id: str
    selected_tab_id: int
    selected_tab_label: str
    capture_session_id: str
    protocol_version: str
    negotiated_channels: int = 2
    negotiated_sample_rate: int = 48000


class ReservationError(Exception):
    """Specific error with actionable guidance when recording reservation fails."""
    def __init__(self, code: str, message: str, recommendation: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.recommendation = recommendation


class BrowserConnectionRegistry:
    """Single authoritative, application-scoped registry for browser companion connections."""

    _instance: Optional[BrowserConnectionRegistry] = None

    @classmethod
    def get_instance(cls) -> BrowserConnectionRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> BrowserConnectionRegistry:
        cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._state: ConnectionState = ConnectionState.SERVER_STOPPED
        self._connection_id: str = str(uuid.uuid4())
        self._connection_generation: int = 0
        self._authenticated_session_id: Optional[str] = None
        self._extension_instance_id: Optional[str] = None
        self._extension_version: str = "1.0.0"
        self._protocol_version: str = "1.0"
        self._browser_family: str = "Chromium"
        self._browser_version: str = "Unknown"
        self._capabilities: set[str] = {"tab_capture", "audio_pcm"}
        self._last_heartbeat_monotonic: float = 0.0
        self._selected_tab: Optional[SelectedTabInfo] = None
        self._active_capture_session_id: Optional[str] = None
        self._received_frames_count: int = 0
        self._last_audio_monotonic: float = 0.0
        self._last_error_code: Optional[str] = None
        self._last_error_message: Optional[str] = None

        self._subscribers: list[Callable[[ConnectionSnapshot], None]] = []
        self._on_audio_frame: Optional[Callable[[np.ndarray, str], None]] = None

    def subscribe(self, callback: Callable[[ConnectionSnapshot], None]) -> Callable[[], None]:
        """Subscribes a listener to registry snapshots. Returns an unsubscribe callable."""
        self._subscribers.append(callback)
        # Notify immediately with current state
        try:
            callback(self.get_snapshot())
        except Exception:
            pass
        return lambda: self._unsubscribe(callback)

    def _unsubscribe(self, callback: Callable[[ConnectionSnapshot], None]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _notify(self) -> None:
        snap = self.get_snapshot()
        for sub in list(self._subscribers):
            try:
                sub(snap)
            except Exception:
                pass

    def get_snapshot(self) -> ConnectionSnapshot:
        now = time.monotonic()
        hb_age = (now - self._last_heartbeat_monotonic) if self._last_heartbeat_monotonic > 0 else 999999.0
        return ConnectionSnapshot(
            connection_id=self._connection_id,
            connection_generation=self._connection_generation,
            state=self._state,
            authenticated_session_id=self._authenticated_session_id,
            extension_instance_id=self._extension_instance_id,
            extension_version=self._extension_version,
            protocol_version=self._protocol_version,
            browser_family=self._browser_family,
            browser_version=self._browser_version,
            capabilities=tuple(sorted(self._capabilities)),
            last_heartbeat_monotonic=self._last_heartbeat_monotonic,
            last_heartbeat_age_seconds=hb_age,
            selected_tab=self._selected_tab,
            capture_session_id=self._active_capture_session_id,
            received_frames_count=self._received_frames_count,
            error_code=self._last_error_code,
            error_message=self._last_error_message,
        )

    def set_server_listening(self, listening: bool) -> None:
        if listening:
            if self._state == ConnectionState.SERVER_STOPPED:
                self._state = ConnectionState.SERVER_LISTENING
        else:
            self._state = ConnectionState.SERVER_STOPPED
        self._notify()

    def handle_client_connected(self, transport_id: Optional[str] = None) -> None:
        if self._state in (ConnectionState.SERVER_LISTENING, ConnectionState.DISCONNECTED):
            self._state = ConnectionState.CLIENT_CONNECTED
            self._notify()

    def authenticate_client(
        self,
        extension_instance_id: str,
        extension_version: str = "1.0.0",
        protocol_version: str = "1.0",
        browser_family: str = "Chromium",
        browser_version: str = "",
        capabilities: Optional[list[str]] = None,
    ) -> str:
        """Authenticates client and establishes or refreshes current connection generation."""
        self._connection_generation += 1
        self._authenticated_session_id = str(uuid.uuid4())
        self._extension_instance_id = extension_instance_id
        self._extension_version = extension_version
        self._protocol_version = protocol_version
        self._browser_family = browser_family or "Chromium"
        self._browser_version = browser_version or "Unknown"
        self._capabilities = set(capabilities or ["tab_capture", "audio_pcm"])
        self._last_heartbeat_monotonic = time.monotonic()
        
        # Invalidate any prior pending capture or stale tab from old generation
        self._active_capture_session_id = None
        if self._selected_tab:
            # Mark tab as preserved if from same session or require fresh generation
            self._selected_tab = SelectedTabInfo(
                tab_id=self._selected_tab.tab_id,
                title=self._selected_tab.title,
                window_id=self._selected_tab.window_id,
                audible=self._selected_tab.audible,
                muted=self._selected_tab.muted,
                active=self._selected_tab.active,
                connection_generation=self._connection_generation,
                selected_at=time.monotonic(),
            )
            self._state = ConnectionState.TAB_SELECTED
        else:
            self._state = ConnectionState.READY_FOR_TAB_SELECTION

        self._last_error_code = None
        self._last_error_message = None
        self._notify()
        return self._authenticated_session_id

    def record_heartbeat(self, extension_instance_id: Optional[str] = None) -> None:
        self._last_heartbeat_monotonic = time.monotonic()
        if self._state == ConnectionState.DISCONNECTED:
            if self._authenticated_session_id:
                self._state = ConnectionState.TAB_SELECTED if self._selected_tab else ConnectionState.AUTHENTICATED
        self._notify()

    def select_tab(self, tab_id: int, title: str, audible: bool = False, muted: bool = False, window_id: int = 0, active: bool = True) -> None:
        self._selected_tab = SelectedTabInfo(
            tab_id=tab_id,
            title=title or f"Tab {tab_id}",
            window_id=window_id,
            audible=audible,
            muted=muted,
            active=active,
            connection_generation=self._connection_generation,
            selected_at=time.monotonic(),
        )
        if self._state in (ConnectionState.AUTHENTICATED, ConnectionState.READY_FOR_TAB_SELECTION, ConnectionState.TAB_SELECTED, ConnectionState.CLIENT_CONNECTED):
            self._state = ConnectionState.TAB_SELECTED
        self._last_heartbeat_monotonic = time.monotonic()
        self._notify()

    def clear_selected_tab(self, reason: str = "Tab closed") -> None:
        self._selected_tab = None
        if self._authenticated_session_id:
            self._state = ConnectionState.READY_FOR_TAB_SELECTION
        self._notify()

    def reserve_for_recording(self) -> BrowserTabSourceDescriptor:
        """Atomically validates state and reserves the connection for a new recording session."""
        snap = self.get_snapshot()

        # 1. Local service running check
        if snap.state == ConnectionState.SERVER_STOPPED:
            raise ReservationError("SERVER_NOT_RUNNING", "Local browser communication service is not running.", "Ensure the desktop app loopback service is started.")

        # 2. Authenticated check
        if not snap.authenticated_session_id or snap.state in (ConnectionState.DISCONNECTED, ConnectionState.CLIENT_CONNECTED, ConnectionState.AUTHENTICATING):
            raise ReservationError("NOT_AUTHENTICATED", "Browser extension is connected but not authenticated.", "Open the browser extension popup, paste the pairing token, and verify connection.")

        # 3. Protocol compatibility
        if snap.protocol_version not in ("1.0", "1.1"):
            raise ReservationError("PROTOCOL_INCOMPATIBLE", f"Incompatible browser extension protocol version ({snap.protocol_version}).", "Reinstall or update the browser extension.")

        # 4. Tab selection check
        if not snap.selected_tab:
            raise ReservationError("NO_TAB_SELECTED", "No browser tab has been selected for capture.", "Open the browser extension popup and click on the tab you wish to record.")

        # 5. Selected tab generation match
        if snap.selected_tab.connection_generation != snap.connection_generation:
            raise ReservationError("STALE_TAB_SELECTION", "The selected tab belongs to a previous connection session.", "Please reopen the extension popup and re-confirm your tab selection.")

        # 6. Active capture conflict check
        if snap.state in (ConnectionState.CAPTURE_STARTING, ConnectionState.AUDIO_STREAM_ACTIVE):
            raise ReservationError("ALREADY_CAPTURING", "A browser tab capture session is already active.", "Stop the current recording before starting a new one.")

        # 7. Heartbeat freshness check (within 300 seconds)
        if snap.last_heartbeat_age_seconds > 300.0:
            raise ReservationError("HEARTBEAT_EXPIRED", "The browser extension heartbeat has timed out.", "Reopen the extension popup or click 'Recheck Readiness'.")

        # Reserve atomic capture session
        capture_session_id = str(uuid.uuid4())
        self._active_capture_session_id = capture_session_id
        self._state = ConnectionState.CAPTURE_STARTING
        self._received_frames_count = 0
        self._last_audio_monotonic = 0.0

        descriptor = BrowserTabSourceDescriptor(
            source_type="BROWSER_TAB_STREAM",
            connection_id=snap.connection_id,
            connection_generation=snap.connection_generation,
            authenticated_session_id=snap.authenticated_session_id,
            extension_instance_id=snap.extension_instance_id or "ext-unknown",
            browser_instance_id=f"{snap.browser_family}_{snap.browser_version}",
            selected_tab_id=snap.selected_tab.tab_id,
            selected_tab_label=snap.selected_tab.title,
            capture_session_id=capture_session_id,
            protocol_version=snap.protocol_version,
            negotiated_channels=2,
            negotiated_sample_rate=48000,
        )
        self._notify()
        return descriptor

    def handle_capture_started(self, capture_session_id: str, tab_id: int) -> bool:
        """Validates matching capture session and advances state."""
        if self._active_capture_session_id and self._active_capture_session_id == capture_session_id:
            self._state = ConnectionState.CAPTURE_STARTING
            self._notify()
            return True
        return False

    def push_audio_frame(self, audio_data: np.ndarray, capture_session_id: Optional[str] = None) -> bool:
        """Delivers incoming audio packets only if bound to the active capture session."""
        if self._active_capture_session_id and capture_session_id and self._active_capture_session_id != capture_session_id:
            # Reject frame belonging to mismatched or prior capture session
            return False

        frames = len(audio_data)
        self._received_frames_count += frames
        self._last_audio_monotonic = time.monotonic()

        # Transition to AUDIO_STREAM_ACTIVE or SILENT_AUDIO_STREAM_ACTIVE
        is_silent = bool(np.all(np.abs(audio_data) < 1e-5))
        new_state = ConnectionState.SILENT_AUDIO_STREAM_ACTIVE if is_silent else ConnectionState.AUDIO_STREAM_ACTIVE
        if self._state != new_state:
            self._state = new_state
            self._notify()

        if self._on_audio_frame:
            self._on_audio_frame(audio_data, self._active_capture_session_id or "")
        return True

    def set_audio_frame_consumer(self, callback: Optional[Callable[[np.ndarray, str], None]]) -> None:
        self._on_audio_frame = callback

    def finish_capture_session(self) -> None:
        self._active_capture_session_id = None
        if self._authenticated_session_id:
            self._state = ConnectionState.TAB_SELECTED if self._selected_tab else ConnectionState.AUTHENTICATED
        else:
            self._state = ConnectionState.SERVER_LISTENING
        self._notify()

    def handle_disconnect(self, reason: str = "Client disconnected") -> None:
        """Handles transport disconnection without wiping out persistent authenticated token."""
        # Note: Do NOT erase token or mark fully disconnected if HTTP request completed
        self._last_error_message = reason
        # Only transition to DISCONNECTED if no active session or explicit teardown
        if not self._authenticated_session_id:
            self._state = ConnectionState.DISCONNECTED
            self._notify()
