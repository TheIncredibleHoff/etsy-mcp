"""Background analysis job: pose estimation → (later stages)."""

import logging

from .. import storage
from ..models import VideoStatus
from .pose import estimate_poses

log = logging.getLogger(__name__)

POSE_FILE = "pose.json"


def _update(video_id: str, **fields) -> None:
    record = storage.load_record(video_id)
    storage.save_record(record.model_copy(update=fields))


def run_analysis(video_id: str) -> None:
    try:
        record = storage.load_record(video_id)
        _update(video_id, stage="Tracking body joints", progress=0.0)
        pose = estimate_poses(
            str(storage.video_file(record)),
            on_progress=lambda p: _update(video_id, progress=round(p, 3)),
        )
        if not any(pose["frames"]):
            raise ValueError(
                "No person was detected in the video. Make sure the hitter's whole body is in frame."
            )
        storage.write_json(video_id, POSE_FILE, pose)

        _update(video_id, status=VideoStatus.complete, stage=None, progress=1.0, error=None)
    except KeyError:
        log.warning("Video %s was deleted during analysis", video_id)
    except Exception as exc:
        log.exception("Analysis failed for %s", video_id)
        try:
            _update(video_id, status=VideoStatus.failed, stage=None, error=str(exc))
        except KeyError:
            pass


def recover_interrupted_jobs() -> None:
    """Jobs run in-process, so any left 'processing' at startup were cut off."""
    for record in storage.list_records():
        if record.status == VideoStatus.processing:
            storage.save_record(
                record.model_copy(
                    update={
                        "status": VideoStatus.failed,
                        "stage": None,
                        "error": "Analysis was interrupted by a server restart. Try again.",
                    }
                )
            )
