"""Audio capture backend interfaces and data structures."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional
import numpy as np


class BackendType(Enum):
    WASAPI = "wasapi"
    PIPEWIRE = "pipewire"
    PULSEAUDIO = "pulseaudio"
    ALSA = "alsa"
    BROWSER_TAB = "browser_tab"
    MOCK = "mock"


@dataclass
class AudioDeviceInfo:
    id: int | str
    name: str
    channels: int
    sample_rate: int
    is_default: bool = False
    is_loopback: bool = True
    backend_type: BackendType = BackendType.MOCK
    extra: dict = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


AudioDataCallback = Callable[[np.ndarray], None]


class AudioCaptureBackend(ABC):
    """Abstract interface for audio capture backends."""

    @abstractmethod
    def get_backend_type(self) -> BackendType:
        """Returns the type of this backend."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the backend is functional on the current system."""
        pass

    @abstractmethod
    def enumerate_devices(self) -> list[AudioDeviceInfo]:
        """Lists available loopback/output endpoints."""
        pass

    @abstractmethod
    def start_capture(
        self,
        device: AudioDeviceInfo,
        sample_rate: int,
        channels: int,
        callback: AudioDataCallback,
    ) -> None:
        """Starts capturing audio frames asynchronously and dispatching to callback."""
        pass

    @abstractmethod
    def stop_capture(self) -> None:
        """Stops the audio capture."""
        pass
