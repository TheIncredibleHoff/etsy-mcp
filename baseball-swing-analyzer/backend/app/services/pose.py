"""Frame-by-frame pose estimation with MediaPipe Pose Landmarker."""

import logging
import shutil
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    PoseLandmarker,
    PoseLandmarkerOptions,
    PoseLandmarksConnections,
    RunningMode,
)

from ..config import get_settings

log = logging.getLogger(__name__)

# The 33 MediaPipe landmark names, in index order.
LANDMARK_NAMES = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer", "right_eye_inner",
    "right_eye", "right_eye_outer", "left_ear", "right_ear", "mouth_left",
    "mouth_right", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_pinky", "right_pinky", "left_index",
    "right_index", "left_thumb", "right_thumb", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle", "left_heel",
    "right_heel", "left_foot_index", "right_foot_index",
]  # fmt: skip

CONNECTIONS = [[c.start, c.end] for c in PoseLandmarksConnections.POSE_LANDMARKS]


def ensure_model() -> Path:
    settings = get_settings()
    path = settings.pose_model_file
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading pose model to %s", path)
    tmp = path.with_suffix(".download")
    with urllib.request.urlopen(settings.pose_model_url, timeout=60) as res, tmp.open("wb") as out:
        shutil.copyfileobj(res, out)
    tmp.replace(path)
    return path


def _round(v: float) -> float:
    return round(float(v), 4)


def estimate_poses(
    video_path: str,
    on_progress: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Run pose estimation on every frame of a video.

    Returns a JSON-serializable dict. Each frame holds either ``null`` (no
    person found) or:

    - ``image``: 33 × [x, y, z, visibility] in normalized image coordinates
      (x, y in 0..1 from the top-left corner) — used for drawing overlays.
    - ``world``: 33 × [x, y, z] in meters, centered between the hips — used
      for angle measurements, since it isn't distorted by the frame's aspect
      ratio.
    """
    settings = get_settings()
    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(ensure_model())),
        running_mode=RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Could not open video")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    limit = min(total, settings.max_analysis_frames)

    frames: list[dict[str, Any] | None] = []
    width = height = 0
    try:
        with PoseLandmarker.create_from_options(options) as landmarker:
            index = 0
            while index < settings.max_analysis_frames:
                ok, bgr = cap.read()
                if not ok:
                    break
                height, width = bgr.shape[:2]
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                # VIDEO mode needs strictly increasing timestamps in ms.
                timestamp_ms = int(round(index * 1000 / fps))
                result = landmarker.detect_for_video(image, timestamp_ms)

                if result.pose_landmarks:
                    img_lms = result.pose_landmarks[0]
                    world_lms = result.pose_world_landmarks[0]
                    frames.append(
                        {
                            "image": [
                                [_round(p.x), _round(p.y), _round(p.z), _round(p.visibility or 0)]
                                for p in img_lms
                            ],
                            "world": [[_round(p.x), _round(p.y), _round(p.z)] for p in world_lms],
                        }
                    )
                else:
                    frames.append(None)

                index += 1
                if on_progress and index % 15 == 0:
                    on_progress(min(index / limit, 1.0))
    finally:
        cap.release()

    if not frames:
        raise ValueError("Could not decode any frames")

    return {
        "fps": fps,
        "width": width,
        "height": height,
        "frame_count": len(frames),
        "truncated": len(frames) < total and len(frames) >= settings.max_analysis_frames,
        "landmark_names": LANDMARK_NAMES,
        "connections": CONNECTIONS,
        "frames": frames,
    }
