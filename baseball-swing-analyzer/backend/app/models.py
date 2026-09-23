from datetime import datetime
from enum import Enum

from typing import Literal

from pydantic import BaseModel, Field


class VideoStatus(str, Enum):
    uploaded = "uploaded"
    processing = "processing"
    complete = "complete"
    failed = "failed"


class VideoInfo(BaseModel):
    fps: float
    frame_count: int
    width: int
    height: int
    duration_s: float


class HitterProfile(BaseModel):
    """Optional details that make the metrics and feedback more specific."""

    height_in: float | None = Field(default=None, gt=36, lt=96)
    level: Literal["youth", "high_school", "college", "pro", "adult"] | None = None
    notes: str | None = Field(default=None, max_length=1000)


class VideoRecord(BaseModel):
    id: str
    original_filename: str
    stored_filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime
    status: VideoStatus = VideoStatus.uploaded
    # Human-readable name of the step currently running, and its progress (0..1)
    stage: str | None = None
    progress: float = 0.0
    error: str | None = None
    info: VideoInfo
    hitter: HitterProfile = HitterProfile()
