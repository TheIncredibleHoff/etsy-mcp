from datetime import datetime
from enum import Enum

from pydantic import BaseModel


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
