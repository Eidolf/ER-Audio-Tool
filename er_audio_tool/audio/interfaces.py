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


class AudioSourceType(Enum):
    SYSTEM_LOOPBACK = "system_loopback"
    APPLICATION_LOOPBACK = "application_loopback"
    BROWSER_TAB_STREAM = "browser_tab_stream"
    MICROPHONE_INPUT = "microphone_input"
    DIAGNOSTIC_GENERATED_AUDIO = "diagnostic_generated_audio"


@dataclass
class AudioSourceDescriptor:
    source_type: AudioSourceType
    source_id: str
    name: str
    backend_type: BackendType
    endpoint_id: int | str | None = None
    host_api: str | None = None
    is_loopback: bool = True
    process_id: int | None = None
    process_name: str | None = None
    browser_tab_id: int | None = None
    browser_tab_title: str | None = None
    channels_supported: list[int] | None = None
    sample_rates_supported: list[int] | None = None

    def validate(self) -> bool:
        if self.source_type == AudioSourceType.SYSTEM_LOOPBACK:
            return bool(self.is_loopback)
        elif self.source_type == AudioSourceType.APPLICATION_LOOPBACK:
            return True
        elif self.source_type == AudioSourceType.BROWSER_TAB_STREAM:
            return self.backend_type == BackendType.BROWSER_TAB
        elif self.source_type == AudioSourceType.MICROPHONE_INPUT:
            return not self.is_loopback
        return True


@dataclass
class CapturedFrameBlock:
    session_id: str
    source_type: AudioSourceType
    data: np.ndarray  # float32 shape (frames, channels)
    sample_rate: int
    channels: int
    timestamp: float
    frame_count: int


class DeviceCapability(Enum):
    PHYSICAL_INPUT = "physical_input"
    OUTPUT_LOOPBACK = "output_loopback"
    PROCESS_LOOPBACK = "process_loopback"
    BROWSER_STREAM = "browser_stream"
    VIRTUAL_INPUT = "virtual_input"
    UNSUPPORTED = "unsupported"


@dataclass
class AudioDeviceInfo:
    id: int | str
    name: str
    channels: int
    sample_rate: int
    is_default: bool = False
    is_loopback: bool = True
    backend_type: BackendType = BackendType.MOCK
    capability: DeviceCapability = DeviceCapability.OUTPUT_LOOPBACK
    extra: dict = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


AudioDataCallback = Callable[[np.ndarray], None]
CanonicalFrameCallback = Callable[[CapturedFrameBlock], None]




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
