from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Frame:
    frame_id: str
    image: Any
    jpeg: bytes
    video_time_s: float
    captured_at_ms: int
    captured_monotonic: float


@dataclass
class Detection:
    bbox: list[int]
    raw_class: str
    object_type: str | None
    confidence: float
    label_bbox: list[int] | None = None


@dataclass
class NumberRead:
    text: str | None = None
    number: int | None = None
    confidence: float | None = None
    label_bbox: list[int] | None = None
    reject_reason: str | None = None
    paper_bbox: list[int] | None = None
    orientation_verified: bool = False


@dataclass
class TelemetrySample:
    video_time_s: float
    sample_time_ms: int | None = None
    alt_rel: float | None = None
    aircraft_yaw: float | None = None
    gimbal_yaw: float | None = None
    gimbal_pitch: float | None = None
    zoom_factor: float | None = None
    source: str = 'recording'


@dataclass
class LocationResult:
    floor: int | None = None
    direction: str | None = None
    telemetry_age_s: float | None = None
    reject_reasons: list[str] = field(default_factory=list)

    @property
    def valid(self):
        return self.floor is not None and self.direction is not None and not self.reject_reasons


def serializable(value):
    return asdict(value)
