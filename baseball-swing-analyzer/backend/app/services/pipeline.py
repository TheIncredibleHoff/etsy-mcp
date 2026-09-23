"""Background analysis job: pose estimation → swing metrics → Claude coaching feedback."""

import logging

from .. import storage
from ..models import VideoStatus
from .coaching import CoachingError, generate_feedback
from .metrics import compute_metrics
from .pose import estimate_poses

log = logging.getLogger(__name__)

POSE_FILE = "pose.json"
METRICS_FILE = "metrics.json"
FEEDBACK_FILE = "feedback.json"


def _update(video_id: str, **fields) -> None:
    record = storage.load_record(video_id)
    storage.save_record(record.model_copy(update=fields))


def _write_feedback(video_id: str, metrics: dict) -> None:
    _update(video_id, stage="Writing coaching feedback", progress=0.0)
    record = storage.load_record(video_id)
    try:
        feedback = generate_feedback(metrics, record.hitter)
    except CoachingError as exc:
        feedback = {"status": "error", "error": str(exc)}
    storage.write_json(video_id, FEEDBACK_FILE, feedback)


def run_analysis(video_id: str) -> None:
    """Full analysis. The feedback step failing doesn't fail the job — the metrics still stand."""
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

        _update(video_id, stage="Measuring swing mechanics", progress=0.0)
        metrics = compute_metrics(pose, record.hitter.height_in)
        storage.write_json(video_id, METRICS_FILE, metrics)

        _write_feedback(video_id, metrics)
        _update(video_id, status=VideoStatus.complete, stage=None, progress=1.0, error=None)
    except KeyError:
        log.warning("Video %s was deleted during analysis", video_id)
    except Exception as exc:
        log.exception("Analysis failed for %s", video_id)
        _fail(video_id, str(exc))


def run_feedback_only(video_id: str) -> None:
    """Regenerate Claude's feedback from stored metrics (e.g. after adding an API key)."""
    try:
        metrics = storage.read_json(video_id, METRICS_FILE)
        if metrics is None:
            raise ValueError("No metrics found — analyze the video first.")
        _write_feedback(video_id, metrics)
        _update(video_id, status=VideoStatus.complete, stage=None, progress=1.0, error=None)
    except KeyError:
        log.warning("Video %s was deleted during analysis", video_id)
    except Exception as exc:
        log.exception("Feedback failed for %s", video_id)
        _fail(video_id, str(exc))


def _fail(video_id: str, message: str) -> None:
    try:
        _update(video_id, status=VideoStatus.failed, stage=None, error=message)
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
