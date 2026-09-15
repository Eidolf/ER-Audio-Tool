"""Application state machine definitions."""
from __future__ import annotations
from enum import Enum, auto


class AppState(Enum):
    IDLE = auto()
    PREPARING = auto()
    RECORDING = auto()
    PAUSED = auto()
    STOPPING = auto()
    ENCODING = auto()
    ANALYZING = auto()
    TRANSCRIBING = auto()
    RENDERING = auto()
    COMPLETED = auto()
    FAILED = auto()


# Valid state transitions
VALID_TRANSITIONS: dict[AppState, set[AppState]] = {
    AppState.IDLE: {AppState.PREPARING, AppState.ANALYZING, AppState.TRANSCRIBING, AppState.RENDERING},
    AppState.PREPARING: {AppState.RECORDING, AppState.FAILED, AppState.IDLE},
    AppState.RECORDING: {AppState.PAUSED, AppState.STOPPING, AppState.FAILED},
    AppState.PAUSED: {AppState.RECORDING, AppState.STOPPING, AppState.FAILED},
    AppState.STOPPING: {AppState.ENCODING, AppState.COMPLETED, AppState.FAILED},
    AppState.ENCODING: {AppState.COMPLETED, AppState.FAILED},
    AppState.ANALYZING: {AppState.COMPLETED, AppState.FAILED, AppState.IDLE},
    AppState.TRANSCRIBING: {AppState.COMPLETED, AppState.FAILED, AppState.IDLE},
    AppState.RENDERING: {AppState.COMPLETED, AppState.FAILED, AppState.IDLE},
    AppState.COMPLETED: {AppState.IDLE},
    AppState.FAILED: {AppState.IDLE},
}


class StateMachine:
    """Thread-safe state manager for er-audio-tool."""

    def __init__(self, initial_state: AppState = AppState.IDLE):
        self._state = initial_state
        self._listeners: list = []

    @property
    def current_state(self) -> AppState:
        return self._state

    def add_listener(self, callback) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def transition_to(self, new_state: AppState) -> bool:
        if new_state in VALID_TRANSITIONS.get(self._state, set()):
            old_state = self._state
            self._state = new_state
            for cb in self._listeners:
                try:
                    cb(old_state, new_state)
                except Exception:
                    pass
            return True
        return False
